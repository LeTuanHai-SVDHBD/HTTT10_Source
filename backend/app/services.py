from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select,update,text
from .db import Session
from .models import User,UserRole,AuthSession
from . import security as sec
class Failure(Exception):
    def __init__(self,status,code,message,**details):
        self.status=status;self.code=code;self.message=message;self.details=details
def audit(db,actor,action):
    db.execute(text("INSERT INTO audit_entries(id,actor_user_id,action,entity_type,entity_id,safe_metadata) VALUES(:id,:actor,:action,'user',:actor,JSON_OBJECT())"),{'id':str(uuid4()),'actor':actor,'action':action})
class AuthService:
    def login(self,email,password):
        with Session.begin() as db:
            user=db.scalar(select(User).where(User.email==str(email).strip().lower()).with_for_update())
            valid=sec.verify(password,user.password_hash if user else None)
            if not user or not valid or user.status!='ACTIVE':raise Failure(401,'INVALID_CREDENTIALS','Email hoặc mật khẩu không đúng, hoặc tài khoản chưa hoạt động.')
            session=AuthSession(id=str(uuid4()),user_id=user.id,auth_version=user.auth_version,issued_at=sec.now(),expires_at=sec.now()+timedelta(minutes=sec.TTL),revoked_at=None)
            db.add(session);audit(db,user.id,'LOGIN');db.flush()
            return {'access_token':sec.token(user,session),'token_type':'bearer','expires_in':sec.TTL*60,'must_change_password':user.must_change_password}
    def identity(self,raw):
        try:c=sec.decode(raw)
        except Exception:raise Failure(401,'SESSION_INVALID','Phiên đăng nhập không hợp lệ hoặc đã hết hạn.')
        with Session() as db:
            user=db.get(User,c['sub']);session=db.get(AuthSession,c['sid'])
            if not user or not session or session.user_id!=user.id or user.status!='ACTIVE' or session.revoked_at is not None or session.expires_at<=sec.now() or session.auth_version!=user.auth_version or c['av']!=user.auth_version:
                raise Failure(401,'SESSION_INVALID','Phiên đăng nhập không hợp lệ hoặc đã hết hạn.')
            roles=list(db.scalars(select(UserRole.role).where(UserRole.user_id==user.id)))
            rooms=list(db.scalars(text('SELECT room_id FROM room_approvers WHERE user_id=:u AND is_active=1'),{'u':user.id})) if 'APPROVER' in roles else []
            deps=list(db.scalars(text('SELECT department_id FROM department_approvers WHERE user_id=:u AND is_active=1'),{'u':user.id})) if 'APPROVER' in roles else []
            return {'id':user.id,'employee_code':user.employee_code,'full_name':user.full_name,'department_id':user.department_id,'email':user.email,'roles':roles,'room_scope_ids':rooms,'department_scope_ids':deps,'must_change_password':user.must_change_password},c
    def logout(self,claims):
        with Session.begin() as db:
            # Lock user before session, matching password changes.
            db.scalar(select(User).where(User.id==claims['sub']).with_for_update())
            db.execute(update(AuthSession).where(AuthSession.id==claims['sid'],AuthSession.user_id==claims['sub'],AuthSession.revoked_at.is_(None)).values(revoked_at=sec.now()))
            audit(db,claims['sub'],'LOGOUT')
    def password(self,claims,current,new):
        with Session.begin() as db:
            user=db.scalar(select(User).where(User.id==claims['sub']).with_for_update())
            session=db.scalar(select(AuthSession).where(AuthSession.id==claims['sid']).with_for_update())
            if not user or not session or user.status!='ACTIVE' or user.auth_version!=claims['av'] or session.revoked_at is not None or session.expires_at<=sec.now():raise Failure(401,'SESSION_INVALID','Phiên không còn hợp lệ.')
            if not sec.verify(current,user.password_hash):raise Failure(422,'VALIDATION_ERROR','Mật khẩu hiện tại không đúng.')
            user.password_hash=sec.HASHER.hash(new);user.must_change_password=False;user.auth_version+=1;user.row_version+=1
            db.execute(update(AuthSession).where(AuthSession.user_id==user.id,AuthSession.revoked_at.is_(None)).values(revoked_at=sec.now()))
            audit(db,user.id,'PASSWORD_CHANGED')
