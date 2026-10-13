"""整站访问口令：HTTP Basic。"""

from __future__ import annotations

import base64
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse

REALM = "Aurora"
_UNAUTHORIZED = PlainTextResponse(
    "需要访问口令", status_code=401, headers={"WWW-Authenticate": f'Basic realm="{REALM}"'}
)


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """口令留空即关闭；账号密码都用常量时间比较，避免时序侧信道。"""

    def __init__(self, app, *, user: str, password: str) -> None:
        super().__init__(app)
        self.user = user
        self.password = password

    async def dispatch(self, request: Request, call_next):
        if not self.password or self._authorized(request.headers.get("authorization")):
            return await call_next(request)
        return _UNAUTHORIZED

    def _authorized(self, header: str | None) -> bool:
        if not header or not header.lower().startswith("basic "):
            return False
        try:
            raw = base64.b64decode(header[6:].strip(), validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return False
        user, _, password = raw.partition(":")
        return secrets.compare_digest(user, self.user) and secrets.compare_digest(
            password, self.password
        )
