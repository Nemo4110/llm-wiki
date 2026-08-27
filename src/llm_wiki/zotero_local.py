"""Temporary direct writer for the Zotero 10 local API.

TEMPORARY boundary relaxation (see docs/ZOTERO_MCP_INTEGRATION.md): writes may go
directly to the Zotero 10 local HTTP API; reads still go through zotero-mcp.
Remove this once zotero-mcp adopts local writes.

Local write handshake (Zotero 10+):
  - every write needs a ``Zotero-Server-ID`` header, read live from ``GET /api/``;
  - writes need a per-app key from ``POST /api/local/authorize`` (the user approves
    a dialog in Zotero Desktop; "Always Allow" makes the key reusable);
  - each PATCH is guarded by ``If-Unmodified-Since-Version`` (optimistic concurrency).

The reusable key is loaded from a gitignored store under ``var/`` and is never
logged or printed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import urlparse

import httpx

from .agent_logger import get_logger

LOG = get_logger("zotero_local")

DEFAULT_BASE_URL = "http://127.0.0.1:23119"
DEFAULT_USER_PREFIX = "users/0"
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class LocalWriteError(RuntimeError):
    """Raised when a local Zotero write cannot be completed."""


def _validate_loopback(base_url: str) -> None:
    """The reusable key grants unscoped local-library write; only send it to loopback."""
    host = (urlparse(base_url).hostname or "").strip().lower()
    if host not in _LOOPBACK_HOSTS:
        raise LocalWriteError(f"local write base_url must be a loopback host, got {base_url!r}")


def _tag_names(raw_tags: Any) -> List[str]:
    names: List[str] = []
    for raw in raw_tags or []:
        name = str(raw.get("tag") if isinstance(raw, Mapping) else raw).strip()
        if name:
            names.append(name)
    return names


def _upsert_extra_lines(extra: str, set_keys: Mapping[str, str]) -> str:
    """Upsert ``Key: Value`` lines into a Zotero ``extra`` field, preserving other lines.

    Produces lines parseable by ``zotero_refresh.parse_extra_keys`` (the verifier's
    view): an existing line whose key matches is replaced, a new key is appended,
    unrelated lines are kept verbatim and in order, and a pre-existing duplicate
    line for a managed key is dropped so the verifier (which reads the last
    occurrence) sees the freshly written value.
    """
    remaining = dict(set_keys)
    out: List[str] = []
    for line in str(extra or "").splitlines():
        if ":" in line:
            key = line.split(":", 1)[0].strip()
            if key in set_keys:
                if key in remaining:
                    out.append(f"{key}: {remaining.pop(key)}")
                # a second line for an already-upserted key is a stale duplicate: drop it
                continue
        out.append(line)
    for key, value in remaining.items():
        out.append(f"{key}: {value}")
    return "\n".join(out)


class LocalZoteroWriter:
    """Minimal async writer for the Zotero 10 local API.

    ``http`` is an optional injected ``httpx.AsyncClient`` (used by tests with a
    MockTransport); when omitted the writer creates and owns one.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        user_prefix: str = DEFAULT_USER_PREFIX,
        timeout: float = 20.0,
        http: Optional[httpx.AsyncClient] = None,
    ) -> None:
        _validate_loopback(base_url)
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._prefix = user_prefix.strip("/")
        self._timeout = timeout
        self._http = http
        self._owns_http = http is None
        self._server_id_cache: Optional[str] = None

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=httpx.Timeout(self._timeout))
        return self._http

    async def aclose(self) -> None:
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _server_id(self) -> str:
        if self._server_id_cache is None:
            client = await self._client()
            resp = await client.get(f"{self._base_url}/api/")
            resp.raise_for_status()
            server_id = resp.headers.get("Zotero-Server-ID")
            if not server_id:
                raise LocalWriteError("local API did not return a Zotero-Server-ID header")
            self._server_id_cache = server_id
        return self._server_id_cache

    async def _get_item(self, item_key: str) -> Tuple[int, Dict[str, Any]]:
        client = await self._client()
        resp = await client.get(f"{self._base_url}/api/{self._prefix}/items/{item_key}")
        if resp.status_code != 200:
            raise LocalWriteError(f"GET item {item_key} -> HTTP {resp.status_code}")
        payload = resp.json()
        return payload.get("version"), payload.get("data") or {}

    async def _patch_item(self, item_key: str, patch: Mapping[str, Any], version: int) -> None:
        if version is None:
            raise LocalWriteError(f"item {item_key} returned no version; cannot set If-Unmodified-Since-Version")
        client = await self._client()
        server_id = await self._server_id()
        resp = await client.patch(
            f"{self._base_url}/api/{self._prefix}/items/{item_key}",
            json=dict(patch),
            headers={
                "Zotero-Server-ID": server_id,
                "Zotero-API-Key": self._api_key,
                "If-Unmodified-Since-Version": str(version),
                "Content-Type": "application/json",
            },
        )
        if resp.status_code >= 400:
            raise LocalWriteError(f"PATCH item {item_key} -> HTTP {resp.status_code}: {resp.text[:200]}")

    async def write_safe_mutation(
        self,
        item_key: str,
        *,
        set_keys: Optional[Mapping[str, Any]] = None,
        add_tags=(),
        remove_tags=(),
        fields: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Apply one item's safe mutation via the local API (mirrors the MCP writer).

        One PATCH carries tags + extra + field updates together so the change is
        atomic and the run_live_refresh verify loop sees a single consistent state.
        """
        normalized_keys = {str(k): str(v) for k, v in (set_keys or {}).items() if v is not None}
        add = sorted({str(t) for t in add_tags if str(t).strip()})
        remove = {str(t) for t in remove_tags if str(t).strip()}
        field_updates = {str(k): v for k, v in (fields or {}).items()}
        if not (normalized_keys or add or remove or field_updates):
            return

        version, data = await self._get_item(item_key)
        patch: Dict[str, Any] = {}
        if add or remove:
            current = _tag_names(data.get("tags"))
            merged = [name for name in current if name not in remove]
            for name in add:
                if name not in merged:
                    merged.append(name)
            patch["tags"] = [{"tag": name} for name in merged]
        if normalized_keys:
            patch["extra"] = _upsert_extra_lines(str(data.get("extra") or ""), normalized_keys)
        for key, value in field_updates.items():
            patch[key] = value

        LOG.info(
            "local write %s: tags +%d -%d, set_keys=%d, fields=%s",
            item_key, len(add), len(remove), len(normalized_keys), sorted(field_updates),
        )
        await self._patch_item(item_key, patch, version)

    @classmethod
    def from_store(cls, store_path, **kwargs) -> "LocalZoteroWriter":
        """Build a writer from the reusable key saved by ``authorize_local``."""
        return cls(load_local_key(store_path), **kwargs)


async def authorize_local(
    app_name: str,
    store_path,
    *,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 180.0,
    http: Optional[httpx.AsyncClient] = None,
) -> str:
    """Obtain a reusable local write key and store it (mode 0600) at ``store_path``.

    Triggers an approval dialog in Zotero Desktop; choose "Always Allow" for a
    reusable key. The key is written to the gitignored store and returned, never
    logged. ``http`` is injectable for tests.
    """
    base = base_url.rstrip("/")
    _validate_loopback(base)
    client = http if http is not None else httpx.AsyncClient(timeout=httpx.Timeout(timeout))
    try:
        resp = await client.get(f"{base}/api/")
        resp.raise_for_status()
        server_id = resp.headers.get("Zotero-Server-ID")
        if not server_id:
            raise LocalWriteError("local API did not return a Zotero-Server-ID header")

        resp = await client.post(
            f"{base}/api/local/authorize",
            json={"appName": app_name},
            headers={"Zotero-Server-ID": server_id, "Content-Type": "application/json"},
        )
        if resp.status_code >= 400:
            raise LocalWriteError(f"authorize -> HTTP {resp.status_code}: {resp.text[:200]}")
        key = str((resp.json() or {}).get("key") or "")
        if not key:
            raise LocalWriteError("authorization returned no key (user may have denied the dialog)")

        store_path = Path(store_path)
        store_path.parent.mkdir(parents=True, exist_ok=True)
        # create with 0600 from the start so the key never sits world-readable
        fd = os.open(store_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, (json.dumps({"app_name": app_name, "key": key}, indent=2) + "\n").encode("utf-8"))
        finally:
            os.close(fd)
        os.chmod(store_path, 0o600)  # tighten a pre-existing looser file too
        LOG.info("stored local write key at %s", store_path)
        return key
    finally:
        if http is None:
            await client.aclose()


def load_local_key(store_path) -> str:
    """Read the reusable local write key from the gitignored store."""
    store_path = Path(store_path)
    try:
        data = json.loads(store_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LocalWriteError(
            f"no local write key at {store_path}; run `agent-bridge.py zotero-local-auth` first"
        ) from exc
    key = str(data.get("key") or "")
    if not key:
        raise LocalWriteError(f"no key stored in {store_path}; run `agent-bridge.py zotero-local-auth` first")
    return key
