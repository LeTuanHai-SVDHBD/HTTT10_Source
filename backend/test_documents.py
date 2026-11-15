"""Milestone E integration against real MySQL and multipart ASGI."""

import json
import hashlib
import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

import pymysql
from fastapi.testclient import TestClient
from sqlalchemy import URL, text

root = Path(__file__).resolve().parents[1]
db_name = "httt10_documents_" + uuid4().hex[:10] + "_test"
params = dict(
    host=os.getenv("MYSQL_TEST_HOST", "127.0.0.1"),
    port=int(os.getenv("MYSQL_TEST_PORT", "43307")),
    user=os.getenv("MYSQL_TEST_USER", "root"),
    password=os.getenv("MYSQL_TEST_PASSWORD", ""),
)
connection = pymysql.connect(**params, autocommit=True)
with connection.cursor() as cur:
    cur.execute(
        "CREATE DATABASE `"
        + db_name
        + "` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
    )
connection.close()
os.environ["DATABASE_URL"] = URL.create(
    "mysql+pymysql",
    username=params["user"],
    password=params["password"],
    host=params["host"],
    port=params["port"],
    database=db_name,
).render_as_string(hide_password=False)
os.environ["JWT_SECRET"] = secrets.token_urlsafe(48)
from app.cli import main as cli
from app.db import Session, engine
from app.main import app, limiter
from app import scheduling as service, security, document_storage as storage
import tempfile
import io
import zipfile
import time
from PIL import Image
from pypdf import PdfWriter

storage_dir = tempfile.TemporaryDirectory()
os.environ["DOCUMENT_STORAGE_DIR"] = storage_dir.name

results = []


def check(name, actual, expected=True):
    assert actual == expected, (name, actual, expected)
    results.append(dict(name=name, status="PASS"))
    print("PASS", name, flush=True)


with patch("sys.argv", ["cli", "migrate"]):
    cli()
password = "Only-Test-Password-2026"
users = {}
with Session.begin() as db:
    for code, roles, dept in [
        ("EMP1", ["EMPLOYEE"], 1),
        ("EMP2", ["EMPLOYEE"], 1),
        ("SHARED", ["EMPLOYEE"], 1),
        ("OPT", ["EMPLOYEE"], 1),
        ("FOREIGN", ["EMPLOYEE"], 2),
        ("LEAD1", ["EMPLOYEE", "APPROVER"], 1),
        ("LEAD2", ["EMPLOYEE", "APPROVER"], 1),
        ("ROGUE", ["APPROVER"], 1),
        ("ADMIN", ["ADMIN"], 1),
    ]:
        person = str(uuid4())
        users[code] = person
        db.execute(
            text(
                "INSERT INTO users(id,employee_code,full_name,email,department_id,status,password_hash,must_change_password) VALUES(:id,:code,:name,:email,:dept,'ACTIVE',:hash,0)"
            ),
            dict(
                id=person,
                code=code,
                name=code,
                email=code.lower() + "@example.com",
                dept=f"10000000-0000-0000-0000-00000000000{dept}",
                hash=security.HASHER.hash(password),
            ),
        )
        for role in roles:
            db.execute(
                text(
                    "INSERT INTO user_roles(user_id,role,granted_by) VALUES(:id,:role,:id)"
                ),
                dict(id=person, role=role),
            )
    for i in [1, 2]:
        for code in ["LEAD1", "LEAD2"] if i == 1 else ["LEAD2"]:
            db.execute(
                text(
                    "INSERT INTO room_approvers(room_id,user_id,granted_by) VALUES(:r,:u,:u)"
                ),
                dict(r=f"20000000-0000-0000-0000-00000000000{i}", u=users[code]),
            )
    for code in ["LEAD1", "LEAD2"]:
        db.execute(
            text(
                "INSERT INTO department_approvers(department_id,user_id,granted_by) VALUES('10000000-0000-0000-0000-000000000001',:u,:u)"
            ),
            dict(u=users[code]),
        )

client = TestClient(app)
headers = {}
for code in users:
    limiter.entries.clear()
    token = client.post(
        "/api/v1/auth/login",
        json=dict(email=code.lower() + "@example.com", password=password),
    ).json()["access_token"]
    headers[code] = {"Authorization": "Bearer " + token}


