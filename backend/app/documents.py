"""Meeting documents retain the permission context of each immutable version."""

from uuid import uuid4

from . import (
    catalog as c,
    document_storage as storage,
    scheduling as schedule,
    security,
)
from .db import Session
from .services import Failure


def root_for(db, schedule_id, lock=False):
    return c.one(
        db,
        "SELECT * FROM schedule_roots WHERE id=:id" + (" FOR UPDATE" if lock else ""),
        id=schedule_id,
    )


def revision_for(db, root, revision_id):
    return c.one(
        db,
        "SELECT * FROM schedule_revisions WHERE schedule_id=:s AND id=:r",
        s=root["id"],
        r=revision_id,
    )


def writable(db, root, revision_id):
    if root["kind"] != "MEETING" or root["cancelled_at"]:
        return False
    if root["current_revision_id"] == revision_id:
        return True
    return bool(
        c.rows(
            db,
            """SELECT id FROM approval_proposals WHERE schedule_id=:s
        AND candidate_revision_id=:r AND status='PENDING' AND expires_at>:now""",
            s=root["id"],
            r=revision_id,
            now=security.now(),
        )
    )


def require_owner(root, ctx):
    c.require_member(ctx)
    if root["created_by"] != ctx[0]["id"]:
        raise Failure(403, "FORBIDDEN", "Chỉ người tạo lịch được quản lý tài liệu.")
    if root["kind"] != "MEETING":
        raise Failure(409, "MEETING_REQUIRED", "Chỉ lịch họp có tài liệu họp.")


def pre_upload(ctx, schedule_id=None, document_id=None):
    with Session() as db:
        if document_id:
            doc = c.one(
                db, "SELECT * FROM meeting_documents WHERE id=:id", id=document_id
            )
            schedule_id = doc["schedule_id"]
        root = root_for(db, schedule_id)
        require_owner(root, ctx)
        if root["cancelled_at"]:
            raise Failure(409, "DOCUMENT_READ_ONLY", "Hồ sơ lịch đã hủy chỉ được đọc.")


def visible(db, ctx, root, versions, context=None):
    allowed = {}
    result = []
    for v in versions:
        rid = v["context_revision_id"]
        if context and context != rid:
            continue
        if rid not in allowed:
            allowed[rid] = schedule.can_read_revision(
                db, ctx[0], root, revision_for(db, root, rid)
            )
        if allowed[rid]:
            result.append(v)
    return result


def version_view(db, v):
    return dict(
        id=v["id"],
        document_id=v["document_id"],
        context_revision_id=v["context_revision_id"],
        version_no=v["version_no"],
        original_filename=v["original_filename"],
        extension=v["extension"],
        mime_type=v["mime_type"],
        size_bytes=v["size_bytes"],
        uploaded_by=schedule.user_ref(db, v["uploaded_by"]),
        created_at=c.aware(v["created_at"]),
    )


def versions_for(db, document_id):
    return c.rows(
        db,
        "SELECT * FROM document_versions WHERE document_id=:id ORDER BY version_no",
        id=document_id,
    )


def document_view(db, ctx, root, doc, found, all_versions):
    latest = all_versions[-1]
    actions = []
    if (
        ctx[0]["id"] == root["created_by"]
        and any(v["id"] == latest["id"] for v in found)
        and not doc["is_hidden"]
        and not root["cancelled_at"]
    ):
        if root["current_revision_id"] or c.rows(
            db,
            "SELECT id FROM approval_proposals WHERE schedule_id=:s AND status='PENDING' AND expires_at>:now AND candidate_revision_id IS NOT NULL",
            s=root["id"],
            now=security.now(),
        ):
            actions.append("UPLOAD_VERSION")
        if writable(db, root, latest["context_revision_id"]):
            actions.append("HIDE")
    # The original label belongs to version 1's context, never a newly added audience.
    label = (
        doc["display_name"]
        if any(v["version_no"] == 1 for v in found)
        else found[-1]["original_filename"]
    )
    return dict(
        id=doc["id"],
        display_name=label,
        context_revision_id=found[-1]["context_revision_id"],
        is_hidden=bool(doc["is_hidden"]),
        versions=[version_view(db, v) for v in found],
        allowed_actions=actions,
    )


def list_documents(ctx, schedule_id, context, hidden, page, size):
    c.require_member(ctx)
    with Session() as db:
        root = root_for(db, schedule_id)
        if root["kind"] != "MEETING":
            raise Failure(404, "NOT_FOUND", "Không tìm thấy tài liệu họp.")
        # Empty listings must not act as a schedule/context existence oracle.
        revisions = c.rows(
            db, "SELECT * FROM schedule_revisions WHERE schedule_id=:id", id=schedule_id
        )
        if not any(
            (not context or r["id"] == context)
            and schedule.can_read_revision(db, ctx[0], root, r)
            for r in revisions
        ):
            raise Failure(404, "NOT_FOUND", "Không tìm thấy tài liệu họp.")
        items = []
        for doc in c.rows(
            db,
            "SELECT * FROM meeting_documents WHERE schedule_id=:id ORDER BY created_at,id",
            id=schedule_id,
        ):
            if doc["is_hidden"] and not hidden:
                continue
            versions = versions_for(db, doc["id"])
            found = visible(db, ctx, root, versions, context)
            if found:
                items.append(document_view(db, ctx, root, doc, found, versions))
        return c.page(items, page, size)


def list_versions(ctx, document_id, context, page, size):
    c.require_member(ctx)
    with Session() as db:
        doc = c.one(db, "SELECT * FROM meeting_documents WHERE id=:id", id=document_id)
        root = root_for(db, doc["schedule_id"])
        found = visible(db, ctx, root, versions_for(db, document_id), context)
        if not found:
            raise Failure(404, "NOT_FOUND", "Không tìm thấy tài liệu.")
        return c.page([version_view(db, v) for v in found], page, size)


