"""Milestone D integration: real CHANGE/CANCEL transactions and revision privacy."""

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
db_name = "httt10_amendments_" + uuid4().hex[:10] + "_test"
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
from app import scheduling as service, security

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


# A room move must keep the original effective booking until approval.
item, original = confirmed(people=[("EMP1", True), ("SHARED", True)])
base = current(item)
base_id = base["current_revision"]["id"]
new = revision_payload(base["current_revision"]) | dict(
    room_id="20000000-0000-0000-0000-000000000002",
    title="NEW_PRIVATE_TITLE",
    description="NEW_PRIVATE_DESCRIPTION",
    participants=[
        dict(user_id=users["EMP1"], is_required=True),
        dict(user_id=users["OPT"], is_required=True),
    ],
)
check(
    "Chủ lịch có các thao tác sửa và hủy họp",
    set(base["allowed_actions"]),
    {"REQUEST_CHANGE", "CANCEL_MEETING"},
)
check(
    "Người tham gia không được quản lý lịch",
    current(item, who="SHARED")["allowed_actions"],
    [],
)
check(
    "Người ngoài không gửi đề nghị sửa",
    change(item, new, who="EMP2", state=base)[0].status_code,
    403,
)
check(
    "Không gửi sửa bằng phiên bản root cũ",
    change(item, new, state=base | dict(row_version=99))[0].json()["error"]["code"],
    "VERSION_CONFLICT",
)
check(
    "Không gửi sửa bằng base revision sai",
    change(item, new, base_id=str(uuid4()))[0].json()["error"]["code"],
    "BASE_REVISION_CHANGED",
)
response, change_body, change_key = change(item, new)
check("Đề nghị sửa được lưu PENDING", response.status_code, 201)
amend = response.json()
check("Gửi sửa giữ current revision cũ", root_row(item)["current_revision_id"], base_id)
check(
    "Gửi sửa chưa giữ phòng mới",
    scalar(
        "SELECT room_id FROM v_effective_schedules WHERE schedule_id=:s",
        s=item["schedule_id"],
    ),
    original["room_id"],
)
check("Gửi sửa tăng phiên bản aggregate", current(item)["row_version"], 3)
check(
    "Chỉ một đề nghị chờ cho mỗi lịch",
    change(item, new)[0].json()["error"]["code"],
    "PENDING_PROPOSAL_EXISTS",
)
check(
    "Lịch có bản sửa chờ vẫn được hủy họp",
    current(item)["allowed_actions"],
    ["CANCEL_MEETING"],
)
replay = request(
    "POST",
    "/schedules/" + item["schedule_id"] + "/change-proposals",
    change_body,
    key=change_key,
    code=201,
)
check(
    "Retry gửi sửa không tạo revision mới",
    replay.headers.get("Idempotency-Replayed"),
    "true",
)
check(
    "Retry gửi sửa chỉ có hai revision",
    scalar(
        "SELECT COUNT(*) FROM schedule_revisions WHERE schedule_id=:s",
        s=item["schedule_id"],
    ),
    2,
)
check(
    "Người duyệt phòng cũ không đọc bản sửa phòng mới",
    request(
        "GET", "/proposals/" + amend["proposal_id"], who="LEAD1", code=None
    ).status_code,
    404,
)
check(
    "Người tham gia cũ không đọc bản sửa riêng",
    request(
        "GET", "/proposals/" + amend["proposal_id"], who="SHARED", code=None
    ).status_code,
    404,
)
p = detail(amend, who="LEAD2")
check("Người duyệt phòng mới đọc bản sửa", p["candidate"]["title"], "NEW_PRIVATE_TITLE")
check(
    "So sánh gốc không lộ mô tả/thành phần cũ",
    set(p["base_comparison"]),
    {
        "revision_id",
        "starts_at",
        "ends_at",
        "room_id",
        "department_id",
        "changed_fields",
    },
)
check(
    "So sánh đánh dấu đúng nhóm thay đổi",
    set(p["base_comparison"]["changed_fields"]),
    {"title", "description", "room_id", "participants"},
)
check(
    "Người mới chỉ thấy root bận trước duyệt",
    current(item, who="OPT")["visibility"],
    "BUSY_ONLY",
)
check(
    "Người mới được xem đề nghị liên quan",
    detail(amend, who="OPT")["candidate"]["title"],
    "NEW_PRIVATE_TITLE",
)
check(
    "Phòng cũ không thấy bản sửa trong hộp duyệt",
    amend["proposal_id"]
    not in [
        r["id"]
        for r in request(
            "GET", "/proposals?scope=REVIEWABLE&status=PENDING", who="LEAD1"
        ).json()["items"]
    ],
)
check(
    "Phòng cũ không được duyệt thay phòng mới",
    decision(amend, who="LEAD1")[0].status_code,
    403,
)
accepted, approval_body, approval_key = decision(amend, who="LEAD2")
check("Người duyệt phòng mới chấp thuận", accepted.status_code, 200)
new_id = detail(amend)["candidate"]["id"]
check(
    "Duyệt đổi current nguyên tử sang bản mới",
    root_row(item)["current_revision_id"],
    new_id,
)
check(
    "Chỉ còn một phiên bản hiệu lực của root",
    scalar(
        "SELECT COUNT(*) FROM v_effective_schedules WHERE schedule_id=:s",
        s=item["schedule_id"],
    ),
    1,
)
check(
    "Phòng cũ được giải phóng sau duyệt",
    scalar(
        "SELECT room_id FROM v_effective_schedules WHERE schedule_id=:s",
        s=item["schedule_id"],
    ),
    new["room_id"],
)
check(
    "Người cũ mất bận do lịch này",
    scalar(
        "SELECT COUNT(*) FROM v_effective_participants WHERE schedule_id=:s AND user_id=:u",
        s=item["schedule_id"],
        u=users["SHARED"],
    ),
    0,
)
check(
    "Người mới có bận sau duyệt",
    scalar(
        "SELECT COUNT(*) FROM v_effective_participants WHERE schedule_id=:s AND user_id=:u",
        s=item["schedule_id"],
        u=users["OPT"],
    ),
    1,
)
check(
    "Người cũ không đọc root chi tiết sau thay đổi",
    current(item, who="SHARED")["visibility"],
    "BUSY_ONLY",
)
check(
    "Người duyệt phòng cũ không lấy revision mới",
    request(
        "GET",
        "/schedules/" + item["schedule_id"] + "/revisions/" + new_id,
        who="LEAD1",
        code=None,
    ).status_code,
    404,
)
check(
    "Người duyệt phòng cũ vẫn xem được bản lịch sử cũ",
    request(
        "GET",
        "/schedules/" + item["schedule_id"] + "/revisions/" + base_id,
        who="LEAD1",
    ).json()["id"],
    base_id,
)
old_audit = request("GET", "/schedules/" + item["schedule_id"] + "/audit", who="LEAD1")
check(
    "Audit phòng cũ chỉ thông báo giải phóng chỗ",
    any(a["action"] == "SCHEDULE_RELEASED" for a in old_audit.json()["items"]),
)
check(
    "Audit phòng cũ không lộ nội dung hoặc revision mới",
    new_id not in old_audit.text and "NEW_PRIVATE" not in old_audit.text,
)
with Session() as db:
    event = (
        db.execute(
            text(
                "SELECT * FROM outbox_events WHERE proposal_id=:p AND event_type='SCHEDULE_RELEASED'"
            ),
            dict(p=amend["proposal_id"]),
        )
        .mappings()
        .one()
    )
    payload = (
        json.loads(event["payload"])
        if isinstance(event["payload"], str)
        else event["payload"]
    )
    recipients = set(
        db.scalars(
            text("SELECT recipient_user_id FROM email_deliveries WHERE event_id=:id"),
            dict(id=event["id"]),
        )
    )
