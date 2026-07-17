"""Pure httpx client for the Gramps Web REST API.

JWT auth with lazy fetch and single refresh on 401. `GRAMPS_API_URL` already
includes the `/api` suffix, so all paths here are relative ("/people/").
This module is NOT a CrewAI tool: it is consumed directly by the genecrew
orchestrator (no LLM) and wrapped by the thin BaseTool classes in read_tools.py.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_TIMEOUT = 15.0


class GrampsConfigError(RuntimeError):
    """Raised when the Gramps environment configuration is incomplete."""


@dataclass(frozen=True)
class GrampsConfig:
    """Connection settings for one Gramps Web instance."""

    api_url: str
    username: str
    password: str

    @staticmethod
    def from_env() -> "GrampsConfig":
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


class GrampsClient:
    """Thin synchronous Gramps Web client; one instance per process."""

    def __init__(
        self,
        config: GrampsConfig,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config
        self._http = httpx.Client(
            base_url=config.api_url, timeout=DEFAULT_TIMEOUT, transport=transport
        )
        self._token: str | None = None

    def _fetch_token(self) -> str:
        response = self._http.post(
            "/token/",
            json={"username": self._config.username, "password": self._config.password},
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if self._token is None:
            self._token = self._fetch_token()
        headers = {"Authorization": f"Bearer {self._token}"}
        response = self._http.request(method, path, headers=headers, **kwargs)
        if response.status_code == 401:  # expired token: refresh once
            self._token = self._fetch_token()
            headers = {"Authorization": f"Bearer {self._token}"}
            response = self._http.request(method, path, headers=headers, **kwargs)
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


def get_client() -> GrampsClient:
    """Lazy per-process singleton configured from the environment."""
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = GrampsClient(GrampsConfig.from_env())
    return _CLIENT
