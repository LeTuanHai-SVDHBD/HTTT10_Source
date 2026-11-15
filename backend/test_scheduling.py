"""Milestone C integration: real HTTP adapters + isolated real MySQL database."""

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
db_name = "httt10_scheduling_" + uuid4().hex[:10] + "_test"
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


# Basic checks and exact request/response behavior.
candidate = meeting()
check(
    "Không có phiên không được kiểm tra lịch",
    client.post(
        "/api/v1/availability/check", json=dict(candidate=candidate)
    ).status_code,
    401,
)
check(
    "Admin kỹ thuật không tự có quyền đăng ký",
    request(
        "POST",
        "/meeting-proposals",
        dict(candidate=candidate),
        who="ADMIN",
        key=str(uuid4()),
        code=None,
    ).status_code,
    403,
)
check(
    "Thiếu Idempotency-Key bị từ chối",
    request(
        "POST", "/meeting-proposals", dict(candidate=candidate), code=None
    ).status_code,
    422,
)
check(
    "Key không hợp lệ bị từ chối",
    request(
        "POST",
        "/meeting-proposals",
        dict(candidate=candidate),
        key="bad key",
        code=None,
    ).status_code,
    422,
)
check(
    "Không nhận trạng thái/người gửi do client tự gán",
    request(
        "POST",
        "/meeting-proposals",
        dict(candidate=candidate, status="APPROVED"),
        key=str(uuid4()),
        code=None,
    ).status_code,
    422,
)
check(
    "Chủ trì phải tham gia bắt buộc",
    request(
        "POST",
        "/availability/check",
        dict(
            candidate=candidate
            | dict(participants=[dict(user_id=users["EMP1"], is_required=False)])
        ),
        code=None,
    ).status_code,
    422,
)
preflight = request("POST", "/availability/check", dict(candidate=candidate)).json()
check(
    "Preflight không giữ tài nguyên",
    (preflight["bookable"], preflight["holds_resources"]),
    (True, False),
)
check("Preflight không tạo root", scalar("SELECT COUNT(*) FROM schedule_roots"), 0)
first, first_body, first_key = submit(candidate)
check("Gửi yêu cầu trả 201", first.status_code, 201)
first = first.json()
check(
    "Biên nhận chỉ có ID không giả xác nhận giữ phòng",
    set(first),
    {"committed", "schedule_id", "proposal_id"},
)
p = detail(first)
check(
    "Yêu cầu mới PENDING / root chưa có lịch hiệu lực",
    (
        p["status"],
        scalar(
            "SELECT current_revision_id FROM schedule_roots WHERE id=:s",
            s=first["schedule_id"],
        ),
    ),
    ("PENDING", None),
)
check("Người gửi chỉ được rút, chưa có nút duyệt", p["allowed_actions"], ["WITHDRAW"])
check(
    "Lưu outbox và delivery cùng yêu cầu",
    scalar(
        "SELECT COUNT(*) FROM outbox_events WHERE schedule_id=:s",
        s=first["schedule_id"],
    ),
    1,
)
check(
    "Email vẫn chờ, chưa có SMTP giả thành công", p["email_summary"]["smtp_accepted"], 0
)
check(
    "Yêu cầu chờ không xuất hiện trong calendar",
    request(
        "GET",
        "/calendar?from="
        + candidate["starts_at"].replace("+", "%2B")
        + "&to="
        + candidate["ends_at"].replace("+", "%2B"),
    ).json()["total"],
    0,
)
check(
    "Người ngoài không đọc yêu cầu chờ",
    request(
        "GET", "/proposals/" + first["proposal_id"], who="EMP2", code=None
    ).status_code,
    404,
)
check(
    "Admin kỹ thuật không đọc yêu cầu riêng",
    request(
        "GET", "/proposals/" + first["proposal_id"], who="ADMIN", code=None
    ).status_code,
    404,
)
check(
    "Root chờ ngoài quyền trả 404",
    request(
        "GET", "/schedules/" + first["schedule_id"], who="EMP2", code=None
    ).status_code,
    404,
)
check(
    "Danh sách theo người gửi không rò toàn bộ yêu cầu",
    request("GET", "/proposals?scope=MINE", who="EMP2").json()["total"],
    0,
)
check(
    "Người duyệt đúng phạm vi thấy yêu cầu",
    request("GET", "/proposals?scope=REVIEWABLE", who="LEAD1").json()["total"],
    1,
)
check(
    "Người duyệt ngoài phạm vi không thấy yêu cầu",
    request("GET", "/proposals?scope=REVIEWABLE", who="ROGUE").json()["total"],
    0,
)
replay = request("POST", "/meeting-proposals", first_body, key=first_key, code=201)
check("Retry cùng key trả cùng ID", replay.json(), first)
check(
    "Retry có header Idempotency-Replayed",
    replay.headers.get("Idempotency-Replayed"),
    "true",
)
check(
    "Retry không nhân đôi root hoặc outbox",
    (
        scalar("SELECT COUNT(*) FROM schedule_roots"),
        scalar("SELECT COUNT(*) FROM outbox_events"),
    ),
    (1, 1),
)
check(
    "Key thành công không được đổi payload",
    request(
        "POST",
        "/meeting-proposals",
        dict(candidate=candidate | dict(title="OTHER")),
        key=first_key,
        code=None,
    ).json()["error"]["code"],
    "IDEMPOTENCY_KEY_REUSED",
)
check(
    "Không tự duyệt yêu cầu",
    decision(first, who="EMP1")[0].json()["error"]["code"],
    "SELF_REVIEW_FORBIDDEN",
)
check(
    "Không tự từ chối yêu cầu",
    decision(first, who="EMP1", approve=False)[0].status_code,
    403,
)
check(
    "Không có scope bị chặn ở server", decision(first, who="ROGUE")[0].status_code, 403
)
old_versions = p | dict(schedule_version=99)
check(
    "Duyệt phiên bản cũ bị chặn",
    decision(first, versions=old_versions)[0].json()["error"]["code"],
    "VERSION_CONFLICT",
)
accepted, decision_body, decision_key = decision(first)
check("Duyệt hợp lệ trả 200", accepted.status_code, 200)
check(
    "Chỉ sau duyệt mới có hiệu lực",
    scalar(
        "SELECT COUNT(*) FROM v_effective_schedules WHERE schedule_id=:s",
        s=first["schedule_id"],
    ),
    1,
)
p = detail(first)
check(
    "Duyệt tăng phiên bản root và proposal",
    (p["status"], p["schedule_version"], p["row_version"]),
    ("APPROVED", 2, 2),
)
check("Lưu người phê duyệt thật", p["resolved_by"]["id"], users["LEAD1"])
check(
    "Replay quyết định được xét trước phiên bản cũ",
    request(
        "POST",
        "/proposals/" + first["proposal_id"] + "/decisions",
        decision_body,
        who="LEAD1",
        key=decision_key,
    ).headers.get("Idempotency-Replayed"),
    "true",
)
check(
    "Replay quyết định không tạo event mới",
    scalar(
        "SELECT COUNT(*) FROM outbox_events WHERE schedule_id=:s",
        s=first["schedule_id"],
    ),
    2,
)
check(
    "Yêu cầu đã xử lý không rút được",
    request(
        "POST",
        "/proposals/" + first["proposal_id"] + "/withdrawals",
        dict(expected_schedule_version=2, expected_proposal_version=2, reason=None),
        key=str(uuid4()),
        code=None,
    ).status_code,
    409,
)
busy = request("GET", "/schedules/" + first["schedule_id"], who="EMP2").json()
check("Root hiệu lực ngoài quyền chỉ BUSY_ONLY", busy["visibility"], "BUSY_ONLY")
check(
    "Busy không lộ title/ID/người tham gia",
    set(busy),
    {"visibility", "starts_at", "ends_at", "room_id", "blocked_until"},
)
check(
    "Người tạo xem chi tiết bản hiệu lực",
    request("GET", "/schedules/" + first["schedule_id"]).json()["current_revision"][
        "title"
    ],
    candidate["title"],
)
check(
    "Người ngoài không lấy được revision",
    request(
        "GET",
        "/schedules/" + first["schedule_id"] + "/revisions/" + p["candidate"]["id"],
        who="EMP2",
        code=None,
    ).status_code,
    404,
)
check(
    "Người tạo xem lịch sử revision",
    request("GET", "/schedules/" + first["schedule_id"] + "/revisions").json()["total"],
    1,
)
check(
    "Người tạo có audit nghiệp vụ",
    request("GET", "/schedules/" + first["schedule_id"] + "/audit").json()["total"],
    2,
)
check(
    "Audit không trả raw metadata",
    all(
        "safe_metadata" not in item
        for item in request(
            "GET", "/schedules/" + first["schedule_id"] + "/audit"
        ).json()["items"]
    ),
)
check(
    "Lịch liên quan lọc đúng quyền",
    request("GET", "/schedules?relation=CREATED&lifecycle=ACTIVE").json()["total"],
    1,
)
check(
    "Admin không tự có lịch chi tiết toàn đơn vị",
    request("GET", "/schedules", who="ADMIN").json()["total"],
    0,
)

