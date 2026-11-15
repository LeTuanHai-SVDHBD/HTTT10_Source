"""Milestone C: CREATE proposals, resource locking, receipts and safe reads.

Commands share the baseline schema and READ COMMITTED transaction. Explicit
lock order is idempotency -> root -> proposal -> room -> department -> users
sorted by ID. Foreign-key lock upgrades can still deadlock; whole transactions
are retried finitely. No SMTP or network request runs inside a transaction.
"""

import hashlib
import json
import random
import time
from datetime import timedelta

import jwt
from sqlalchemy.exc import OperationalError

from . import catalog as c, schemas as s, security as sec
from .db import Session
from .services import Failure


def fail(status, code, message, **details):
    raise Failure(status, code, message, **details)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def candidate_json(candidate):
    data = candidate.model_dump(mode="json")
    if candidate.kind == "MEETING":
        data["participants"].sort(key=lambda p: p["user_id"])
    else:
        data["participant_user_ids"].sort()
    return data


def participant_pairs(candidate):
    if candidate.kind == "MEETING":
        return [(str(p.user_id), p.is_required) for p in candidate.participants]
    return [(str(u), True) for u in candidate.participant_user_ids]


def fresh_actor(db, ctx):
    claims = ctx[1]
    user = c.one(db, "SELECT * FROM users WHERE id=:id", id=claims["sub"])
    sessions = c.rows(
        db,
        """SELECT id FROM auth_sessions WHERE id=:sid AND user_id=:u
        AND auth_version=:av AND revoked_at IS NULL AND expires_at>:now""",
        sid=claims["sid"],
        u=user["id"],
        av=claims["av"],
        now=sec.now(),
    )
    if (
        user["status"] != "ACTIVE"
        or user["auth_version"] != claims["av"]
        or not sessions
    ):
        fail(401, "SESSION_INVALID", "Phiên đăng nhập không còn hợp lệ.")
    if user["must_change_password"]:
        fail(403, "PASSWORD_CHANGE_REQUIRED", "Vui lòng đổi mật khẩu tạm.")
    user["roles"] = [
        r["role"]
        for r in c.rows(
            db, "SELECT role FROM user_roles WHERE user_id=:u", u=user["id"]
        )
    ]
    return user


def lock_resources(db, candidate, user_ids):
    if candidate.kind == "MEETING":
        c.one(
            db,
            "SELECT id FROM meeting_rooms WHERE id=:id FOR UPDATE",
            id=str(candidate.room_id),
        )
    else:
        c.one(
            db,
            "SELECT id FROM departments WHERE id=:id FOR UPDATE",
            id=str(candidate.department_id),
        )
    for user_id in sorted(set(user_ids) | {u for u, _ in participant_pairs(candidate)}):
        c.one(db, "SELECT id FROM users WHERE id=:id FOR UPDATE", id=user_id)


def approvers(db, candidate, submitter):
    table, column, resource = (
        ("room_approvers", "room_id", str(candidate.room_id))
        if candidate.kind == "MEETING"
        else ("department_approvers", "department_id", str(candidate.department_id))
    )
    return [
        r["id"]
        for r in c.rows(
            db,
            f"""SELECT u.id FROM {table} a JOIN users u ON u.id=a.user_id
        JOIN user_roles r ON r.user_id=u.id AND r.role='APPROVER'
        WHERE a.{column}=:resource AND a.is_active=1 AND u.status='ACTIVE' AND u.id<>:submitter ORDER BY u.id""",
            resource=resource,
            submitter=submitter,
        )
    ]


def require_review(db, actor, candidate, submitter):
    if actor["id"] == submitter:
        fail(
            403,
            "SELF_REVIEW_FORBIDDEN",
            "Bạn không được tự duyệt hoặc từ chối yêu cầu của mình.",
        )
    if "APPROVER" not in actor["roles"] or actor["id"] not in approvers(
        db, candidate, submitter
    ):
        fail(403, "FORBIDDEN", "Bạn không được phân công duyệt yêu cầu này.")


def warning_token(actor, candidate, excluded, fingerprint):
    payload_hash = digest(dict(candidate=candidate_json(candidate), excluded=excluded))
    return jwt.encode(
        dict(
            purpose="warning-ack",
            sub=actor,
            ph=payload_hash,
            wh=fingerprint,
            exp=int(c.aware(sec.now()).timestamp()) + 300,
        ),
        sec.SECRET,
        algorithm="HS256",
    )


def valid_warning_token(token, actor, candidate, excluded, fingerprint):
    try:
        value = jwt.decode(
            token or "",
            sec.SECRET,
            algorithms=["HS256"],
            options={"require": ["purpose", "sub", "ph", "wh", "exp"]},
        )
        return (
            value["purpose"] == "warning-ack"
            and value["sub"] == actor
            and value["ph"]
            == digest(dict(candidate=candidate_json(candidate), excluded=excluded))
            and value["wh"] == fingerprint
        )
    except jwt.PyJWTError:
        return False


