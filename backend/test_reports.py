"""DP-09 permission filtering, weighted historical usage and snapshot reads."""

import os

os.environ["TEST_SUITE"] = "reports"
from integration_support import *
from app import catalog as catalog, reports
from math import isclose

room1 = "20000000-0000-0000-0000-000000000001"
room2 = "20000000-0000-0000-0000-000000000002"
start = "2026-01-19T00:00:00+07:00"
end = "2026-01-20T00:00:00+07:00"


def report(who="ADMIN", rooms=None, start=start, end=end, code=200):
    params = {"from": start, "to": end}
    if rooms is not None:
        params["room_ids"] = rooms
    r = client.get("/api/v1/reports/room-usage", headers=headers[who], params=params)
    assert r.status_code == code, (r.status_code, r.text)
    return r.json()


def booking(room, begin, duration=1, cancelled=False, pending=False, parent=None):
    with Session.begin() as db:
        sid = parent or str(uuid4())
        rid = str(uuid4())
        if not parent:
            db.execute(
                text(
                    "INSERT INTO schedule_roots(id,kind,created_by) VALUES(:s,'MEETING',:u)"
                ),
                dict(s=sid, u=users["EMP1"]),
            )
        number = db.scalar(
            text(
                "SELECT COALESCE(MAX(revision_no),0)+1 FROM schedule_revisions WHERE schedule_id=:s"
            ),
            dict(s=sid),
        )
        db.execute(
            text(
                """INSERT INTO schedule_revisions(id,schedule_id,kind,revision_no,title,description,starts_at,ends_at,room_id,chair_user_id,created_by)
            VALUES(:r,:s,'MEETING',:n,'SECRET_REPORT_TITLE','SECRET_REPORT_BODY',:a,:b,:room,:u,:u)"""
            ),
            dict(
                r=rid,
                s=sid,
                n=number,
                a=begin,
                b=begin + timedelta(hours=duration),
                room=room,
                u=users["EMP1"],
            ),
        )
        if not pending:
            db.execute(
                text("UPDATE schedule_roots SET current_revision_id=:r WHERE id=:s"),
                dict(r=rid, s=sid),
            )
        if cancelled:
            db.execute(
                text(
                    "UPDATE schedule_roots SET cancelled_at=:now,cancelled_by=:u,cancel_reason='Secret reason' WHERE id=:s"
                ),
                dict(now=security.now(), u=users["EMP1"], s=sid),
            )
        return sid


check(
    "Không phiên không đọc báo cáo",
    client.get(
        "/api/v1/reports/room-usage", params={"from": start, "to": end}
    ).status_code,
    401,
)
check(
    "Nhân viên không có quyền báo cáo",
    report(who="EMP1", code=403)["error"]["code"],
    "FORBIDDEN",
)
check(
    "Người duyệt không được phân công có báo cáo rỗng", report(who="ROGUE")["rooms"], []
)
check(
    "Người duyệt chỉ thấy phòng được giao",
    [r["room_id"] for r in report(who="LEAD1")["rooms"]],
    [room1],
)
check("Admin tổng hợp được cả hai phòng", len(report()["rooms"]), 2)
check(
    "Bộ lọc gồm phòng ngoài quyền từ chối cả yêu cầu",
    report(who="LEAD1", rooms=[room1, room2], code=403)["error"]["code"],
    "FORBIDDEN",
)
check(
    "Phòng không tồn tại không suy ra dữ liệu",
    report(rooms=[str(uuid4())], code=403)["error"]["code"],
    "FORBIDDEN",
)
for label, a, b in [
    ("Khoảng ngược", end, start),
    ("Bằng nhau", start, start),
    ("Thiếu offset", "2026-01-19T00:00:00", end),
    ("Quá 366 ngày", start, "2028-01-20T00:00:00+07:00"),
]:
    check(
        label,
        report(start=a, end=b, code=422)["error"]["code"]
        in ("INVALID_TIME_RANGE", "VALIDATION_ERROR"),
    )
