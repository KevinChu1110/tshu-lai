"""家人身分：app 用 Google 帳號登入，把 ID token 帶上來，引擎驗簽後對照家人名單。

引擎只拿 email 和名字當身分，不拿任何 Google 資料權限。素材權限由共享 Drive 資料夾管。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import AuthConfig


@dataclass
class Member:
    email: str
    called: str   # 阿嬤怎麼叫這個人


class AuthError(Exception):
    pass


def verify(token: str | None, cfg: AuthConfig) -> Member:
    if not cfg.enabled:
        return Member("local@localhost", "")
    if not token:
        raise AuthError("需要登入")
    try:
        from google.auth.transport import requests as grequests
        from google.oauth2 import id_token
    except ImportError as e:  # pragma: no cover
        raise AuthError("引擎沒裝 google-auth：uv sync --extra drive") from e
    req = grequests.Request()
    last: Exception | None = None
    for aud in cfg.google_client_ids or [None]:
        try:
            info = id_token.verify_oauth2_token(token, req, audience=aud)
            break
        except ValueError as e:
            last = e
    else:
        raise AuthError(f"登入憑證無效：{last}")
    email = (info.get("email") or "").lower()
    if not info.get("email_verified"):
        raise AuthError("Google 帳號的 email 尚未驗證")
    family = {k.lower(): v for k, v in cfg.family.items()}
    if email not in family:
        raise AuthError(f"{email} 不在家人名單，請擁有者加到 data/config.yaml 的 auth.family")
    return Member(email, family[email])