def availability(
    db, actor, candidate, *, submitter=None, excluded=None, submitting=True
):
    now = sec.now()
    start, end = c.utc(candidate.starts_at), c.utc(candidate.ends_at)
    submitter = submitter or actor["id"]
    if start <= now:
        fail(422, "SCHEDULE_TIME_INVALID", "Thời điểm bắt đầu phải ở tương lai.")
    people = participant_pairs(candidate)
    for person, _ in people:
        user = c.one(
            db, "SELECT status,department_id FROM users WHERE id=:id", id=person
        )
        if user["status"] != "ACTIVE":
            fail(
                422,
                "PARTICIPANT_INACTIVE",
                "Có người tham gia đã bị khóa. Vui lòng cập nhật thành phần.",
            )
        if candidate.kind == "WORK" and user["department_id"] != str(
            candidate.department_id
        ):
            fail(
                422,
                "WORK_DEPARTMENT_MISMATCH",
                "Mọi người đi công tác phải cùng phòng ban của yêu cầu.",
            )
    conflicts, warnings, fingerprints = [], [], []
    buffer = 0
    if candidate.kind == "MEETING":
        if not timedelta(minutes=15) <= end - start <= timedelta(hours=4):
            fail(
                422, "MEETING_TIME_INVALID", "Thời lượng họp phải từ 15 phút đến 4 giờ."
            )
        if submitting and (
            start < now + timedelta(minutes=30) or start > now + timedelta(days=90)
        ):
            fail(
                422,
                "MEETING_TIME_INVALID",
                "Gửi trước ít nhất 30 phút và trong 90 ngày tới.",
            )
        room = c.one(
            db, "SELECT * FROM meeting_rooms WHERE id=:id", id=str(candidate.room_id)
        )
        if not room["accepts_new_requests"]:
            fail(422, "ROOM_NOT_ACCEPTING_REQUESTS", "Phòng đã ngừng nhận yêu cầu mới.")
        policy = c.at_time(c.policies(db, room["id"]), start)
        if (
            not policy
            or policy["capacity"] < len(people)
            or not c.in_service(policy, start, end)
        ):
            conflicts.append(
                dict(
                    code="ROOM_CONFIG_INVALID",
                    resource_type="ROOM",
                    resource_id=room["id"],
                    starts_at=None,
                    ends_at=None,
                    message="Phòng không đủ sức chứa hoặc ngoài giờ phục vụ.",
                )
            )
        if policy:
            buffer = policy["buffer_minutes"]
            for r in c.rows(
                db,
                """SELECT * FROM v_effective_meetings WHERE room_id=:room
                AND starts_at<:blocked AND blocked_until>:start AND (:excluded IS NULL OR schedule_id<>:excluded)
                ORDER BY starts_at,schedule_id""",
                room=room["id"],
                start=start,
                blocked=end + timedelta(minutes=buffer),
                excluded=excluded,
            ):
                conflicts.append(
                    dict(
                        code="ROOM_BUSY",
                        resource_type="ROOM",
                        resource_id=room["id"],
                        starts_at=c.aware(r["starts_at"]),
                        ends_at=c.aware(r["blocked_until"]),
                        message="Phòng đã được giữ trong khoảng thời gian này, gồm thời gian chuyển tiếp.",
                    )
                )
        pending_room = c.rows(
            db,
            """SELECT a.id,a.row_version,v.id AS revision_id FROM approval_proposals a JOIN schedule_revisions v ON v.id=a.candidate_revision_id
            WHERE a.status='PENDING' AND a.expires_at>:now AND v.room_id=:room
            AND v.starts_at<:blocked AND TIMESTAMPADD(MINUTE,COALESCE((SELECT p.buffer_minutes FROM room_policy_versions p
                WHERE p.room_id=v.room_id AND p.effective_from<=v.starts_at ORDER BY p.effective_from DESC LIMIT 1),:buffer),v.ends_at)>:start
            AND (:excluded IS NULL OR a.schedule_id<>:excluded) ORDER BY a.id""",
            now=now,
            room=room["id"],
            blocked=end + timedelta(minutes=buffer),
            buffer=buffer,
            start=start,
            excluded=excluded,
        )
        if pending_room:
            warnings.append(
                dict(
                    code="PENDING_ROOM_REQUEST",
                    resource_type="ROOM",
                    resource_id=room["id"],
                    starts_at=None,
                    ends_at=None,
                    message="Phòng có yêu cầu khác đang chờ duyệt trong khoảng này; chưa có yêu cầu nào được giữ chỗ.",
                )
            )
            fingerprints.append(("pending_room", pending_room))
    else:
        department = c.one(
            db,
            "SELECT * FROM departments WHERE id=:id",
            id=str(candidate.department_id),
        )
        if not department["accepts_new_requests"]:
            fail(422, "DEPARTMENT_INACTIVE", "Phòng ban đã ngừng nhận yêu cầu mới.")
        if submitting and actor["department_id"] != str(candidate.department_id):
            fail(
                403,
                "FORBIDDEN",
                "Bạn chỉ đăng ký công tác cho phòng ban hiện tại của mình.",
            )
    if not approvers(db, candidate, submitter):
        fail(
            422,
            "NO_ELIGIBLE_APPROVER",
            "Chưa có người duyệt phù hợp khác người gửi. Hãy nhờ Admin phân công người duyệt thay.",
        )
    for person, required in sorted(people):
        effective = c.rows(
            db,
            """SELECT * FROM v_effective_participants WHERE user_id=:person
            AND starts_at<:end AND ends_at>:start AND (:excluded IS NULL OR schedule_id<>:excluded)
            ORDER BY starts_at,revision_id""",
            person=person,
            start=start,
            end=end,
            excluded=excluded,
        )
        hard = [r for r in effective if required and r["is_required"]]
        soft = [r for r in effective if not (required and r["is_required"])]
        if hard:
            conflicts.append(
                dict(
                    code="REQUIRED_PERSON_BUSY",
                    resource_type="PERSON",
                    resource_id=person,
                    starts_at=None,
                    ends_at=None,
                    message="Người tham gia bắt buộc đã có lịch bắt buộc trùng giờ.",
                )
            )
        if soft:
            warnings.append(
                dict(
                    code="OPTIONAL_PARTICIPANT_BUSY",
                    resource_type="PERSON",
                    resource_id=person,
                    starts_at=None,
                    ends_at=None,
                    message="Có lịch trùng giờ với người tham gia tùy chọn; cần xác nhận trước khi tiếp tục.",
                )
            )
            fingerprints.append(
                (
                    "optional",
                    person,
                    [(r["revision_id"], r["is_required"]) for r in soft],
                )
            )
        pending = c.rows(
            db,
            """SELECT a.id,a.row_version FROM approval_proposals a
            JOIN revision_participants p ON p.revision_id=a.candidate_revision_id JOIN schedule_revisions v ON v.id=p.revision_id
            WHERE a.status='PENDING' AND a.expires_at>:now AND p.user_id=:person AND v.starts_at<:end AND v.ends_at>:start
            AND (:excluded IS NULL OR a.schedule_id<>:excluded) ORDER BY a.id""",
            now=now,
            person=person,
            start=start,
            end=end,
            excluded=excluded,
        )
        if pending:
            warnings.append(
                dict(
                    code="PENDING_PERSON_REQUEST",
                    resource_type="PERSON",
                    resource_id=person,
                    starts_at=None,
                    ends_at=None,
                    message="Người tham gia có yêu cầu khác đang chờ duyệt trong khoảng này.",
                )
            )
            fingerprints.append(("pending_person", person, pending))
    fingerprint = digest(fingerprints)
    token = (
        warning_token(actor["id"], candidate, excluded, fingerprint)
        if warnings
        else None
    )
    return (
        dict(
            checked_at=c.aware(now),
            holds_resources=False,
            bookable=not conflicts,
            conflicts=conflicts,
            warnings=warnings,
            warning_acknowledgement_token=token,
        ),
        fingerprint,
    )


