"""SMTP outbox worker: leased claims, permission rechecks, bounded retries (DP-08).

SMTP is deliberately outside SQL transactions. A process dying after DATA may
leave an UNKNOWN attempt; a stable Message-ID helps, but cannot guarantee exactly
one email at the recipient. No exception text, credentials or message body is logged.
"""

import argparse
import json
import logging
import os
import signal
import smtplib
import ssl
import threading
from dataclasses import dataclass, field
from datetime import timedelta
from email.message import EmailMessage
from email.utils import format_datetime
from urllib.parse import urlencode, urlsplit
from uuid import UUID

from pydantic import EmailStr, TypeAdapter

from . import catalog as c, scheduling, security
from .db import Session

RETRY_SECONDS = (60, 300, 900)
LEASE_SECONDS = 120
LABELS = {
    "PROPOSAL_SUBMITTED": "Có yêu cầu mới cần xét duyệt",
    "CHANGE_SUBMITTED": "Có đề nghị sửa lịch cần xét duyệt",
    "WORK_CANCELLATION_SUBMITTED": "Có đề nghị hủy công tác cần xét duyệt",
    "PROPOSAL_APPROVED": "Yêu cầu đã được chấp thuận",
    "PROPOSAL_REJECTED": "Yêu cầu đã bị từ chối",
    "PROPOSAL_WITHDRAWN": "Người gửi đã rút yêu cầu",
    "PROPOSAL_EXPIRED": "Yêu cầu đã hết hạn",
    "SCHEDULE_RELEASED": "Lượt đặt cũ đã được giải phóng",
    "MEETING_CANCELLED": "Lịch họp đã được hủy",
}
SUBMISSIONS = {"PROPOSAL_SUBMITTED", "CHANGE_SUBMITTED", "WORK_CANCELLATION_SUBMITTED"}


@dataclass(frozen=True)
class Settings:
    enabled: bool
    host: str = ""
    port: int = 587
    mode: str = "starttls"
    username: str = ""
    password: str = field(default="", repr=False)
    sender: str = ""
    app_url: str = "http://localhost:8080"
    timeout: int = 10

    @classmethod
    def load(cls):
        enabled = os.getenv("SMTP_ENABLED", "false").lower() == "true"
        if not enabled:
            return cls(False)
        try:
            mode = os.getenv("SMTP_MODE", "starttls").lower()
            host = os.environ["SMTP_HOST"].strip()
            sender = str(TypeAdapter(EmailStr).validate_python(os.environ["SMTP_FROM"]))
            app_url = os.getenv("APP_BASE_URL", "http://localhost:8080").rstrip("/")
            url = urlsplit(app_url)
            port = int(os.getenv("SMTP_PORT", "465" if mode == "ssl" else "587"))
            timeout = int(os.getenv("SMTP_TIMEOUT_SECONDS", "10"))
            username = os.getenv("SMTP_USERNAME", "")
            password = os.getenv("SMTP_PASSWORD", "")
            if (
                not host
                or any(ch in host for ch in "\r\n")
                or mode not in ("ssl", "starttls", "plain")
                or not 1 <= port <= 65535
                or not 1 <= timeout <= 30
                or url.scheme not in ("http", "https")
                or not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
                or bool(username) != bool(password)
            ):
                raise ValueError()
            if (
                mode == "plain"
                and os.getenv("SMTP_ALLOW_PLAIN", "false").lower() != "true"
            ):
                raise ValueError()
            return cls(
                True, host, port, mode, username, password, sender, app_url, timeout
            )
        except Exception:
            raise ValueError(
                "Cấu hình SMTP chưa hợp lệ; kiểm tra các biến môi trường, không chia sẻ bí mật."
            ) from None