def request(method, path, body=None, who="EMP1", key=None, code=200):
    response = client.request(
        method,
        "/api/v1" + path,
        headers=headers[who] | ({"Idempotency-Key": key} if key else {}),
        json=body,
    )
    if code is not None:
        assert response.status_code == code, (path, response.status_code, response.text)
    return response


def scalar(sql, **params):
    with Session() as db:
        return db.scalar(text(sql), params)


def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat()


slot_number = 0
start_base = security.now().replace(
    hour=2, minute=0, second=0, microsecond=0
) + timedelta(days=2)


def slot():
    global slot_number
    value = start_base + timedelta(days=slot_number)
    while value.isoweekday() > 5:
        value += timedelta(days=1)
    slot_number = (value.date() - start_base.date()).days + 1
    return value


def meeting(start=None, room=1, who="EMP1", people=None):
    begin = start or slot()
    people = people or [(who, True)]
    return dict(
        kind="MEETING",
        title="PRIVATE_MEETING_" + uuid4().hex[:8],
        description="PRIVATE_DESCRIPTION",
        starts_at=iso(begin),
        ends_at=iso(begin + timedelta(hours=1)),
        room_id=f"20000000-0000-0000-0000-00000000000{room}",
        chair_user_id=users[people[0][0]],
        participants=[
            dict(user_id=users[p], is_required=required) for p, required in people
        ],
    )


def work(start=None, who="EMP1", people=None):
    begin = start or slot()
    return dict(
        kind="WORK",
        title="PRIVATE_WORK_" + uuid4().hex[:8],
        description="PRIVATE_WORK_DESCRIPTION",
        starts_at=iso(begin),
        ends_at=iso(begin + timedelta(days=2)),
        department_id="10000000-0000-0000-0000-000000000001",
        work_location="PRIVATE_LOCATION",
        work_context="EXTERNAL",
        participant_user_ids=[users[p] for p in (people or [who])],
    )


def submit(candidate, who="EMP1", key=None, ack=True):
    body = dict(candidate=candidate)
    key = key or str(uuid4())
    path = "/meeting-proposals" if candidate["kind"] == "MEETING" else "/work-proposals"
    response = request("POST", path, body, who, key, code=None)
    if (
        response.status_code == 409
        and response.json()["error"]["code"] == "WARNINGS_REQUIRE_ACK"
        and ack
    ):
        body["warning_acknowledgement_token"] = response.json()["error"][
            "warning_acknowledgement_token"
        ]
        response = request("POST", path, body, who, key, code=None)
    return response, body, key


def detail(receipt, who="EMP1"):
    return request("GET", "/proposals/" + receipt["proposal_id"], who=who).json()


def decision(receipt, who="LEAD1", approve=True, key=None, ack=True, versions=None):
    current = versions or detail(receipt)
    body = dict(
        expected_schedule_version=current["schedule_version"],
        expected_proposal_version=current["row_version"],
        decision="APPROVE" if approve else "REJECT",
        reason=None if approve else "Không phù hợp nhu cầu công việc.",
    )
    path = "/proposals/" + receipt["proposal_id"] + "/decisions"
    key = key or str(uuid4())
    response = request("POST", path, body, who, key, code=None)
    if (
        response.status_code == 409
        and response.json()["error"]["code"] == "WARNINGS_REQUIRE_ACK"
        and ack
    ):
        body["warning_acknowledgement_token"] = response.json()["error"][
            "warning_acknowledgement_token"
        ]
        response = request("POST", path, body, who, key, code=None)
    return response, body, key


# Use six non-overlapping service slots per weekday to keep all test bookings
# within the 90-day submit horizon, in a fresh database for this suite.
slot_counter = 0
first_day = (security.now() + timedelta(days=2)).date()


def slot():
    global slot_counter
    day = first_day
    day_index, index = divmod(slot_counter, 6)
    slot_counter += 1
    for _ in range(day_index):
        day += timedelta(days=1)
        while day.isoweekday() > 5:
            day += timedelta(days=1)
    while day.isoweekday() > 5:
        day += timedelta(days=1)
    hour, minute = [(1, 0), (2, 15), (3, 30), (6, 0), (7, 15), (8, 30)][index]
    return datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute)


