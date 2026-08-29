from hmac import compare_digest

from fastapi import Header, HTTPException

from thati.config import get_settings


def require_admin(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")) -> None:
    configured = get_settings().admin_token.encode("utf-8")
    supplied = (x_admin_token or "").encode("utf-8")
    if not configured:
        raise HTTPException(status_code=401, detail={"error": "unauthorized"})
    dummy = b"\0" * len(configured)
    candidate = supplied if len(supplied) == len(configured) else dummy
    if not compare_digest(candidate, configured) or len(supplied) != len(configured):
        raise HTTPException(status_code=401, detail={"error": "unauthorized"})