def check_result(result, fingerprint, actor, candidate, excluded, token):
    if result["conflicts"]:
        fail(
            409,
            result["conflicts"][0]["code"],
            "Phương án đang có xung đột. Vui lòng chọn lại thời gian hoặc thành phần.",
            conflicts=result["conflicts"],
        )
    if result["warnings"] and not valid_warning_token(
        token, actor["id"], candidate, excluded, fingerprint
    ):
        fail(
            409,
            "WARNINGS_REQUIRE_ACK",
            "Hãy xem và xác nhận các cảnh báo hiện tại trước khi tiếp tục.",
            warnings=result["warnings"],
            warning_acknowledgement_token=result["warning_acknowledgement_token"],
        )


def preflight(ctx, data):
    c.require_member(ctx)
    with Session() as db:
        actor = fresh_actor(db, ctx)
        if "EMPLOYEE" not in actor["roles"]:
            fail(403, "FORBIDDEN", "Cần quyền Nhân viên để đăng ký lịch.")
        excluded = str(data.exclude_schedule_id) if data.exclude_schedule_id else None
        if excluded:
            root = c.one(
                db, "SELECT created_by FROM schedule_roots WHERE id=:id", id=excluded
            )
            if root["created_by"] != actor["id"]:
                fail(403, "FORBIDDEN", "Chỉ loại trừ lịch do chính bạn tạo.")
        return availability(db, actor, data.candidate, excluded=excluded)[0]


def claim_key(db, actor_id, operation, target, data, key):
    request_hash = digest(dict(target=target, payload=data.model_dump(mode="json")))
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    c.run(
        db,
        """INSERT INTO idempotency_keys(user_id,operation,key_hash,request_hash,response_status,expires_at)
        VALUES(:u,:op,:key,:request,0,:expires) ON DUPLICATE KEY UPDATE key_hash=key_hash""",
        u=actor_id,
        op=operation,
        key=key_hash,
        request=request_hash,
        expires=sec.now() + timedelta(hours=24),
    )
    row = c.one(
        db,
        "SELECT * FROM idempotency_keys WHERE user_id=:u AND operation=:op AND key_hash=:key FOR UPDATE",
        u=actor_id,
        op=operation,
        key=key_hash,
    )
    if row["response_status"] and row["expires_at"] <= sec.now():
        fail(
            409,
            "IDEMPOTENCY_KEY_EXPIRED",
            "Khóa thao tác đã hết hạn. Hãy đọc lại yêu cầu trước khi tạo thao tác mới.",
        )
    if row["response_status"] and row["request_hash"] != request_hash:
        fail(
            409,
            "IDEMPOTENCY_KEY_REUSED",
            "Khóa thao tác đã được dùng cho dữ liệu hoặc yêu cầu khác.",
        )
    return row