check("Thông báo giải phóng gắn revision cũ", payload["revision_id"], base_id)
check(
    "Thông báo giải phóng đến người cũ/phòng cũ",
    users["SHARED"] in recipients and users["LEAD1"] in recipients,
)
check(
    "Thông báo giải phóng không cấp nội dung mới cho người mới",
    users["OPT"] not in recipients,
)
check(
    "Retry duyệt sửa không tạo thông báo lần nữa",
    request(
        "POST",
        "/proposals/" + amend["proposal_id"] + "/decisions",
        approval_body,
        who="LEAD2",
        key=approval_key,
    ).headers.get("Idempotency-Replayed"),
    "true",
)
check(
    "Mỗi đề nghị chỉ một event giải phóng",
    scalar(
        "SELECT COUNT(*) FROM outbox_events WHERE proposal_id=:p AND event_type='SCHEDULE_RELEASED'",
        p=amend["proposal_id"],
    ),
    1,
)

# Historical rights survive cancellation of a newer private revision.
assert cancel(item)[0].status_code == 200
check(
    "Bản mới bị hủy không mở root riêng tư cho người cũ",
    request(
        "GET", "/schedules/" + item["schedule_id"], who="SHARED", code=None
    ).status_code,
    404,
)
check(
    "Người cũ vẫn tra cứu được revision cũ sau hủy bản mới",
    request(
        "GET",
        "/schedules/" + item["schedule_id"] + "/revisions/" + base_id,
        who="SHARED",
    ).json()["id"],
    base_id,
)

