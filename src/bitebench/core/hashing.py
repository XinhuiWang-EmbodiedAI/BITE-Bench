"""Stable content hashes; non-finite numbers are invalid."""

import hashlib
import json


def content_hash(value) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()
