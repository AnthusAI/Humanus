from __future__ import annotations

import hashlib
import json
from typing import Any


def hash_stable(value: Any) -> str:
    if isinstance(value, str):
        payload = value
    else:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def hash_short(value: Any) -> str:
    return hash_stable(value)[:16]