# Validation, warnings and pending competition.
check(
    "Đã giữ phòng thì preflight không bookable",
    request(
        "POST", "/availability/check", dict(candidate=candidate), who="EMP2"
    ).json()["bookable"],
    False,
)
check(
    "Xung đột không tiết lộ title/root đối thủ",
    candidate["title"]
    not in request(
        "POST",
        "/availability/check",
        dict(
            candidate=meeting(
                start=datetime.fromisoformat(candidate["starts_at"]).replace(
                    tzinfo=None
                ),
                who="EMP2",
            )
        ),
        who="EMP2",
    ).text,
)
check(
    "Phương án cứng xung đột không được gửi",
    submit(candidate, who="EMP2")[0].status_code,
    409,
)
check(
    "Phòng không đủ sức chứa trả conflict",
    request(
        "POST",
        "/availability/check",
        dict(
            candidate=meeting(
                room=2,
                people=[
                    ("EMP1", True),
                    ("EMP2", True),
                    ("SHARED", True),
                    ("OPT", True),
                    ("FOREIGN", True),
                    ("LEAD1", True),
                    ("LEAD2", True),
                    ("ROGUE", True),
                    ("ADMIN", True),
                ],
            )
        ),
    ).json()["conflicts"][0]["code"],
    "ROOM_CONFIG_INVALID",
)
with Session.begin() as db:
    db.execute(
        text(
            "UPDATE room_approvers SET is_active=0 WHERE room_id='20000000-0000-0000-0000-000000000002'"
        )
    )
