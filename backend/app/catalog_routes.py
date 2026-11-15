"""Milestone B HTTP adapters; DTOs whitelist every response."""
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response
from . import catalog as c
from .db import Session
from .dependencies import identity
from . import schemas as s

router = APIRouter(prefix='/api/v1')
Page = Annotated[int, Query(ge=1)]
Size = Annotated[int, Query(ge=1, le=100)]
Search = Annotated[str, Query(max_length=150)]


def member(ctx=Depends(identity)):
    return c.require_member(ctx)


def admin(ctx=Depends(identity)):
    return c.require_admin(ctx)


@router.get('/directory/users', response_model=s.UserDirectoryPage, tags=['directory'])
def directory(page: Page = 1, page_size: Size = 20, q: Search = '', department_id: UUID | None = None, ctx=Depends(member)):
    return c.users(ctx, page, page_size, q, department_id, directory=True)


@router.get('/users', response_model=s.UserAdminPage, tags=['users'])
def users(page: Page = 1, page_size: Size = 20, q: Search = '', department_id: UUID | None = None, status: Literal['ACTIVE','LOCKED'] | None = None, ctx=Depends(admin)):
    return c.users(ctx, page, page_size, q, department_id, status)


@router.post('/users', response_model=s.UserAdminView, status_code=201, tags=['users'])
def create_user(data: s.UserCreate, ctx=Depends(admin)):
    return c.save_user(ctx, data)


@router.get('/users/{user_id}', response_model=s.UserAdminView, tags=['users'])
def get_user(user_id: UUID, ctx=Depends(admin)):
    with Session() as db:
        return c.user_view(db, str(user_id))


@router.put('/users/{user_id}', response_model=s.UserAdminView, tags=['users'])
def update_user(user_id: UUID, data: s.UserUpdate, ctx=Depends(admin)):
    return c.save_user(ctx, data, str(user_id))


@router.put('/users/{user_id}/temporary-password', status_code=204, tags=['users'])
def reset_password(user_id: UUID, data: s.PasswordReset, ctx=Depends(admin)):
    c.reset_password(ctx, str(user_id), data)
    return Response(status_code=204)


@router.get('/departments', response_model=s.DepartmentPage, tags=['departments'])
def departments(page: Page = 1, page_size: Size = 20, ctx=Depends(member)):
    with Session() as db:
        return c.page(c.rows(db, 'SELECT id,code,name,accepts_new_requests,row_version FROM departments ORDER BY code,id'), page, page_size)


@router.post('/departments', response_model=s.DepartmentView, status_code=201, tags=['departments'])
def create_department(data: s.DepartmentCreate, ctx=Depends(admin)):
    return c.save_department(ctx, data)


@router.get('/departments/{department_id}', response_model=s.DepartmentView, tags=['departments'])
def department(department_id: UUID, ctx=Depends(member)):
    with Session() as db:
        return c.one(db, 'SELECT id,code,name,accepts_new_requests,row_version FROM departments WHERE id=:id', id=str(department_id))


@router.put('/departments/{department_id}', response_model=s.DepartmentView, tags=['departments'])
def update_department(department_id: UUID, data: s.DepartmentUpdate, ctx=Depends(admin)):
    return c.save_department(ctx, data, str(department_id))


@router.get('/rooms', response_model=s.RoomPage, tags=['rooms'])
def rooms(page: Page = 1, page_size: Size = 20, q: Search = '', ctx=Depends(member)):
    with Session() as db:
        query = '%'+q.replace('!', '!!').replace('%', '!%').replace('_', '!_')+'%'
        found = c.rows(db, "SELECT * FROM meeting_rooms WHERE code LIKE :q ESCAPE '!' OR name LIKE :q ESCAPE '!' OR location LIKE :q ESCAPE '!' ORDER BY code,id", q=query)
        result = c.page(found, page, page_size)
        result['items'] = [c.room_view(db, r) for r in result['items']]
        return result


@router.post('/rooms', response_model=s.RoomView, status_code=201, tags=['rooms'])
def create_room(data: s.RoomCreate, ctx=Depends(admin)):
    return c.save_room(ctx, data)


# Static path must precede /rooms/{room_id}.
@router.get('/rooms/availability', response_model=s.RoomAvailabilityPage, tags=['rooms'])
def available(starts_at: s.UtcDatetime, ends_at: s.UtcDatetime, participant_count: Annotated[int, Query(ge=1, le=65535)],
              equipment_codes: Annotated[list[str], Query(max_length=50)] = [], exclude_schedule_id: UUID | None = None,
              page: Page = 1, page_size: Size = 20, ctx=Depends(member)):
    return c.find_rooms(ctx, starts_at, ends_at, participant_count, equipment_codes, exclude_schedule_id, page, page_size)


@router.get('/rooms/{room_id}', response_model=s.RoomView, tags=['rooms'])
def room(room_id: UUID, ctx=Depends(member)):
    with Session() as db:
        return c.room_view(db, c.one(db, 'SELECT * FROM meeting_rooms WHERE id=:id', id=str(room_id)))


@router.put('/rooms/{room_id}', response_model=s.RoomView, tags=['rooms'])
def update_room(room_id: UUID, data: s.RoomUpdate, ctx=Depends(admin)):
    return c.save_room(ctx, data, str(room_id))


@router.get('/rooms/{room_id}/policies', response_model=s.RoomPolicyPage, tags=['rooms'])
def policies(room_id: UUID, page: Page = 1, page_size: Size = 20, ctx=Depends(admin)):
    with Session() as db:
        c.one(db, 'SELECT id FROM meeting_rooms WHERE id=:id', id=str(room_id))
        return c.page(list(reversed(c.policies(db, str(room_id)))), page, page_size)


@router.post('/rooms/{room_id}/policies', response_model=s.RoomPolicyView, status_code=201, tags=['rooms'])
def create_policy(room_id: UUID, data: s.RoomPolicyCreate, ctx=Depends(admin)):
    return c.save_policy(ctx, str(room_id), data)


@router.get('/rooms/{room_id}/approvers', response_model=s.RoomApproversView, tags=['assignments'])
def room_approvers(room_id: UUID, ctx=Depends(admin)):
    with Session() as db:
        return c.scope_view(db, 'room', str(room_id))


@router.put('/rooms/{room_id}/approvers', response_model=s.RoomApproversView, tags=['assignments'])
def set_room_approvers(room_id: UUID, data: s.RoomApproversUpdate, ctx=Depends(admin)):
    return c.save_scope(ctx, 'room', str(room_id), data)


@router.get('/departments/{department_id}/approvers', response_model=s.DepartmentApproversView, tags=['assignments'])
def department_approvers(department_id: UUID, ctx=Depends(admin)):
    with Session() as db:
        return c.scope_view(db, 'department', str(department_id))


@router.put('/departments/{department_id}/approvers', response_model=s.DepartmentApproversView, tags=['assignments'])
def set_department_approvers(department_id: UUID, data: s.DepartmentApproversUpdate, ctx=Depends(admin)):
    return c.save_scope(ctx, 'department', str(department_id), data)


@router.get('/calendar', response_model=s.CalendarPage, tags=['calendar'])
def calendar(period_from: Annotated[s.UtcDatetime, Query(alias='from')], period_to: Annotated[s.UtcDatetime, Query(alias='to')],
             room_id: UUID | None = None, user_id: UUID | None = None, page: Page = 1, page_size: Size = 20, ctx=Depends(member)):
    return c.calendar(ctx, period_from, period_to, room_id, user_id, page, page_size)