def receipt(row):
    return dict(
        committed=True,
        schedule_id=row["result_schedule_id"],
        proposal_id=row["result_proposal_id"],
    )


def finish_key(db, key, schedule_id, proposal_id, status):
    c.run(
        db,
        """UPDATE idempotency_keys SET result_schedule_id=:s,result_proposal_id=:p,response_status=:status
        WHERE user_id=:u AND operation=:op AND key_hash=:key""",
        s=schedule_id,
        p=proposal_id,
        status=status,
        u=key["user_id"],
        op=key["operation"],
        key=key["key_hash"],
    )
    return dict(committed=True, schedule_id=schedule_id, proposal_id=proposal_id)


def schedule_audit(db, actor, action, schedule_id, revision_id):
    c.run(
        db,
        """INSERT INTO audit_entries(id,actor_user_id,action,entity_type,entity_id,schedule_id,revision_id,safe_metadata)
        VALUES(:id,:actor,:action,'schedule',:s,:s,:r,JSON_OBJECT())""",
        id=c.uid(),
        actor=actor,
        action=action,
        s=schedule_id,
        r=revision_id,
    )


def notify(db, action, root, proposal, candidate, actor=None):
    event_id = c.uid()
    c.run(
        db,
        """INSERT INTO outbox_events(id,schedule_id,proposal_id,event_type,dedupe_key,payload)
        VALUES(:id,:s,:p,:action,:dedupe,CAST(:payload AS JSON))""",
        id=event_id,
        s=root["id"],
        p=proposal["id"],
        action=action,
        dedupe=proposal["id"] + ":" + action,
        payload=json.dumps(dict(revision_id=proposal["candidate_revision_id"])),
    )
    recipients = (
        {root["created_by"]}
        | {u for u, _ in participant_pairs(candidate)}
        | set(approvers(db, candidate, root["created_by"]))
    )
    for user_id in sorted(recipients):
        if (
            c.one(db, "SELECT status FROM users WHERE id=:id", id=user_id)["status"]
            == "ACTIVE"
        ):
            c.run(
                db,
                "INSERT INTO email_deliveries(id,event_id,recipient_user_id,next_attempt_at) VALUES(:id,:event,:u,:now)",
                id=c.uid(),
                event=event_id,
                u=user_id,
                now=sec.now(),
            )
    schedule_audit(db, actor, action, root["id"], proposal["candidate_revision_id"])


def candidate_from_revision(db, revision_id):
    r = c.one(db, "SELECT * FROM schedule_revisions WHERE id=:id", id=revision_id)
    values = dict(
        kind=r["kind"],
        title=r["title"],
        description=r["description"],
        starts_at=c.aware(r["starts_at"]),
        ends_at=c.aware(r["ends_at"]),
    )
    people = c.rows(
        db,
        "SELECT user_id,is_required FROM revision_participants WHERE revision_id=:id ORDER BY user_id",
        id=revision_id,
    )
    if r["kind"] == "MEETING":
        return s.MeetingInput(
            **values,
            room_id=r["room_id"],
            chair_user_id=r["chair_user_id"],
            participants=people,
        )
    return s.WorkInput(
        **values,
        department_id=r["department_id"],
        work_location=r["work_location"],
        work_context=r["work_context"],
        participant_user_ids=[p["user_id"] for p in people],
    )