def current(item, who="EMP1"):
    return request("GET", "/schedules/" + item["schedule_id"], who=who).json()


def confirmed(kind="MEETING", who="EMP1", room=1, people=None, start=None):
    value = (
        meeting(start=start, room=room, who=who, people=people)
        if kind == "MEETING"
        else work(
            start=start, who=who, people=[p[0] for p in people] if people else None
        )
    )
    if kind == "WORK":
        value["ends_at"] = iso(
            datetime.fromisoformat(value["starts_at"]).replace(tzinfo=None)
            + timedelta(hours=1)
        )
    response, _, _ = submit(value, who=who)
    assert response.status_code == 201, response.text
    item = response.json()
    d = detail(item, who=who)
    response, _, _ = decision(item, who="LEAD2" if room == 2 else "LEAD1", versions=d)
    assert response.status_code == 200, response.text
    return item, value


def revision_payload(revision):
    fields = ["kind", "title", "description", "starts_at", "ends_at"]
    value = {key: revision[key] for key in fields}
    if value["kind"] == "MEETING":
        value.update(
            room_id=revision["room_id"],
            chair_user_id=revision["chair_user_id"],
            participants=[
                dict(user_id=p["user"]["id"], is_required=p["is_required"])
                for p in revision["participants"]
            ],
        )
    else:
        value.update(
            department_id=revision["department_id"],
            work_location=revision["work_location"],
            work_context=revision["work_context"],
            participant_user_ids=[p["user"]["id"] for p in revision["participants"]],
        )
    return value


def change(item, candidate, who="EMP1", key=None, ack=True, state=None, base_id=None):
    state = state or current(item, who=who)
    body = dict(
        expected_schedule_version=state["row_version"],
        base_revision_id=base_id or state["current_revision"]["id"],
        candidate=candidate,
    )
    key = key or str(uuid4())
    path = "/schedules/" + item["schedule_id"] + "/change-proposals"
    response = request("POST", path, body, who=who, key=key, code=None)
    if (
        ack
        and response.status_code == 409
        and response.json()["error"]["code"] == "WARNINGS_REQUIRE_ACK"
    ):
        body["warning_acknowledgement_token"] = response.json()["error"][
            "warning_acknowledgement_token"
        ]
        response = request("POST", path, body, who=who, key=key, code=None)
    return response, body, key


def cancel(
    item,
    work=False,
    who="EMP1",
    reason="Không còn nhu cầu theo kế hoạch.",
    key=None,
    state=None,
):
    state = state or current(item, who=who)
    body = dict(expected_schedule_version=state["row_version"], reason=reason)
    path = (
        "/schedules/"
        + item["schedule_id"]
        + ("/work-cancellation-proposals" if work else "/meeting-cancellations")
    )
    key = key or str(uuid4())
    return request("POST", path, body, who=who, key=key, code=None), body, key


def withdraw(item, who="EMP1"):
    p = detail(item, who=who)
    return request(
        "POST",
        "/proposals/" + item["proposal_id"] + "/withdrawals",
        dict(
            expected_schedule_version=p["schedule_version"],
            expected_proposal_version=p["row_version"],
        ),
        who=who,
        key=str(uuid4()),
        code=None,
    )


def root_row(item):
    with Session() as db:
        return dict(
            db.execute(
                text("SELECT * FROM schedule_roots WHERE id=:id"),
                dict(id=item["schedule_id"]),
            )
            .mappings()
            .one()
        )


def file_bytes(extension):
    out = io.BytesIO()
    if extension in ("jpg", "jpeg", "png"):
        Image.new("RGB", (3, 3), "green").save(
            out, format="PNG" if extension == "png" else "JPEG"
        )
    elif extension == "pdf":
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.write(out)
    else:
        main, tag, ctype = {
            "docx": (
                "word/document.xml",
                "document",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
            ),
            "pptx": (
                "ppt/presentation.xml",
                "presentation",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
            ),
            "xlsx": (
                "xl/workbook.xml",
                "workbook",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
            ),
        }[extension]
        with zipfile.ZipFile(out, "w") as z:
            z.writestr(
                "[Content_Types].xml",
                f'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/{main}" ContentType="{ctype}"/></Types>',
            )
            z.writestr(
                "_rels/.rels",
                f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="{main}" Id="rId1"/></Relationships>',
            )
            z.writestr(main, f'<{tag} xmlns="urn:test"/>')
    return out.getvalue()


