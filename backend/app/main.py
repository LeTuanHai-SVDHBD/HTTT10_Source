import logging,time,threading
from collections import OrderedDict,deque
from uuid import uuid4
from fastapi import FastAPI,Depends,Request,Response
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from .db import engine
from .services import AuthService,Failure
from .schemas import LoginInput,PasswordChange,TokenResponse,CurrentUser,HealthView
app=FastAPI(title='HTTT10 - Mốc A',version='0.1.0',description='Chỉ auth và health đã cài đặt. Hợp đồng toàn dự án nằm trong docs/contracts. Các API lịch sẽ bổ sung ở mốc B-F.',openapi_url='/api/v1/openapi.json',docs_url='/api/docs',redoc_url=None)
bearer=HTTPBearer(auto_error=False);service=AuthService()
def error(request,status,code,message,fields=None):
    headers={'Cache-Control':'no-store'}
    if status==401:headers['WWW-Authenticate']='Bearer'
    if status==429:headers['Retry-After']='60'
    return JSONResponse(status_code=status,headers=headers,content={'request_id':request.state.request_id,'error':{'code':code,'message':message,'field_errors':fields or [],'conflicts':[],'warnings':[],'warning_acknowledgement_token':None,'expiration_committed':False}})
@app.middleware('http')
async def request_id(request,call_next):
    request.state.request_id=str(uuid4())
    try:response=await call_next(request)
    except Exception:
        logging.error('Unhandled request error id=%s',request.state.request_id)
        response=error(request,500,'INTERNAL_ERROR','Không thể xử lý yêu cầu. Vui lòng thử lại.')
    response.headers['X-Request-ID']=request.state.request_id;response.headers['Cache-Control']='no-store'
    return response
@app.exception_handler(Failure)
async def failure(request,exc):return error(request,exc.status,exc.code,exc.message)
@app.exception_handler(RequestValidationError)
async def validation(request,exc):return error(request,422,'VALIDATION_ERROR','Dữ liệu chưa hợp lệ.',[{'path':'.'.join(map(str,e['loc'])),'code':e['type']} for e in exc.errors()])
@app.exception_handler(SQLAlchemyError)
async def database_error(request,exc):return error(request,503,'TEMPORARY_UNAVAILABLE','Cơ sở dữ liệu chưa sẵn sàng.')
def identity(credentials:HTTPAuthorizationCredentials|None=Depends(bearer)):
    if credentials is None:raise Failure(401,'SESSION_INVALID','Vui lòng đăng nhập.')
    return service.identity(credentials.credentials)
class LoginLimiter:
    def __init__(self):self.lock=threading.Lock();self.entries=OrderedDict()
    def check(self,key):
        with self.lock:
            now=time.monotonic();q=self.entries.setdefault(key,deque());self.entries.move_to_end(key)
            while q and q[0]<now-60:q.popleft()
            if len(q)>=10:raise Failure(429,'RATE_LIMITED','Bạn thử quá nhiều lần. Vui lòng thử lại sau một phút.')
            q.append(now)
            while len(self.entries)>10000:self.entries.popitem(last=False)
limiter=LoginLimiter()
@app.post('/api/v1/auth/login',response_model=TokenResponse)
def login(data:LoginInput,request:Request):
    limiter.check(request.client.host if request.client else 'unknown')
    return service.login(data.email,data.password.get_secret_value())
@app.get('/api/v1/auth/me',response_model=CurrentUser)
def me(ctx=Depends(identity)):return ctx[0]
@app.post('/api/v1/auth/logout',status_code=204)
def logout(ctx=Depends(identity)):
    service.logout(ctx[1]);return Response(status_code=204)
@app.put('/api/v1/auth/password',status_code=204)
def password(data:PasswordChange,ctx=Depends(identity)):
    service.password(ctx[1],data.current_password.get_secret_value(),data.new_password.get_secret_value());return Response(status_code=204)
@app.get('/api/v1/health/live',response_model=HealthView)
def live():return {'status':'ok'}
@app.get('/api/v1/health/ready',response_model=HealthView)
def ready():
    with engine.connect() as c:
        if c.scalar(text('SELECT version_num FROM alembic_version'))!='001_baseline':raise Failure(503,'TEMPORARY_UNAVAILABLE','Cần hoàn thành migration.')
    return {'status':'ready'}