def insert_create(db, actor, candidate):
    schedule_id, revision_id, proposal_id = c.uid(), c.uid(), c.uid()
    c.run(
        db,
        "INSERT INTO schedule_roots(id,kind,created_by) VALUES(:id,:kind,:u)",
        id=schedule_id,
        kind=candidate.kind,
        u=actor["id"],
    )
    c.run(
        db,
        """INSERT INTO schedule_revisions(id,schedule_id,kind,revision_no,title,description,starts_at,ends_at,room_id,chair_user_id,department_id,work_location,work_context,created_by)
        VALUES(:id,:s,:kind,1,:title,:description,:start,:end,:room,:chair,:dept,:location,:context,:u)""",
        id=revision_id,
        s=schedule_id,
        kind=candidate.kind,
        title=candidate.title,
        description=candidate.description,
        start=c.utc(candidate.starts_at),
        end=c.utc(candidate.ends_at),
        room=str(candidate.room_id) if candidate.kind == "MEETING" else None,
        chair=str(candidate.chair_user_id) if candidate.kind == "MEETING" else None,
        dept=str(candidate.department_id) if candidate.kind == "WORK" else None,
        location=candidate.work_location if candidate.kind == "WORK" else None,
        context=candidate.work_context if candidate.kind == "WORK" else None,
        u=actor["id"],
    )
    for person, required in participant_pairs(candidate):
        c.run(
            db,
            "INSERT INTO revision_participants(revision_id,user_id,is_required) VALUES(:r,:u,:required)",
            r=revision_id,
            u=person,
            required=required,
        )
    c.run(
        db,
        """INSERT INTO approval_proposals(id,schedule_id,kind,submitted_by,candidate_revision_id,expires_at)
        VALUES(:id,:s,'CREATE',:u,:r,:expires)""",
        id=proposal_id,
        s=schedule_id,
        u=actor["id"],
        r=revision_id,
        expires=c.utc(candidate.starts_at),
    )
    root = c.one(db, "SELECT * FROM schedule_roots WHERE id=:id", id=schedule_id)
    proposal = c.one(
        db, "SELECT * FROM approval_proposals WHERE id=:id", id=proposal_id
    )
    notify(db, "PROPOSAL_SUBMITTED", root, proposal, candidate, actor["id"])
    return root, proposal


def transaction_retry(action):
    for attempt in range(3):
        try:
            return action()
        except OperationalError as exc:
            if getattr(exc.orig, "args", [None])[0] not in (1205, 1213) or attempt == 2:
                raise
            time.sleep(random.uniform(0.015, 0.06) * (attempt + 1))


def submit(ctx, data, key, operation):
    c.require_member(ctx)

    def action():
        with Session.begin() as db:
            saved = claim_key(db, ctx[0]["id"], operation, operation, data, key)
            candidate = data.candidate
            # A replay does not create or revalidate a new schedule proposal.
            lock_resources(db, candidate, [ctx[0]["id"]])
            actor = fresh_actor(db, ctx)
            if "EMPLOYEE" not in actor["roles"]:
                fail(403, "FORBIDDEN", "Cần quyền Nhân viên để đăng ký lịch.")
            if saved["response_status"]:
                return receipt(saved), True
            result, fingerprint = availability(db, actor, candidate)
            check_result(
                result,
                fingerprint,
                actor,
                candidate,
                None,
                data.warning_acknowledgement_token,
            )
            root, proposal = insert_create(db, actor, candidate)
            return finish_key(db, saved, root["id"], proposal["id"], 201), False

    return transaction_retry(action)


def expire_one(db, root, proposal, candidate):
    c.run(
        db,
        "UPDATE approval_proposals SET status='EXPIRED',resolved_at=:now,reason=:reason,row_version=row_version+1 WHERE id=:id",
        now=sec.now(),
        reason="Đã đến giờ bắt đầu, yêu cầu hết hạn xử lý.",
        id=proposal["id"],
    )
    c.run(
        db,
        "UPDATE schedule_roots SET row_version=row_version+1 WHERE id=:id",
        id=root["id"],
    )
    notify(db, "PROPOSAL_EXPIRED", root, proposal, candidate)