check(
    "Không có người duyệt thay chặn gửi",
    submit(meeting(room=2))[0].json()["error"]["code"],
    "NO_ELIGIBLE_APPROVER",
)
with Session.begin() as db:
    db.execute(
        text(
            "UPDATE room_approvers SET is_active=1 WHERE room_id='20000000-0000-0000-0000-000000000002'"
        )
    )
self_candidate = meeting(who="LEAD2", room=2)
check(
    "Chỉ có chính người gửi làm người duyệt thì chặn",
    submit(self_candidate, who="LEAD2")[0].json()["error"]["code"],
    "NO_ELIGIBLE_APPROVER",
)
compete_start = slot()
a, _, _ = submit(meeting(start=compete_start))
assert a.status_code == 201
a = a.json()
b_candidate = meeting(start=compete_start, who="EMP2")
blocked, _, failed_key = submit(b_candidate, who="EMP2", ack=False)
check(
    "Hai yêu cầu chờ cùng phòng cần xác nhận cảnh báo",
    blocked.json()["error"]["code"],
    "WARNINGS_REQUIRE_ACK",
)
check(
    "Chưa xác nhận cảnh báo không chiếm key",
    scalar(
        "SELECT COUNT(*) FROM idempotency_keys WHERE key_hash=:k",
        k=hashlib.sha256(failed_key.encode()).hexdigest(),
    ),
    0,
)
ack_token = blocked.json()["error"]["warning_acknowledgement_token"]
check("Token xác nhận không chứa UUID lịch đối thủ", a["schedule_id"] not in ack_token)
check(
    "Token cảnh báo không dùng làm token đăng nhập",
    client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer " + ack_token}
    ).status_code,
    401,
)
wrong_actor = request(
    "POST",
    "/meeting-proposals",
    dict(candidate=b_candidate, warning_acknowledgement_token=ack_token),
    who="EMP1",
    key=str(uuid4()),
    code=None,
)
check(
    "Token cảnh báo gắn người thao tác",
    wrong_actor.json()["error"]["code"],
    "WARNINGS_REQUIRE_ACK",
)
changed_payload = request(
    "POST",
    "/meeting-proposals",
    dict(
        candidate=b_candidate | dict(title="CHANGED"),
        warning_acknowledgement_token=ack_token,
    ),
    who="EMP2",
    key=str(uuid4()),
    code=None,
)
check(
    "Token cảnh báo gắn payload",
    changed_payload.json()["error"]["code"],
    "WARNINGS_REQUIRE_ACK",
)
b, b_body, _ = submit(b_candidate, who="EMP2", key=failed_key)
check("Xác nhận cảnh báo cho phép lưu yêu cầu thứ hai", b.status_code, 201)
b = b.json()
check(
    "Hai yêu cầu chờ vẫn không giữ phòng",
    scalar(
        "SELECT COUNT(*) FROM v_effective_schedules WHERE schedule_id IN (:a,:b)",
        a=a["schedule_id"],
        b=b["schedule_id"],
    ),
    0,
)
check(
    "Duyệt cũng phải xác nhận warning hiện tại",
    decision(a, ack=False)[0].json()["error"]["code"],
    "WARNINGS_REQUIRE_ACK",
)
check("Yêu cầu thứ nhất được duyệt", decision(a)[0].status_code, 200)
check(
    "Yêu cầu thứ hai không được duyệt khi phòng đã giữ",
    decision(b, versions=detail(b, who="EMP2"))[0].json()["error"]["code"],
    "ROOM_BUSY",
)
check(
    "Xung đột giữ PENDING, không tự từ chối", detail(b, who="EMP2")["status"], "PENDING"
)

