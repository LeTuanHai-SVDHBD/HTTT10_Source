from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .services import AuthService, Failure

bearer = HTTPBearer(auto_error=False)
service = AuthService()


def identity(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None:
        raise Failure(401, 'SESSION_INVALID', 'Vui lòng đăng nhập.')
    return service.identity(credentials.credentials)