def upload(ctx, data, file, schedule_id=None, document_id=None):
    key = uuid4().hex + ".blob"
    staged = None
    with storage.guard(key) as conn:
        try:
            staged, info = storage.stage(file, key)
            with Session(bind=conn) as db:
                with db.begin():
                    if document_id:
                        # Resolve immutable parent ID before the root lock, then lock root/document.
                        parent = c.one(
                            db,
                            "SELECT schedule_id FROM meeting_documents WHERE id=:id",
                            id=document_id,
                        )
                        schedule_id = parent["schedule_id"]
                    root = root_for(db, schedule_id, True)
                    doc = (
                        c.one(
                            db,
                            "SELECT * FROM meeting_documents WHERE id=:id FOR UPDATE",
                            id=document_id,
                        )
                        if document_id
                        else None
                    )
                    c.one(
                        db,
                        "SELECT id FROM users WHERE id=:id FOR UPDATE",
                        id=ctx[0]["id"],
                    )
                    actor = schedule.fresh_actor(db, ctx)
                    require_owner(root, (actor, ctx[1]))
                    rid = str(data.context_revision_id)
                    revision_for(db, root, rid)
                    if not writable(db, root, rid):
                        raise Failure(
                            409,
                            "DOCUMENT_READ_ONLY",
                            "Bản lịch này chỉ được đọc tài liệu.",
                        )
                    version_no = 1
                    if doc:
                        latest = versions_for(db, document_id)[-1]
                        if latest["id"] != str(data.expected_latest_version_id):
                            raise Failure(
                                409,
                                "DOCUMENT_VERSION_CHANGED",
                                "Tài liệu đã có phiên bản mới. Vui lòng tải lại.",
                            )
                        if doc["is_hidden"]:
                            raise Failure(
                                409,
                                "DOCUMENT_READ_ONLY",
                                "Tài liệu đã ẩn chỉ được đọc lịch sử.",
                            )
                        version_no = latest["version_no"] + 1
                    else:
                        document_id = c.uid()
                        c.run(
                            db,
                            "INSERT INTO meeting_documents(id,schedule_id,display_name) VALUES(:id,:s,:n)",
                            id=document_id,
                            s=schedule_id,
                            n=data.display_name.strip(),
                        )
                    vid = c.uid()
                    c.run(
                        db,
                        """INSERT INTO document_versions(id,document_id,schedule_id,context_revision_id,version_no,
                        original_filename,extension,mime_type,size_bytes,sha256,storage_key,uploaded_by)
                        VALUES(:id,:d,:s,:r,:v,:original_filename,:extension,:mime_type,:size_bytes,:sha256,:storage_key,:u)""",
                        id=vid,
                        d=document_id,
                        s=schedule_id,
                        r=rid,
                        v=version_no,
                        u=actor["id"],
                        **info
                    )
                    schedule.schedule_audit(
                        db,
                        actor["id"],
                        (
                            "DOCUMENT_VERSION_UPLOADED"
                            if version_no > 1
                            else "DOCUMENT_UPLOADED"
                        ),
                        schedule_id,
                        rid,
                    )
                    storage.publish(staged, key)
            with Session(bind=conn) as db:
                result = version_view(
                    db,
                    c.one(db, "SELECT * FROM document_versions WHERE id=:id", id=vid),
                )
            return result
        except BaseException:
            storage.discard_unreferenced(conn, key)
            raise
        finally:
            if staged:
                staged.unlink(missing_ok=True)


def hide(ctx, document_id, data):
    def action():
        with Session.begin() as db:
            parent = c.one(
                db,
                "SELECT schedule_id FROM meeting_documents WHERE id=:id",
                id=document_id,
            )
            root = root_for(db, parent["schedule_id"], True)
            doc = c.one(
                db,
                "SELECT * FROM meeting_documents WHERE id=:id FOR UPDATE",
                id=document_id,
            )
            c.one(db, "SELECT id FROM users WHERE id=:id FOR UPDATE", id=ctx[0]["id"])
            actor = schedule.fresh_actor(db, ctx)
            require_owner(root, (actor, ctx[1]))
            latest = versions_for(db, document_id)[-1]
            if latest["id"] != str(data.expected_latest_version_id):
                raise Failure(
                    409,
                    "DOCUMENT_VERSION_CHANGED",
                    "Tài liệu đã có phiên bản mới. Vui lòng tải lại.",
                )
            if doc["is_hidden"] or not writable(
                db, root, latest["context_revision_id"]
            ):
                raise Failure(409, "DOCUMENT_READ_ONLY", "Tài liệu hiện chỉ được đọc.")
            c.run(
                db,
                "UPDATE meeting_documents SET is_hidden=1,hidden_by=:u,hidden_at=:now,hide_reason=:reason WHERE id=:id",
                u=actor["id"],
                now=security.now(),
                reason=data.reason.strip(),
                id=document_id,
            )
            schedule.schedule_audit(
                db,
                actor["id"],
                "DOCUMENT_HIDDEN",
                root["id"],
                latest["context_revision_id"],
            )

    schedule.transaction_retry(action)


def content(ctx, document_id, version_id):
    c.require_member(ctx)
    with Session() as db:
        version = c.one(
            db,
            "SELECT * FROM document_versions WHERE document_id=:d AND id=:v",
            d=document_id,
            v=version_id,
        )
        root = root_for(db, version["schedule_id"])
        if not visible(db, ctx, root, [version]):
            raise Failure(404, "NOT_FOUND", "Không tìm thấy tệp.")
        return storage.open_verified(version), version