# Rejected and withdrawn changes preserve the current booking and version history.
item, original = confirmed()
base = current(item)
new = revision_payload(base["current_revision"]) | dict(title="REJECT_ME")
a, _, _ = change(item, new)
a = a.json()
check("Từ chối bản sửa được xử lý", decision(a, approve=False)[0].status_code, 200)
check(
    "Từ chối bản sửa giữ current cũ",
    root_row(item)["current_revision_id"],
    base["current_revision"]["id"],
)
a, _, _ = change(item, new)
a = a.json()
check("Rút bản sửa được xử lý", withdraw(a).status_code, 200)
check(
    "Rút bản sửa giữ lịch gốc",
    root_row(item)["current_revision_id"],
    base["current_revision"]["id"],
)
check(
    "Revision không tái dùng số sau bản sửa bị từ chối/rút",
    request("GET", "/schedules/" + item["schedule_id"] + "/revisions").json()["items"][
        0
    ]["revision_no"],
    3,
)
check(
    "Không chuyển họp thành công tác khi sửa",
    change(item, work())[0].json()["error"]["code"],
    "SCHEDULE_KIND_CHANGED",
)

# A requested new slot can be lost while waiting; no old booking is released.
item, original = confirmed()
base = current(item)
target = meeting(room=2)
a, _, _ = change(item, target)
a = a.json()
blocker, _ = confirmed(
    who="EMP2",
    room=2,
    start=datetime.fromisoformat(target["starts_at"]).replace(tzinfo=None),
)
blocked = decision(a, who="LEAD2")[0]
check(
    "Chỗ mới bị duyệt giữ trong lúc chờ chặn sửa",
    blocked.json()["error"]["code"],
    "ROOM_BUSY",
)
check("Xung đột không tự từ chối đề nghị sửa", detail(a)["status"], "PENDING")
check(
    "Mất chỗ mới vẫn giữ chỗ gốc",
    root_row(item)["current_revision_id"],
    base["current_revision"]["id"],
)
occupied = change(item, target)[0]
check(
    "Có đề nghị chờ không nhận bản sửa khác",
    occupied.json()["error"]["code"],
    "PENDING_PROPOSAL_EXISTS",
)
assert withdraw(a).status_code == 200
check(
    "Ngay lúc gửi cũng chặn nếu chỗ mới đã giữ",
    change(item, target)[0].json()["error"]["code"],
    "ROOM_BUSY",
)

