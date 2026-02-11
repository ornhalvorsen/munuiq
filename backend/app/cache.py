import time
from typing import Any

_store: dict[str, tuple[float, Any]] = {}

DEFAULT_TTL = 600  # 10 minutes


def get(key: str) -> Any | None:
    if key in _store:
        expires, value = _store[key]
        if time.time() < expires:
            return value
        del _store[key]
    return None


def put(key: str, value: Any, ttl: int = DEFAULT_TTL):
    _store[key] = (time.time() + ttl, value)