def upload(
    item,
    rid,
    who="EMP1",
    name="Hồ sơ riêng",
    filename="tài liệu.pdf",
    data=None,
    doc=None,
    expected=None,
    code=201,
):
    metadata = dict(context_revision_id=rid)
    metadata.update(
        dict(expected_latest_version_id=expected) if doc else dict(display_name=name)
    )
    path = (
        "/documents/" + doc + "/versions"
        if doc
        else "/schedules/" + item["schedule_id"] + "/documents"
    )
    r = client.post(
        "/api/v1" + path,
        headers=headers[who],
        data={"metadata": json.dumps(metadata)},
        files={
            "file": (
                filename,
                file_bytes("pdf") if data is None else data,
                "application/octet-stream",
            )
        },
    )
    if code is not None:
        assert r.status_code == code, (r.status_code, r.text)
    return r


def listing(item, who="EMP1", rid=None, hidden=False):
    return request(
        "GET",
        f"/schedules/{item['schedule_id']}/documents?include_hidden={str(hidden).lower()}"
        + (f"&context_revision_id={rid}" if rid else ""),
        who=who,
    ).json()


def download(v, who="EMP1", code=200):
    return request(
        "GET",
        f"/documents/{v['document_id']}/versions/{v['id']}/content",
        who=who,
        code=code,
    )


item, candidate = confirmed(people=[("EMP1", True), ("SHARED", True)])
rid = current(item)["current_revision"]["id"]
version_before = root_row(item)["row_version"]
for ext in ("pdf", "docx", "pptx", "xlsx", "jpg", "jpeg", "png"):
    data = file_bytes(ext)
    v = upload(item, rid, filename="Nội dung." + ext, data=data).json()
    got = download(v, "SHARED")
    check("Tải lên/xuống đúng byte định dạng " + ext, got.content, data)
    check("Không lộ storage key/hash " + ext, not {"storage_key", "sha256"} & v.keys())
check("Tệp không đổi phiên bản lịch", root_row(item)["row_version"], version_before)
check("MIME tải xuống an toàn", got.headers["content-type"], "application/octet-stream")
check(
    "Tải xuống dạng attachment",
    got.headers["content-disposition"].startswith("attachment;"),
)
check(
    "nosniff và no-store",
    (got.headers["x-content-type-options"], got.headers["cache-control"]),
    ("nosniff", "no-store"),
)
check(
    "Tải xuống cần đăng nhập",
    client.get(
        "/api/v1/documents/" + v["document_id"] + "/versions/" + v["id"] + "/content"
    ).status_code,
    401,
)
for who in ("ADMIN", "ROGUE", "EMP2", "LEAD2"):
    # LEAD2 is scoped to room1 and can read, ADMIN/ROGUE alone cannot.
    check(
        "Quyền đọc " + who,
        download(v, who, code=None).status_code,
        200 if who == "LEAD2" else 404,
    )
for who in ("SHARED", "LEAD1", "ADMIN"):
    check(
        "Chỉ chủ lịch tải lên " + who,
        upload(item, rid, who=who, code=None).status_code,
        403,
    )
check(
    "Danh sách không lộ lịch ngoài quyền",
    request(
        "GET", "/schedules/" + item["schedule_id"] + "/documents", who="EMP2", code=None
    ).status_code,
    404,
)
check(
    "Phân trang đúng số lượng",
    request(
        "GET", "/schedules/" + item["schedule_id"] + "/documents?page_size=2"
    ).json()["total"],
    7,
)
for name, data, status in [
    ("bad.exe", b"MZ", 415),
    ("bad.pdf", b"%PDF-spoof", 422),
    ("bad.png", file_bytes("jpg"), 422),
    ("empty.pdf", b"", 422),
    ("bad.docx", b"PKfake", 422),
    ("a" * 256 + ".pdf", file_bytes("pdf"), 422),
]:
    check(
        "Chặn tệp " + name[:20],
        upload(item, rid, filename=name, data=data, code=None).status_code,
        status,
    )