def resolve(ctx, proposal_id, data, key, withdrawing=False):
    c.require_member(ctx)
    operation = "WITHDRAW_PROPOSAL" if withdrawing else "DECIDE_PROPOSAL"

    def action():
        expired = False
        with Session.begin() as db:
            saved = claim_key(db, ctx[0]["id"], operation, proposal_id, data, key)
            location = c.one(
                db,
                "SELECT schedule_id FROM approval_proposals WHERE id=:id",
                id=proposal_id,
            )
            root = c.one(
                db,
                "SELECT * FROM schedule_roots WHERE id=:id FOR UPDATE",
                id=location["schedule_id"],
            )
            proposal = c.one(
                db,
                "SELECT * FROM approval_proposals WHERE id=:id FOR UPDATE",
                id=proposal_id,
            )
            if proposal["kind"] != "CREATE":
                fail(
                    409,
                    "PROPOSAL_KIND_UNAVAILABLE",
                    "Loại đề nghị này chưa được triển khai ở mốc C.",
                )
            candidate = candidate_from_revision(db, proposal["candidate_revision_id"])
            lock_resources(db, candidate, [ctx[0]["id"], proposal["submitted_by"]])
            actor = fresh_actor(db, ctx)
            if withdrawing:
                if actor["id"] != proposal["submitted_by"]:
                    fail(403, "FORBIDDEN", "Chỉ người gửi được rút yêu cầu.")
            else:
                require_review(db, actor, candidate, proposal["submitted_by"])
            if saved["response_status"]:
                return receipt(saved), True
            if (
                root["row_version"] != data.expected_schedule_version
                or proposal["row_version"] != data.expected_proposal_version
            ):
                fail(
                    409,
                    "VERSION_CONFLICT",
                    "Hồ sơ đã thay đổi. Hãy tải lại trước khi xử lý.",
                )
            if proposal["status"] != "PENDING":
                fail(
                    409,
                    "PROPOSAL_ALREADY_RESOLVED",
                    "Yêu cầu đã được xử lý hoặc hết hiệu lực.",
                )
            if proposal["expires_at"] <= sec.now():
                expire_one(db, root, proposal, candidate)
                c.run(
                    db,
                    "DELETE FROM idempotency_keys WHERE user_id=:u AND operation=:op AND key_hash=:key",
                    u=saved["user_id"],
                    op=operation,
                    key=saved["key_hash"],
                )
                expired = True
            else:
                if root["current_revision_id"] or root["cancelled_at"]:
                    fail(
                        409,
                        "BASE_REVISION_CHANGED",
                        "Lịch không còn ở trạng thái chờ xác nhận ban đầu.",
                    )
                status = (
                    "WITHDRAWN"
                    if withdrawing
                    else ("APPROVED" if data.decision == "APPROVE" else "REJECTED")
                )
                if status == "APPROVED":
                    result, fingerprint = availability(
                        db,
                        actor,
                        candidate,
                        submitter=proposal["submitted_by"],
                        excluded=root["id"],
                        submitting=False,
                    )
                    check_result(
                        result,
                        fingerprint,
                        actor,
                        candidate,
                        root["id"],
                        data.warning_acknowledgement_token,
                    )
                    c.run(
                        db,
                        "UPDATE schedule_roots SET current_revision_id=:r WHERE id=:id",
                        r=proposal["candidate_revision_id"],
                        id=root["id"],
                    )
                c.run(
                    db,
                    "UPDATE schedule_roots SET row_version=row_version+1 WHERE id=:id",
                    id=root["id"],
                )
                c.run(
                    db,
                    """UPDATE approval_proposals SET status=:status,resolved_by=:u,resolved_at=:now,reason=:reason,row_version=row_version+1 WHERE id=:id""",
                    status=status,
                    u=actor["id"],
                    now=sec.now(),
                    reason=data.reason,
                    id=proposal_id,
                )
                notify(db, "PROPOSAL_" + status, root, proposal, candidate, actor["id"])
                return finish_key(db, saved, root["id"], proposal_id, 200), False
        if expired:
            fail(
                409,
                "PROPOSAL_EXPIRED",
                "Yêu cầu đã đến giờ bắt đầu và được ghi nhận hết hạn.",
                expiration_committed=True,
            )

    return transaction_retry(action)


def expire_due(limit=100):
    with Session() as db:
        due = c.rows(
            db,
            "SELECT id FROM approval_proposals WHERE status='PENDING' AND expires_at<=:now ORDER BY expires_at,id LIMIT :limit",
            now=sec.now(),
            limit=limit,
        )
    count = 0
    for row in due:

        def action():
            with Session.begin() as db:
                location = c.one(
                    db,
                    "SELECT schedule_id FROM approval_proposals WHERE id=:id",
                    id=row["id"],
                )
                root = c.one(
                    db,
                    "SELECT * FROM schedule_roots WHERE id=:id FOR UPDATE",
                    id=location["schedule_id"],
                )
                proposal = c.one(
                    db,
                    "SELECT * FROM approval_proposals WHERE id=:id FOR UPDATE",
                    id=row["id"],
                )
                if (
                    proposal["status"] != "PENDING"
                    or proposal["expires_at"] > sec.now()
                    or proposal["kind"] != "CREATE"
                ):
                    return False
                candidate = candidate_from_revision(
                    db, proposal["candidate_revision_id"]
                )
                lock_resources(db, candidate, [proposal["submitted_by"]])
                expire_one(db, root, proposal, candidate)
                return True

        count += bool(transaction_retry(action))
    return count


def user_ref(db, user_id):
    return c.one(
        db,
        "SELECT id,employee_code,full_name,department_id FROM users WHERE id=:id",
        id=user_id,
    )


def can_read_revision(db, viewer, root, revision):
    if viewer["id"] == root["created_by"]:
        return True
    if c.rows(
        db,
        "SELECT user_id FROM revision_participants WHERE revision_id=:r AND user_id=:u",
        r=revision["id"],
        u=viewer["id"],
    ):
        return True
    return (
        revision["room_id"] in viewer["room_scope_ids"]
        or revision["department_id"] in viewer["department_scope_ids"]
    )


def revision_view(db, revision):
    candidate = candidate_from_revision(db, revision["id"])
    data = candidate.model_dump(mode="json")
    people = participant_pairs(candidate)
    data.pop("participant_user_ids", None)
    data["participants"] = [
        dict(user=user_ref(db, user_id), is_required=required)
        for user_id, required in people
    ]
    data.update(
        id=revision["id"],
        schedule_id=revision["schedule_id"],
        revision_no=revision["revision_no"],
    )
    return data


def summary(proposal, revision):
    return {
        **{
            k: proposal[k]
            for k in ["id", "schedule_id", "kind", "status", "row_version"]
        },
        "schedule_kind": revision["kind"],
        "title": revision["title"],
        "expires_at": c.aware(proposal["expires_at"]),
        "created_at": c.aware(proposal["created_at"]),
    }


