from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartParser, MultiPartException
from starlette.responses import StreamingResponse

from . import documents as service, document_storage as storage, schemas as s
from .dependencies import identity
from .services import Failure

router = APIRouter(prefix="/api/v1", tags=["documents"])
Page = Annotated[int, Query(ge=1)]
Size = Annotated[int, Query(ge=1, le=100)]


class LimitedParser(MultiPartParser):
    def on_part_begin(self):
        super().on_part_begin()
        self.part_bytes = 0

    def on_part_data(self, data, start, end):
        self.part_bytes += end - start
        if self._current_part.field_name == "metadata" and self.part_bytes > 16384:
            raise MultiPartException("Metadata too large")
        if self._current_part.file is not None and self.part_bytes > storage.MAX_SIZE:
            raise Failure(413, "FILE_TOO_LARGE", "Mỗi tệp tối đa 20 MiB.")
        super().on_part_data(data, start, end)


async def form_upload(request, ctx, model, schedule_id=None, document_id=None):
    await run_in_threadpool(service.pre_upload, ctx, schedule_id, document_id)
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "multipart/form-data"
    ):
        raise Failure(
            415,
            "MULTIPART_REQUIRED",
            "Cần gửi metadata và file bằng multipart/form-data.",
        )

    async def bounded():
        count = 0
        async for chunk in request.stream():
            count += len(chunk)
            if count > storage.MAX_SIZE + 256 * 1024:
                raise Failure(
                    413, "FILE_TOO_LARGE", "Dung lượng yêu cầu vượt giới hạn."
                )
            yield chunk

    parser = LimitedParser(
        request.headers, bounded(), max_files=2, max_fields=1, max_part_size=16384
    )
    form = None
    try:
        form = await parser.parse()
        fields = form.multi_items()
        if (
            len(fields) != 2
            or {k for k, v in fields} != {"metadata", "file"}
            or not isinstance(form["metadata"], (str, UploadFile))
            or not isinstance(form["file"], UploadFile)
        ):
            raise Failure(
                422, "INVALID_MULTIPART", "Cần đúng một metadata JSON và một tệp file."
            )
        try:
            value = form["metadata"]
            if isinstance(value, UploadFile):
                value = await value.read(16385)
            metadata = model.model_validate_json(value)
        except ValidationError as exc:
            raise Failure(
                422,
                "VALIDATION_ERROR",
                "Metadata tài liệu chưa hợp lệ.",
                field_errors=[
                    dict(
                        path="metadata." + ".".join(map(str, e["loc"])), code=e["type"]
                    )
                    for e in exc.errors()
                ],
            ) from exc
        return await run_in_threadpool(
            service.upload, ctx, metadata, form["file"], schedule_id, document_id
        )
    except MultiPartException as exc:
        raise Failure(
            400, "INVALID_MULTIPART", "Nội dung multipart chưa hợp lệ."
        ) from exc
    finally:
        if form:
            await form.close()
        # Also close spooled parts on early parse/validation failures.
        for f in parser._files_to_close_on_error:
            f.close()


def multipart_schema(metadata):
    return {
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["metadata", "file"],
                        "properties": {
                            "metadata": metadata.model_json_schema(),
                            "file": {"type": "string", "format": "binary"},
                        },
                    },
                    "encoding": {"metadata": {"contentType": "application/json"}},
                }
            },
        }
    }


@router.get("/schedules/{schedule_id}/documents", response_model=s.DocumentPage)
def documents(
    schedule_id: UUID,
    context_revision_id: UUID | None = None,
    include_hidden: bool = False,
    page: Page = 1,
    page_size: Size = 20,
    ctx=Depends(identity),
):
    return service.list_documents(
        ctx,
        str(schedule_id),
        str(context_revision_id) if context_revision_id else None,
        include_hidden,
        page,
        page_size,
    )


@router.post(
    "/schedules/{schedule_id}/documents",
    response_model=s.DocumentVersionView,
    status_code=201,
    openapi_extra=multipart_schema(s.DocumentUploadMetadata),
)
async def upload(schedule_id: UUID, request: Request, ctx=Depends(identity)):
    return await form_upload(
        request, ctx, s.DocumentUploadMetadata, schedule_id=str(schedule_id)
    )


@router.get("/documents/{document_id}/versions", response_model=s.DocumentVersionPage)
def versions(
    document_id: UUID,
    context_revision_id: UUID | None = None,
    page: Page = 1,
    page_size: Size = 20,
    ctx=Depends(identity),
):
    return service.list_versions(
        ctx,
        str(document_id),
        str(context_revision_id) if context_revision_id else None,
        page,
        page_size,
    )


@router.post(
    "/documents/{document_id}/versions",
    response_model=s.DocumentVersionView,
    status_code=201,
    openapi_extra=multipart_schema(s.DocumentVersionUpload),
)
async def upload_version(document_id: UUID, request: Request, ctx=Depends(identity)):
    return await form_upload(
        request, ctx, s.DocumentVersionUpload, document_id=str(document_id)
    )


@router.post("/documents/{document_id}/hides", status_code=204)
def hide(document_id: UUID, data: s.DocumentHide, ctx=Depends(identity)):
    service.hide(ctx, str(document_id), data)
    return Response(status_code=204)


@router.get(
    "/documents/{document_id}/versions/{version_id}/content",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"}
                }
            }
        }
    },
)
def download(document_id: UUID, version_id: UUID, ctx=Depends(identity)):
    f, v = service.content(ctx, str(document_id), str(version_id))

    def chunks():
        try:
            while chunk := f.read(65536):
                yield chunk
        finally:
            f.close()

    from starlette.background import BackgroundTask

    return StreamingResponse(
        chunks(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": 'attachment; filename="document.'
            + v["extension"]
            + "\"; filename*=UTF-8''"
            + quote(v["original_filename"], safe=""),
            "Content-Length": str(v["size_bytes"]),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
        background=BackgroundTask(f.close),
    )