# Deadlines are the earlier of the original and proposed starts.
earlier = slot()
later = slot()
item, _ = confirmed(start=later)
a, _, _ = change(item, meeting(start=earlier))
a = a.json()
check(
    "Đổi sang sớm hơn hết hạn theo giờ mới",
    detail(a)["expires_at"],
    iso(earlier).replace("+00:00", "Z"),
)
item, _ = confirmed()
base = current(item)
later = slot()
a, _, _ = change(item, meeting(start=later))
a = a.json()
check(
    "Đổi sang muộn hơn vẫn hết hạn theo giờ gốc",
    detail(a)["expires_at"],
    base["current_revision"]["starts_at"],
)
with Session.begin() as db:
    db.execute(
        text("UPDATE approval_proposals SET expires_at=:past WHERE id=:id"),
        dict(past=security.now() - timedelta(seconds=1), id=a["proposal_id"]),
    )
expired = decision(a)[0]
check(
    "Duyệt bản sửa đến hạn ghi EXPIRED", expired.json()["error"]["expiration_committed"]
)
check(
    "Bản sửa hết hạn không bỏ lịch gốc",
    root_row(item)["current_revision_id"],
    base["current_revision"]["id"],
)

# Direct meeting cancellation works even with a pending change and is replayable.
item, _ = confirmed()
base = current(item)
a, _, _ = change(item, meeting(room=2))
a = a.json()
check(
    "Người tham gia không hủy họp thay người tạo",
    cancel(item, who="LEAD1", state=current(item))[0].status_code,
    403,
)
check("Hủy họp cần lý do", cancel(item, reason="   ")[0].status_code, 422)
cancelled, cancel_body, cancel_key = cancel(item)
check(
    "Hủy họp trả receipt không có proposal mới", cancelled.json()["proposal_id"], None
)
check(
    "Hủy họp giữ current cho lịch sử",
    root_row(item)["current_revision_id"],
    base["current_revision"]["id"],
)
check(
    "Hủy họp giải phóng phòng và đệm",
    scalar(
        "SELECT COUNT(*) FROM v_effective_meetings WHERE schedule_id=:s",
        s=item["schedule_id"],
    ),
    0,
)
check(
    "Hủy họp giải phóng bận của người",
    scalar(
        "SELECT COUNT(*) FROM v_effective_participants WHERE schedule_id=:s",
        s=item["schedule_id"],
    ),
    0,
)
check("Hủy họp đồng thời vô hiệu bản sửa chờ", detail(a)["status"], "EXPIRED")
check(
    "Không duyệt lại bản sửa để khôi phục lịch hủy",
    decision(a, who="LEAD2")[0].status_code,
    409,
)
check(
    "Root đã hủy ngoài quyền trả 404",
    request(
        "GET", "/schedules/" + item["schedule_id"], who="EMP2", code=None
    ).status_code,
    404,
)
check("Lịch hủy không còn thao tác sửa/hủy", current(item)["allowed_actions"], [])
check(
    "Retry hủy họp trả lại receipt cũ",
    request(
        "POST",
        "/schedules/" + item["schedule_id"] + "/meeting-cancellations",
        cancel_body,
        key=cancel_key,
    ).headers.get("Idempotency-Replayed"),
    "true",
)
check(
    "Retry hủy không nhân đôi event",
    scalar(
        "SELECT COUNT(*) FROM outbox_events WHERE schedule_id=:s AND event_type='MEETING_CANCELLED'",
        s=item["schedule_id"],
    ),
    1,
)
check(
    "Lý do hủy họp được lưu",
    current(item)["cancellation"]["reason"],
    cancel_body["reason"],
)