check(
    "Làm sạch đường dẫn và ký tự tên tệp",
    upload(item, rid, filename="C:\\secret\\safe\r\n.pdf").json()["original_filename"],
    "safe%0D%0A.pdf",
)
# Metadata and total multipart limits also apply without Content-Length.
path = "/api/v1/schedules/" + item["schedule_id"] + "/documents"
check(
    "Chặn JSON thay multipart",
    client.post(path, headers=headers["EMP1"], json={}).status_code,
    415,
)
check(
    "Chặn metadata sai",
    client.post(
        path,
        headers=headers["EMP1"],
        data={"metadata": "{}"},
        files={"file": ("ok.pdf", file_bytes("pdf"))},
    ).status_code,
    422,
)
check(
    "Chặn metadata quá dài",
    client.post(
        path,
        headers=headers["EMP1"],
        data={"metadata": "x" * 17000},
        files={"file": ("ok.pdf", file_bytes("pdf"))},
    ).status_code,
    400,
)
check(
    "Chặn hai payload file",
    client.post(
        path,
        headers=headers["EMP1"],
        data={"metadata": json.dumps(dict(context_revision_id=rid, display_name="A"))},
        files=[
            ("file", ("a.pdf", file_bytes("pdf"))),
            ("file", ("b.pdf", file_bytes("pdf"))),
        ],
    ).status_code,
    422,
)
base = file_bytes("pdf")
index = base.index(b"startxref")
large = (
    base[:index]
    + b"%"
    + b" " * (storage.MAX_SIZE - len(base) - 2)
    + b"\n"
    + base[index:]
)
check("Chấp nhận đúng 20 MiB", upload(item, rid, data=large).status_code, 201)
check(
    "Chặn hơn 20 MiB", upload(item, rid, data=large + b" ", code=None).status_code, 413
)
boundary = "chunk-boundary"
prefix = (
    f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'
    + json.dumps(dict(context_revision_id=rid, display_name="Chunk"))
    + f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="big.pdf"\r\n\r\n'
).encode()


def chunks():
    yield prefix
    for _ in range(321):
        yield b"x" * 65536
    yield f"\r\n--{boundary}--\r\n".encode()


check(
    "Chặn chunked vượt giới hạn",
    client.post(
        path,
        headers=headers["EMP1"]
        | {"Content-Type": "multipart/form-data; boundary=" + boundary},
        content=chunks(),
    ).status_code,
    413,
)
for label, member, content in [
    ("zip traversal", "../evil", b"x"),
    (
        "XML entity",
        "[Content_Types].xml",
        b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///etc/passwd">]><x>&x;</x>',
    ),
    ("macro", "word/vbaProject.bin", b"x"),
    ("zip bomb", "huge", b"x" * (31 * 1024 * 1024)),
]:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(member, content)
    check(
        "Chặn " + label,
        upload(
            item, rid, filename="bad.docx", data=out.getvalue(), code=None
        ).status_code,
        422,
    )

