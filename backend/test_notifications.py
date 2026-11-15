"""DP-08: a real loopback SMTP receiver and leased MySQL outbox processing."""

import os

os.environ["TEST_SUITE"] = "notifications"
from integration_support import *
import socketserver
import threading
import smtplib
from email import policy
from email.parser import BytesParser
from app import email_worker as worker


class Receiver(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self):
        self.messages = []
        self.data_reply = 250
        self.quit_failure = False
        super().__init__(("127.0.0.1", 0), Handler)


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        def reply(value):
            self.wfile.write(value + b"\r\n")
            self.wfile.flush()

        reply(b"220 loopback test SMTP")
        while line := self.rfile.readline():
            command = line.split(b" ", 1)[0].strip().upper()
            if command in (b"EHLO", b"HELO"):
                reply(b"250-loopback\r\n250 SIZE 1048576")
            elif command in (b"MAIL", b"RCPT", b"RSET", b"NOOP"):
                reply(b"250 OK")
            elif command == b"DATA":
                reply(b"354 end with dot")
                data = []
                while (part := self.rfile.readline()) not in (b".\r\n", b""):
                    data.append(part[1:] if part.startswith(b"..") else part)
                self.server.messages.append(
                    BytesParser(policy=policy.default).parsebytes(b"".join(data))
                )
                reply(
                    b"250 Accepted"
                    if self.server.data_reply == 250
                    else b"451 SECRET-SMTP-DIAGNOSTIC"
                )
            elif command == b"QUIT":
                reply(b"421 closing error" if self.server.quit_failure else b"221 bye")
                return
            else:
                reply(b"502 unsupported")


def row(did):
    with Session() as db:
        return dict(
            db.execute(
                text("SELECT * FROM email_deliveries WHERE id=:id"), dict(id=did)
            )
            .mappings()
            .one()
        )


def isolate(did):
    with Session.begin() as db:
        db.execute(
            text(
                "UPDATE email_deliveries SET status='SKIPPED',lease_token=NULL,lease_until=NULL WHERE id<>:id AND status IN ('PENDING','RETRY','PROCESSING')"
            ),
            dict(id=did),
        )


def queue(who="LEAD1"):
    r, _, _ = submit(meeting(people=[("EMP1", True), ("SHARED", True)]))
    assert r.status_code == 201, r.text
    item = r.json()
    did = scalar(
        "SELECT d.id FROM email_deliveries d JOIN outbox_events e ON e.id=d.event_id WHERE e.proposal_id=:p AND e.event_type='PROPOSAL_SUBMITTED' AND d.recipient_user_id=:u",
        p=item["proposal_id"],
        u=users[who],
    )
    isolate(did)
    return did, item


with patch.dict(os.environ, {"SMTP_ENABLED": "false"}):
    check("SMTP mặc định không gửi thư", worker.Settings.load().enabled, False)
for label, env in [
    ("Thiếu host", {"SMTP_ENABLED": "true"}),
    (
        "URL không hợp lệ",
        {
            "SMTP_ENABLED": "true",
            "SMTP_HOST": "example.com",
            "SMTP_FROM": "calendar@example.com",
            "APP_BASE_URL": "file:///secret",
        },
    ),
    (
        "Không chấp nhận plain ngầm",
        {
            "SMTP_ENABLED": "true",
            "SMTP_HOST": "example.com",
            "SMTP_FROM": "calendar@example.com",
            "SMTP_MODE": "plain",
        },
    ),
]:
    with patch.dict(os.environ, env, clear=True):
        try:
            worker.Settings.load()
            valid = False
        except ValueError as exc:
            valid = "secret" not in str(exc)
        check(label, valid)
