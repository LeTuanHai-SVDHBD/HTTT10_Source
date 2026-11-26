from fastapi import Depends, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .services import AuthService, Failure

bearer = HTTPBearer(auto_error=False)
service = AuthService()
SESSION_COOKIE = 'httt10_session'


def is_web_request(request: Request) -> bool:
    # The browser client sends a custom header. Cross-origin forms cannot set
    # it, and cross-origin fetches would require a CORS preflight.
    return (
        request.headers.get('X-HTTT10-Web') == '1'
        and request.headers.get('Sec-Fetch-Site', 'same-origin') == 'same-origin'
    )


def set_web_session(request: Request, response: Response, token='', max_age=0):
    if is_web_request(request):
        response.set_cookie(
            SESSION_COOKIE, token, max_age=max_age, path='/api/v1',
            httponly=True, samesite='strict', secure=request.url.scheme == 'https',
        )


def identity(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is not None:
        return service.identity(credentials.credentials)
    token = request.cookies.get(SESSION_COOKIE) if is_web_request(request) else None
    if not token:
        raise Failure(401, 'SESSION_INVALID', 'Vui lòng đăng nhập.')
    ctx = service.identity(token)
    expected_user = request.headers.get('X-HTTT10-User')
    if expected_user is not None and expected_user != ctx[0]['id']:
        raise Failure(401, 'SESSION_INVALID', 'Tài khoản trên trình duyệt đã thay đổi.')
    return ctx