# One logical document spans revisions, while every version keeps its own audience.
v1 = upload(item, rid, name="OLD_SECRET_LABEL", filename="OLD_SECRET_FILE.pdf").json()
doc = v1["document_id"]
new = revision_payload(current(item)["current_revision"]) | dict(
    room_id="20000000-0000-0000-0000-000000000002",
    participants=[
        dict(user_id=users["EMP1"], is_required=True),
        dict(user_id=users["OPT"], is_required=True),
    ],
)
changed, _, _ = change(item, new)
assert changed.status_code == 201, changed.text
amendment = changed.json()
new_rid = detail(amendment)["candidate"]["id"]
v2 = upload(
    item, new_rid, filename="NEW_SECRET_FILE.pdf", doc=doc, expected=v1["id"]
).json()
owner_old = next(d for d in listing(item, rid=rid)["items"] if d["id"] == doc)
check(
    "Bộ lọc giấu latest không cấp thao tác dùng expected cũ",
    owner_old["allowed_actions"],
    [],
)
check(
    "Xem mọi ngữ cảnh cho chủ lịch quản lý latest",
    bool(next(d for d in listing(item)["items"] if d["id"] == doc)["allowed_actions"]),
)
old_view = listing(item, "SHARED")
new_view = listing(item, "OPT")
check("Người cũ không thấy tên/tệp mới", "NEW_SECRET" not in json.dumps(old_view))
check("Người mới không thấy nhãn/tệp cũ", "OLD_SECRET" not in json.dumps(new_view))
check(
    "Nhãn an toàn dùng tên phiên bản được phép",
    new_view["items"][0]["display_name"],
    "NEW_SECRET_FILE.pdf",
)
check("Phiên bản mới chỉ thấy một tệp", len(new_view["items"][0]["versions"]), 1)
check("Người cũ không tải được v2", download(v2, "SHARED", code=None).status_code, 404)
check("Người mới không tải được v1", download(v1, "OPT", code=None).status_code, 404)
check(
    "Người duyệt phòng cũ không tải được v2",
    download(v2, "LEAD1", code=None).status_code,
    404,
)
check("Người duyệt phòng mới tải v2", download(v2, "LEAD2").status_code, 200)
check(
    "Version endpoint lọc trước phân trang",
    request("GET", "/documents/" + doc + "/versions?page_size=1", who="SHARED").json()[
        "total"
    ],
    1,
)
other, _ = confirmed()
check(
    "Không gắn phiên bản sang lịch khác", upload(other, rid, code=None).status_code, 404
)
check(
    "Chặn expected latest cũ",
    upload(item, new_rid, doc=doc, expected=v1["id"], code=None).status_code,
    409,
)
check(
    "Duyệt đổi lịch có tài liệu", decision(amendment, who="LEAD2")[0].status_code, 200
)
check("Bản cũ chỉ đọc", upload(item, rid, code=None).status_code, 409)
check("Bản mới giữ tài liệu", download(v2, "OPT").status_code, 200)
check("Không tự chuyển tệp cũ", listing(item, rid=new_rid)["total"], 1)
# A document whose last version is historical can still receive a new current-context version.
old_doc = listing(item, rid=rid)["items"][0]
v3 = upload(
    item, new_rid, doc=old_doc["id"], expected=old_doc["versions"][-1]["id"]
).json()
check(
    "Thêm version từ tài liệu cũ vào bản lịch mới", v3["context_revision_id"], new_rid
)
# No meeting-time cutoff: minutes can be attached after it ends.
with Session.begin() as db:
    db.execute(
        text("UPDATE schedule_revisions SET starts_at=:s,ends_at=:e WHERE id=:id"),
        dict(
            s=security.now() - timedelta(hours=2),
            e=security.now() - timedelta(hours=1),
            id=new_rid,
        ),
    )
try:
    check("Cho bổ sung biên bản sau cuộc họp", upload(item, new_rid).status_code, 201)
finally:
    with Session.begin() as db:
        db.execute(
            text("UPDATE schedule_revisions SET starts_at=:s,ends_at=:e WHERE id=:id"),
            dict(
                s=datetime.fromisoformat(new["starts_at"]).replace(tzinfo=None),
                e=datetime.fromisoformat(new["ends_at"]).replace(tzinfo=None),
                id=new_rid,
            ),
        )
# Concurrent version requests share expected_latest; exactly one wins.
race = upload(item, new_rid).json()
barrier = Barrier(2)


def racer():
    barrier.wait()
    return upload(
        item, new_rid, doc=race["document_id"], expected=race["id"], code=None
    ).status_code


with ThreadPoolExecutor(2) as pool:
    statuses = list(pool.map(lambda _: racer(), range(2)))