check(
    "Mật khẩu không có trong repr cấu hình",
    "VERY_SECRET" not in repr(worker.Settings(False, password="VERY_SECRET")),
)
server = Receiver()
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
settings = worker.Settings(
    True,
    "127.0.0.1",
    server.server_address[1],
    "plain",
    sender="calendar@example.com",
    app_url="http://localhost:8080",
)
try:
    did, item = queue()
    check(
        "Disable giữ nguyên hàng chờ",
        worker.process_one(worker.Settings(False)),
        "DISABLED",
    )
    check("Không đổi trạng thái khi disabled", row(did)["status"], "PENDING")
    real_send = worker.send

    def send_outside_transaction(config, msg):
        with Session.begin() as db:
            db.execute(
                text(
                    "UPDATE email_deliveries SET last_error_code='LOCK_CHECK' WHERE id=:id"
                ),
                dict(id=did),
            )
        return real_send(config, msg)

    with patch("app.email_worker.send", side_effect=send_outside_transaction):
        check(
            "SMTP thật TCP ngoài transaction khóa SQL",
            worker.process_one(settings),
            "SMTP_ACCEPTED",
        )
    check("Một delivery gửi đúng một thư", len(server.messages), 1)
    msg = server.messages[-1]
    check("Một địa chỉ người nhận", str(msg["To"]), "lead1@example.com")
    check(
        "Email có liên kết đăng nhập đúng hồ sơ",
        "?proposal=" + item["proposal_id"] in msg.get_content(),
    )
    check(
        "Email không có nội dung lịch riêng",
        all(
            x not in msg.as_string()
            for x in [
                "PRIVATE_MEETING",
                "PRIVATE_DESCRIPTION",
                "Bearer ",
                "password",
                "access_token",
            ]
        ),
    )
    check("Email không đính kèm tệp", not msg.is_multipart())
    check(
        "Attempt được ghi SMTP_ACCEPTED",
        scalar("SELECT outcome FROM email_attempts WHERE delivery_id=:id", id=did),
        "SMTP_ACCEPTED",
    )
    check("Không gửi lại delivery đã được nhận", worker.process_one(settings), "EMPTY")
    check("Không tạo SMTP lần hai", len(server.messages), 1)
    # Retry due times are relative to the FIRST failed attempt, not the last one.
    did, item = queue()
    server.data_reply = 451
    t0 = security.now()
    for index, seconds in enumerate((0, 60, 300, 900), 1):
        with patch(
            "app.email_worker.security.now",
            return_value=t0 + timedelta(seconds=seconds),
        ):
            check("Lỗi SMTP lần " + str(index), worker.process_one(settings), "ERROR")
        state = row(did)
        check("Số lần gửi " + str(index), state["attempt_count"], index)
        check(
            "Chỉ lưu mã lỗi an toàn " + str(index),
            state["last_error_code"],
            "SMTP_DATA_ERROR",
        )
        if index < 4:
            check(
                "Hẹn lại từ lỗi đầu " + str(index),
                state["next_attempt_at"],
                t0 + timedelta(seconds=(60, 300, 900)[index - 1]),
            )
            with patch(
                "app.email_worker.security.now",
                return_value=state["next_attempt_at"] - timedelta(microseconds=1),
            ):
                check(
                    "Chưa đến hạn không gửi " + str(index),
                    worker.process_one(settings),
                    "EMPTY",
                )
    check("Bốn lần lỗi kết thúc FAILED", row(did)["status"], "FAILED")
    with Session() as db:
        errors = [
            dict(x)
            for x in db.execute(
                text(
                    "SELECT safe_error_code FROM email_attempts WHERE delivery_id=:id"
                ),
                dict(id=did),
            ).mappings()
        ]
    check(
        "Không lộ phản hồi SMTP vào DB",
        "SECRET" not in json.dumps(errors) + str(row(did)["last_error_code"]),
    )
    check(
        "Đủ bốn attempt lưu vết",
        scalar("SELECT COUNT(*) FROM email_attempts WHERE delivery_id=:id", id=did),
        4,
    )
    with patch("app.email_worker.security.now", return_value=t0 + timedelta(hours=1)):
        check("Không gửi lần thứ năm", worker.process_one(settings), "EMPTY")
    server.data_reply = 250
    did, item = queue()
    assert withdraw(item).status_code == 200
    isolate(did)
    check("Không gửi thông báo chờ đã bị rút", worker.process_one(settings), "SKIPPED")
    check("Bỏ qua stale có mã lý do", row(did)["last_error_code"], "STALE_EVENT")
    check("Bỏ qua trước gửi không tạo attempt", row(did)["attempt_count"], 0)
    did, item = queue("SHARED")
    with Session.begin() as db:
        db.execute(
            text("UPDATE users SET status='LOCKED' WHERE id=:id"),
            dict(id=users["SHARED"]),
        )
    check("Không gửi cho tài khoản khóa", worker.process_one(settings), "SKIPPED")
    with Session.begin() as db:
        db.execute(
            text("UPDATE users SET status='ACTIVE' WHERE id=:id"),
            dict(id=users["SHARED"]),
        )
    did, item = queue()
    with Session.begin() as db:
        db.execute(
            text("UPDATE room_approvers SET is_active=0 WHERE user_id=:id"),
            dict(id=users["LEAD1"]),
        )
    check("Thu hồi scope ngăn gửi", worker.process_one(settings), "SKIPPED")
    check(
        "Lý do ngoài quyền không có dữ liệu riêng",
        row(did)["last_error_code"],
        "RECIPIENT_OUT_OF_SCOPE",
    )
    with Session.begin() as db:
        db.execute(
            text("UPDATE room_approvers SET is_active=1 WHERE user_id=:id"),
            dict(id=users["LEAD1"]),
        )
    # A second read catches address changes after the claim committed.
    did, item = queue()
    real_claim = worker.claim

    def claim_then_change_address():
        job = real_claim()
        with Session.begin() as db:
            db.execute(
                text("UPDATE users SET email='new-address@example.com' WHERE id=:id"),
                dict(id=users["LEAD1"]),
            )
        return job

    count = len(server.messages)
    with patch("app.email_worker.claim", side_effect=claim_then_change_address):
        check(
            "Kiểm tra lại người nhận ngay trước SMTP",
            worker.process_one(settings),
            "SKIPPED",
        )
    check("Đổi email sau claim không gửi địa chỉ cũ", len(server.messages), count)
    with Session.begin() as db:
        db.execute(
            text("UPDATE users SET email='lead1@example.com' WHERE id=:id"),
            dict(id=users["LEAD1"]),
        )
    did, item = queue()
    barrier = Barrier(2)
    count = len(server.messages)

    def racer():
        barrier.wait()
        return worker.process_one(settings)

    with ThreadPoolExecutor(2) as pool:
        status = list(pool.map(lambda _: racer(), range(2)))
    check(
        "Hai worker chỉ một claim delivery", sorted(status), ["EMPTY", "SMTP_ACCEPTED"]
    )
    check("Không gửi trùng khi hai worker cạnh tranh", len(server.messages) - count, 1)
    did, item = queue()
    server.quit_failure = True
    check(
        "QUIT lỗi sau DATA accepted không tạo retry",
        worker.process_one(settings),
        "SMTP_ACCEPTED",
    )
    check("QUIT lỗi vẫn lưu accepted", row(did)["status"], "SMTP_ACCEPTED")
    server.quit_failure = False
    # Simulate a crash AFTER SMTP accepted but before SQL acknowledgement.
    did, item = queue()
    count = len(server.messages)
    with patch(
        "app.email_worker.finish", side_effect=RuntimeError("simulated process death")
    ):
        try:
            worker.process_one(settings)
        except RuntimeError:
            pass
    check(
        "Crash sau SMTP giữ attempt chưa rõ kết quả", row(did)["status"], "PROCESSING"
    )
    initial_message_id = str(server.messages[-1]["Message-ID"])
    lease = row(did)["lease_until"]
    with patch(
        "app.email_worker.security.now", return_value=lease + timedelta(seconds=1)
    ):
        check("Lease hết hạn được thu hồi", worker.process_one(settings), "RECOVERED")
    check(
        "Attempt cũ được đánh dấu UNKNOWN",
        scalar(
            "SELECT outcome FROM email_attempts WHERE delivery_id=:id AND attempt_no=1",
            id=did,
        ),
        "UNKNOWN",
    )
    next_time = row(did)["next_attempt_at"]
    with patch("app.email_worker.security.now", return_value=next_time):
        check(
            "Thử lại sau crash có thể gửi lại",
            worker.process_one(settings),
            "SMTP_ACCEPTED",
        )
    check(
        "Message-ID ổn định qua lần thử lại",
        str(server.messages[-1]["Message-ID"]),
        initial_message_id,
    )
    check("Ghi nhận giới hạn có thể trùng sau crash", len(server.messages) - count, 2)
    old_job = dict(id=did, token=str(uuid4()), attempt=1)
    check(
        "Worker cũ không ghi đè lease mới", worker.finish(old_job, accepted=True), False
    )
    # Terminal events and room-move events retain their own audiences.
    item, base = confirmed(people=[("EMP1", True), ("SHARED", True)])
    old = current(item)["current_revision"]["id"]
    new = revision_payload(current(item)["current_revision"]) | dict(
        room_id="20000000-0000-0000-0000-000000000002",
        participants=[
            dict(user_id=users["EMP1"], is_required=True),
            dict(user_id=users["OPT"], is_required=True),
        ],
    )
    r, _, _ = change(item, new)
    amended = r.json()
    assert decision(amended, who="LEAD2")[0].status_code == 200
    for action, who in [("SCHEDULE_RELEASED", "SHARED"), ("PROPOSAL_APPROVED", "OPT")]:
        did = scalar(
            "SELECT d.id FROM email_deliveries d JOIN outbox_events e ON e.id=d.event_id WHERE e.proposal_id=:p AND e.event_type=:action AND d.recipient_user_id=:u",
            p=amended["proposal_id"],
            action=action,
            u=users[who],
        )
        with Session.begin() as db:
            db.execute(
                text(
                    "UPDATE email_deliveries SET status='PENDING' WHERE id=:id AND status='SKIPPED'"
                ),
                dict(id=did),
            )
        isolate(did)
        check("Đúng audience " + action, worker.process_one(settings), "SMTP_ACCEPTED")
        check(
            "Không lộ thông tin phòng/người mới trong email " + action,
            "PRIVATE_" not in server.messages[-1].as_string(),
        )
    check("SMTP không thay đổi trạng thái lịch", current(item)["lifecycle"], "ACTIVE")
    check(
        "Tóm tắt thư đã gửi chỉ cho người gửi",
        detail(amended)["email_summary"]["smtp_accepted"] >= 1,
    )
    check(
        "Lỗi được phân loại không có raw text",
        worker.error_code(smtplib.SMTPAuthenticationError(535, b"secret")),
        "SMTP_AUTH_ERROR",
    )
    finish_suite(
        "notifications",
        "Real MySQL + loopback TCP SMTP receiver. Claims, permission/address/status rechecks, retry 1/5/15 minutes, concurrent workers, expired leases, crash ambiguity and stable Message-ID. No real external mailbox/TLS provider/Windows/Docker/LAN verification.",
    )
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)