# Required/optional people at both ends; distinct rooms share a person lock.
shared_time = slot()
a, _, _ = submit(meeting(start=shared_time, people=[("EMP1", True), ("SHARED", True)]))
a = a.json()
assert decision(a)[0].status_code == 200
other = meeting(
    start=shared_time, room=2, who="EMP2", people=[("EMP2", True), ("SHARED", True)]
)
check(
    "Người bắt buộc bận chặn dù phòng khác",
    submit(other, who="EMP2")[0].json()["error"]["code"],
    "REQUIRED_PERSON_BUSY",
)
other["participants"][1]["is_required"] = False
optional, _, _ = submit(other, who="EMP2", ack=False)
check(
    "Một bên tùy chọn chỉ cảnh báo",
    optional.json()["error"]["code"],
    "WARNINGS_REQUIRE_ACK",
)
optional, _, _ = submit(other, who="EMP2")
check("Xác nhận tùy chọn được gửi", optional.status_code, 201)
check(
    "Tùy chọn vẫn được duyệt sau xác nhận",
    decision(
        optional.json(), who="LEAD2", versions=detail(optional.json(), who="EMP2")
    )[0].status_code,
    200,
)
optional_time = slot()
a, _, _ = submit(meeting(start=optional_time, people=[("EMP1", True), ("OPT", False)]))
a = a.json()
assert decision(a)[0].status_code == 200
other = meeting(
    start=optional_time, room=2, who="EMP2", people=[("EMP2", True), ("OPT", True)]
)
check(
    "Lịch cũ tùy chọn, lịch mới bắt buộc vẫn chỉ cảnh báo",
    submit(other, who="EMP2", ack=False)[0].json()["error"]["code"],
    "WARNINGS_REQUIRE_ACK",
)

