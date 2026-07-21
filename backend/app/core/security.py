"""API-key authentication.

Service-to-service auth (key in a header), not user auth (JWT/sessions): this is
a backend document API called by other systems, so there are no user identities
to model. Keys come from the environment so rotation needs no code change.
"""

import hmac

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def _valid_keys() -> set[str]:
    raw = get_settings().api_keys
    return {k.strip() for k in raw.split(",") if k.strip()}


def require_api_key(x_api_key: str | None = Header(default=None)) -> str:
    """FastAPI dependency. If no keys are configured, auth is OFF (dev default).
    Otherwise the X-API-Key header must match one configured key.

    Uses hmac.compare_digest for constant-time comparison — a plain == leaks key
    length and prefix through timing, a real (if subtle) side channel.
    """
    keys = _valid_keys()
    if not keys:
        return "anonymous"  # auth disabled in dev; enable by setting API_KEYS

    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if not any(hmac.compare_digest(x_api_key, k) for k in keys):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Invalid API key")
    return x_api_key
