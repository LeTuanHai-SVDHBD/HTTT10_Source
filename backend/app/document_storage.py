"""Private immutable objects. No user-controlled path ever reaches the filesystem."""

import hashlib
import os
import re
import stat
import time
import warnings
from contextlib import contextmanager
from pathlib import Path
from zipfile import ZipFile

from defusedxml.ElementTree import fromstring
from PIL import Image
from pypdf import PdfReader
from sqlalchemy import text

from .db import engine
from .services import Failure

MAX_SIZE = 20 * 1024 * 1024
MIMES = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
KEY = re.compile(r"^[a-f0-9]{32}\.blob$")


def directories():
    root = Path(
        os.getenv(
            "DOCUMENT_STORAGE_DIR",
            str(Path(__file__).resolve().parents[1] / "data/documents"),
        )
    )
    for path in (root, root / "staging", root / "objects"):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def filename(value):
    # Browsers may submit a Windows path. Never keep path segments or header controls.
    value = (value or "").replace("\\", "/").rsplit("/", 1)[-1]
    value = "".join(c for c in value if c.isprintable() and c not in "/\\")
    if not value.strip() or len(value) > 255 or "." not in value:
        raise Failure(
            422, "INVALID_FILENAME", "Tên tệp phải có phần mở rộng và tối đa 255 ký tự."
        )
    return value


@contextmanager
def guard(key, timeout=5):
    # Named locks survive transaction commits. Cleaner and writer use this same lock.
    with engine.connect() as conn:
        name = "httt10-doc-" + key[:32]
        acquired = conn.scalar(text("SELECT GET_LOCK(:n,:t)"), dict(n=name, t=timeout))
        conn.commit()
        if acquired != 1:
            raise Failure(503, "STORAGE_BUSY", "Kho tệp đang bận. Vui lòng thử lại.")
        try:
            yield conn
        finally:
            try:
                if conn.in_transaction():
                    conn.rollback()
                conn.execute(text("SELECT RELEASE_LOCK(:n)"), dict(n=name))
                conn.commit()
            except Exception:
                # Invalidate rather than returning a connection holding an advisory lock.
                conn.invalidate()