# Work rules and scope.
work_candidate = work(start=slot() + timedelta(hours=12))
work_response, _, _ = submit(work_candidate)
check(
    "Công tác qua đêm nhiều ngày không bị giới hạn giờ phòng",
    work_response.status_code,
    201,
)
w = work_response.json()
check("Người duyệt công tác theo phòng ban chấp thuận", decision(w)[0].status_code, 200)
wrong_group = work()
wrong_group["participant_user_ids"].append(users["FOREIGN"])
check(
    "Công tác không trộn người khác phòng ban",
    submit(wrong_group)[0].json()["error"]["code"],
    "WORK_DEPARTMENT_MISMATCH",
)
foreign = work(who="FOREIGN", people=["EMP1"])
check(
    "Người gửi không đăng ký thay phòng ban khác",
    submit(foreign, who="FOREIGN")[0].status_code,
    403,
)
check(
    "Công tác nhiều ngày chặn trùng người với họp",
    submit(
        meeting(
            start=datetime.fromisoformat(work_candidate["starts_at"]).replace(
                tzinfo=None
            )
            + timedelta(hours=13)
        )
    )[0].status_code,
    409,
)

# Rejections and withdrawals are real state transitions.
r, _, _ = submit(meeting())
r = r.json()
p = detail(r)
missing_reason = request(
    "POST",
    "/proposals/" + r["proposal_id"] + "/decisions",
    dict(
        expected_schedule_version=p["schedule_version"],
        expected_proposal_version=p["row_version"],
        decision="REJECT",
    ),
    who="LEAD1",
    key=str(uuid4()),
    code=None,
)
check("Từ chối bắt buộc có lý do", missing_reason.status_code, 422)
check("Từ chối hợp lệ lưu quyết định", decision(r, approve=False)[0].status_code, 200)
check(
    "Từ chối không giữ chỗ",
    scalar(
        "SELECT COUNT(*) FROM v_effective_schedules WHERE schedule_id=:s",
        s=r["schedule_id"],
    ),
    0,
)
withdraw, _, _ = submit(meeting())
withdraw = withdraw.json()
p = detail(withdraw)
withdraw_body = dict(
    expected_schedule_version=p["schedule_version"],
    expected_proposal_version=p["row_version"],
    reason="Không cần họp nữa.",
)
check(
    "Người khác không rút hộ yêu cầu",
    request(
        "POST",
        "/proposals/" + withdraw["proposal_id"] + "/withdrawals",
        withdraw_body,
        who="EMP2",
        key=str(uuid4()),
        code=None,
    ).status_code,
    403,
)
withdraw_key = str(uuid4())
wr = request(
    "POST",
    "/proposals/" + withdraw["proposal_id"] + "/withdrawals",
    withdraw_body,
    key=withdraw_key,
)
check("Người gửi được rút yêu cầu", detail(withdraw)["status"], "WITHDRAWN")
check(
    "Retry rút không bị phiên bản cũ chặn",
    request(
        "POST",
        "/proposals/" + withdraw["proposal_id"] + "/withdrawals",
        withdraw_body,
        key=withdraw_key,
    ).headers.get("Idempotency-Replayed"),
    "true",
)
check("Yêu cầu rút không thể được duyệt", decision(withdraw)[0].status_code, 409)

# Expiration commits even though the command returns HTTP 409.
expired, _, _ = submit(meeting())
expired = expired.json()
with Session.begin() as db:
    db.execute(
        text("UPDATE approval_proposals SET expires_at=:past WHERE id=:id"),
        dict(past=security.now() - timedelta(seconds=1), id=expired["proposal_id"]),
    )
expiration = decision(expired)[0]
check(
    "Đến hạn trả PROPOSAL_EXPIRED",
    expiration.json()["error"]["code"],
    "PROPOSAL_EXPIRED",
)
check(
    "Lỗi hết hạn nói rõ đã commit", expiration.json()["error"]["expiration_committed"]
)
check("EXPIRED được lưu thật", detail(expired)["status"], "EXPIRED")
job_expired, _, _ = submit(meeting())
job_expired = job_expired.json()
with Session.begin() as db:
    db.execute(
        text("UPDATE approval_proposals SET expires_at=:past WHERE id=:id"),
        dict(past=security.now() - timedelta(seconds=1), id=job_expired["proposal_id"]),
    )
check("Sweep tự hết hạn xử lý hồ sơ chờ", service.expire_due(), 1)
check("Sweep lặp không ghi event lần hai", service.expire_due(), 0)