def proposal_data(db, ctx, proposal_id):
    p = c.one(db, "SELECT * FROM approval_proposals WHERE id=:id", id=proposal_id)
    root = c.one(db, "SELECT * FROM schedule_roots WHERE id=:id", id=p["schedule_id"])
    r = c.one(
        db,
        "SELECT * FROM schedule_revisions WHERE id=:id",
        id=p["candidate_revision_id"],
    )
    if not can_read_revision(db, ctx[0], root, r):
        fail(404, "NOT_FOUND", "Không tìm thấy yêu cầu trong phạm vi của bạn.")
    return root, p, r


def get_proposal(ctx, proposal_id):
    c.require_member(ctx)
    with Session() as db:
        root, p, r = proposal_data(db, ctx, proposal_id)
        candidate = candidate_from_revision(db, r["id"])
        reviewer = (
            ctx[0]["id"] in approvers(db, candidate, p["submitted_by"])
            and "APPROVER" in ctx[0]["roles"]
        )
        allowed = []
        if (
            p["status"] == "PENDING"
            and p["expires_at"] > sec.now()
            and p["kind"] == "CREATE"
        ):
            if p["submitted_by"] == ctx[0]["id"]:
                allowed.append("WITHDRAW")
            elif reviewer:
                allowed.extend(["APPROVE", "REJECT"])
        mail = None
        if reviewer or root["created_by"] == ctx[0]["id"]:
            counts = c.rows(
                db,
                """SELECT d.status,COUNT(*) AS n FROM email_deliveries d JOIN outbox_events e ON e.id=d.event_id WHERE e.proposal_id=:id GROUP BY d.status""",
                id=proposal_id,
            )
            counts = {v["status"]: v["n"] for v in counts}
            mail = dict(
                pending=sum(
                    counts.get(k, 0) for k in ["PENDING", "RETRY", "PROCESSING"]
                ),
                smtp_accepted=counts.get("SMTP_ACCEPTED", 0),
                failed=counts.get("FAILED", 0),
                skipped=counts.get("SKIPPED", 0),
            )
        return dict(
            **summary(p, r),
            schedule_version=root["row_version"],
            submitted_by=user_ref(db, p["submitted_by"]),
            candidate=revision_view(db, r),
            base_comparison=None,
            resolved_by=user_ref(db, p["resolved_by"]) if p["resolved_by"] else None,
            resolved_at=c.aware(p["resolved_at"]) if p["resolved_at"] else None,
            reason=p["reason"],
            allowed_actions=allowed,
            email_summary=mail,
        )


def list_proposals(ctx, scope, status, page_no, page_size):
    c.require_member(ctx)
    with Session() as db:
        result = []
        for p in c.rows(
            db,
            "SELECT * FROM approval_proposals WHERE kind='CREATE' ORDER BY created_at DESC,id",
        ):
            root = c.one(
                db, "SELECT * FROM schedule_roots WHERE id=:id", id=p["schedule_id"]
            )
            r = c.one(
                db,
                "SELECT * FROM schedule_revisions WHERE id=:id",
                id=p["candidate_revision_id"],
            )
            if status and p["status"] != status:
                continue
            if scope == "MINE" and p["submitted_by"] != ctx[0]["id"]:
                continue
            if scope == "REVIEWABLE":
                candidate = candidate_from_revision(db, r["id"])
                if "APPROVER" not in ctx[0]["roles"] or ctx[0]["id"] not in approvers(
                    db, candidate, p["submitted_by"]
                ):
                    continue
            if not can_read_revision(db, ctx[0], root, r):
                continue
            result.append(summary(p, r))
        return c.page(result, page_no, page_size)


def get_schedule(ctx, schedule_id):
    c.require_member(ctx)
    with Session() as db:
        root = c.one(db, "SELECT * FROM schedule_roots WHERE id=:id", id=schedule_id)
        revisions = c.rows(
            db,
            "SELECT * FROM schedule_revisions WHERE schedule_id=:id ORDER BY revision_no DESC",
            id=schedule_id,
        )
        r = next(
            (v for v in revisions if v["id"] == root["current_revision_id"]),
            revisions[0] if revisions else None,
        )
        if not r:
            fail(404, "NOT_FOUND", "Không tìm thấy lịch.")
        if not can_read_revision(db, ctx[0], root, r):
            if root["current_revision_id"] and not root["cancelled_at"]:
                meeting = c.rows(
                    db,
                    "SELECT blocked_until FROM v_effective_meetings WHERE schedule_id=:id",
                    id=schedule_id,
                )
                return dict(
                    visibility="BUSY_ONLY",
                    starts_at=c.aware(r["starts_at"]),
                    ends_at=c.aware(r["ends_at"]),
                    room_id=r["room_id"],
                    blocked_until=(
                        c.aware(meeting[0]["blocked_until"]) if meeting else None
                    ),
                )
            fail(404, "NOT_FOUND", "Không tìm thấy lịch trong phạm vi của bạn.")
        visible = []
        for p in c.rows(
            db,
            "SELECT * FROM approval_proposals WHERE schedule_id=:id ORDER BY created_at DESC,id",
            id=schedule_id,
        ):
            pr = next(
                (v for v in revisions if v["id"] == p["candidate_revision_id"]), None
            )
            if pr and can_read_revision(db, ctx[0], root, pr):
                visible.append(summary(p, pr))
        cancellation = (
            dict(
                cancelled_at=c.aware(root["cancelled_at"]),
                cancelled_by=user_ref(db, root["cancelled_by"]),
                reason=root["cancel_reason"],
            )
            if root["cancelled_at"]
            else None
        )
        return dict(
            visibility="DETAIL",
            id=root["id"],
            kind=root["kind"],
            row_version=root["row_version"],
            lifecycle=(
                "CANCELLED"
                if root["cancelled_at"]
                else "ACTIVE" if root["current_revision_id"] else "UNCONFIRMED"
            ),
            created_by=user_ref(db, root["created_by"]),
            current_revision=(
                revision_view(db, r) if root["current_revision_id"] else None
            ),
            visible_proposals=visible,
            cancellation=cancellation,
            allowed_actions=[],
        )


