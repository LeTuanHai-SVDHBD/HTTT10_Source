"""Shared real-MySQL fixtures for notification/report integration suites."""

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
db_name = "httt10_" + os.environ["TEST_SUITE"] + "_" + uuid4().hex[:10] + "_test"
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


def finish_suite(name, scope):
    result_dir = Path(os.getenv("TEST_RESULT_DIR", str(root / "verification")))
    result_dir.mkdir(parents=True, exist_ok=True)
    result_dir.joinpath(name + "-result.json").write_text(
        json.dumps(
            dict(
                passed=len(results),
                total=len(results),
                tests=results,
                mysql_version=scalar("SELECT VERSION()"),
                scope=scope,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    print(json.dumps(dict(passed=len(results), total=len(results))), flush=True)
    engine.dispose()