# Approval rechecks live state, but does not reapply the submit lead-time rule.
late, _, _ = submit(meeting())
late = late.json()
p = detail(late)
late_now = datetime.fromisoformat(p["candidate"]["starts_at"]).replace(
    tzinfo=None
) - timedelta(minutes=10)
# Advance business time while keeping the existing authenticated test session valid.
with Session.begin() as db:
    db.execute(
        text("UPDATE auth_sessions SET expires_at=:expires"),
        dict(expires=security.now() + timedelta(days=180)),
    )
with patch("app.security.now", return_value=late_now):
    response = decision(late, versions=p)[0]
check("Duyệt sát giờ không áp lại điều kiện 30 phút", response.status_code, 200)
locked, _, _ = submit(meeting())
locked = locked.json()
with Session.begin() as db:
    db.execute(
        text("UPDATE users SET status='LOCKED' WHERE id=:id"), dict(id=users["EMP1"])
    )
check(
    "Duyệt kiểm tra lại thành viên bị khóa",
    decision(locked, versions=detail(locked, who="LEAD1"))[0].json()["error"]["code"],
    "PARTICIPANT_INACTIVE",
)
with Session.begin() as db:
    db.execute(
        text("UPDATE users SET status='ACTIVE' WHERE id=:id"), dict(id=users["EMP1"])
    )
scope_revoked, _, _ = submit(meeting())
scope_revoked = scope_revoked.json()
with Session.begin() as db:
    db.execute(
        text(
            "UPDATE room_approvers SET is_active=0 WHERE user_id=:id AND room_id='20000000-0000-0000-0000-000000000001'"
        ),
        dict(id=users["LEAD1"]),
    )
check(
    "Quyền duyệt bị thu hồi có hiệu lực tại server",
    decision(scope_revoked)[0].status_code,
    403,
)
with Session.begin() as db:
    db.execute(
        text(
            "UPDATE room_approvers SET is_active=1 WHERE user_id=:id AND room_id='20000000-0000-0000-0000-000000000001'"
        ),
        dict(id=users["LEAD1"]),
    )

# A failure after schedule mutation rolls everything back, including outbox/key.
rollback, _, _ = submit(meeting())
rollback = rollback.json()
before = detail(rollback)
try:
    with patch(
        "app.scheduling.notify", side_effect=RuntimeError("injected after UPDATE")
    ):
        service.resolve(
            __import__("app.dependencies", fromlist=["service"]).service.identity(
                headers["LEAD1"]["Authorization"][7:]
            ),
            rollback["proposal_id"],
            __import__("app.schemas", fromlist=["ProposalDecision"]).ProposalDecision(
                expected_schedule_version=before["schedule_version"],
                expected_proposal_version=before["row_version"],
                decision="APPROVE",
            ),
            str(uuid4()),
        )
except RuntimeError:
    pass
else:
    raise AssertionError("Injected failure did not happen")
check(
    "Lỗi sau UPDATE hoàn tác current và trạng thái",
    (
        scalar(
            "SELECT current_revision_id FROM schedule_roots WHERE id=:s",
            s=rollback["schedule_id"],
        ),
        detail(rollback)["status"],
    ),
    (None, "PENDING"),
)
check(
    "Lỗi sau UPDATE không ghi event quyết định",
    scalar(
        "SELECT COUNT(*) FROM outbox_events WHERE schedule_id=:s",
        s=rollback["schedule_id"],
    ),
    1,
)
check("Có thể duyệt lại sau rollback", decision(rollback)[0].status_code, 200)

# A room can stop accepting requests while a proposal is pending.
stopped, _, _ = submit(meeting())
stopped = stopped.json()
with Session.begin() as db:
    db.execute(
        text(
            "UPDATE meeting_rooms SET accepts_new_requests=0 WHERE id='20000000-0000-0000-0000-000000000001'"
        )
    )
check(
    "Duyệt đọc lại trạng thái phòng nhận mới",
    decision(stopped)[0].json()["error"]["code"],
    "ROOM_NOT_ACCEPTING_REQUESTS",
)
check(
    "Phòng ngừng nhận không tự từ chối hồ sơ chờ", detail(stopped)["status"], "PENDING"
)
with Session.begin() as db:
    db.execute(
        text(
            "UPDATE meeting_rooms SET accepts_new_requests=1 WHERE id='20000000-0000-0000-0000-000000000001'"
        )
    )

