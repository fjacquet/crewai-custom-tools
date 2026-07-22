"""Pure httpx client for the Gramps Web REST API.

JWT auth with lazy fetch and single refresh on 401. `GRAMPS_API_URL` already
includes the `/api` suffix, so all paths here are relative ("/people/").
This module is NOT a CrewAI tool: it is consumed directly by the genecrew
orchestrator (no LLM) and wrapped by the thin BaseTool classes in read_tools.py.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

DEFAULT_TIMEOUT = 15.0
TOKEN_EXPIRY_SKEW_S = 60  # treat a token as expired this many seconds before its real exp
FALLBACK_TOKEN_TTL_S = 300  # used when a token's exp claim can't be decoded


class GrampsConfigError(RuntimeError):
    """Raised when the Gramps environment configuration is incomplete."""


@dataclass(frozen=True)
class GrampsConfig:
    """Connection settings for one Gramps Web instance."""

    api_url: str
    username: str
    password: str

    @staticmethod
    def from_env() -> GrampsConfig:
        try:
            return GrampsConfig(
                api_url=os.environ["GRAMPS_API_URL"].rstrip("/"),
                username=os.environ["GRAMPS_USERNAME"],
                password=os.environ["GRAMPS_PASSWORD"],
            )
        except KeyError as exc:
            raise GrampsConfigError(
                f"Missing environment variable: {exc.args[0]}"
            ) from exc


def _decode_jwt_exp(token: str) -> int:
    """Best-effort decode of a JWT's `exp` claim (unix seconds).

    Falls back to a conservative short TTL from now if the token isn't a
    well-formed JWT, so a fresh login is never cached as valid "forever".
    """
    try:
        _, payload_b64, *_ = token.split(".")
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        return int(payload["exp"])
    except Exception:
        return int(time.time()) + FALLBACK_TOKEN_TTL_S


def _is_expired(exp: int) -> bool:
    return time.time() >= exp - TOKEN_EXPIRY_SKEW_S


def _load_token_cache(path: Path) -> dict[str, Any] | None:
    """Read {"token", "exp"} from the cache file, or None if missing/unreadable.

    We trust the `exp` stored alongside the token (rather than re-decoding the
    JWT on every load): it was already decoded once when the token was first
    cached, and re-deriving it here would just duplicate that work.
    """
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(data, dict) or "token" not in data or "exp" not in data:
        return None
    return data


def _write_token_cache(path: Path, token: str, exp: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Create the file pre-locked (owner read/write only) instead of writing at
    # the umask's default mode and chmod-ing after: that would leave a window
    # where the bearer token is world/group-readable on disk.
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps({"token": token, "exp": exp}))


def _invalidate_token_cache(path: Path) -> None:
    with contextlib.suppress(OSError):
        path.unlink()


class GrampsClient:
    """Thin synchronous Gramps Web client; one instance per process."""

    def __init__(
        self,
        config: GrampsConfig,
        transport: httpx.BaseTransport | None = None,
        token_cache: str | Path | None = None,
    ) -> None:
        self._config = config
        self._http = httpx.Client(
            base_url=config.api_url, timeout=DEFAULT_TIMEOUT, transport=transport
        )
        # Opt-in: None (the default) preserves the previous login-on-first-request
        # behaviour used by existing callers/tests that don't pass this parameter.
        self._token_cache = Path(token_cache) if token_cache is not None else None
        self._token: str | None = None

        if self._token_cache is not None:
            cached = _load_token_cache(self._token_cache)
            if cached is not None and not _is_expired(cached["exp"]):
                self._token = cached["token"]

    def _fetch_token(self) -> str:
        # Gramps Web rate-limits /token/ as brute-force protection; retry a
        # bounded number of times on 429, honoring Retry-After, so a
        # transient throttle self-heals instead of failing the whole run.
        for attempt in range(3):
            response = self._http.post(
                "/token/",
                json={"username": self._config.username, "password": self._config.password},
            )
            if response.status_code == 429 and attempt < 2:
                retry_after = response.headers.get("Retry-After")
                delay = (
                    float(retry_after)
                    if (retry_after or "").strip().isdigit()
                    else 2**attempt
                )
                time.sleep(min(delay, 30.0))
                continue
            response.raise_for_status()
            token = response.json()["access_token"]
            if self._token_cache is not None:
                _write_token_cache(self._token_cache, token, _decode_jwt_exp(token))
            return token
        response.raise_for_status()  # exhausted retries -> raise the last 429 clearly

    def _send_with_429_retry(
        self, method: str, path: str, headers: dict[str, str], **kwargs: Any
    ) -> httpx.Response:
        # Data endpoints (people, places, notes, tags, ...) are rate-limited
        # the same way /token/ is; retry a bounded number of times on 429,
        # honoring Retry-After, mirroring _fetch_token()'s pattern so a
        # transient throttle self-heals instead of failing the whole call.
        for attempt in range(3):
            response = self._http.request(method, path, headers=headers, **kwargs)
            if response.status_code == 429 and attempt < 2:
                retry_after = response.headers.get("Retry-After")
                delay = (
                    float(retry_after)
                    if (retry_after or "").strip().isdigit()
                    else 2**attempt
                )
                time.sleep(min(delay, 30.0))
                continue
            return response
        return response  # exhausted retries -> caller's raise_for_status() surfaces the last 429

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if self._token is None:
            self._token = self._fetch_token()
        caller_headers = dict(kwargs.pop("headers", None) or {})  # ex. Content-Type upload
        headers = {**caller_headers, "Authorization": f"Bearer {self._token}"}
        response = self._send_with_429_retry(method, path, headers, **kwargs)
        if response.status_code == 401:  # expired token: refresh once
            if self._token_cache is not None:
                _invalidate_token_cache(self._token_cache)
            self._token = self._fetch_token()
            headers = {**caller_headers, "Authorization": f"Bearer {self._token}"}
            response = self._send_with_429_retry(method, path, headers, **kwargs)
        response.raise_for_status()
        return response

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", path, params=params).json()

    # -- typed read helpers -------------------------------------------------

    def count_objects(self, object_type: str) -> int:
        response = self.request("GET", f"/{object_type}/", params={"pagesize": 1})
        total = response.headers.get("X-Total-Count")
        if total is None:
            raise RuntimeError(
                f"Gramps Web response for /{object_type}/ lacks the X-Total-Count header"
            )
        return int(total)

    def get_tree_info(self) -> dict:
        trees = self.get_json("/trees/")
        return trees[0] if isinstance(trees, list) and trees else {}

    def search(self, query: str, page: int = 1, pagesize: int = 20) -> list:
        return self.get_json(
            "/search/", params={"query": query, "page": page, "pagesize": pagesize}
        )

    def get_object(self, object_type: str, handle: str) -> dict:
        return self.get_json(f"/{object_type}/{handle}")

    def find_by_gramps_id(self, object_type: str, gramps_id: str) -> dict:
        matches = self.get_json(f"/{object_type}/", params={"gramps_id": gramps_id})
        if not matches:
            raise LookupError(f"No {object_type} object with gramps_id {gramps_id}")
        return matches[0]

    def list_people(self, page: int = 1, pagesize: int = 25) -> list:
        return self.get_json(
            "/people/", params={"page": page, "pagesize": pagesize, "sort": "gramps_id"}
        )

    def get_timeline(self, handle: str) -> list:
        return self.get_json(f"/people/{handle}/timeline")


_CLIENT: GrampsClient | None = None


def _default_token_cache_path(config: GrampsConfig) -> Path:
    """Per-config cache file path, so different trees/servers don't collide."""
    cache_dir = Path(os.environ.get("GENECREW_TOKEN_CACHE", Path.home() / ".cache" / "genecrew"))
    digest = hashlib.sha256(f"{config.api_url}|{config.username}".encode()).hexdigest()[:16]
    return cache_dir / f"gramps-token-{digest}.json"


def get_client() -> GrampsClient:
    """Lazy per-process singleton configured from the environment.

    Uses a default on-disk token cache so real invocations reuse the JWT
    across process runs instead of logging in (and risking 429s) every time.
    """
    global _CLIENT
    if _CLIENT is None:
        config = GrampsConfig.from_env()
        _CLIENT = GrampsClient(config, token_cache=_default_token_cache_path(config))
    return _CLIENT