check("Hai phiên bản đồng thời chỉ một thắng", sorted(statuses), [201, 409])
latest = request("GET", "/documents/" + race["document_id"] + "/versions").json()[
    "items"
][-1]
check(
    "Ẩn kiểm tra latest",
    request(
        "POST",
        "/documents/" + race["document_id"] + "/hides",
        dict(expected_latest_version_id=race["id"], reason="Lỗi tệp"),
        code=None,
    ).status_code,
    409,
)
check(
    "Chủ lịch ẩn tài liệu",
    request(
        "POST",
        "/documents/" + race["document_id"] + "/hides",
        dict(expected_latest_version_id=latest["id"], reason="Đã thay thế"),
        code=None,
    ).status_code,
    204,
)
check(
    "Danh sách mặc định loại tệp đã ẩn",
    race["document_id"] not in [x["id"] for x in listing(item)["items"]],
)
check("Lịch sử vẫn tải được tệp ẩn", download(latest, "OPT").status_code, 200)
check(
    "Không thêm version vào tệp ẩn",
    upload(
        item, new_rid, doc=race["document_id"], expected=latest["id"], code=None
    ).status_code,
    409,
)
check(
    "Tệp ẩn có thể tra cứu lịch sử",
    race["document_id"] in [x["id"] for x in listing(item, hidden=True)["items"]],
)
check(
    "Audit tài liệu không lộ tên riêng",
    "OLD_SECRET"
    not in request(
        "GET", "/schedules/" + item["schedule_id"] + "/audit", who="OPT"
    ).text,
)
check(
    "Audit có sự kiện tài liệu",
    any(
        x["action"] == "DOCUMENT_HIDDEN"
        for x in request("GET", "/schedules/" + item["schedule_id"] + "/audit").json()[
            "items"
        ]
    ),
)

for resolution in ("WITHDRAWN", "REJECTED", "EXPIRED"):
    r, _, _ = submit(meeting())
    pending = r.json()
    prid = detail(pending)["candidate"]["id"]
    pv = upload(pending, prid).json()
    if resolution == "WITHDRAWN":
        assert withdraw(pending).status_code == 200
    elif resolution == "REJECTED":
        assert decision(pending, approve=False)[0].status_code == 200
    else:
        with Session.begin() as db:
            db.execute(
                text("UPDATE approval_proposals SET expires_at=:t WHERE id=:id"),
                dict(
                    t=security.now() - timedelta(seconds=1), id=pending["proposal_id"]
                ),
            )
    check(
        resolution + " không ghi thêm tài liệu",
        upload(pending, prid, code=None).status_code,
        409,
    )
    check(resolution + " vẫn đọc lịch sử", download(pv).status_code, 200)
check("Hủy họp đã có tài liệu", cancel(item)[0].status_code, 200)
check("Họp đã hủy chỉ đọc", upload(item, new_rid, code=None).status_code, 409)
check("Tệp vẫn đọc sau hủy", download(v2, "OPT").status_code, 200)
work_item, _ = confirmed(kind="WORK")
check(
    "Không tải tệp lên công tác",
    upload(
        work_item, current(work_item)["current_revision"]["id"], code=None
    ).status_code,
    409,
)

# Root lock serializes upload against direct cancellation without changing row_version.
racing_item, _ = confirmed()
racing_rid = current(racing_item)["current_revision"]["id"]
barrier = Barrier(2)


def cancel_race():
    barrier.wait()
    return cancel(racing_item)[0].status_code


def upload_race():
    barrier.wait()
    return upload(racing_item, racing_rid, code=None).status_code


with ThreadPoolExecutor(2) as pool:
    f1 = pool.submit(cancel_race)
    f2 = pool.submit(upload_race)
    cancel_status, upload_status = f1.result(), f2.result()
check("Hủy đồng thời upload vẫn hoàn tất", cancel_status, 200)
check(
    "Upload cạnh tranh hủy chỉ commit trước hoặc bị chặn", upload_status in (201, 409)
)
check(
    "Sau hủy không ghi thêm tệp",
    upload(racing_item, racing_rid, code=None).status_code,
    409,
)

# Filesystem failure and orphan reconciliation leave no half-committed metadata.
active, _ = confirmed()
arid = current(active)["current_revision"]["id"]
real_stage = storage.stage


def stage_then_require_password(file, key):
    result = real_stage(file, key)
    with Session.begin() as db:
        db.execute(
            text("UPDATE users SET must_change_password=1 WHERE id=:id"),
            dict(id=users["EMP1"]),
        )
    return result


try:
    with patch("app.document_storage.stage", side_effect=stage_then_require_password):
        check(
            "Kiểm tra lại quyền sau khi đã nhận tệp",
            upload(active, arid, code=None).status_code,
            403,
        )
finally:
    with Session.begin() as db:
        db.execute(
            text("UPDATE users SET must_change_password=0 WHERE id=:id"),
            dict(id=users["EMP1"]),
        )