# Acknowledgement binds the actual warning set, not just its public messages.
warning_start = slot()
wa, _, _ = submit(meeting(start=warning_start))
wa = wa.json()
wb_candidate = meeting(start=warning_start, who="EMP2")
wb_warning, _, _ = submit(wb_candidate, who="EMP2", ack=False)
stale_token = wb_warning.json()["error"]["warning_acknowledgement_token"]
wc, _, _ = submit(meeting(start=warning_start))
assert wc.status_code == 201
stale = request(
    "POST",
    "/meeting-proposals",
    dict(candidate=wb_candidate, warning_acknowledgement_token=stale_token),
    who="EMP2",
    key=str(uuid4()),
    code=None,
)
check(
    "Tập cảnh báo đổi bắt buộc xác nhận lại",
    stale.json()["error"]["code"],
    "WARNINGS_REQUIRE_ACK",
)
expired_token = service.jwt.decode(stale_token, security.SECRET, algorithms=["HS256"])
expired_token["exp"] = 1
expired_token = service.jwt.encode(expired_token, security.SECRET, algorithm="HS256")
check(
    "Token xác nhận hết hạn không được dùng",
    request(
        "POST",
        "/meeting-proposals",
        dict(candidate=wb_candidate, warning_acknowledgement_token=expired_token),
        who="EMP2",
        key=str(uuid4()),
        code=None,
    ).json()["error"]["code"],
    "WARNINGS_REQUIRE_ACK",
)

# Stored successful receipts expire without silently turning into a new intent.
key_expired, expired_body, expired_key = submit(meeting())
assert key_expired.status_code == 201
with Session.begin() as db:
    db.execute(
        text("UPDATE idempotency_keys SET expires_at=:past WHERE key_hash=:key"),
        dict(
            past=security.now() - timedelta(seconds=1),
            key=hashlib.sha256(expired_key.encode()).hexdigest(),
        ),
    )
check(
    "Key hết hạn yêu cầu đọc lại hồ sơ trước khi tạo mới",
    request(
        "POST", "/meeting-proposals", expired_body, key=expired_key, code=None
    ).json()["error"]["code"],
    "IDEMPOTENCY_KEY_EXPIRED",
)


# Parallel requests have independent HTTP clients/connections and a barrier.
def parallel(actions):
    barrier = Barrier(len(actions))

    def run(action):
        barrier.wait()
        return action()

    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        futures = [pool.submit(run, action) for action in actions]
        return [f.result() for f in futures]


same_key = str(uuid4())
same_payload = dict(candidate=meeting())


def same_submit():
    with TestClient(app) as client2:
        return client2.post(
            "/api/v1/meeting-proposals",
            json=same_payload,
            headers=headers["EMP1"] | {"Idempotency-Key": same_key},
        )


responses = parallel([same_submit, same_submit])
check(
    "Hai POST cùng key đồng thời đều nhận receipt",
    [r.status_code for r in responses],
    [201, 201],
)
check("Hai POST cùng key chỉ tạo một lịch", responses[0].json(), responses[1].json())

race_start = slot()
a, _, _ = submit(meeting(start=race_start))
b, _, _ = submit(meeting(start=race_start, who="EMP2"), who="EMP2")
a = a.json()
b = b.json()


# Capture warning tokens for the same pending set before racing approvals.
def approve_action(item, owner, reviewer):
    current = detail(item, who=owner)
    base = dict(
        expected_schedule_version=current["schedule_version"],
        expected_proposal_version=current["row_version"],
        decision="APPROVE",
    )
    warning = request(
        "POST",
        "/proposals/" + item["proposal_id"] + "/decisions",
        base,
        who=reviewer,
        key=str(uuid4()),
        code=None,
    )
    assert (
        warning.status_code == 409
        and warning.json()["error"]["code"] == "WARNINGS_REQUIRE_ACK"
    ), warning.text
    base["warning_acknowledgement_token"] = warning.json()["error"][
        "warning_acknowledgement_token"
    ]

    def call():
        with TestClient(app) as other:
            return other.post(
                "/api/v1/proposals/" + item["proposal_id"] + "/decisions",
                json=base,
                headers=headers[reviewer] | {"Idempotency-Key": str(uuid4())},
            )

    return call