# Work cancellation is a proposal and does not cancel until an approver accepts.
item, original = confirmed(kind="WORK")
base = current(item)
check(
    "Công tác có đề nghị hủy, không hủy trực tiếp",
    set(base["allowed_actions"]),
    {"REQUEST_CHANGE", "REQUEST_WORK_CANCELLATION"},
)
check("Không dùng đường hủy họp cho công tác", cancel(item)[0].status_code, 422)
a, body, key = cancel(item, work=True, reason="REQUEST_REASON_ORIGINAL")
check("Gửi hủy công tác trả 201", a.status_code, 201)
a = a.json()
check(
    "Chờ hủy công tác vẫn có hiệu lực",
    scalar(
        "SELECT COUNT(*) FROM v_effective_schedules WHERE schedule_id=:s",
        s=item["schedule_id"],
    ),
    1,
)
check(
    "Đề nghị hủy không tạo revision giả",
    scalar(
        "SELECT COUNT(*) FROM schedule_revisions WHERE schedule_id=:s",
        s=item["schedule_id"],
    ),
    1,
)
p = detail(a)
check(
    "CANCEL trả candidate null và base comparison",
    (p["candidate"], p["base_comparison"]["revision_id"]),
    (None, base["current_revision"]["id"]),
)
check(
    "Đề nghị hủy và sửa loại trừ nhau",
    change(item, revision_payload(base["current_revision"]))[0].json()["error"]["code"],
    "PENDING_PROPOSAL_EXISTS",
)
check("Không tự duyệt hủy công tác", decision(a, who="EMP1")[0].status_code, 403)
check(
    "Không có phạm vi không duyệt hủy công tác",
    decision(a, who="ROGUE")[0].status_code,
    403,
)
check(
    "Từ chối hủy giữ công tác hoạt động", decision(a, approve=False)[0].status_code, 200
)
check("Sau từ chối hủy công tác vẫn hiệu lực", root_row(item)["cancelled_at"], None)
a2, _, _ = cancel(item, work=True, reason="SECOND_REQUEST_REASON")
a2 = a2.json()
check("Rút hủy công tác không vi phạm CHECK reason", withdraw(a2).status_code, 200)
check(
    "Rút hủy không giải phóng công tác",
    scalar(
        "SELECT COUNT(*) FROM v_effective_schedules WHERE schedule_id=:s",
        s=item["schedule_id"],
    ),
    1,
)
a3, _, _ = cancel(item, work=True, reason="THIRD_REQUEST_REASON")
a3 = a3.json()
check(
    "Lý do hủy ban đầu có lịch sử riêng không bị ghi đè",
    "REQUEST_REASON_ORIGINAL"
    in request("GET", "/schedules/" + item["schedule_id"] + "/audit").text,
)
accepted, decision_body, decision_key = decision(a3)
check("Chấp thuận hủy công tác thành công", accepted.status_code, 200)
check(
    "Chấp thuận hủy mới giải phóng bận",
    scalar(
        "SELECT COUNT(*) FROM v_effective_schedules WHERE schedule_id=:s",
        s=item["schedule_id"],
    ),
    0,
)
check(
    "Lý do hủy công tác lấy từ đề nghị đã gửi",
    current(item)["cancellation"]["reason"],
    "THIRD_REQUEST_REASON",
)
check(
    "Retry duyệt hủy không bị lịch đã hủy chặn",
    request(
        "POST",
        "/proposals/" + a3["proposal_id"] + "/decisions",
        decision_body,
        who="LEAD1",
        key=decision_key,
    ).headers.get("Idempotency-Replayed"),
    "true",
)
check(
    "Retry gửi hủy sau khi lịch đã hủy vẫn trả ID cũ",
    request(
        "POST",
        "/schedules/" + item["schedule_id"] + "/work-cancellation-proposals",
        body,
        key=key,
        code=201,
    ).json()["proposal_id"],
    a["proposal_id"],
)

