import os
from datetime import datetime,timezone,timedelta
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError,InvalidHashError
HASHER=PasswordHasher()
SECRET=os.environ['JWT_SECRET']
if len(SECRET)<32 or SECRET.startswith('REPLACE'):raise RuntimeError('JWT_SECRET must be at least 32 random characters')
ISSUER='httt10';AUDIENCE='httt10-web';TTL=int(os.getenv('ACCESS_TOKEN_MINUTES','30'))
if not 1<=TTL<=1440:raise RuntimeError('Invalid ACCESS_TOKEN_MINUTES')
DUMMY=HASHER.hash('not-an-account-password')
def now():return datetime.now(timezone.utc).replace(tzinfo=None)
def verify(password,hashed):
    try:return HASHER.verify(hashed or DUMMY,password)
    except (VerificationError,InvalidHashError):return False
def token(user,session):
    return jwt.encode({'sub':user.id,'sid':session.id,'av':user.auth_version,'iss':ISSUER,'aud':AUDIENCE,'iat':session.issued_at.replace(tzinfo=timezone.utc),'exp':session.expires_at.replace(tzinfo=timezone.utc)},SECRET,algorithm='HS256')
def decode(value):
    c=jwt.decode(value,SECRET,algorithms=['HS256'],issuer=ISSUER,audience=AUDIENCE,options={'require':['sub','sid','av','iat','exp','iss','aud']})
    from uuid import UUID
    UUID(c['sub']);UUID(c['sid'])
    if type(c['av']) is not int:raise ValueError('Invalid auth version')
    return c