race = parallel(
    [approve_action(a, "EMP1", "LEAD1"), approve_action(b, "EMP2", "LEAD2")]
)
check(
    "Hai duyệt cùng phòng chỉ một được chấp thuận",
    sorted(r.status_code for r in race),
    [200, 409],
)
check(
    "Cùng phòng không có hai lịch hiệu lực",
    scalar(
        "SELECT COUNT(*) FROM v_effective_schedules WHERE schedule_id IN (:a,:b)",
        a=a["schedule_id"],
        b=b["schedule_id"],
    ),
    1,
)

race_start = slot()
a, _, _ = submit(meeting(start=race_start, people=[("EMP1", True), ("SHARED", True)]))
b, _, _ = submit(
    meeting(
        start=race_start, room=2, who="EMP2", people=[("EMP2", True), ("SHARED", True)]
    ),
    who="EMP2",
)
a = a.json()
b = b.json()
race = parallel(
    [approve_action(a, "EMP1", "LEAD1"), approve_action(b, "EMP2", "LEAD2")]
)
check(
    "Duyệt khác phòng nhưng chung người bắt buộc chỉ một thắng",
    sorted(r.status_code for r in race),
    [200, 409],
)
check(
    "Người bắt buộc không bị giữ ở hai lịch cùng giờ",
    scalar(
        "SELECT COUNT(*) FROM v_effective_schedules WHERE schedule_id IN (:a,:b)",
        a=a["schedule_id"],
        b=b["schedule_id"],
    ),
    1,
)

race, _, _ = submit(meeting())
race = race.json()
p = detail(race)


def race_decide():
    with TestClient(app) as other:
        return other.post(
            "/api/v1/proposals/" + race["proposal_id"] + "/decisions",
            json=dict(
                expected_schedule_version=p["schedule_version"],
                expected_proposal_version=p["row_version"],
                decision="APPROVE",
            ),
            headers=headers["LEAD1"] | {"Idempotency-Key": str(uuid4())},
        )


def race_withdraw():
    with TestClient(app) as other:
        return other.post(
            "/api/v1/proposals/" + race["proposal_id"] + "/withdrawals",
            json=dict(
                expected_schedule_version=p["schedule_version"],
                expected_proposal_version=p["row_version"],
            ),
            headers=headers["EMP1"] | {"Idempotency-Key": str(uuid4())},
        )


races = parallel([race_decide, race_withdraw])
check(
    "Duyệt và rút cạnh tranh chỉ một thành công",
    sorted(r.status_code for r in races),
    [200, 409],
)
check(
    "Kết quả duyệt/rút nhất quán với hiệu lực",
    scalar(
        "SELECT COUNT(*) FROM v_effective_schedules WHERE schedule_id=:s",
        s=race["schedule_id"],
    ),
    1 if detail(race)["status"] == "APPROVED" else 0,
)
check(
    "OpenAPI giữ đủ API gửi/duyệt mốc C",
    all(p in app.openapi()["paths"] for p in ["/api/v1/meeting-proposals","/api/v1/work-proposals","/api/v1/proposals/{proposal_id}/decisions","/api/v1/proposals/{proposal_id}/withdrawals"]),
    True,
)
output = dict(
    passed=len(results),
    total=len(results),
    tests=results,
    mysql_version=scalar("SELECT VERSION()"),
    scope="Real MySQL + FastAPI ASGI, CREATE submit/approve/reject/withdraw; concurrent transactions, no SMTP/browser/Docker Windows/LAN",
)
result_dir = Path(os.getenv("TEST_RESULT_DIR", str(root / "verification")))
result_dir.mkdir(parents=True, exist_ok=True)
(result_dir / "scheduling-result.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2)
)
print(json.dumps(dict(passed=len(results), total=len(results))), flush=True)
engine.dispose()
