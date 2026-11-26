"""Integration tests: real MySQL + FastAPI ASGI, creates its own empty database."""
import os,sys,json,secrets,uuid,subprocess
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import pymysql
from fastapi.testclient import TestClient
from sqlalchemy import text

ROOT=Path(__file__).resolve().parents[1]
db_name='httt10_auth_'+uuid.uuid4().hex[:10]+'_test'
host=os.getenv('MYSQL_TEST_HOST','127.0.0.1');port=int(os.getenv('MYSQL_TEST_PORT','43307'))
pw=os.getenv('MYSQL_TEST_PASSWORD','');user=os.getenv('MYSQL_TEST_USER','root')
c=pymysql.connect(host=host,port=port,user=user,password=pw,autocommit=True)
with c.cursor() as q:q.execute('CREATE DATABASE `'+db_name+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
c.close()
from sqlalchemy import URL
os.environ['DATABASE_URL']=URL.create('mysql+pymysql',username=user,password=pw,host=host,port=port,database=db_name).render_as_string(hide_password=False)
os.environ['JWT_SECRET']=secrets.token_urlsafe(48)
from app.cli import main as cli
from app.db import Session,engine
from app.main import app,limiter
from app import security
from app.models import User
results=[]
def check(name,fn):fn();results.append({'name':name,'status':'PASS'});print('PASS',name,flush=True)
def equal(a,b):assert a==b,(a,b)
with patch('sys.argv',['cli','migrate']):cli()
with patch('sys.argv',['cli','adopt-baseline']):cli()
temp='Example-Only-Temp-2026';new='Example-Only-New-2026'
with patch('sys.argv',['cli','bootstrap']),patch('builtins.input',return_value='admin@example.com'),patch('getpass.getpass',return_value=temp):cli()
client=TestClient(app)
def login(password=temp,email='admin@example.com'):
 return client.post('/api/v1/auth/login',json={'email':email,'password':password})
def headers(token):return {'Authorization':'Bearer '+token}
check('Migration baseline và adoption chạy được trên MySQL',lambda:equal(client.get('/api/v1/health/ready').status_code,200))
check('Health live',lambda:equal(client.get('/api/v1/health/live').json(),{'status':'ok'}))
check('Không Bearer -> 401',lambda:equal(client.get('/api/v1/auth/me').status_code,401))
check('Sai mật khẩu -> 401',lambda:equal(login('wrong').status_code,401))
check('Email không tồn tại cùng lỗi chung',lambda:equal(login('wrong','absent@example.com').json()['error']['message'],login('wrong').json()['error']['message']))
check('Validation không lộ input mật khẩu',lambda:equal('input' in client.post('/api/v1/auth/login',json={'email':'invalid','password':'DO_NOT_LEAK'}).text,False))
r=login();equal(r.status_code,200);t=r.json()['access_token'];h=headers(t)
check('Login cấp JWT và cờ mật khẩu tạm',lambda:equal(r.json()['must_change_password'],True))
me=client.get('/api/v1/auth/me',headers=h)
check('Admin không tự có quyền Nhân viên',lambda:equal(me.json()['roles'],['ADMIN']))
check('Me không trả hash/token',lambda:equal(any(k in me.json() for k in ['password_hash','access_token','auth_version']),False))
check('JWT giả bị từ chối',lambda:equal(client.get('/api/v1/auth/me',headers=headers(t+'x')).status_code,401))
check('Response có request ID/no-store',lambda:equal((bool(me.headers.get('X-Request-ID')),me.headers.get('Cache-Control')),(True,'no-store')))
check('Đổi mật khẩu sai xác nhận -> 422',lambda:equal(client.put('/api/v1/auth/password',headers=h,json={'current_password':temp,'new_password':new,'confirm_password':temp}).status_code,422))
check('Đổi mật khẩu sai hiện tại -> 422',lambda:equal(client.put('/api/v1/auth/password',headers=h,json={'current_password':'wrong','new_password':new,'confirm_password':new}).status_code,422))
check('Đổi mật khẩu tạm -> 204',lambda:equal(client.put('/api/v1/auth/password',headers=h,json={'current_password':temp,'new_password':new,'confirm_password':new}).status_code,204))
check('Token cũ hết hiệu lực sau đổi mật khẩu',lambda:equal(client.get('/api/v1/auth/me',headers=h).status_code,401))
limiter.entries.clear()
check('Mật khẩu cũ không đăng nhập được',lambda:equal(login(temp).status_code,401))
t1=login(new).json()['access_token'];t2=login(new).json()['access_token']
check('Bỏ cờ mật khẩu tạm sau đổi',lambda:equal(client.get('/api/v1/auth/me',headers=headers(t1)).json()['must_change_password'],False))
check('Logout -> 204 không body',lambda:equal((client.post('/api/v1/auth/logout',headers=headers(t1)).status_code),204))
check('Token logout không dùng lại được',lambda:equal(client.get('/api/v1/auth/me',headers=headers(t1)).status_code,401))
check('Logout chỉ thu hồi đúng phiên',lambda:equal(client.get('/api/v1/auth/me',headers=headers(t2)).status_code,200))
with Session.begin() as s:s.execute(text("UPDATE users SET status='LOCKED' WHERE email='admin@example.com'"))
check('Khóa tài khoản vô hiệu token ngay ở server',lambda:equal(client.get('/api/v1/auth/me',headers=headers(t2)).status_code,401))
check('Tài khoản khóa không login được',lambda:equal(login(new).status_code,401))
with Session.begin() as s:s.execute(text("UPDATE users SET status='ACTIVE' WHERE email='admin@example.com'"))
limiter.entries.clear()
t3=login(new).json()['access_token']
with Session.begin() as s:s.execute(text('UPDATE users SET auth_version=auth_version+1'))
check('auth_version đổi vô hiệu token',lambda:equal(client.get('/api/v1/auth/me',headers=headers(t3)).status_code,401))
with Session() as s:
 u=s.scalar(__import__('sqlalchemy').select(User));claims={'sub':u.id,'sid':str(uuid.uuid4()),'av':u.auth_version,'iat':1,'exp':2,'iss':'httt10','aud':'httt10-web'}
 expired=__import__('jwt').encode(claims,security.SECRET,algorithm='HS256')
check('JWT hết hạn bị chặn',lambda:equal(client.get('/api/v1/auth/me',headers=headers(expired)).status_code,401))
with Session() as s:
 hashed=s.scalar(text('SELECT password_hash FROM users LIMIT 1'))
check('Mật khẩu được băm Argon2, không plain text',lambda:equal((hashed.startswith('$argon2id$'),security.verify(new,hashed)),(True,True)))
limiter.entries.clear()
for _ in range(10):login('wrong')
check('Rate limit lần 11 trả 429 và Retry-After',lambda:equal((login('wrong').status_code,login('wrong').headers.get('Retry-After')),(429,'60')))
check('API giữ đủ 6 operation nền mốc A',lambda:equal(all(p in app.openapi()['paths'] for p in ['/api/v1/auth/login','/api/v1/auth/me','/api/v1/auth/logout','/api/v1/auth/password','/api/v1/health/live','/api/v1/health/ready']),True))
with Session() as s:
 check('Lưu audit của các thao tác tài khoản',lambda:equal(s.scalar(text("SELECT COUNT(DISTINCT action) FROM audit_entries WHERE action IN ('BOOTSTRAP_ADMIN','LOGIN','LOGOUT','PASSWORD_CHANGED')")),4))

def check_web_session():
    web_headers = {'X-HTTT10-Web': '1'}
    with TestClient(app, base_url='http://192.0.2.10:8080') as web:
        with patch.object(security, 'TTL', 480):
            response = web.post('/api/v1/auth/login', headers=web_headers,
                                json={'email': 'admin@example.com', 'password': new})
        equal(response.status_code, 200)
        result = response.json()
        equal(result['expires_in'], 28800)
        cookie = response.headers['set-cookie'].lower()
        for attribute in ('httponly', 'samesite=strict', 'path=/api/v1', 'max-age=28800'):
            assert attribute in cookie
        equal('; secure' in cookie, False)
        claims = security.decode(result['access_token'])
        equal(claims['exp'] - claims['iat'], 28800)

        path = '/api/v1/auth/me'
        equal(web.get(path, headers=web_headers).status_code, 200)
        equal(web.get(path).status_code, 401)
        equal(web.get(path, headers={**web_headers, 'Sec-Fetch-Site': 'cross-site'}).status_code, 401)
        equal(web.get(path, headers={**web_headers, 'X-HTTT10-User': str(uuid.uuid4())}).status_code, 401)
        equal(web.get(path, headers={**web_headers, **headers('invalid')}).status_code, 401)

        # Advance the server session clock without making the suite wait.
        now = security.now()
        with patch.object(security, 'now', return_value=now + timedelta(minutes=31)):
            equal(web.get(path, headers=web_headers).status_code, 200)
        with patch.object(security, 'now', return_value=now + timedelta(hours=8)):
            equal(web.get(path, headers=web_headers).status_code, 401)

        response = web.post('/api/v1/auth/logout', headers=web_headers)
        equal(response.status_code, 204)
        assert 'max-age=0' in response.headers['set-cookie'].lower()
        equal(web.get(path, headers=web_headers).status_code, 401)
        equal(client.get(path, headers=headers(result['access_token'])).status_code, 401)

limiter.entries.clear()
check('Cookie phiên web khôi phục đăng nhập, hỗ trợ hạn 8 giờ và bị thu hồi khi đăng xuất', check_web_session)
out={'passed':len(results),'total':len(results),'tests':results,'mysql_version':engine.connect().execute(text('SELECT VERSION()')).scalar(),'scope':'FastAPI ASGI + MySQL integration, not Docker/Windows/browser','frontend_build':'verified separately'}
result_dir=Path(os.getenv('TEST_RESULT_DIR',str(ROOT/'verification')));result_dir.mkdir(parents=True,exist_ok=True)
(result_dir/'auth-result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({'passed':out['passed'],'total':out['total']}))
engine.dispose()