check("Lặp phòng chỉ tính một lần", len(report(rooms=[room1, room1])["rooms"]), 1)
check(
    "Báo cáo rỗng vẫn tính giờ phục vụ",
    report(rooms=[room1])["total"]["service_hours"],
    8,
)
check("Chưa có đặt phòng cho tỷ lệ 0", report()["total"]["planned_rate_percent"], 0)
with Session.begin() as db:
    db.execute(
        text(
            "DELETE FROM room_weekly_windows WHERE policy_id='30000000-0000-0000-0000-000000000002' AND start_time='13:00:00'"
        )
    )
a = booking(room1, datetime(2026, 1, 19, 1), 2)
booking(room1, datetime(2026, 1, 19, 4), cancelled=True)
booking(room1, datetime(2026, 1, 19, 7), pending=True)
b = booking(room1, datetime(2026, 1, 19, 8))
booking(room1, datetime(2026, 1, 19, 6), parent=b)
booking(room2, datetime(2026, 1, 19, 1))
r = report()
total = r["total"]
first = next(x for x in r["rooms"] if x["room_id"] == room1)
check("Đếm chỉ current, không đếm bản cũ và pending", total["confirmed_count"], 3)
check("Số lượt hủy tách riêng", total["cancelled_count"], 1)
check("Giờ họp loại hủy và bản cũ", total["meeting_hours"], 4)
check("Giờ chuyển tiếp tách riêng", total["buffer_hours"], 0.75)
check("Tổng giờ phục vụ theo từng phòng", total["service_hours"], 12)
check("Tỷ lệ tổng dùng trọng số", isclose(total["planned_rate_percent"], 100 / 3))
check("Tỷ lệ từng phòng", first["planned_rate_percent"], 37.5)
check(
    "Không trả lịch/nội dung/người/tệp riêng",
    not any(
        word in json.dumps(r)
        for word in [
            "SECRET_REPORT",
            "schedule_id",
            "description",
            "participant",
            "document",
            "cancel_reason",
            "employee_code",
        ]
    ),
)
check("Nhãn là kế hoạch", r["basis"], "PLANNED_BOOKINGS")
cut = report(
    rooms=[room1], start="2026-01-19T09:00:00+07:00", end="2026-01-19T11:00:00+07:00"
)["total"]
check("Cắt giờ họp theo kỳ", cut["meeting_hours"], 1)
check("Không đếm hủy bắt đầu đúng mốc cuối", cut["cancelled_count"], 0)
check("Cắt giờ phục vụ theo kỳ", cut["service_hours"], 2)
only_buffer = report(
    rooms=[room1], start="2026-01-19T10:05:00+07:00", end="2026-01-19T10:10:00+07:00"
)["total"]
check("Kỳ chỉ có đệm không tính thêm lượt họp", only_buffer["confirmed_count"], 0)
check("Cắt đệm vào kỳ", isclose(only_buffer["buffer_hours"], 5 / 60))
check("Đệm không vào tử số", only_buffer["planned_rate_percent"], 0)
check(
    "Offset tương đương cho cùng kết quả",
    report(start="2026-01-18T17:00:00Z", end="2026-01-19T17:00:00Z")["total"],
    total,
)
# Historical config effective at 10:00 local; service denominator splits at that instant.
policy = str(uuid4())
with Session.begin() as db:
    db.execute(
        text(
            "INSERT INTO room_policy_versions(id,room_id,effective_from,capacity,buffer_minutes) VALUES(:p,:room,:at,20,60)"
        ),
        dict(p=policy, room=room1, at=datetime(2026, 1, 19, 3)),
    )
    for weekday in range(1, 6):
        db.execute(
            text(
                "INSERT INTO room_weekly_windows(id,policy_id,weekday,start_time,end_time) VALUES(:id,:p,:day,'08:00:00','11:00:00')"
            ),
            dict(id=str(uuid4()), p=policy, day=weekday),
        )