# Work changes use the same original-retention and department rules.
item, _ = confirmed(kind="WORK")
base = current(item)
new = revision_payload(base["current_revision"]) | dict(
    title="CHANGED_WORK", work_location="NEW_WORK_PLACE"
)
a, _, _ = change(item, new)
a = a.json()
check(
    "Sửa công tác cũng giữ nguyên bản gốc trong lúc chờ",
    root_row(item)["current_revision_id"],
    base["current_revision"]["id"],
)
check("Duyệt sửa công tác thành công", decision(a)[0].status_code, 200)
check(
    "Sửa công tác áp dụng địa điểm mới sau duyệt",
    current(item)["current_revision"]["work_location"],
    "NEW_WORK_PLACE",
)
new = revision_payload(current(item)["current_revision"]) | dict(
    department_id="10000000-0000-0000-0000-000000000002",
    participant_user_ids=[users["FOREIGN"]],
)
check(
    "Không tự chuyển phòng ban của lịch sử công tác",
    change(item, new)[0].json()["error"]["code"],
    "WORK_DEPARTMENT_CHANGED",
)

# Expiry sweep handles both CHANGE and CANCEL without changing current revision.
exp_change, _ = confirmed()
exp_base = current(exp_change)
exp, _, _ = change(exp_change, meeting(room=2))
exp = exp.json()
exp_cancel, _ = confirmed(kind="WORK")
exp_cancel_base = current(exp_cancel)
cancel_exp, _, _ = cancel(exp_cancel, work=True)
cancel_exp = cancel_exp.json()
with Session.begin() as db:
    for identifier in [exp["proposal_id"], cancel_exp["proposal_id"]]:
        db.execute(
            text("UPDATE approval_proposals SET expires_at=:past WHERE id=:id"),
            dict(past=security.now() - timedelta(seconds=1), id=identifier),
        )
check("Sweep hết hạn xử lý cả CHANGE và CANCEL", service.expire_due(), 2)
check(
    "CHANGE hết hạn giữ lịch gốc",
    root_row(exp_change)["current_revision_id"],
    exp_base["current_revision"]["id"],
)
check("CANCEL hết hạn không hủy công tác", root_row(exp_cancel)["cancelled_at"], None)
check("CANCEL hết hạn có reason hợp lệ", detail(cancel_exp)["status"], "EXPIRED")

# Started originals cannot be modified/cancelled even if the new slot is future.
started, _ = confirmed()
state = current(started)
now = datetime.fromisoformat(state["current_revision"]["starts_at"]).replace(
    tzinfo=None
) + timedelta(seconds=1)
with Session.begin() as db:
    db.execute(
        text("UPDATE auth_sessions SET expires_at=:future"),
        dict(future=security.now() + timedelta(days=180)),
    )
with patch("app.security.now", return_value=now):
    cancel_result = cancel(started, state=state)[0]
    change_result = change(
        started, meeting(start=now + timedelta(days=2)), state=state
    )[0]
check(
    "Không hủy họp đã bắt đầu",
    cancel_result.json()["error"]["code"],
    "ORIGINAL_SCHEDULE_STARTED",
)
check(
    "Không sửa lịch gốc đã bắt đầu dù giờ mới còn xa",
    change_result.json()["error"]["code"],
    "ORIGINAL_SCHEDULE_STARTED",
)

# Inject a failure after effect updates to verify transaction rollback.
from app.dependencies import service as auth_service
from app.schemas import ProposalDecision, CancellationRequest

ctx = auth_service.identity(headers["LEAD2"]["Authorization"][7:])
item, _ = confirmed()
base = current(item)
a, _, _ = change(item, meeting(room=2))
a = a.json()
p = detail(a)
try:
    with patch(
        "app.scheduling.notify",
        side_effect=RuntimeError("injected after change UPDATE"),
    ):
        service.resolve(
            ctx,
            a["proposal_id"],
            ProposalDecision(
                expected_schedule_version=p["schedule_version"],
                expected_proposal_version=p["row_version"],
                decision="APPROVE",
            ),
            str(uuid4()),
        )