def eligible(db, delivery):
    event = c.one(
        db, "SELECT * FROM outbox_events WHERE id=:id", id=delivery["event_id"]
    )
    action = event["event_type"]
    if action not in LABELS:
        return None, "UNSUPPORTED_EVENT"
    root = c.one(
        db, "SELECT * FROM schedule_roots WHERE id=:id", id=event["schedule_id"]
    )
    user = c.one(
        db, "SELECT * FROM users WHERE id=:id", id=delivery["recipient_user_id"]
    )
    if user["status"] != "ACTIVE":
        return None, "RECIPIENT_INACTIVE"
    try:
        payload = event["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        rid = str(UUID(payload["revision_id"]))
    except (ValueError, KeyError, TypeError):
        return None, "INVALID_EVENT"
    revisions = c.rows(
        db,
        "SELECT * FROM schedule_revisions WHERE id=:r AND schedule_id=:s",
        r=rid,
        s=root["id"],
    )
    if not revisions:
        return None, "INVALID_EVENT"
    roles = {
        r["role"]
        for r in c.rows(
            db, "SELECT role FROM user_roles WHERE user_id=:id", id=user["id"]
        )
    }
    user["room_scope_ids"] = (
        [
            r["room_id"]
            for r in c.rows(
                db,
                "SELECT room_id FROM room_approvers WHERE user_id=:id AND is_active=1",
                id=user["id"],
            )
        ]
        if "APPROVER" in roles
        else []
    )
    user["department_scope_ids"] = (
        [
            r["department_id"]
            for r in c.rows(
                db,
                "SELECT department_id FROM department_approvers WHERE user_id=:id AND is_active=1",
                id=user["id"],
            )
        ]
        if "APPROVER" in roles
        else []
    )
    if not scheduling.can_read_revision(db, user, root, revisions[0]):
        return None, "RECIPIENT_OUT_OF_SCOPE"
    proposal = (
        c.one(
            db,
            "SELECT * FROM approval_proposals WHERE id=:id AND schedule_id=:s",
            id=event["proposal_id"],
            s=root["id"],
        )
        if event["proposal_id"]
        else None
    )
    valid = False
    if action in SUBMISSIONS:
        valid = bool(
            proposal
            and proposal["status"] == "PENDING"
            and proposal["expires_at"] > security.now()
            and not root["cancelled_at"]
        )
    elif action == "SCHEDULE_RELEASED":
        valid = bool(
            proposal
            and proposal["kind"] == "CHANGE"
            and proposal["status"] == "APPROVED"
            and proposal["base_revision_id"] == rid
        )
    elif action == "MEETING_CANCELLED":
        valid = bool(root["cancelled_at"] and root["current_revision_id"] == rid)
    elif proposal and action == "PROPOSAL_" + proposal["status"]:
        valid = True
        if proposal["status"] == "APPROVED":
            valid = (
                (bool(root["cancelled_at"]) and root["current_revision_id"] == rid)
                if proposal["kind"] == "CANCEL"
                else (not root["cancelled_at"] and root["current_revision_id"] == rid)
            )
    if not valid:
        return None, "STALE_EVENT"
    return (
        dict(
            email=user["email"],
            event_id=event["id"],
            action=action,
            schedule_id=root["id"],
            proposal_id=(
                proposal["id"] if proposal and action != "SCHEDULE_RELEASED" else None
            ),
        ),
        None,
    )


def terminal(db, delivery, status, code=None):
    c.run(
        db,
        """UPDATE email_deliveries SET status=:status,last_error_code=:code,
        lease_token=NULL,lease_until=NULL WHERE id=:id""",
        status=status,
        code=code,
        id=delivery["id"],
    )


def recover(db, d, now):
    c.run(
        db,
        """UPDATE email_attempts SET outcome='UNKNOWN',finished_at=:now,safe_error_code='LEASE_EXPIRED'
        WHERE delivery_id=:id AND attempt_no=:n AND outcome='STARTED'""",
        now=now,
        id=d["id"],
        n=d["attempt_count"],
    )
    failed = d["first_failed_at"] or now
    if d["attempt_count"] >= 4:
        terminal(db, d, "FAILED", "LEASE_EXPIRED")
    else:
        c.run(
            db,
            """UPDATE email_deliveries SET status='RETRY',first_failed_at=:first,next_attempt_at=:next,
            lease_token=NULL,lease_until=NULL,last_error_code='LEASE_EXPIRED' WHERE id=:id""",
            first=failed,
            next=failed
            + timedelta(seconds=RETRY_SECONDS[max(0, d["attempt_count"] - 1)]),
            id=d["id"],
        )


def claim():
    now = security.now()
    with Session.begin() as db:
        found = c.rows(
            db,
            """SELECT * FROM email_deliveries WHERE
            (status IN ('PENDING','RETRY') AND next_attempt_at<=:now) OR
            (status='PROCESSING' AND lease_until<=:now)
            ORDER BY next_attempt_at,created_at,id LIMIT 1 FOR UPDATE SKIP LOCKED""",
            now=now,
        )
        if not found:
            return None
        d = found[0]
        if d["status"] == "PROCESSING":
            recover(db, d, now)
            return dict(recovered=True)
        if d["attempt_count"] >= 4:
            terminal(db, d, "FAILED", "MAX_ATTEMPTS")
            return dict(skipped=True)
        context, code = eligible(db, d)
        if not context:
            terminal(db, d, "SKIPPED", code)
            return dict(skipped=True)
        token = c.uid()
        attempt = d["attempt_count"] + 1
        c.run(
            db,
            """UPDATE email_deliveries SET status='PROCESSING',attempt_count=:n,
            lease_token=:token,lease_until=:until WHERE id=:id""",
            n=attempt,
            token=token,
            until=now + timedelta(seconds=LEASE_SECONDS),
            id=d["id"],
        )
        c.run(
            db,
            """INSERT INTO email_attempts(delivery_id,attempt_no,started_at,outcome,recipient_email)
            VALUES(:id,:n,:now,'STARTED',:email)""",
            id=d["id"],
            n=attempt,
            now=now,
            email=context["email"],
        )
        return dict(
            id=d["id"],
            event_id=d["event_id"],
            recipient_user_id=d["recipient_user_id"],
            token=token,
            attempt=attempt,
            context=context,
        )


def finish(job, accepted=False, error=None, skipped=False):
    now = security.now()
    with Session.begin() as db:
        d = c.one(
            db, "SELECT * FROM email_deliveries WHERE id=:id FOR UPDATE", id=job["id"]
        )
        if d["status"] != "PROCESSING" or d["lease_token"] != job["token"]:
            return False
        outcome = "SMTP_ACCEPTED" if accepted else "ERROR"
        c.run(
            db,
            """UPDATE email_attempts SET outcome=:outcome,finished_at=:now,safe_error_code=:code
            WHERE delivery_id=:id AND attempt_no=:n AND outcome='STARTED'""",
            outcome=outcome,
            now=now,
            code=error,
            id=d["id"],
            n=job["attempt"],
        )
        if accepted:
            c.run(
                db,
                """UPDATE email_deliveries SET status='SMTP_ACCEPTED',smtp_accepted_at=:now,
                lease_token=NULL,lease_until=NULL,last_error_code=NULL WHERE id=:id""",
                now=now,
                id=d["id"],
            )
        elif skipped:
            terminal(db, d, "SKIPPED", error)
        else:
            first = d["first_failed_at"] or now
            c.run(
                db,
                """UPDATE email_deliveries SET status=:status,first_failed_at=:first,
                next_attempt_at=:next,lease_token=NULL,lease_until=NULL,last_error_code=:code WHERE id=:id""",
                status="FAILED" if d["attempt_count"] >= 4 else "RETRY",
                first=first,
                next=first
                + timedelta(seconds=RETRY_SECONDS[min(d["attempt_count"] - 1, 2)]),
                code=error,
                id=d["id"],
            )
        return True


def message(settings, job, context):
    msg = EmailMessage()
    msg["Subject"] = "HTTT10 — " + LABELS[context["action"]]
    msg["From"] = settings.sender
    msg["To"] = context["email"]
    msg["Date"] = format_datetime(c.aware(security.now()))
    msg["Message-ID"] = "<" + job["id"] + "@httt10.local>"
    query = (
        {"proposal": context["proposal_id"]}
        if context["proposal_id"]
        else {"schedule": context["schedule_id"]}
    )
    link = settings.app_url + "/?" + urlencode(query)
    msg.set_content(
        LABELS[context["action"]]
        + ".\n\nCó cập nhật liên quan đến hồ sơ lịch trong phạm vi của bạn.\nĐăng nhập để xem tình trạng mới nhất:\n"
        + link
        + "\n\nEmail không xác nhận việc cuộc họp/công tác đã diễn ra. Không trả lời email tự động này.\n"
    )
    return msg


def send(settings, msg):
    smtp = None
    try:
        if settings.mode == "ssl":
            smtp = smtplib.SMTP_SSL(
                settings.host,
                settings.port,
                timeout=settings.timeout,
                context=ssl.create_default_context(),
            )
        else:
            smtp = smtplib.SMTP(settings.host, settings.port, timeout=settings.timeout)
            smtp.ehlo()
            if settings.mode == "starttls":
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
        if settings.username:
            smtp.login(settings.username, settings.password)
        if smtp.send_message(msg, from_addr=settings.sender, to_addrs=[msg["To"]]):
            raise smtplib.SMTPRecipientsRefused({})
        # DATA accepted; a later QUIT failure must not turn this into a retry.
    finally:
        if smtp:
            try:
                smtp.quit()
            except Exception:
                smtp.close()


def error_code(exc):
    for kind, code in [
        (smtplib.SMTPAuthenticationError, "SMTP_AUTH_ERROR"),
        (smtplib.SMTPRecipientsRefused, "SMTP_RECIPIENT_REFUSED"),
        (smtplib.SMTPSenderRefused, "SMTP_SENDER_REFUSED"),
        (smtplib.SMTPDataError, "SMTP_DATA_ERROR"),
        (ssl.SSLError, "SMTP_TLS_ERROR"),
        (TimeoutError, "SMTP_TIMEOUT"),
        (smtplib.SMTPServerDisconnected, "SMTP_DISCONNECTED"),
        (OSError, "SMTP_CONNECTION_ERROR"),
    ]:
        if isinstance(exc, kind):
            return code
    return "SMTP_ERROR"


def process_one(settings):
    if not settings.enabled:
        return "DISABLED"
    job = claim()
    if not job:
        return "EMPTY"
    if job.get("recovered"):
        return "RECOVERED"
    if job.get("skipped"):
        return "SKIPPED"
    # Recheck the current recipient and event immediately before the network call.
    with Session() as db:
        lease = c.one(db, "SELECT * FROM email_deliveries WHERE id=:id", id=job["id"])
        if (
            lease["status"] != "PROCESSING"
            or lease["lease_token"] != job["token"]
            or lease["lease_until"] <= security.now()
        ):
            return "LEASE_LOST"
        context, code = eligible(db, job)
    if not context or context["email"] != job["context"]["email"]:
        finish(job, error=code or "RECIPIENT_CHANGED", skipped=True)
        return "SKIPPED"
    try:
        send(settings, message(settings, job, context))
    except Exception as exc:
        finish(job, error=error_code(exc))
        return "ERROR"
    return "SMTP_ACCEPTED" if finish(job, accepted=True) else "LEASE_LOST"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true")
    p.add_argument("--limit", type=int, default=100)
    a = p.parse_args()
    if not 1 <= a.limit <= 1000:
        p.error("--limit phải trong 1..1000")
    try:
        settings = Settings.load()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    if not settings.enabled:
        print("SMTP disabled; outbox is preserved.", flush=True)
    while not stop.is_set():
        try:
            result = "EMPTY"
            for _ in range(a.limit):
                result = process_one(settings)
                if result in ("EMPTY", "DISABLED") or stop.is_set():
                    break
            if a.once:
                print(json.dumps(dict(status=result)))
                return
        except Exception:
            logging.error(
                "Email worker could not complete a cycle; will retry. Check database connectivity."
            )
            if a.once:
                raise SystemExit(1) from None
        stop.wait(2)


if __name__ == "__main__":
    main()
