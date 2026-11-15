"""Aggregate planned room usage in one read-only consistent snapshot (DP-09)."""

from datetime import datetime, time, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from . import catalog as c, schemas as s, scheduling, security
from .db import Session, engine
from .dependencies import identity
from .services import Failure

router = APIRouter(prefix="/api/v1", tags=["reports"])


def overlap(a, b, start, end):
    return max(0.0, (min(b, end) - max(a, start)).total_seconds())


def union(intervals):
    merged = []
    for start, end in sorted(intervals):
        if start >= end:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def service_intervals(timeline, start, end):
    result = []
    day = c.aware(start).astimezone(c.LOCAL_ZONE).date()
    last = c.aware(end).astimezone(c.LOCAL_ZONE).date()
    while day <= last:
        midnight = datetime.combine(day, time(), c.LOCAL_ZONE)
        for index, policy in enumerate(timeline):
            effective = c.utc(policy["effective_from"])
            until = (
                c.utc(timeline[index + 1]["effective_from"])
                if index + 1 < len(timeline)
                else end
            )
            left, right = max(start, effective), min(end, until)
            if left >= right:
                continue
            exception = next(
                (d for d in policy["calendar_days"] if d["local_date"] == str(day)),
                None,
            )
            windows = (
                ([] if exception["is_closed"] else exception["windows"])
                if exception
                else [
                    w
                    for w in policy["weekly_windows"]
                    if w["weekday"] == day.isoweekday()
                ]
            )
            for window in windows:

                def boundary(value):
                    hour, minute = map(int, value.split(":"))
                    return c.utc(midnight + timedelta(hours=hour, minutes=minute))

                a, b = max(left, boundary(window["start_time"])), min(
                    right, boundary(window["end_time"])
                )
                if a < b:
                    result.append((a, b))
        day += timedelta(days=1)
    return union(result)


def metrics(confirmed, cancelled, meeting, buffer, service, numerator):
    return dict(
        confirmed_count=confirmed,
        cancelled_count=cancelled,
        meeting_hours=meeting / 3600,
        buffer_hours=buffer / 3600,
        service_hours=service / 3600,
        planned_rate_percent=min(100, numerator / service * 100) if service else None,
    )


def usage(ctx, start, end, room_ids):
    c.require_member(ctx)
    c.validate_range(start, end, 366)
    start, end = c.utc(start), c.utc(end)
    # No locks/network work in a report. Permission filtering belongs to this snapshot too.
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
        with conn.begin():
            conn.exec_driver_sql(
                "START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY"
            )
            with Session(bind=conn) as db:
                actor = scheduling.fresh_actor(db, ctx)
                if not set(actor["roles"]) & {"ADMIN", "APPROVER"}:
                    raise Failure(
                        403,
                        "FORBIDDEN",
                        "Chỉ Admin hoặc người phụ trách phòng được xem báo cáo.",
                    )
                rooms = c.rows(db, "SELECT id FROM meeting_rooms ORDER BY code,id")
                permitted = (
                    {r["id"] for r in rooms}
                    if "ADMIN" in actor["roles"]
                    else {
                        r["room_id"]
                        for r in c.rows(
                            db,
                            "SELECT room_id FROM room_approvers WHERE user_id=:u AND is_active=1",
                            u=actor["id"],
                        )
                    }
                )
                selected = {str(r) for r in room_ids} if room_ids else permitted
                if not selected <= permitted:
                    raise Failure(
                        403,
                        "FORBIDDEN",
                        "Chỉ chọn phòng trong phạm vi báo cáo được giao.",
                    )
                report = []
                totals = [0, 0, 0.0, 0.0, 0.0, 0.0]
                for room in rooms:
                    if room["id"] not in selected:
                        continue
                    timeline = c.policies(db, room["id"])
                    windows = service_intervals(timeline, start, end)
                    service = sum((b - a).total_seconds() for a, b in windows)
                    confirmed = cancelled = 0
                    meeting = buffer = 0.0
                    booked = []
                    for row in c.rows(
                        db,
                        """SELECT v.starts_at,v.ends_at,r.cancelled_at FROM schedule_roots r
                        JOIN schedule_revisions v ON v.schedule_id=r.id AND v.id=r.current_revision_id
                        WHERE r.kind='MEETING' AND v.room_id=:room AND v.starts_at<:end AND v.ends_at>:earliest""",
                        room=room["id"],
                        end=end,
                        earliest=start
                        - timedelta(
                            minutes=max(
                                (p["buffer_minutes"] for p in timeline), default=0
                            )
                        ),
                    ):
                        duration = overlap(row["starts_at"], row["ends_at"], start, end)
                        if row["cancelled_at"]:
                            cancelled += int(duration > 0)
                            continue
                        confirmed += int(duration > 0)
                        meeting += duration
                        policy = c.at_time(timeline, row["starts_at"])
                        blocked = row["ends_at"] + timedelta(
                            minutes=policy["buffer_minutes"] if policy else 0
                        )
                        buffer += overlap(row["ends_at"], blocked, start, end)
                        if duration:
                            booked.append(
                                (max(start, row["starts_at"]), min(end, row["ends_at"]))
                            )
                    numerator = sum(
                        overlap(a, b, x, y)
                        for a, b in union(booked)
                        for x, y in windows
                    )
                    values = [confirmed, cancelled, meeting, buffer, service, numerator]
                    totals = [a + b for a, b in zip(totals, values)]
                    report.append(dict(room_id=room["id"], **metrics(*values)))
                return dict(
                    period_from=c.aware(start),
                    period_to=c.aware(end),
                    generated_at=c.aware(security.now()),
                    basis="PLANNED_BOOKINGS",
                    rooms=report,
                    total=metrics(*totals),
                )


@router.get("/reports/room-usage", response_model=s.UsageReport)
def room_usage(
    period_from: Annotated[s.UtcDatetime, Query(alias="from")],
    period_to: Annotated[s.UtcDatetime, Query(alias="to")],
    room_ids: Annotated[list[UUID], Query(max_length=1000)] = [],
    ctx=Depends(identity),
):
    return usage(ctx, period_from, period_to, room_ids)