except RuntimeError:
    pass
else:
    raise AssertionError("Expected injected failure")
check(
    "Lỗi khi duyệt sửa giữ current gốc",
    root_row(item)["current_revision_id"],
    base["current_revision"]["id"],
)
check("Lỗi khi duyệt sửa giữ PENDING", detail(a)["status"], "PENDING")
ctx = auth_service.identity(headers["EMP1"]["Authorization"][7:])
try:
    with patch(
        "app.scheduling.notify",
        side_effect=RuntimeError("injected during cancellation"),
    ):
        service.cancel_meeting(
            ctx,
            item["schedule_id"],
            CancellationRequest(
                expected_schedule_version=current(item)["row_version"],
                reason="Rollback demo",
            ),
            str(uuid4()),
        )
except RuntimeError:
    pass
else:
    raise AssertionError("Expected injected failure")
check("Lỗi hủy họp hoàn tác trạng thái hủy", root_row(item)["cancelled_at"], None)
check("Lỗi hủy họp hoàn tác cả việc vô hiệu bản sửa", detail(a)["status"], "PENDING")


# Independent connections begin together to exercise root/resource locks.
def parallel(actions):
    barrier = Barrier(len(actions))

    def invoke(action):
        barrier.wait()
        return action()

    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        futures = [pool.submit(invoke, a) for a in actions]
        return [f.result() for f in futures]


def http_action(path, body, who="EMP1", key=None):
    def invoke():
        with TestClient(app) as other:
            return other.post(
                "/api/v1" + path,
                json=body,
                headers=headers[who] | {"Idempotency-Key": key or str(uuid4())},
            )

    return invoke


def approval_action(item, who="LEAD1", owner="EMP1"):
    p = detail(item, who=owner)
    body = dict(
        expected_schedule_version=p["schedule_version"],
        expected_proposal_version=p["row_version"],
        decision="APPROVE",
    )
    path = "/proposals/" + item["proposal_id"] + "/decisions"
    # Preflight a known warning set only when another pending request overlaps.
    candidate = p["candidate"]
    with Session() as db:
        context = service.fresh_actor(
            db, auth_service.identity(headers[who]["Authorization"][7:])
        )
        model = service.candidate_from_revision(db, candidate["id"])
        result, fingerprint = service.availability(
            db,
            context,
            model,
            submitter=users[owner],
            excluded=item["schedule_id"],
            submitting=False,
            warning_context=(
                {"base_revision_id": p["base_comparison"]["revision_id"]}
                if p["base_comparison"]
                else None
            ),
        )
    if result["warnings"]:
        body["warning_acknowledgement_token"] = result["warning_acknowledgement_token"]
    return http_action(path, body, who)


item, _ = confirmed()
base = current(item)
new = revision_payload(base["current_revision"]) | dict(title="PARALLEL_CHANGE")
body = dict(
    expected_schedule_version=base["row_version"],
    base_revision_id=base["current_revision"]["id"],
    candidate=new,
)
race = parallel(
    [
        http_action("/schedules/" + item["schedule_id"] + "/change-proposals", body),
        http_action("/schedules/" + item["schedule_id"] + "/change-proposals", body),
    ]
)
check(
    "Hai gửi sửa đồng thời chỉ một đề nghị được lưu",
    sorted(r.status_code for r in race),
    [201, 409],
)
check(
    "Hai gửi sửa không tạo hai revision mới",
    scalar(
        "SELECT COUNT(*) FROM schedule_revisions WHERE schedule_id=:s",
        s=item["schedule_id"],
    ),
    2,
)

