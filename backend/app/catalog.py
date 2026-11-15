"""Milestone B: catalog administration and privacy-safe calendar queries.

All values are bound parameters. Baseline tables remain canonical; no parallel
create_all schema. Administrative writes serialize on the baseline ledger row,
then lock the resource and affected users. Schedule approval (milestone C) must
lock the same room row before checking its policy and availability.
"""
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import text

from . import security
from .db import Session
from .services import Failure

LOCAL_ZONE = ZoneInfo('Asia/Ho_Chi_Minh')


def rows(db, sql, **params):
    result = [dict(r) for r in db.execute(text(sql), params).mappings()]
    for row in result:
        for key in ('accepts_new_requests', 'must_change_password', 'is_closed', 'is_active', 'is_required'):
            if key in row:
                row[key] = bool(row[key])
    return result


def one(db, sql, **params):
    result = rows(db, sql, **params)
    if not result:
        raise Failure(404, 'NOT_FOUND', 'Không tìm thấy dữ liệu.')
    return result[0]


def run(db, sql, **params):
    return db.execute(text(sql), params)


def uid():
    return str(uuid4())


def utc(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def aware(value):
    return value.replace(tzinfo=timezone.utc)


def version(row, expected):
    if row['row_version'] != expected:
        raise Failure(409, 'STALE_VERSION', 'Dữ liệu đã thay đổi. Vui lòng tải lại trước khi lưu.')


def audit(db, actor, action, kind, entity_id, **metadata):
    run(db, '''INSERT INTO audit_entries
        (id,actor_user_id,action,entity_type,entity_id,safe_metadata)
        VALUES(:id,:actor,:action,:kind,:entity,CAST(:meta AS JSON))''',
        id=uid(), actor=actor, action=action, kind=kind, entity=entity_id,
        meta=json.dumps(metadata, ensure_ascii=False))


def require_member(ctx):
    if ctx[0]['must_change_password']:
        raise Failure(403, 'PASSWORD_CHANGE_REQUIRED', 'Vui lòng đổi mật khẩu tạm trước khi sử dụng chức năng này.')
    return ctx


def require_admin(ctx):
    require_member(ctx)
    if 'ADMIN' not in ctx[0]['roles']:
        raise Failure(403, 'FORBIDDEN', 'Chức năng này dành cho quản trị viên.')
    return ctx


def admin_write(db, ctx):
    require_admin(ctx)
    # A stable, pre-existing row also protects concurrent demotions of two admins.
    one(db, "SELECT version FROM schema_migrations WHERE version='001_baseline' FOR UPDATE")
    claims = ctx[1]
    actor = one(db, 'SELECT * FROM users WHERE id=:id', id=claims['sub'])
    valid_session = rows(db, '''SELECT id FROM auth_sessions WHERE id=:sid
        AND user_id=:u AND revoked_at IS NULL AND expires_at>:now AND auth_version=:av''',
        sid=claims['sid'], u=actor['id'], now=security.now(), av=claims['av'])
    roles = rows(db, "SELECT role FROM user_roles WHERE user_id=:u AND role='ADMIN'", u=actor['id'])
    if actor['status'] != 'ACTIVE' or actor['auth_version'] != claims['av'] or not valid_session:
        raise Failure(401, 'SESSION_INVALID', 'Phiên đăng nhập không còn hợp lệ.')
    if actor['must_change_password'] or not roles:
        raise Failure(403, 'FORBIDDEN', 'Quyền thao tác đã thay đổi. Vui lòng tải lại.')
    return actor['id']


def page(items, page, page_size):
    return dict(items=items[(page-1)*page_size:page*page_size], page=page,
                page_size=page_size, total=len(items))


def query_page(db, sql, params, page_no, page_size):
    total = db.scalar(text('SELECT COUNT(*) FROM ('+sql+') AS result_count'), params)
    items = rows(db, sql+' ORDER BY full_name,id LIMIT :limit OFFSET :offset',
                 **params, limit=page_size, offset=(page_no-1)*page_size)
    return dict(items=items, page=page_no, page_size=page_size, total=total)


def user_view(db, user_id):
    r = one(db, '''SELECT id,employee_code,full_name,email,department_id,status,
        row_version,must_change_password FROM users WHERE id=:id''', id=user_id)
    r['roles'] = [x['role'] for x in rows(db, 'SELECT role FROM user_roles WHERE user_id=:id ORDER BY role', id=user_id)]
    return r


def users(ctx, page_no, page_size, q='', department_id=None, status=None, directory=False):
    require_member(ctx) if directory else require_admin(ctx)
    params = {'q': '%'+q.replace('!', '!!').replace('%', '!%').replace('_', '!_')+'%'}
    where = ["(full_name LIKE :q ESCAPE '!' OR employee_code LIKE :q ESCAPE '!'"+
             (')' if directory else " OR email LIKE :q ESCAPE '!')")]
    if department_id:
        where.append('department_id=:d'); params['d'] = str(department_id)
    if directory:
        where.append("status='ACTIVE'")
    elif status:
        where.append('status=:status'); params['status'] = status
    fields = 'id,employee_code,full_name,department_id' if directory else 'id,employee_code,full_name,email,department_id,status,row_version,must_change_password'
    with Session() as db:
        result = query_page(db, 'SELECT '+fields+' FROM users WHERE '+' AND '.join(where), params, page_no, page_size)
        if not directory:
            for r in result['items']:
                r['roles'] = [x['role'] for x in rows(db, 'SELECT role FROM user_roles WHERE user_id=:id ORDER BY role', id=r['id'])]
        return result


def revoke(db, user_id):
    run(db, 'UPDATE users SET auth_version=auth_version+1 WHERE id=:id', id=user_id)
    run(db, 'UPDATE auth_sessions SET revoked_at=:now WHERE user_id=:id AND revoked_at IS NULL', now=security.now(), id=user_id)


def save_user(ctx, data, user_id=None):
    with Session.begin() as db:
        actor = admin_write(db, ctx)
        removed_scopes = []
        if user_id and (data.status != 'ACTIVE' or 'APPROVER' not in data.roles):
            for table, column, resource in [('room_approvers','room_id','meeting_rooms'), ('department_approvers','department_id','departments')]:
                for scope in rows(db, f'SELECT {column} AS resource_id FROM {table} WHERE user_id=:u AND is_active=1 ORDER BY {column}', u=user_id):
                    one(db, f'SELECT id FROM {resource} WHERE id=:id FOR UPDATE', id=scope['resource_id'])
                    removed_scopes.append((resource, scope['resource_id']))
        dept = one(db, 'SELECT * FROM departments WHERE id=:id', id=str(data.department_id))
        old = one(db, 'SELECT * FROM users WHERE id=:id FOR UPDATE', id=user_id) if user_id else None
        if old:
            version(old, data.expected_user_version)
        if (not old or old['department_id'] != dept['id']) and not dept['accepts_new_requests']:
            raise Failure(422, 'DEPARTMENT_INACTIVE', 'Phòng ban đã ngừng nhận tài khoản/yêu cầu mới.')
        old_roles = [r['role'] for r in rows(db, 'SELECT role FROM user_roles WHERE user_id=:id', id=user_id)] if old else []
        losing_admin = old and old['status'] == 'ACTIVE' and 'ADMIN' in old_roles and (data.status != 'ACTIVE' or 'ADMIN' not in data.roles)
        if losing_admin and db.scalar(text("SELECT COUNT(*) FROM users u JOIN user_roles r ON r.user_id=u.id WHERE u.status='ACTIVE' AND r.role='ADMIN'")) <= 1:
            raise Failure(409, 'LAST_ACTIVE_ADMIN', 'Phải giữ ít nhất một tài khoản Admin hoạt động.')
        user_id = user_id or uid()
        values = dict(id=user_id, code=data.employee_code.strip(), name=data.full_name.strip(),
                      email=str(data.email).strip().lower(), dept=str(data.department_id), status=data.status)
        if old:
            run(db, '''UPDATE users SET employee_code=:code,full_name=:name,email=:email,
                department_id=:dept,status=:status,row_version=row_version+1 WHERE id=:id''', **values)
            if old['status'] != data.status or old['department_id'] != str(data.department_id) or set(old_roles) != set(data.roles) or old['email'] != values['email']:
                revoke(db, user_id)
        else:
            run(db, '''INSERT INTO users(id,employee_code,full_name,email,department_id,status,password_hash)
                VALUES(:id,:code,:name,:email,:dept,:status,:hash)''', **values,
                hash=security.HASHER.hash(data.temporary_password.get_secret_value()))
        # Preserve unchanged grant timestamps; audit records removed grants.
        for role in set(old_roles)-set(data.roles):
            run(db, 'DELETE FROM user_roles WHERE user_id=:u AND role=:r', u=user_id, r=role)
        for role in set(data.roles)-set(old_roles):
            run(db, 'INSERT INTO user_roles(user_id,role,granted_by) VALUES(:u,:r,:a)', u=user_id, r=role, a=actor)
        if data.status != 'ACTIVE' or 'APPROVER' not in data.roles:
            run(db, 'UPDATE room_approvers SET is_active=0 WHERE user_id=:u', u=user_id)
            run(db, 'UPDATE department_approvers SET is_active=0 WHERE user_id=:u', u=user_id)
            for resource, resource_id in removed_scopes:
                run(db, f'UPDATE {resource} SET row_version=row_version+1 WHERE id=:id', id=resource_id)
        audit(db, actor, 'USER_UPDATED' if old else 'USER_CREATED', 'user', user_id,
              old_roles=old_roles, roles=data.roles, status=data.status)
        return user_view(db, user_id)


def reset_password(ctx, user_id, data):
    with Session.begin() as db:
        actor = admin_write(db, ctx)
        old = one(db, 'SELECT * FROM users WHERE id=:id FOR UPDATE', id=user_id)
        version(old, data.expected_user_version)
        run(db, '''UPDATE users SET password_hash=:hash,must_change_password=1,
            row_version=row_version+1 WHERE id=:id''',
            id=user_id, hash=security.HASHER.hash(data.new_temporary_password.get_secret_value()))
        revoke(db, user_id)
        audit(db, actor, 'TEMPORARY_PASSWORD_RESET', 'user', user_id)


def save_department(ctx, data, department_id=None):
    with Session.begin() as db:
        actor = admin_write(db, ctx)
        updating = department_id is not None
        if department_id:
            old = one(db, 'SELECT * FROM departments WHERE id=:id FOR UPDATE', id=department_id)
            version(old, data.expected_department_version)
        else:
            department_id = uid()
        values = dict(id=department_id, code=data.code.strip(), name=data.name.strip(), accepts=data.accepts_new_requests)
        if updating:
            run(db, 'UPDATE departments SET code=:code,name=:name,accepts_new_requests=:accepts,row_version=row_version+1 WHERE id=:id', **values)
        else:
            run(db, 'INSERT INTO departments(id,code,name,accepts_new_requests) VALUES(:id,:code,:name,:accepts)', **values)
        audit(db, actor, 'DEPARTMENT_SAVED', 'department', department_id)
        return one(db, 'SELECT id,code,name,accepts_new_requests,row_version FROM departments WHERE id=:id', id=department_id)


def time_text(value):
    if isinstance(value, timedelta):
        minutes = int(value.total_seconds()//60)
        return f'{minutes//60:02}:{minutes%60:02}'
    return value.strftime('%H:%M')


def policy_view(db, r):
    r = dict(r)
    r.pop('created_by', None); r.pop('created_at', None)
    r['effective_from'] = aware(r['effective_from'])
    r['weekly_windows'] = [dict(weekday=w['weekday'], start_time=time_text(w['start_time']), end_time=time_text(w['end_time']))
        for w in rows(db, 'SELECT * FROM room_weekly_windows WHERE policy_id=:id ORDER BY weekday,start_time', id=r['id'])]
    days = rows(db, 'SELECT * FROM room_calendar_days WHERE policy_id=:id ORDER BY local_date', id=r['id'])
    r['calendar_days'] = [dict(local_date=str(d['local_date']), is_closed=bool(d['is_closed']), reason=d['reason'],
        windows=[dict(start_time=time_text(w['start_time']), end_time=time_text(w['end_time'])) for w in
                 rows(db, 'SELECT * FROM room_calendar_windows WHERE calendar_day_id=:id ORDER BY start_time', id=d['id'])]) for d in days]
    return r


def policies(db, room_id):
    return [policy_view(db, r) for r in rows(db, 'SELECT * FROM room_policy_versions WHERE room_id=:id ORDER BY effective_from,id', id=room_id)]


def at_time(timeline, starts_at):
    valid = [p for p in timeline if utc(p['effective_from']) <= starts_at]
    return valid[-1] if valid else None


def room_view(db, room, at=None):
    r = {k: room[k] for k in ['id','code','name','location','accepts_new_requests','row_version']}
    r['equipment'] = rows(db, 'SELECT equipment_code,display_name,quantity FROM room_equipment WHERE room_id=:id ORDER BY equipment_code', id=r['id'])
    r['effective_policy'] = at_time(policies(db, r['id']), at or security.now())
    return r


def in_service(policy, start, end):
    start_local, end_local = aware(start).astimezone(LOCAL_ZONE), aware(end).astimezone(LOCAL_ZONE)
    if start_local.date() != end_local.date():
        return False
    special = next((d for d in policy['calendar_days'] if d['local_date'] == start_local.date().isoformat()), None)
    windows = ([] if special['is_closed'] else special['windows']) if special else [w for w in policy['weekly_windows'] if w['weekday'] == start_local.isoweekday()]
    # Compare full time values: 12:00:01 must not fit a window ending 12:00.
    return any(datetime.combine(start_local.date(), datetime.strptime(w['start_time'], '%H:%M').time(), LOCAL_ZONE) <= start_local
        and end_local <= datetime.combine(start_local.date(), datetime.strptime(w['end_time'], '%H:%M').time(), LOCAL_ZONE) for w in windows)


def insert_policy(db, room_id, actor, data):
    policy_id = uid()
    run(db, '''INSERT INTO room_policy_versions(id,room_id,effective_from,capacity,buffer_minutes,created_by)
        VALUES(:id,:room,:start,:capacity,:buffer,:actor)''', id=policy_id, room=room_id,
        start=utc(data.effective_from), capacity=data.capacity, buffer=data.buffer_minutes, actor=actor)
    for w in data.weekly_windows:
        run(db, 'INSERT INTO room_weekly_windows(id,policy_id,weekday,start_time,end_time) VALUES(:id,:p,:day,:start,:end)',
            id=uid(), p=policy_id, day=w.weekday, start=w.start_time+':00', end=w.end_time+':00')
    for d in data.calendar_days:
        day_id = uid()
        run(db, 'INSERT INTO room_calendar_days(id,policy_id,local_date,is_closed,reason) VALUES(:id,:p,:date,:closed,:reason)',
            id=day_id, p=policy_id, date=d.local_date, closed=d.is_closed, reason=d.reason)
        for w in d.windows:
            run(db, 'INSERT INTO room_calendar_windows(id,calendar_day_id,start_time,end_time) VALUES(:id,:d,:start,:end)',
                id=uid(), d=day_id, start=w.start_time+':00', end=w.end_time+':00')
    return policy_id


def save_room(ctx, data, room_id=None):
    with Session.begin() as db:
        actor = admin_write(db, ctx)
        old = one(db, 'SELECT * FROM meeting_rooms WHERE id=:id FOR UPDATE', id=room_id) if room_id else None
        if old:
            version(old, data.expected_room_version)
        room_id = room_id or uid()
        values = dict(id=room_id, code=data.code.strip(), name=data.name.strip(), location=data.location.strip(), accepts=data.accepts_new_requests)
        if old:
            run(db, 'UPDATE meeting_rooms SET code=:code,name=:name,location=:location,accepts_new_requests=:accepts,row_version=row_version+1 WHERE id=:id', **values)
            run(db, 'DELETE FROM room_equipment WHERE room_id=:id', id=room_id)
        else:
            run(db, 'INSERT INTO meeting_rooms(id,code,name,location,accepts_new_requests) VALUES(:id,:code,:name,:location,:accepts)', **values)
            insert_policy(db, room_id, actor, data.initial_policy)
        for e in data.equipment:
            run(db, 'INSERT INTO room_equipment(room_id,equipment_code,display_name,quantity) VALUES(:r,:code,:name,:qty)',
                r=room_id, code=e.equipment_code.strip(), name=e.display_name.strip(), qty=e.quantity)
        audit(db, actor, 'ROOM_SAVED', 'room', room_id)
        return room_view(db, one(db, 'SELECT * FROM meeting_rooms WHERE id=:id', id=room_id))


def save_policy(ctx, room_id, data):
    with Session.begin() as db:
        actor = admin_write(db, ctx)
        room = one(db, 'SELECT * FROM meeting_rooms WHERE id=:id FOR UPDATE', id=room_id)
        version(room, data.expected_room_version)
        now = security.now()
        if utc(data.effective_from) < now:
            raise Failure(422, 'POLICY_IN_PAST', 'Cấu hình mới phải có hiệu lực từ hiện tại hoặc tương lai.')
        policy_id = insert_policy(db, room_id, actor, data)
        timeline = policies(db, room_id)
        meetings = rows(db, '''SELECT e.*,(SELECT COUNT(*) FROM revision_participants p WHERE p.revision_id=e.revision_id) AS participant_count
            FROM v_effective_schedules e WHERE e.room_id=:id ORDER BY e.starts_at,e.schedule_id''', id=room_id)
        previous_blocked = None
        for m in meetings:
            p = at_time(timeline, m['starts_at'])
            if m['ends_at'] > now:
                if not p or p['capacity'] < m['participant_count'] or not in_service(p, m['starts_at'], m['ends_at']):
                    raise Failure(409, 'ROOM_CONFIG_INVALID', 'Cấu hình mới làm lịch đã duyệt không còn hợp lệ. Hãy xử lý lịch liên quan trước.')
                if previous_blocked and previous_blocked > m['starts_at']:
                    raise Failure(409, 'ROOM_CONFIG_INVALID', 'Khoảng chuyển tiếp mới làm các lịch đã duyệt bị chồng nhau.')
            previous_blocked = m['ends_at'] + timedelta(minutes=p['buffer_minutes']) if p else m['ends_at']
        run(db, 'UPDATE meeting_rooms SET row_version=row_version+1 WHERE id=:id', id=room_id)
        audit(db, actor, 'ROOM_POLICY_CREATED', 'room', room_id, policy_id=policy_id)
        return next(p for p in timeline if p['id'] == policy_id)


def scope_view(db, kind, resource_id):
    table, column, version_key = ('room_approvers','room_id','room_version') if kind == 'room' else ('department_approvers','department_id','department_version')
    resource = 'meeting_rooms' if kind == 'room' else 'departments'
    current = one(db, f'SELECT row_version FROM {resource} WHERE id=:id', id=resource_id)
    people = rows(db, f'''SELECT u.id,u.employee_code,u.full_name,u.department_id FROM users u
        JOIN {table} a ON a.user_id=u.id WHERE a.{column}=:id AND a.is_active=1
        AND u.status='ACTIVE' AND EXISTS(SELECT 1 FROM user_roles r WHERE r.user_id=u.id AND r.role='APPROVER') ORDER BY u.full_name,u.id''', id=resource_id)
    # Safe count lets the admin review effects without seeing proposal contents.
    pending = db.scalar(text(f'''SELECT COUNT(*) FROM approval_proposals p JOIN schedule_revisions v
        ON v.id=COALESCE(p.candidate_revision_id,p.base_revision_id)
        WHERE p.status='PENDING' AND p.expires_at>:now AND v.{column}=:id'''), dict(id=resource_id, now=security.now()))
    return {column:resource_id, version_key:current['row_version'], 'approvers':people, 'pending_proposal_count':pending}


def save_scope(ctx, kind, resource_id, data):
    table, column, resource = ('room_approvers','room_id','meeting_rooms') if kind == 'room' else ('department_approvers','department_id','departments')
    with Session.begin() as db:
        actor = admin_write(db, ctx)
        current = one(db, f'SELECT * FROM {resource} WHERE id=:id FOR UPDATE', id=resource_id)
        version(current, data.expected_room_version if kind == 'room' else data.expected_department_version)
        ids = sorted(str(u) for u in data.approver_user_ids)
        for user_id in ids:
            u = one(db, 'SELECT status FROM users WHERE id=:id FOR UPDATE', id=user_id)
            if u['status'] != 'ACTIVE' or not rows(db, "SELECT role FROM user_roles WHERE user_id=:id AND role='APPROVER'", id=user_id):
                raise Failure(422, 'INVALID_APPROVER', 'Chỉ phân công tài khoản hoạt động có quyền Người phê duyệt.')
        run(db, f'UPDATE {table} SET is_active=0 WHERE {column}=:id', id=resource_id)
        for user_id in ids:
            existing = rows(db, f'SELECT user_id FROM {table} WHERE {column}=:id AND user_id=:u', id=resource_id, u=user_id)
            if existing:
                run(db, f'UPDATE {table} SET is_active=1,granted_by=:a,created_at=:now WHERE {column}=:id AND user_id=:u', a=actor, now=security.now(), id=resource_id, u=user_id)
            else:
                run(db, f'INSERT INTO {table}({column},user_id,is_active,granted_by) VALUES(:id,:u,1,:a)', id=resource_id, u=user_id, a=actor)
        run(db, f'UPDATE {resource} SET row_version=row_version+1 WHERE id=:id', id=resource_id)
        audit(db, actor, 'APPROVERS_ASSIGNED', kind, resource_id, approver_user_ids=ids)
        return scope_view(db, kind, resource_id)


def validate_range(start, end, maximum_days):
    if start >= end or end-start > timedelta(days=maximum_days):
        raise Failure(422, 'INVALID_TIME_RANGE', f'Khoảng thời gian phải tăng và không vượt {maximum_days} ngày.')


def find_rooms(ctx, start, end, count, equipment, exclude, page_no, page_size):
    require_member(ctx)
    start, end = utc(start), utc(end)
    validate_range(start, end, 1)
    now = security.now()
    if not timedelta(minutes=15) <= end-start <= timedelta(hours=4) or start < now+timedelta(minutes=30) or start > now+timedelta(days=90):
        raise Failure(422, 'MEETING_TIME_INVALID', 'Họp dài 15 phút–4 giờ, bắt đầu sau ít nhất 30 phút và trong 90 ngày tới.')
    with Session() as db:
        if exclude:
            root = one(db, 'SELECT * FROM schedule_roots WHERE id=:id', id=str(exclude))
            if root['created_by'] != ctx[0]['id']:
                raise Failure(403, 'FORBIDDEN', 'Chỉ loại trừ lịch do chính bạn tạo.')
        result = []
        for r in rows(db, 'SELECT * FROM meeting_rooms WHERE accepts_new_requests=1 ORDER BY code,id'):
            view = room_view(db, r, start)
            p = view['effective_policy']
            if not p or p['capacity'] < count or not in_service(p, start, end):
                continue
            if not set(equipment).issubset({e['equipment_code'] for e in view['equipment']}):
                continue
            blocked = end+timedelta(minutes=p['buffer_minutes'])
            conflict = rows(db, '''SELECT schedule_id FROM v_effective_meetings WHERE room_id=:room
                AND starts_at<:blocked AND blocked_until>:start AND (:excluded IS NULL OR schedule_id<>:excluded)''',
                room=r['id'], start=start, blocked=blocked, excluded=str(exclude) if exclude else None)
            if conflict:
                continue
            pending = rows(db, '''SELECT v.starts_at,v.ends_at FROM approval_proposals a JOIN schedule_revisions v ON v.id=a.candidate_revision_id
                WHERE a.status='PENDING' AND a.expires_at>:now AND v.room_id=:room
                AND v.starts_at<:blocked AND TIMESTAMPADD(MINUTE,COALESCE((SELECT p.buffer_minutes
                    FROM room_policy_versions p WHERE p.room_id=v.room_id AND p.effective_from<=v.starts_at
                    ORDER BY p.effective_from DESC LIMIT 1),:buffer),v.ends_at)>:start
                AND (:excluded IS NULL OR a.schedule_id<>:excluded) LIMIT 1''',
                now=now, room=r['id'], start=start, blocked=blocked, buffer=p['buffer_minutes'], excluded=str(exclude) if exclude else None)
            warnings = [dict(code='PENDING_ROOM_REQUEST', resource_type='ROOM', resource_id=r['id'], starts_at=None, ends_at=None,
                message='Phòng có yêu cầu đang chờ duyệt trong khoảng này; tìm phòng chưa giữ chỗ.')] if pending else []
            result.append(dict(room=view, capacity_at_requested_start=p['capacity'], buffer_minutes_at_requested_start=p['buffer_minutes'], warnings=warnings))
        return page(result, page_no, page_size)


def entry_key(viewer_id, revision_id, category):
    # Opaque per viewer; a BUSY_ONLY entry must not expose a revision/schedule ID.
    return hmac.new(security.SECRET.encode(), f'{viewer_id}:{revision_id}:{category}'.encode(), hashlib.sha256).hexdigest()[:32]


def calendar(ctx, start, end, room_id, user_id, page_no, page_size):
    require_member(ctx)
    start, end = utc(start), utc(end)
    validate_range(start, end, 93)
    viewer = ctx[0]
    if not room_id and not user_id:
        user_id = viewer['id']
    with Session() as db:
        if room_id:
            one(db, 'SELECT id FROM meeting_rooms WHERE id=:id', id=str(room_id))
        if user_id:
            one(db, 'SELECT id FROM users WHERE id=:id', id=str(user_id))
        schedules = rows(db, '''SELECT e.*,v.title,m.blocked_until FROM v_effective_schedules e
            JOIN schedule_revisions v ON v.id=e.revision_id
            LEFT JOIN v_effective_meetings m ON m.revision_id=e.revision_id
            WHERE e.starts_at<:end AND COALESCE(m.blocked_until,e.ends_at)>:start
            AND (:room IS NULL OR e.room_id=:room)
            AND (:user IS NULL OR e.organizer_user_id=:user OR EXISTS(SELECT 1 FROM revision_participants p WHERE p.revision_id=e.revision_id AND p.user_id=:user))
            ORDER BY e.starts_at,e.schedule_id''', start=start, end=end, room=str(room_id) if room_id else None, user=str(user_id) if user_id else None)
        entries = []
        for r in schedules:
            participant = bool(rows(db, 'SELECT user_id FROM revision_participants WHERE revision_id=:r AND user_id=:u', r=r['revision_id'], u=viewer['id']))
            detailed = r['organizer_user_id'] == viewer['id'] or participant or r['room_id'] in viewer['room_scope_ids'] or r['department_id'] in viewer['department_scope_ids']
            if r['ends_at'] > start:
                common = dict(starts_at=aware(r['starts_at']), ends_at=aware(r['ends_at']), room_id=r['room_id'], entry_key=entry_key(viewer['id'], r['revision_id'], 'BUSY'))
                if detailed:
                    entries.append(dict(**common, visibility='DETAIL', schedule_id=r['schedule_id'], revision_id=r['revision_id'], kind=r['kind'], title=r['title']))
                else:
                    entries.append(dict(**common, visibility='BUSY_ONLY', busy_type='BUSY'))
            # Buffers belong to the room, not to a person's busy calendar.
            if room_id and r['blocked_until'] and r['blocked_until'] > max(start, r['ends_at']) and r['ends_at'] < end:
                entries.append(dict(visibility='BUSY_ONLY', busy_type='BUFFER', entry_key=entry_key(viewer['id'], r['revision_id'], 'BUFFER'),
                    room_id=r['room_id'], starts_at=aware(r['ends_at']), ends_at=aware(r['blocked_until'])))
        entries.sort(key=lambda r: (r['starts_at'], r['entry_key']))
        return page(entries, page_no, page_size)
