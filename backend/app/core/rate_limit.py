from __future__ import annotations

from collections import defaultdict, deque
from time import monotonic

from fastapi import HTTPException, Request, status

_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


def enforce_rate_limit(request: Request, *, limit: int, window_seconds: int = 60) -> None:
    """Small in-process sliding-window limiter for high-cost local/API actions.

    A production deployment would move this bucket to Redis so all app replicas
    share limits. The interface is intentionally tiny so that swap is mechanical.
    """
    if limit <= 0:
        return

    identifier = request.headers.get("authorization") or request.client.host if request.client else "anonymous"
    bucket_key = f"{request.url.path}:{identifier}"
    now = monotonic()
    bucket = _BUCKETS[bucket_key]

    while bucket and now - bucket[0] >= window_seconds:
        bucket.popleft()

    if len(bucket) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait before retrying.",
        )

    bucket.append(now)