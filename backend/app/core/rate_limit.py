"""Fixed-window rate limiter backed by Redis (already running as the Celery broker).

Per-key window: INCR a key that expires after the window. Simple and correct for
our scale. A sliding-window or token-bucket would be smoother under bursty load,
but fixed-window is the right complexity for now — noted as a future improvement.
"""

import time

import redis
from fastapi import Depends, HTTPException, status

from app.core.config import get_settings
from app.core.security import require_api_key

_redis: redis.Redis | None = None


def _client() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


def rate_limit(identity: str = Depends(require_api_key)) -> str:
    """Dependency: enforce N requests/minute per identity. Fails OPEN if Redis is
    unreachable — a rate limiter must never take down the API it protects."""
    settings = get_settings()
    limit = settings.rate_limit_per_minute
    window = int(time.time() // 60)
    key = f"ratelimit:{identity}:{window}"

    try:
        client = _client()
        count = client.incr(key)
        if count == 1:
            client.expire(key, 60)
    except redis.RedisError:
        return identity  # fail open: availability over strict enforcement

    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({limit}/min)",
            headers={"Retry-After": "60"},
        )
    return identity