# A meeting cancellation and change approval cannot both use the same version.
item, _ = confirmed()
base = current(item)
a, _, _ = change(item, meeting(room=2))
a = a.json()
state = current(item)
race = parallel(
    [
        approval_action(a, who="LEAD2"),
        http_action(
            "/schedules/" + item["schedule_id"] + "/meeting-cancellations",
            dict(
                expected_schedule_version=state["row_version"],
                reason="Concurrent cancel",
            ),
        ),
    ]
)
check(
    "Duyệt sửa và hủy họp cạnh tranh chỉ một thắng",
    sorted(r.status_code for r in race),
    [200, 409],
)
r = root_row(item)
p = detail(a)
check(
    "Không khôi phục lịch đã hủy bằng bản sửa cạnh tranh",
    (r["cancelled_at"] is None and p["status"] == "APPROVED")
    or (r["cancelled_at"] is not None and p["status"] == "EXPIRED"),
)

# Two moves lock both rooms in the same order, even in opposite directions.
time_a = slot()
time_b = slot()
a, _ = confirmed(start=time_a)
b, _ = confirmed(start=time_b, room=2, who="EMP2")
ca, _, _ = change(a, meeting(start=time_a, room=2))
ca = ca.json()
cb, _, _ = change(b, meeting(start=time_b, who="EMP2", room=1), who="EMP2")
cb = cb.json()
race = parallel(
    [approval_action(ca, who="LEAD2"), approval_action(cb, who="LEAD1", owner="EMP2")]
)
check(
    "Hai đổi phòng ngược chiều hợp lệ cùng hoàn thành",
    [r.status_code for r in race],
    [200, 200],
)
check(
    "Cả hai root chỉ có một current revision",
    scalar(
        "SELECT COUNT(*) FROM v_effective_schedules WHERE schedule_id IN (:a,:b)",
        a=a["schedule_id"],
        b=b["schedule_id"],
    ),
    2,
)

# Two old bookings compete for one new slot; the loser retains its original.
a, _ = confirmed()
b, _ = confirmed(who="EMP2", room=2)
old_a = root_row(a)["current_revision_id"]
old_b = root_row(b)["current_revision_id"]
target = slot()
ca, _, _ = change(a, meeting(start=target))
ca = ca.json()
cb, _, _ = change(b, meeting(start=target, who="EMP2"), who="EMP2")
cb = cb.json()
race = parallel(
    [approval_action(ca, who="LEAD1"), approval_action(cb, who="LEAD2", owner="EMP2")]
)
check(
    "Hai bản sửa tranh cùng chỗ mới chỉ một được duyệt",
    sorted(r.status_code for r in race),
    [200, 409],
)
check(
    "Bản sửa thua vẫn giữ lịch cũ",
    (root_row(a)["current_revision_id"] == old_a)
    != (root_row(b)["current_revision_id"] == old_b),
)
check(
    "Không mất bất kỳ lịch gốc nào ngoài bản thay thế",
    scalar(
        "SELECT COUNT(*) FROM v_effective_schedules WHERE schedule_id IN (:a,:b)",
        a=a["schedule_id"],
        b=b["schedule_id"],
    ),
    2,
)
check(
    "OpenAPI hiện công bố 50 thao tác",
    sum(len(v) for v in app.openapi()["paths"].values()),
    50,
)
output = dict(
    passed=len(results),
    total=len(results),
    tests=results,
    mysql_version=scalar("SELECT VERSION()"),
    scope="Real MySQL + FastAPI ASGI, CHANGE/CANCEL creation/decisions/direct meeting cancellation, privacy/expiry/rollback/concurrency; no SMTP/browser/Docker Windows/LAN",
)
result_dir = Path(os.getenv("TEST_RESULT_DIR", str(root / "verification")))
result_dir.mkdir(parents=True, exist_ok=True)
(result_dir / "amendments-result.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2)
)
print(json.dumps(dict(passed=len(results), total=len(results))), flush=True)
engine.dispose()