def validate(path, extension):
    try:
        if extension == "pdf":
            with path.open("rb") as f:
                if f.read(5) != b"%PDF-":
                    raise ValueError()
                reader = PdfReader(f, strict=True)
                if reader.is_encrypted or not 1 <= len(reader.pages) <= 2000:
                    raise ValueError()
        elif extension in ("png", "jpg", "jpeg"):
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as im:
                    if (
                        im.format != ("PNG" if extension == "png" else "JPEG")
                        or im.width * im.height > 25_000_000
                    ):
                        raise ValueError()
                    im.verify()
                with Image.open(path) as im:
                    im.load()
        else:
            main, root_tag, main_type = {
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
            with ZipFile(path) as z:
                infos = z.infolist()
                if (
                    len(infos) > 2000
                    or sum(i.file_size for i in infos) > 100 * 1024 * 1024
                ):
                    raise ValueError()
                names = [i.filename for i in infos]
                if len(names) != len(set(names)):
                    raise ValueError()
                for i in infos:
                    if (
                        i.flag_bits & 1
                        or i.filename.startswith(("/", "\\"))
                        or ".." in i.filename.replace("\\", "/").split("/")
                        or i.file_size > 30 * 1024 * 1024
                        or i.file_size > max(i.compress_size, 1) * 1000
                    ):
                        raise ValueError()
                    if "vbaproject" in i.filename.lower():
                        raise ValueError()
                    # Reading every member checks its CRC without extracting any path.
                    with z.open(i) as member:
                        while member.read(65536):
                            pass
                for name in ("[Content_Types].xml", "_rels/.rels", main):
                    if z.getinfo(name).file_size > 8 * 1024 * 1024:
                        raise ValueError()
                types = fromstring(z.read("[Content_Types].xml"))
                if not any(
                    x.attrib.get("PartName") == "/" + main
                    and x.attrib.get("ContentType") == main_type
                    for x in types
                ):
                    raise ValueError()
                relations = fromstring(z.read("_rels/.rels"))
                if not any(
                    x.attrib.get("Type", "").endswith("/officeDocument")
                    and x.attrib.get("Target", "").lstrip("/") == main
                    and x.attrib.get("TargetMode") != "External"
                    for x in relations
                ):
                    raise ValueError()
                if fromstring(z.read(main)).tag.rsplit("}", 1)[-1] != root_tag:
                    raise ValueError()
    except Exception as exc:
        raise Failure(
            422,
            "INVALID_FILE_CONTENT",
            "Nội dung tệp không khớp định dạng hoặc vượt giới hạn xử lý an toàn.",
        ) from exc


def stage(upload, key):
    root = directories()
    path = root / "staging" / (key[:32] + ".part")
    name = filename(upload.filename)
    extension = name.rsplit(".", 1)[-1].lower()
    if extension not in MIMES:
        raise Failure(
            415,
            "UNSUPPORTED_FILE_TYPE",
            "Chỉ nhận PDF, DOCX, PPTX, XLSX, JPG, JPEG, PNG.",
        )
    size, digest = 0, hashlib.sha256()
    try:
        with path.open("xb") as f:
            os.chmod(path, 0o600)
            while chunk := upload.file.read(65536):
                size += len(chunk)
                if size > MAX_SIZE:
                    raise Failure(413, "FILE_TOO_LARGE", "Mỗi tệp tối đa 20 MiB.")
                digest.update(chunk)
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
        if not size:
            raise Failure(422, "EMPTY_FILE", "Không nhận tệp rỗng.")
        validate(path, extension)
        return path, dict(
            original_filename=name,
            extension=extension,
            mime_type=MIMES[extension],
            size_bytes=size,
            sha256=digest.hexdigest(),
            storage_key=key,
        )
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def publish(path, key):
    target = directories() / "objects" / key
    # Reserve the name first; an existing immutable object is never overwritten.
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        os.replace(path, target)
        fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def discard_unreferenced(conn, key):
    # On an ambiguous commit or broken connection, leave bytes for the cleaner.
    try:
        if conn.in_transaction():
            conn.rollback()
        found = conn.scalar(
            text("SELECT COUNT(*) FROM document_versions WHERE storage_key=:k"),
            dict(k=key),
        )
        conn.commit()
        if not found:
            (directories() / "objects" / key).unlink(missing_ok=True)
    except Exception:
        pass


def open_verified(version):
    key = version["storage_key"]
    if not KEY.fullmatch(key):
        raise Failure(
            503, "FILE_UNAVAILABLE", "Tệp hiện chưa sẵn sàng. Liên hệ quản trị viên."
        )
    f = None
    try:
        fd = os.open(
            directories() / "objects" / key, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        )
        f = os.fdopen(fd, "rb")
        if (
            not stat.S_ISREG(os.fstat(fd).st_mode)
            or os.fstat(fd).st_size != version["size_bytes"]
        ):
            raise ValueError()
        digest = hashlib.file_digest(f, "sha256").hexdigest()
        if digest != version["sha256"]:
            raise ValueError()
        f.seek(0)
        return f
    except Exception as exc:
        if f:
            f.close()
        raise Failure(
            503, "FILE_UNAVAILABLE", "Tệp hiện chưa sẵn sàng. Liên hệ quản trị viên."
        ) from exc


def cleanup(apply=False, grace_seconds=86400):
    counts = dict(orphan_objects=0, stale_staging=0, removed=0, busy=0)
    root = directories()
    for folder, pattern, label in [
        ("objects", "*.blob", "orphan_objects"),
        ("staging", "*.part", "stale_staging"),
    ]:
        for path in (root / folder).glob(pattern):
            key = path.stem + ".blob"
            if (
                not KEY.fullmatch(key)
                or path.is_symlink()
                or time.time() - path.stat().st_mtime < grace_seconds
            ):
                continue
            try:
                with guard(key, 0) as conn:
                    # Recheck after acquiring the writer's lock.
                    if (
                        not path.exists()
                        or time.time() - path.stat().st_mtime < grace_seconds
                    ):
                        continue
                    found = conn.scalar(
                        text(
                            "SELECT COUNT(*) FROM document_versions WHERE storage_key=:k"
                        ),
                        dict(k=key),
                    )
                    conn.commit()
                    if folder == "objects" and found:
                        continue
                    counts[label] += 1
                    if apply:
                        path.unlink()
                        counts["removed"] += 1
            except Failure:
                counts["busy"] += 1
    return counts
