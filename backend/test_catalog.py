"""Real MySQL integration for milestone B; isolated database, no production data.

Run with the same MYSQL_TEST_* variables as test_auth.py. Each named assertion
is written to verification/catalog-result.json only after the suite succeeds.
"""
import json
import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

import pymysql
from fastapi.testclient import TestClient
from sqlalchemy import URL, text

root = Path(__file__).resolve().parents[1]
db_name = 'httt10_catalog_' + uuid4().hex[:10] + '_test'
params = dict(host=os.getenv('MYSQL_TEST_HOST', '127.0.0.1'), port=int(os.getenv('MYSQL_TEST_PORT', '43307')),
              user=os.getenv('MYSQL_TEST_USER', 'root'), password=os.getenv('MYSQL_TEST_PASSWORD', ''))
connection = pymysql.connect(**params, autocommit=True)
with connection.cursor() as cur:
    cur.execute('CREATE DATABASE `' + db_name + '` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
connection.close()
os.environ['DATABASE_URL'] = URL.create('mysql+pymysql', username=params['user'], password=params['password'], host=params['host'], port=params['port'], database=db_name).render_as_string(hide_password=False)
os.environ['JWT_SECRET'] = secrets.token_urlsafe(48)
from app.cli import main as cli
from app.db import Session, engine
from app.main import app, limiter
from app import security

results = []
def check(name, actual, expected=True):
    assert actual == expected, (name, actual, expected)
    results.append(dict(name=name, status='PASS'))
    print('PASS', name, flush=True)

with patch('sys.argv', ['cli', 'migrate']):
    cli()
with patch('sys.argv', ['cli', 'bootstrap']), patch('builtins.input', return_value='admin@example.com'), patch('getpass.getpass', return_value='Temp-Password-2026'):
    cli()
client = TestClient(app)

def login(email='admin@example.com', password='Real-Password-2026'):
    limiter.entries.clear()
    response = client.post('/api/v1/auth/login', json=dict(email=email, password=password))
    assert response.status_code == 200, response.text
    return {'Authorization': 'Bearer ' + response.json()['access_token']}

h = login(password='Temp-Password-2026')
check('Mật khẩu tạm không được truy cập danh mục', client.get('/api/v1/rooms', headers=h).status_code, 403)
client.put('/api/v1/auth/password', headers=h, json=dict(current_password='Temp-Password-2026', new_password='Real-Password-2026', confirm_password='Real-Password-2026'))
h = login()
admin = client.get('/api/v1/auth/me', headers=h).json()
check('Admin không tự nhận vai trò nhân viên', admin['roles'], ['ADMIN'])
check('Không có phiên -> 401', client.get('/api/v1/rooms').status_code, 401)
check('UUID sai -> 422', client.get('/api/v1/rooms/bad-id', headers=h).status_code, 422)
check('Phân trang vượt giới hạn -> 422', client.get('/api/v1/rooms?page_size=101', headers=h).status_code, 422)
check('Danh mục baseline giữ nguyên', client.get('/api/v1/rooms', headers=h).json()['total'], 2)


def request(method, path, body=None, auth=None, code=200):
    response = client.request(method, '/api/v1' + path, headers=h if auth is None else auth, json=body)
    assert response.status_code == code, (path, response.status_code, response.text)
    return response.json() if response.status_code != 204 else None


dep = request('POST', '/departments', dict(code='TEST', name='Phòng kiểm chứng', accepts_new_requests=True), code=201)
check('Tạo phòng ban', dep['row_version'], 1)
request('POST', '/departments', dict(code='TEST', name='Trùng mã', accepts_new_requests=True), code=409)
check('Mã phòng ban trùng trả 409', True)
request('PUT', '/departments/' + dep['id'], dict(code='TEST', name='Tên mới', accepts_new_requests=True, expected_department_version=99), code=409)
check('Chặn sửa phòng ban bằng phiên bản cũ', True)
dep = request('PUT', '/departments/' + dep['id'], dict(code='TEST', name='Phòng kiểm chứng mới', accepts_new_requests=True, expected_department_version=1))
check('Sửa phòng ban tăng phiên bản', dep['row_version'], 2)


def create_user(code, role_list, name=None):
    return request('POST', '/users', dict(employee_code=code, full_name=name or code, email=code.lower() + '@example.com', department_id=dep['id'], status='ACTIVE', roles=role_list, temporary_password='Temp-Password-2026'), code=201)


def activate(user):
    headers = login(user['email'], 'Temp-Password-2026')
    request('PUT', '/auth/password', dict(current_password='Temp-Password-2026', new_password='Real-Password-2026', confirm_password='Real-Password-2026'), auth=headers, code=204)
    return login(user['email'])


def update_user(user, **patches):
    current = request('GET', '/users/' + user['id'])
    data = {k: current[k] for k in ['employee_code','full_name','email','department_id','status','roles']}
    return request('PUT', '/users/' + user['id'], dict(**data, expected_user_version=current['row_version']) | patches)

employee = create_user('EMP001', ['EMPLOYEE'], 'Nhân viên kiểm chứng')
check('Cấp tài khoản không trả mật khẩu/hash', not any(k in employee for k in ['temporary_password','password_hash','auth_version']))
employee_h = activate(employee)
check('Nhân viên không được đọc tài khoản quản trị', client.get('/api/v1/users', headers=employee_h).status_code, 403)
check('Nhân viên không được tạo phòng ban', client.post('/api/v1/departments', headers=employee_h, json=dict(code='DENY',name='Deny',accepts_new_requests=True)).status_code, 403)
approver = create_user('APP001', ['EMPLOYEE','APPROVER'])
approver_h = activate(approver)
outsider = create_user('EMP002', ['EMPLOYEE'])
outsider_h = activate(outsider)
directory = request('GET', '/directory/users', auth=employee_h)
check('Directory chỉ trả UserRef', set(directory['items'][0]), {'id','employee_code','full_name','department_id'})
check('Tìm kiếm tài khoản phân trang', request('GET', '/users?q=EMP&page_size=1')['total'], 2)
check('Tìm kiếm không coi ký tự % là wildcard', request('GET', '/users?q=%25')['total'], 0)
request('POST', '/users', dict(employee_code='DUP', full_name='Duplicate', email=employee['email'].upper(), department_id=dep['id'], status='ACTIVE', roles=['EMPLOYEE'], temporary_password='Temp-Password-2026'), code=409)
check('Email duy nhất không phân biệt hoa thường', True)
update_user(employee, full_name='Tên hiển thị mới')
check('Chỉ đổi tên không thu hồi phiên', request('GET', '/auth/me', auth=employee_h)['full_name'], 'Tên hiển thị mới')
update_user(employee, roles=['EMPLOYEE','APPROVER'])
check('Đổi vai trò thu hồi token hiện có', client.get('/api/v1/auth/me', headers=employee_h).status_code, 401)
employee_h = login(employee['email'])
update_user(employee, status='LOCKED')
check('Khóa tài khoản vô hiệu phiên', client.get('/api/v1/rooms', headers=employee_h).status_code, 401)
check('Directory không trả người bị khóa', employee['id'] not in [u['id'] for u in request('GET', '/directory/users')['items']])
update_user(employee, status='ACTIVE', roles=['EMPLOYEE'])
employee_h = login(employee['email'])
current = request('GET', '/users/' + employee['id'])
request('PUT', '/users/' + employee['id'] + '/temporary-password', dict(expected_user_version=current['row_version'], new_temporary_password='Reset-Password-2026'), code=204)
check('Đặt lại mật khẩu thu hồi phiên', client.get('/api/v1/rooms', headers=employee_h).status_code, 401)
reset_h = login(employee['email'], 'Reset-Password-2026')
check('Đặt lại mật khẩu bắt buộc đổi', request('GET', '/auth/me', auth=reset_h)['must_change_password'])
request('PUT', '/auth/password', dict(current_password='Reset-Password-2026',new_password='Real-Password-2026',confirm_password='Real-Password-2026'), auth=reset_h, code=204)
employee_h = login(employee['email'])

# Every administrator downgrade is serialized, including two competing requests.
current = request('GET', '/users/' + admin['id'])
body = {k: current[k] for k in ['employee_code','full_name','email','department_id','status','roles']}
request('PUT', '/users/' + admin['id'], body | dict(status='LOCKED', expected_user_version=current['row_version']), code=409)
check('Không khóa Admin hoạt động cuối cùng', True)
request('PUT', '/users/' + admin['id'], body | dict(roles=['EMPLOYEE'], expected_user_version=current['row_version']), code=409)
check('Không gỡ quyền Admin hoạt động cuối cùng', True)

weekly = [dict(weekday=day,start_time=a,end_time=b) for day in range(1,6) for a,b in [('08:00','12:00'),('13:00','17:00')]]
policy = dict(effective_from=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat(), capacity=6, buffer_minutes=15, weekly_windows=weekly, calendar_days=[])
room = request('POST', '/rooms', dict(code='TESTROOM',name='Phòng tích hợp',location='Tầng 3', accepts_new_requests=True, equipment=[dict(equipment_code='PROJECTOR',display_name='Máy chiếu',quantity=1),dict(equipment_code='TV',display_name='TV',quantity=1)], initial_policy=policy), code=201)
room_id = room['id']
check('Tạo phòng đồng thời cấu hình và thiết bị', (room['effective_policy']['capacity'],len(room['equipment'])), (6,2))
invalid = policy | dict(weekly_windows=[dict(weekday=1,start_time='08:00',end_time='12:00'),dict(weekday=1,start_time='11:00',end_time='13:00')])
request('POST', '/rooms/' + room_id + '/policies', invalid | dict(expected_room_version=room['row_version']), code=422)
check('Chặn khoảng phục vụ chồng nhau', True)
request('PUT', '/rooms/' + room_id + '/approvers', dict(expected_room_version=room['row_version'],approver_user_ids=[employee['id']]), code=422)
check('Chỉ gán người có APPROVER và ACTIVE', True)
scoped = request('PUT', '/rooms/' + room_id + '/approvers', dict(expected_room_version=room['row_version'],approver_user_ids=[approver['id']]))
check('Phân công phòng cập nhật phiên bản', scoped['room_version'], room['row_version']+1)
check('Me tải phạm vi duyệt từ server', room_id in request('GET', '/auth/me', auth=approver_h)['room_scope_ids'])
request('PUT', '/rooms/' + room_id + '/approvers', dict(expected_room_version=room['row_version'],approver_user_ids=[]), code=409)
check('Phân công từ màn hình cũ bị chặn', True)
dep = request('GET', '/departments/' + dep['id'])
request('PUT', '/departments/' + dep['id'] + '/approvers', dict(expected_department_version=dep['row_version'],approver_user_ids=[approver['id']]))
check('Phân công công tác theo phòng ban', dep['id'] in request('GET', '/auth/me', auth=approver_h)['department_scope_ids'])
check('Người duyệt không được quản lý phân công', client.get('/api/v1/rooms/' + room_id + '/approvers',headers=approver_h).status_code, 403)

# Seed confirmed and pending schedules ONLY in isolated test DB. There is no
# fake approval endpoint. Dates below use UTC converted from Vietnam 09:00.
day = datetime.now(timezone.utc).date()+timedelta(days=2)
while day.isoweekday() > 5:
    day += timedelta(days=1)
start = datetime.combine(day, datetime.min.time()).replace(hour=2)
end = start+timedelta(hours=1)

def iso(d): return d.replace(tzinfo=timezone.utc).isoformat()

def fixture(title, begin, finish, organizer, participant_ids, kind='MEETING', confirmed=True, cancelled=False):
    schedule_id, revision_id = str(uuid4()), str(uuid4())
    with Session.begin() as db:
        db.execute(text('INSERT INTO schedule_roots(id,kind,created_by) VALUES(:s,:k,:u)'), dict(s=schedule_id,k=kind,u=organizer))
        db.execute(text('''INSERT INTO schedule_revisions(id,schedule_id,kind,revision_no,title,description,starts_at,ends_at,room_id,chair_user_id,department_id,work_location,work_context,created_by)
            VALUES(:r,:s,:k,1,:title,'PRIVATE_DESCRIPTION',:a,:b,:room,:chair,:dep,:loc,:context,:u)'''),
            dict(r=revision_id,s=schedule_id,k=kind,title=title,a=begin,b=finish,room=room_id if kind=='MEETING' else None,
                 chair=organizer if kind=='MEETING' else None,dep=dep['id'] if kind=='WORK' else None,loc='PRIVATE_LOCATION' if kind=='WORK' else None,context='EXTERNAL' if kind=='WORK' else None,u=organizer))
        for person in participant_ids:
            db.execute(text('INSERT INTO revision_participants(revision_id,user_id,is_required) VALUES(:r,:u,1)'),dict(r=revision_id,u=person))
        if confirmed:
            db.execute(text('UPDATE schedule_roots SET current_revision_id=:r WHERE id=:s'),dict(r=revision_id,s=schedule_id))
            if cancelled:
                db.execute(text("UPDATE schedule_roots SET cancelled_at=UTC_TIMESTAMP(6),cancelled_by=:u,cancel_reason='Test' WHERE id=:s"),dict(s=schedule_id,u=organizer))
        else:
            db.execute(text("INSERT INTO approval_proposals(id,schedule_id,kind,submitted_by,candidate_revision_id,expires_at) VALUES(:id,:s,'CREATE',:u,:r,:expires)"),dict(id=str(uuid4()),s=schedule_id,u=organizer,r=revision_id,expires=begin))
    return schedule_id, revision_id

s1, r1 = fixture('PRIVATE_CONFIRMED_TITLE', start, end, employee['id'], [employee['id'],approver['id']])
s2, r2 = fixture('SECOND_CONFIRMED', end+timedelta(minutes=15), end+timedelta(hours=1), employee['id'], [employee['id']])
pending_id, pending_rev = fixture('PRIVATE_PENDING_TITLE', start+timedelta(hours=5), end+timedelta(hours=5), employee['id'], [employee['id']], confirmed=False)
fixture('PRIVATE_CANCELLED', start+timedelta(hours=7), end+timedelta(hours=7), employee['id'], [employee['id']], cancelled=True)
fixture('PRIVATE_WORK_TITLE', start, end, employee['id'], [employee['id']], kind='WORK')
cal_params = dict(**{'from':iso(start-timedelta(hours=3)),'to':iso(end+timedelta(hours=8))}, room_id=room_id)
def cal(auth=h, **changes):
    return client.get('/api/v1/calendar', params=cal_params|changes, headers=auth)
busy = cal(outsider_h)
check('Ngoài phạm vi chỉ thấy bận và chuyển tiếp', all(i['visibility']=='BUSY_ONLY' for i in busy.json()['items']))
check('Busy DTO không lộ title/ID/nội dung', all(not any(k in i for k in ['title','schedule_id','revision_id','description','participants']) for i in busy.json()['items']))
check('Entry key che mã revision gốc', r1 not in busy.text and s1 not in busy.text)
check('Calendar không hiện chờ duyệt hoặc đã hủy', 'PRIVATE_PENDING_TITLE' not in cal(employee_h).text and 'PRIVATE_CANCELLED' not in cal(employee_h).text)
check('Người tham gia được xem tiêu đề', 'PRIVATE_CONFIRMED_TITLE' in cal(approver_h).text)
check('Admin chưa có phạm vi không xem chi tiết', all(i['visibility']=='BUSY_ONLY' for i in cal().json()['items']))
check('Bộ lọc phòng và người dùng là AND', cal(outsider_h,user_id=outsider['id']).json()['total'], 0)
check('Khoảng đệm hiện riêng khi xem phòng', len([i for i in busy.json()['items'] if i.get('busy_type')=='BUFFER']), 2)
personal = request('GET','/calendar?from='+iso(start-timedelta(hours=3)).replace('+','%2B')+'&to='+iso(end+timedelta(hours=8)).replace('+','%2B'),auth=employee_h)
check('Calendar cá nhân không tính đệm của phòng', all(i.get('busy_type')!='BUFFER' for i in personal['items']))
check('Calendar mặc định trả cả công tác của mình', any(i.get('title')=='PRIVATE_WORK_TITLE' for i in personal['items']))
check('Calendar chỉ phần đệm vẫn có kết quả', cal(outsider_h,**{'from':iso(end+timedelta(minutes=1)),'to':iso(end+timedelta(minutes=5))}).json()['total'], 1)
check('Calendar buộc múi giờ RFC3339', client.get('/api/v1/calendar',params={'from':'2026-12-01T00:00:00','to':'2026-12-02T00:00:00'},headers=h).status_code,422)
check('Calendar chặn khoảng quá rộng', cal(**{'to':iso(end+timedelta(days=100))}).status_code,422)


def search(begin,finish,count=2,**more):
    return client.get('/api/v1/rooms/availability',params=dict(starts_at=iso(begin),ends_at=iso(finish),participant_count=count)|more,headers=employee_h)

def has_room(response):
    assert response.status_code==200,response.text
    return room_id in [i['room']['id'] for i in response.json()['items']]

check('Đường availability được nhận trước UUID động', search(start,end).status_code,200)
check('Tìm phòng chặn lịch đã xác nhận', has_room(search(start,end)),False)
check('Tìm phòng tính đệm sau lịch trước', has_room(search(end,end+timedelta(minutes=15))),False)
check('Đệm của lịch mới cũng không đè lịch tiếp', has_room(search(start-timedelta(minutes=30),start-timedelta(minutes=10))),False)
check('Đúng mép đệm cho phép', has_room(search(end+timedelta(hours=1,minutes=15),end+timedelta(hours=2))))
check('Giờ nghỉ trưa không được đặt', has_room(search(start+timedelta(hours=3),start+timedelta(hours=4))),False)
check('Đệm được chạy qua giờ nghỉ', has_room(search(start+timedelta(hours=2,minutes=30),start+timedelta(hours=3))))
check('Không bỏ qua giây khi kiểm tra giờ đóng', has_room(search(start+timedelta(hours=2,minutes=30),start+timedelta(hours=3,seconds=1))),False)
check('Sức chứa tính toàn bộ người',has_room(search(start+timedelta(hours=6),end+timedelta(hours=6),count=7)),False)
check('Thiết bị lọc AND',has_room(search(start+timedelta(hours=6),end+timedelta(hours=6),equipment_codes=['TV','PROJECTOR'])))
check('Thiếu một thiết bị thì loại',has_room(search(start+timedelta(hours=6),end+timedelta(hours=6),equipment_codes=['TV','MISSING'])),False)
waiting = search(start+timedelta(hours=5),end+timedelta(hours=5))
check('Yêu cầu chờ không giữ phòng',has_room(waiting))
check('Yêu cầu chờ có cảnh báo an toàn', next(i for i in waiting.json()['items'] if i['room']['id']==room_id)['warnings'][0]['code'],'PENDING_ROOM_REQUEST')
check('Cảnh báo không lộ tiêu đề yêu cầu', 'PRIVATE_PENDING_TITLE' not in waiting.text)
check('Người tạo được loại trừ chính lịch cũ',has_room(search(start,end,exclude_schedule_id=s1)))
check('Không được loại trừ lịch người khác',client.get('/api/v1/rooms/availability',params=dict(starts_at=iso(start),ends_at=iso(end),participant_count=2,exclude_schedule_id=s1),headers=outsider_h).status_code,403)
check('Loại trừ UUID không tồn tại -> 404',search(start,end,exclude_schedule_id=str(uuid4())).status_code,404)
check('Thời lượng dưới 15 phút -> 422',search(start,start+timedelta(minutes=10)).status_code,422)
check('Bắt đầu dưới 30 phút -> 422',search(security.now()+timedelta(minutes=10),security.now()+timedelta(hours=1)).status_code,422)
check('Quá 90 ngày -> 422',search(start+timedelta(days=95),end+timedelta(days=95)).status_code,422)

room = request('GET','/rooms/'+room_id)
future_policy = policy | dict(effective_from=iso(security.now()+timedelta(minutes=5)))
request('POST','/rooms/'+room_id+'/policies',future_policy|dict(capacity=1,expected_room_version=room['row_version']),code=409)
check('Giảm sức chứa không làm sai lịch đã duyệt',True)
request('POST','/rooms/'+room_id+'/policies',future_policy|dict(weekly_windows=[],expected_room_version=room['row_version']),code=409)
check('Đổi giờ không làm lịch đã duyệt ngoài giờ',True)
request('POST','/rooms/'+room_id+'/policies',future_policy|dict(buffer_minutes=30,expected_room_version=room['row_version']),code=409)
check('Tăng đệm không gây chồng lịch đã duyệt',True)
check('Cấu hình bị từ chối không tăng phiên bản/không lưu', (request('GET','/rooms/'+room_id)['row_version'],request('GET','/rooms/'+room_id+'/policies')['total']),(room['row_version'],1))
request('POST','/rooms/'+room_id+'/policies',policy|dict(expected_room_version=room['row_version']),code=422)
check('Không sửa ngược cấu hình lịch sử',True)
new_policy=request('POST','/rooms/'+room_id+'/policies',future_policy|dict(expected_room_version=room['row_version']),code=201)
check('Thêm cấu hình hợp lệ giữ lịch sử cũ',request('GET','/rooms/'+room_id+'/policies')['total'],2)
room = request('GET','/rooms/'+room_id)
# A new policy can add a date exception when it does not invalidate a booking.
exception_day = day+timedelta(days=3)
while exception_day.isoweekday()>5:exception_day+=timedelta(days=1)
request('POST','/rooms/'+room_id+'/policies',future_policy|dict(effective_from=iso(security.now()+timedelta(minutes=6)),calendar_days=[dict(local_date=exception_day.isoformat(),is_closed=True,reason='Nghỉ kiểm chứng',windows=[])],expected_room_version=room['row_version']),code=201)
check('Ngày nghỉ riêng loại khỏi tìm phòng',has_room(search(datetime.combine(exception_day,datetime.min.time()).replace(hour=2),datetime.combine(exception_day,datetime.min.time()).replace(hour=3))),False)
room = request('GET','/rooms/'+room_id)
metadata={k:room[k] for k in ['code','name','location','accepts_new_requests','equipment']}
request('PUT','/rooms/'+room_id,metadata|dict(accepts_new_requests=False,expected_room_version=room['row_version']))
check('Ngừng nhận mới không còn được tìm thấy',has_room(search(start+timedelta(hours=6),end+timedelta(hours=6))),False)
check('Ngừng nhận mới giữ lịch đã duyệt', 'PRIVATE_CONFIRMED_TITLE' in cal(employee_h).text)
check('Phân công hiển thị số yêu cầu chờ',request('GET','/rooms/'+room_id+'/approvers')['pending_proposal_count'],1)
scoped=request('GET','/rooms/'+room_id+'/approvers')
request('PUT','/rooms/'+room_id+'/approvers',dict(approver_user_ids=[],expected_room_version=scoped['room_version']))
check('Thu hồi phạm vi có hiệu lực ngay',room_id not in request('GET','/auth/me',auth=approver_h)['room_scope_ids'])
before_department_version=request('GET','/departments/'+dep['id'])['row_version']
update_user(approver,roles=['EMPLOYEE'])
check('Gỡ APPROVER vô hiệu phân công công tác',request('GET','/departments/'+dep['id']+'/approvers')['approvers'],[])
check('Thu hồi vai trò tăng phiên bản phạm vi bị ảnh hưởng',request('GET','/departments/'+dep['id'])['row_version'],before_department_version+1)

# Two active admins cannot both demote themselves.
second=create_user('ADMIN002',['ADMIN'])
second_h=activate(second)
a1=request('GET','/users/'+admin['id']);a2=request('GET','/users/'+second['id'])
barrier=Barrier(2)
def demote(current,auth):
    body={k:current[k] for k in ['employee_code','full_name','email','department_id','status','roles']}
    barrier.wait()
    with TestClient(app) as parallel:
        return parallel.put('/api/v1/users/'+current['id'],headers=auth,json=body|dict(roles=['EMPLOYEE'],expected_user_version=current['row_version'])).status_code
with ThreadPoolExecutor(max_workers=2) as pool:
    f1=pool.submit(demote,a1,h);f2=pool.submit(demote,a2,second_h)
    statuses=sorted([f1.result(),f2.result()])
check('Hai Admin gỡ quyền đồng thời chỉ một thành công',statuses,[200,409])
with Session() as db:
    check('Sau cạnh tranh vẫn còn đúng một Admin hoạt động',db.scalar(text("SELECT COUNT(*) FROM user_roles r JOIN users u ON u.id=r.user_id WHERE r.role='ADMIN' AND u.status='ACTIVE'")),1)
    check('Mốc B lưu audit nhưng không ghi mật khẩu',db.scalar(text("SELECT COUNT(*) FROM audit_entries WHERE action='TEMPORARY_PASSWORD_RESET' AND CAST(safe_metadata AS CHAR) NOT LIKE '%Password%'")),1)
    mysql=db.scalar(text('SELECT VERSION()'))
check('OpenAPI công bố 28 thao tác đã cài',sum(len(v) for v in app.openapi()['paths'].values()),28)
output=dict(passed=len(results),total=len(results),tests=results,mysql_version=mysql,scope='FastAPI ASGI + real MySQL; test fixtures only; not Docker Desktop Windows/LAN')
(root/'verification/catalog-result.json').write_text(json.dumps(output,ensure_ascii=False,indent=2))
print(json.dumps(dict(passed=len(results),total=len(results))),flush=True)
engine.dispose()