check(
    "Phiên bị hạn chế không để byte staging",
    list((storage.directories() / "staging").iterdir()),
    [],
)
# application/json metadata can be sent as a typed multipart part.
check(
    "Metadata JSON dạng part có Content-Type",
    client.post(
        "/api/v1/schedules/" + active["schedule_id"] + "/documents",
        headers=headers["EMP1"],
        files={
            "metadata": (
                "metadata.json",
                json.dumps(dict(context_revision_id=arid, display_name="Typed JSON")),
                "application/json",
            ),
            "file": ("typed.pdf", file_bytes("pdf"), "application/pdf"),
        },
    ).status_code,
    201,
)
count = scalar("SELECT COUNT(*) FROM document_versions")
objects = set((storage.directories() / "objects").iterdir())
real_publish = storage.publish


def fail_after_publish(path, key):
    real_publish(path, key)
    raise OSError("simulated failure")


with patch("app.document_storage.publish", side_effect=fail_after_publish):
    check(
        "Lỗi sau publish được chuẩn hóa",
        upload(active, arid, code=None).status_code,
        500,
    )
check(
    "Lỗi lưu rollback metadata", scalar("SELECT COUNT(*) FROM document_versions"), count
)
check(
    "Lỗi lưu dọn byte chưa commit",
    set((storage.directories() / "objects").iterdir()),
    objects,
)
check("Không còn tệp staging", list((storage.directories() / "staging").iterdir()), [])
healthy = upload(active, arid).json()
with Session() as db:
    info = dict(
        db.execute(
            text("SELECT * FROM document_versions WHERE id=:id"), dict(id=healthy["id"])
        )
        .mappings()
        .one()
    )
with storage.guard(info["storage_key"]) as conn:
    storage.discard_unreferenced(conn, info["storage_key"])
check("Không xóa byte có tham chiếu DB", download(healthy).status_code, 200)
object_path = storage.directories() / "objects" / info["storage_key"]
original = object_path.read_bytes()
object_path.write_bytes(b"corrupt")
check("Tệp hỏng trả lỗi an toàn", download(healthy, code=None).status_code, 503)
object_path.unlink()
check("Tệp thiếu trả lỗi an toàn", download(healthy, code=None).status_code, 503)
object_path.write_bytes(original)
ref = object_path
os.utime(ref, (0, 0))
orphan = storage.directories() / "objects" / (uuid4().hex + ".blob")
orphan.write_bytes(b"orphan")
os.utime(orphan, (0, 0))
stale = storage.directories() / "staging" / (uuid4().hex + ".part")
stale.write_bytes(b"stale")
os.utime(stale, (0, 0))
fresh = storage.directories() / "objects" / (uuid4().hex + ".blob")
fresh.write_bytes(b"fresh")
check("Cleanup mặc định chỉ xem trước", storage.cleanup()["removed"], 0)
with storage.guard(orphan.name):
    check("Cleanup bỏ qua upload đang khóa", storage.cleanup(apply=True)["busy"], 1)
check("Cleanup dọn orphan quá hạn", storage.cleanup(apply=True)["removed"], 1)
check("Cleanup giữ byte có DB và tệp mới", ref.exists() and fresh.exists())
check("Cleanup không xóa lịch sử ẩn", download(latest, "OPT").status_code, 200)
check(
    "OpenAPI đủ 49 thao tác", sum(len(v) for v in app.openapi()["paths"].values()), 49
)
check(
    "OpenAPI upload trả DocumentVersionView",
    app.openapi()["paths"]["/api/v1/documents/{document_id}/versions"]["post"][
        "responses"
    ]["201"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/DocumentVersionView"
    ),
)
result_dir = Path(os.getenv("TEST_RESULT_DIR", str(root / "verification")))
result_dir.mkdir(parents=True, exist_ok=True)
(result_dir / "documents-result.json").write_text(
    json.dumps(
        dict(
            passed=len(results),
            total=len(results),
            tests=results,
            mysql_version=scalar("SELECT VERSION()"),
            scope="Real MySQL + ASGI multipart, revision privacy, immutable bytes, size/format limits, concurrency and failure cleanup. No browser/Docker Windows/LAN/SMTP.",
        ),
        ensure_ascii=False,
        indent=2,
    )
)
print(json.dumps(dict(passed=len(results), total=len(results))), flush=True)
engine.dispose()
storage_dir.cleanup()
