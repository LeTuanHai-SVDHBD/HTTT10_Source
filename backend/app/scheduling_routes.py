from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response

from . import schemas as s, scheduling as service
from .dependencies import identity

router = APIRouter(prefix="/api/v1", tags=["scheduling"])
Key = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=16,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
    ),
]
Page = Annotated[int, Query(ge=1)]
Size = Annotated[int, Query(ge=1, le=100)]


def command_response(response, result):
    receipt, replayed = result
    if replayed:
        response.headers["Idempotency-Replayed"] = "true"
    return receipt


@router.post("/availability/check", response_model=s.AvailabilityResult)
def check(data: s.AvailabilityCheck, ctx=Depends(identity)):
    return service.preflight(ctx, data)


@router.post("/meeting-proposals", response_model=s.CommandReceipt, status_code=201)
def submit_meeting(
    data: s.SubmitMeeting, response: Response, key: Key, ctx=Depends(identity)
):
    return command_response(response, service.submit(ctx, data, key, "SUBMIT_MEETING"))


@router.post("/work-proposals", response_model=s.CommandReceipt, status_code=201)
def submit_work(
    data: s.SubmitWork, response: Response, key: Key, ctx=Depends(identity)
):
    return command_response(response, service.submit(ctx, data, key, "SUBMIT_WORK"))


@router.get("/proposals", response_model=s.ProposalPage)
def proposals(
    scope: Literal["MINE", "RELATED", "REVIEWABLE"] = "MINE",
    status: (
        Literal["PENDING", "APPROVED", "REJECTED", "WITHDRAWN", "EXPIRED"] | None
    ) = None,
    page: Page = 1,
    page_size: Size = 20,
    ctx=Depends(identity),
):
    return service.list_proposals(ctx, scope, status, page, page_size)


@router.get("/proposals/{proposal_id}", response_model=s.ProposalDetail)
def proposal(proposal_id: UUID, ctx=Depends(identity)):
    return service.get_proposal(ctx, str(proposal_id))


@router.post("/proposals/{proposal_id}/decisions", response_model=s.CommandReceipt)
def decide(
    proposal_id: UUID,
    data: s.ProposalDecision,
    response: Response,
    key: Key,
    ctx=Depends(identity),
):
    return command_response(response, service.resolve(ctx, str(proposal_id), data, key))


@router.post("/proposals/{proposal_id}/withdrawals", response_model=s.CommandReceipt)
def withdraw(
    proposal_id: UUID,
    data: s.ProposalWithdrawal,
    response: Response,
    key: Key,
    ctx=Depends(identity),
):
    return command_response(
        response, service.resolve(ctx, str(proposal_id), data, key, withdrawing=True)
    )


@router.get("/schedules", response_model=s.SchedulePage)
def schedules(
    relation: Literal["CREATED", "PARTICIPATING", "RELATED"] = "RELATED",
    lifecycle: Literal["UNCONFIRMED", "ACTIVE", "CANCELLED"] | None = None,
    page: Page = 1,
    page_size: Size = 20,
    ctx=Depends(identity),
):
    return service.list_schedules(ctx, relation, lifecycle, page, page_size)


@router.get("/schedules/{schedule_id}", response_model=s.ScheduleView)
def schedule(schedule_id: UUID, ctx=Depends(identity)):
    return service.get_schedule(ctx, str(schedule_id))


@router.get("/schedules/{schedule_id}/revisions", response_model=s.RevisionPage)
def revisions(
    schedule_id: UUID, page: Page = 1, page_size: Size = 20, ctx=Depends(identity)
):
    return service.revisions(ctx, str(schedule_id), page, page_size)


@router.get(
    "/schedules/{schedule_id}/revisions/{revision_id}", response_model=s.RevisionView
)
def revision(schedule_id: UUID, revision_id: UUID, ctx=Depends(identity)):
    return service.revisions(ctx, str(schedule_id), 1, 1, str(revision_id))


@router.get("/schedules/{schedule_id}/audit", response_model=s.AuditPage)
def audit(
    schedule_id: UUID, page: Page = 1, page_size: Size = 20, ctx=Depends(identity)
):
    return service.audit_history(ctx, str(schedule_id), page, page_size)


@router.post(
    "/schedules/{schedule_id}/change-proposals",
    response_model=s.CommandReceipt,
    status_code=201,
)
def change(
    schedule_id: UUID,
    data: s.ChangeRequest,
    response: Response,
    key: Key,
    ctx=Depends(identity),
):
    return command_response(
        response, service.submit_amendment(ctx, str(schedule_id), data, key)
    )


@router.post(
    "/schedules/{schedule_id}/meeting-cancellations", response_model=s.CommandReceipt
)
def cancel_meeting(
    schedule_id: UUID,
    data: s.CancellationRequest,
    response: Response,
    key: Key,
    ctx=Depends(identity),
):
    return command_response(
        response, service.cancel_meeting(ctx, str(schedule_id), data, key)
    )


@router.post(
    "/schedules/{schedule_id}/work-cancellation-proposals",
    response_model=s.CommandReceipt,
    status_code=201,
)
def cancel_work(
    schedule_id: UUID,
    data: s.CancellationRequest,
    response: Response,
    key: Key,
    ctx=Depends(identity),
):
    return command_response(
        response,
        service.submit_amendment(ctx, str(schedule_id), data, key, cancelling=True),
    )