historical = report(rooms=[room1])["total"]
check(
    "Giờ phục vụ dùng lịch sử cấu hình, chia giữa ngày", historical["service_hours"], 3
)
check("Giờ đặt vẫn báo riêng phần ngoài giờ phục vụ", historical["meeting_hours"], 3)
check(
    "Tử số chỉ lấy phần trong giờ phục vụ",
    isclose(historical["planned_rate_percent"], 200 / 3),
)
check("Đệm lấy cấu hình tại giờ bắt đầu từng họp", historical["buffer_hours"], 1.25)
with Session.begin() as db:
    db.execute(
        text("UPDATE meeting_rooms SET accepts_new_requests=0 WHERE id=:r"),
        dict(r=room1),
    )
check(
    "Ngừng nhận mới không xóa mẫu số lịch sử",
    report(rooms=[room1])["total"],
    historical,
)
with Session.begin() as db:
    db.execute(
        text(
            "INSERT INTO room_calendar_days(id,policy_id,local_date,is_closed,reason) VALUES(:id,:p,'2026-01-20',1,'Nghỉ')"
        ),
        dict(id=str(uuid4()), p=policy),
    )
    day = str(uuid4())
    db.execute(
        text(
            "INSERT INTO room_calendar_days(id,policy_id,local_date,is_closed,reason) VALUES(:id,:p,'2026-01-21',0,'Lịch riêng')"
        ),
        dict(id=day, p=policy),
    )
    db.execute(
        text(
            "INSERT INTO room_calendar_windows(id,calendar_day_id,start_time,end_time) VALUES(:id,:day,'12:00:00','14:00:00')"
        ),
        dict(id=str(uuid4()), day=day),
    )
booking(room1, datetime(2026, 1, 20, 1))
zero = report(
    rooms=[room1], start="2026-01-20T00:00:00+07:00", end="2026-01-21T00:00:00+07:00"
)["total"]
check("Ngày đóng không có giờ phục vụ", zero["service_hours"], 0)
check("Mẫu số 0 trả null", zero["planned_rate_percent"], None)
booking(room1, datetime(2026, 1, 21, 5, 30))
special = report(
    rooms=[room1], start="2026-01-21T00:00:00+07:00", end="2026-01-22T00:00:00+07:00"
)["total"]
check("Ngày ngoại lệ thay giờ tuần", special["service_hours"], 2)
check("Họp trong giờ ngoại lệ tính tỷ lệ đúng", special["planned_rate_percent"], 50)
# Concurrent commit after snapshot begins cannot mix numerator and denominator.
original = catalog.policies
changed = False


def concurrent_change(db, rid):
    global changed
    value = original(db, rid)
    if not changed:
        changed = True
        with Session.begin() as other:
            other.execute(
                text(
                    "UPDATE schedule_roots SET cancelled_at=:at,cancelled_by=:u,cancel_reason='Test concurrent' WHERE id=:id"
                ),
                dict(at=security.now(), u=users["EMP1"], id=a),
            )
    return value


with patch("app.reports.c.policies", side_effect=concurrent_change):
    check(
        "Snapshot không trộn bản ghi vừa commit",
        report(rooms=[room1])["total"]["confirmed_count"],
        2,
    )
check(
    "Lần báo cáo sau thấy cập nhật mới",
    report(rooms=[room1])["total"]["confirmed_count"],
    1,
)
with Session.begin() as db:
    db.execute(
        text("UPDATE room_approvers SET is_active=0 WHERE user_id=:u"),
        dict(u=users["LEAD1"]),
    )
check("Thu hồi phạm vi có hiệu lực ngay", report(who="LEAD1")["rooms"], [])
check(
    "OpenAPI hoàn thành 50 thao tác",
    sum(len(x) for x in app.openapi()["paths"].values()),
    50,
)
finish_suite(
    "reports",
    "Real MySQL + ASGI; scoped aggregates, half-open clipping, historical service windows, weighted rates, read-only consistent snapshot. Not Windows/Docker/LAN.",
)
