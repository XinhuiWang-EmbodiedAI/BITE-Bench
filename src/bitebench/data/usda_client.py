"""FDC client with immutable, credential-redacted response snapshots."""

import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx

from bitebench.core.hashing import content_hash

BASE_URL = "https://api.nal.usda.gov/fdc/v1"


class SourceError(RuntimeError):
    def __init__(self, reason_code: str, status_code: int | None = None):
        self.reason_code = reason_code
        self.status_code = status_code
        super().__init__(reason_code)


def configured_key(path: Path = Path(".env")) -> str | None:
    value = os.getenv("USDA_FDC_API_KEY")
    if value:
        return value.strip() or None
    if path.is_file():
        for line in path.read_text().splitlines():
            name, sep, value = line.partition("=")
            if sep and name.strip() == "USDA_FDC_API_KEY":
                return value.strip().strip('"').strip("'") or None
    return None


def redact(value, secret: str | None):
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if key.lower() in {"api_key", "apikey", "authorization"}
            else redact(item, secret)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, secret) for item in value]
    if isinstance(value, str) and secret:
        return value.replace(secret, "[REDACTED]")
    return value


class USDAClient:
    def __init__(
        self,
        key: str | None = None,
        cache_dir: Path = Path("data/raw/usda"),
        transport=None,
        sleep=time.sleep,
        max_attempts: int = 3,
    ):
        self.requests_sent = 0
        self.network_budget = None
        self.key = key
        self.cache_dir = cache_dir
        self.sleep = sleep
        self.max_attempts = max_attempts
        self.http = httpx.Client(
            transport=transport, timeout=15, follow_redirects=False
        )

    def close(self):
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def request(self, endpoint: str, params: dict) -> dict:
        request = {
            "endpoint": endpoint,
            "params": params,
            "version": "fdc_client_v4",
            "method": "POST" if endpoint == "/foods/search" else "GET",
        }
        request_id = content_hash(request)
        pointer = self.cache_dir / f"{request_id}.index.json"
        if pointer.is_file():
            info = json.loads(pointer.read_text())
            if Path(info["snapshot"]).name != info["snapshot"] or not info[
                "snapshot"
            ].startswith(request_id + "_"):
                raise SourceError("INVALID_CACHE_POINTER")
            payload = json.loads((self.cache_dir / info["snapshot"]).read_text())
            if content_hash(payload) != info["snapshot_sha256"]:
                raise SourceError("CACHE_HASH_MISMATCH")
            return payload | {
                "cache_hit": True,
                "snapshot_path": str(self.cache_dir / info["snapshot"]),
            }
        if not self.key:
            raise SourceError("NO_API_KEY")
        for attempt in range(self.max_attempts):
            if (
                self.network_budget is not None
                and self.requests_sent >= self.network_budget
            ):
                raise SourceError("NETWORK_BUDGET_EXHAUSTED")
            self.requests_sent += 1
            try:
                if endpoint == "/foods/search":
                    auth_query = urlencode({"api_key": self.key}, quote_via=quote)
                    response = self.http.post(
                        BASE_URL + endpoint + "?" + auth_query, json=params
                    )
                else:
                    query = urlencode(
                        params | {"api_key": self.key}, doseq=True, quote_via=quote
                    )
                    response = self.http.get(BASE_URL + endpoint + "?" + query)
            except httpx.HTTPError:
                raise SourceError("NETWORK_ERROR") from None
            if response.status_code == 429:
                try:
                    wait = float(response.headers.get("Retry-After", 2**attempt))
                except ValueError:
                    # A date-valued/unknown retry deadline must not be ignored.
                    raise SourceError("RATE_LIMITED", 429) from None
                if (
                    not math.isfinite(wait)
                    or wait < 0
                    or wait > 5
                    or attempt + 1 == self.max_attempts
                ):
                    raise SourceError("RATE_LIMITED", 429)
                self.sleep(wait)
                continue
            if response.status_code != 200:
                raise SourceError("HTTP_ERROR", response.status_code)
            try:
                body = response.json()
            except ValueError:
                raise SourceError("INVALID_JSON") from None
            if not isinstance(body, dict):
                raise SourceError("INVALID_RESPONSE_SCHEMA")
            payload = {
                "request": request,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "credential_class": "DEMO" if self.key == "DEMO_KEY" else "USER",
                "source_system": "USDA_FDC",
                "response": redact(body, self.key),
            }
            digest = content_hash(payload)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            snapshot = f"{request_id}_{digest}.json"
            (self.cache_dir / snapshot).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
            )
            pointer.write_text(
                json.dumps({"snapshot": snapshot, "snapshot_sha256": digest}) + "\n"
            )
            return payload | {
                "cache_hit": False,
                "snapshot_path": str(self.cache_dir / snapshot),
            }
        raise SourceError("RATE_LIMITED", 429)

    def search(self, query: str, limit: int = 5) -> dict:
        if not query.strip() or not 1 <= limit <= 25:
            raise ValueError("query required; limit must be 1..25")
        return self.request(
            "/foods/search",
            {
                "query": query,
                "pageSize": limit,
                "dataType": ["Foundation", "SR Legacy", "Survey (FNDDS)"],
            },
        )

    def fetch(self, fdc_id: int) -> dict:
        if fdc_id <= 0:
            raise ValueError("fdc_id must be positive")
        payload = self.request(f"/food/{fdc_id}", {})
        if payload["response"].get("fdcId") != fdc_id:
            raise SourceError("SOURCE_ID_MISMATCH")
        return payload