def list_schedules(ctx, relation, lifecycle, page_no, page_size):
    c.require_member(ctx)
    with Session() as db:
        result = []
        for root in c.rows(
            db, "SELECT * FROM schedule_roots ORDER BY created_at DESC,id"
        ):
            state = (
                "CANCELLED"
                if root["cancelled_at"]
                else "ACTIVE" if root["current_revision_id"] else "UNCONFIRMED"
            )
            if lifecycle and lifecycle != state:
                continue
            revisions = c.rows(
                db,
                "SELECT * FROM schedule_revisions WHERE schedule_id=:id ORDER BY revision_no DESC",
                id=root["id"],
            )
            visible = []
            for r in revisions:
                involved = bool(
                    c.rows(
                        db,
                        "SELECT user_id FROM revision_participants WHERE revision_id=:r AND user_id=:u",
                        r=r["id"],
                        u=ctx[0]["id"],
                    )
                )
                if relation == "CREATED" and root["created_by"] != ctx[0]["id"]:
                    continue
                if relation == "PARTICIPATING" and not involved:
                    continue
                if can_read_revision(db, ctx[0], root, r):
                    visible.append(r)
            if not visible:
                continue
            r = next(
                (v for v in visible if v["id"] == root["current_revision_id"]),
                visible[0],
            )
            result.append(
                dict(
                    id=root["id"],
                    visible_revision_id=r["id"],
                    kind=r["kind"],
                    title=r["title"],
                    lifecycle=state,
                    is_effective_revision=r["id"] == root["current_revision_id"],
                    starts_at=c.aware(r["starts_at"]),
                    ends_at=c.aware(r["ends_at"]),
                )
            )
        return c.page(result, page_no, page_size)


def visible_revisions(db, ctx, schedule_id):
    root = c.one(db, "SELECT * FROM schedule_roots WHERE id=:id", id=schedule_id)
    found = [
        r
        for r in c.rows(
            db,
            "SELECT * FROM schedule_revisions WHERE schedule_id=:id ORDER BY revision_no DESC",
            id=schedule_id,
        )
        if can_read_revision(db, ctx[0], root, r)
    ]
    if not found:
        fail(404, "NOT_FOUND", "Không có phiên bản lịch trong phạm vi của bạn.")
    return found


def revisions(ctx, schedule_id, page_no, page_size, revision_id=None):
    c.require_member(ctx)
    with Session() as db:
        found = visible_revisions(db, ctx, schedule_id)
        if revision_id:
            r = next((r for r in found if r["id"] == revision_id), None)
            if not r:
                fail(404, "NOT_FOUND", "Không tìm thấy phiên bản lịch.")
            return revision_view(db, r)
        return c.page([revision_view(db, r) for r in found], page_no, page_size)


def audit_history(ctx, schedule_id, page_no, page_size):
    c.require_member(ctx)
    with Session() as db:
        ids = {r["id"] for r in visible_revisions(db, ctx, schedule_id)}
        labels = {
            "PROPOSAL_SUBMITTED": "Đã gửi yêu cầu",
            "PROPOSAL_APPROVED": "Đã chấp thuận yêu cầu",
            "PROPOSAL_REJECTED": "Đã từ chối yêu cầu",
            "PROPOSAL_WITHDRAWN": "Người gửi đã rút yêu cầu",
            "PROPOSAL_EXPIRED": "Yêu cầu hết hạn xử lý",
        }
        result = [
            dict(
                id=a["id"],
                action=a["action"],
                actor=user_ref(db, a["actor_user_id"]) if a["actor_user_id"] else None,
                revision_id=a["revision_id"],
                occurred_at=c.aware(a["created_at"]),
                summary=labels.get(a["action"], "Đã cập nhật hồ sơ"),
            )
            for a in c.rows(
                db,
                "SELECT * FROM audit_entries WHERE schedule_id=:id ORDER BY created_at DESC,id",
                id=schedule_id,
            )
            if a["revision_id"] in ids
        ]
        return c.page(result, page_no, page_size)
