"""Tests for the temporary direct Zotero 10 local-API write backend.

All tests use httpx.MockTransport with synthetic fixtures — no real Zotero, no
real network. Expected values come from the fixtures, not recomputed from the
implementation.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from src.llm_wiki.zotero.local import LocalWriteError, LocalZoteroWriter, authorize_local
from src.llm_wiki.zotero.refresh import parse_extra_keys

ITEM_KEY = "TESTKEY1"
SERVER_ID = "SID123"
API_KEY = "SECRETKEY"

BASE_ITEM = {
    "key": ITEM_KEY,
    "version": 5,
    "data": {
        "key": ITEM_KEY,
        "version": 5,
        "tags": [{"tag": "重排"}],
        "extra": "LLM-Wiki DOI Verified: 2026-01-01",
        "url": "",
    },
}


def make_transport(captured, item=None, get_item=None):
    """MockTransport handler for the Zotero local API.

    captured: list that collects PATCH requests for assertion.
    get_item: optional callable returning the current item JSON (lets a test
              mutate state between the pre-write GET and any later GET).
    """
    state = {"item": json.loads(json.dumps(item if item is not None else BASE_ITEM))}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/":
            return httpx.Response(200, headers={"Zotero-Server-ID": SERVER_ID})
        if path == f"/api/users/0/items/{ITEM_KEY}":
            if request.method == "GET":
                current = get_item() if get_item else state["item"]
                return httpx.Response(200, json=current)
            if request.method == "PATCH":
                captured.append(request)
                body = json.loads(request.content)
                if not get_item:
                    state["item"]["data"].update(body)
                    state["item"]["version"] += 1
                    state["item"]["data"]["version"] = state["item"]["version"]
                return httpx.Response(204)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def run(coro):
    return asyncio.run(coro)


def test_write_add_tags_sends_versioned_patch_with_merged_tags():
    captured = []
    http = httpx.AsyncClient(transport=make_transport(captured))
    writer = LocalZoteroWriter(API_KEY, http=http)

    run(writer.write_safe_mutation(ITEM_KEY, add_tags=["llm-wiki:ingested"]))

    assert len(captured) == 1
    req = captured[0]
    assert req.headers["Zotero-Server-ID"] == SERVER_ID
    assert req.headers["Zotero-API-Key"] == API_KEY
    assert req.headers["If-Unmodified-Since-Version"] == "5"
    body = json.loads(req.content)
    assert {"tag": "重排"} in body["tags"]
    assert {"tag": "llm-wiki:ingested"} in body["tags"]


def test_write_remove_tags_drops_only_the_named_tag():
    item = json.loads(json.dumps(BASE_ITEM))
    item["data"]["tags"] = [{"tag": "重排"}, {"tag": "llm-wiki:doi-missing"}]
    captured = []
    http = httpx.AsyncClient(transport=make_transport(captured, item=item))
    writer = LocalZoteroWriter(API_KEY, http=http)

    run(writer.write_safe_mutation(ITEM_KEY, remove_tags=["llm-wiki:doi-missing"]))

    body = json.loads(captured[0].content)
    assert {"tag": "重排"} in body["tags"]
    assert {"tag": "llm-wiki:doi-missing"} not in body["tags"]


def test_write_set_keys_upserts_extra_lines_without_duplicates():
    captured = []
    http = httpx.AsyncClient(transport=make_transport(captured))
    writer = LocalZoteroWriter(API_KEY, http=http)

    run(writer.write_safe_mutation(
        ITEM_KEY,
        set_keys={
            "LLM-Wiki DOI Verified": "2026-08-27",      # existing key -> replace, not duplicate
            "LLM-Wiki Citation Checked": "2026-08-27",  # new key -> append
        },
    ))

    body = json.loads(captured[0].content)
    extra = body["extra"]
    # the verifier parses extra with parse_extra_keys; assert against that same view
    parsed = parse_extra_keys(extra)
    assert parsed["LLM-Wiki DOI Verified"] == "2026-08-27"
    assert parsed["LLM-Wiki Citation Checked"] == "2026-08-27"
    doi_lines = [ln for ln in extra.splitlines() if ln.startswith("LLM-Wiki DOI Verified:")]
    assert doi_lines == ["LLM-Wiki DOI Verified: 2026-08-27"]


def test_write_fields_updates_url_without_touching_tags_or_extra():
    captured = []
    http = httpx.AsyncClient(transport=make_transport(captured))
    writer = LocalZoteroWriter(API_KEY, http=http)

    run(writer.write_safe_mutation(ITEM_KEY, fields={"url": "https://doi.org/10.1234/x"}))

    body = json.loads(captured[0].content)
    assert body["url"] == "https://doi.org/10.1234/x"
    assert "tags" not in body
    assert "extra" not in body


def test_write_with_no_changes_makes_no_request():
    captured = []
    http = httpx.AsyncClient(transport=make_transport(captured))
    writer = LocalZoteroWriter(API_KEY, http=http)

    run(writer.write_safe_mutation(ITEM_KEY))

    assert captured == []


def test_patch_error_status_raises_localwriteerror():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/":
            return httpx.Response(200, headers={"Zotero-Server-ID": SERVER_ID})
        if request.method == "GET":
            return httpx.Response(200, json=BASE_ITEM)
        if request.method == "PATCH":
            return httpx.Response(412)  # version conflict
        return httpx.Response(404)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    writer = LocalZoteroWriter(API_KEY, http=http)

    with pytest.raises(LocalWriteError):
        run(writer.write_safe_mutation(ITEM_KEY, add_tags=["x"]))


def test_authorize_local_handshake_stores_reusable_key(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/":
            return httpx.Response(200, headers={"Zotero-Server-ID": SERVER_ID})
        if request.url.path == "/api/local/authorize" and request.method == "POST":
            assert request.headers["Zotero-Server-ID"] == SERVER_ID
            assert json.loads(request.content) == {"appName": "llm-wiki"}
            return httpx.Response(200, json={"key": "NEWKEY32", "remember": True})
        return httpx.Response(404)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    store = tmp_path / "zotero-local.json"

    key = run(authorize_local("llm-wiki", store, http=http))

    assert key == "NEWKEY32"
    saved = json.loads(store.read_text(encoding="utf-8"))
    assert saved["key"] == "NEWKEY32"


def test_authorize_local_can_keep_key_in_process_memory_only(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/":
            return httpx.Response(200, headers={"Zotero-Server-ID": SERVER_ID})
        if request.url.path == "/api/local/authorize":
            return httpx.Response(200, json={"key": "MEMORYKEY", "remember": False})
        return httpx.Response(404)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    key = run(authorize_local("llm-wiki", None, http=http))

    assert key == "MEMORYKEY"
    assert list(tmp_path.iterdir()) == []


def test_write_preserves_full_existing_tag_objects():
    item = json.loads(json.dumps(BASE_ITEM))
    item["data"]["tags"] = [{"tag": "automatic", "type": 1}]
    captured = []
    http = httpx.AsyncClient(transport=make_transport(captured, item=item))
    writer = LocalZoteroWriter(API_KEY, http=http)

    run(writer.write_safe_mutation(ITEM_KEY, add_tags=["llm-wiki:ingested"]))

    body = json.loads(captured[0].content)
    assert {"tag": "automatic", "type": 1} in body["tags"]
    assert {"tag": "llm-wiki:ingested"} in body["tags"]


def test_write_retries_one_version_conflict_from_fresh_state():
    state = {"item": json.loads(json.dumps(BASE_ITEM)), "patches": 0}
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/":
            return httpx.Response(200, headers={"Zotero-Server-ID": SERVER_ID})
        if request.url.path != f"/api/users/0/items/{ITEM_KEY}":
            return httpx.Response(404)
        if request.method == "GET":
            return httpx.Response(200, json=state["item"])
        captured.append(request)
        state["patches"] += 1
        if state["patches"] == 1:
            state["item"]["version"] = 6
            state["item"]["data"]["version"] = 6
            state["item"]["data"]["tags"].append({"tag": "concurrent", "type": 1})
            return httpx.Response(412)
        state["item"]["data"].update(json.loads(request.content))
        state["item"]["version"] = 7
        state["item"]["data"]["version"] = 7
        return httpx.Response(204)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    writer = LocalZoteroWriter(API_KEY, http=http)

    result = run(writer.write_safe_mutation(ITEM_KEY, add_tags=["llm-wiki:ingested"]))

    assert result.status == "updated_verified"
    assert result.attempts == 2
    assert len(captured) == 2
    assert captured[1].headers["If-Unmodified-Since-Version"] == "6"
    assert {"tag": "concurrent", "type": 1} in json.loads(captured[1].content)["tags"]


def test_write_fails_when_read_after_write_does_not_match():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/":
            return httpx.Response(200, headers={"Zotero-Server-ID": SERVER_ID})
        if request.method == "GET":
            return httpx.Response(200, json=BASE_ITEM)
        if request.method == "PATCH":
            return httpx.Response(204)
        return httpx.Response(404)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    writer = LocalZoteroWriter(API_KEY, http=http)

    with pytest.raises(LocalWriteError, match="verification"):
        run(writer.write_safe_mutation(ITEM_KEY, add_tags=["llm-wiki:ingested"]))


def test_patch_failure_does_not_echo_api_key():
    leaked = "KEY-MUST-NOT-LEAK"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/":
            return httpx.Response(200, headers={"Zotero-Server-ID": SERVER_ID})
        if request.method == "GET":
            return httpx.Response(200, json=BASE_ITEM)
        if request.method == "PATCH":
            return httpx.Response(500, text=f"debug api key={leaked}")
        return httpx.Response(404)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    writer = LocalZoteroWriter(leaked, http=http)

    with pytest.raises(LocalWriteError) as exc_info:
        run(writer.write_safe_mutation(ITEM_KEY, add_tags=["x"]))

    assert leaked not in str(exc_info.value)


def test_existing_reciprocal_relation_pair_is_a_noop():
    target_key = "TARGET01"
    source_uri = "http://zotero.org/users/1234/items/TESTKEY1"
    target_uri = "http://zotero.org/users/1234/items/TARGET01"
    items = {
        ITEM_KEY: {
            "key": ITEM_KEY, "version": 5, "library": {"type": "user", "id": 1234},
            "data": {"key": ITEM_KEY, "version": 5, "relations": {"dc:relation": [target_uri]}},
        },
        target_key: {
            "key": target_key, "version": 9, "library": {"type": "user", "id": 1234},
            "data": {"key": target_key, "version": 9, "relations": {"dc:relation": [source_uri]}},
        },
    }
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/":
            return httpx.Response(200, headers={"Zotero-Server-ID": SERVER_ID})
        key = request.url.path.rsplit("/", 1)[-1]
        if request.method == "GET" and key in items:
            return httpx.Response(200, json=items[key])
        if request.method == "PATCH":
            captured.append(request)
            return httpx.Response(204)
        return httpx.Response(404)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    writer = LocalZoteroWriter(API_KEY, http=http)

    result = run(writer.ensure_relation_pair(ITEM_KEY, target_key))

    assert result.changed_items == ()
    assert captured == []


def test_relation_pair_repairs_only_missing_direction():
    target_key = "TARGET01"
    source_uri = "http://zotero.org/users/1234/items/TESTKEY1"
    target_uri = "http://zotero.org/users/1234/items/TARGET01"
    items = {
        ITEM_KEY: {
            "key": ITEM_KEY, "version": 5, "library": {"type": "user", "id": 1234},
            "data": {"key": ITEM_KEY, "version": 5, "relations": {"dc:relation": [target_uri]}},
        },
        target_key: {
            "key": target_key, "version": 9, "library": {"type": "user", "id": 1234},
            "data": {"key": target_key, "version": 9, "relations": {"owl:sameAs": "https://example.test/work"}},
        },
    }
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/":
            return httpx.Response(200, headers={"Zotero-Server-ID": SERVER_ID})
        key = request.url.path.rsplit("/", 1)[-1]
        if key not in items:
            return httpx.Response(404)
        if request.method == "GET":
            return httpx.Response(200, json=items[key])
        captured.append((key, request))
        body = json.loads(request.content)
        items[key]["data"].update(body)
        items[key]["version"] += 1
        items[key]["data"]["version"] = items[key]["version"]
        return httpx.Response(204)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    writer = LocalZoteroWriter(API_KEY, http=http)

    result = run(writer.ensure_relation_pair(ITEM_KEY, target_key))

    assert result.changed_items == (target_key,)
    assert [key for key, _ in captured] == [target_key]
    relations = json.loads(captured[0][1].content)["relations"]
    assert relations["owl:sameAs"] == "https://example.test/work"
    assert relations["dc:relation"] == [source_uri]


def test_writer_rejects_non_loopback_base_url():
    with pytest.raises(LocalWriteError):
        LocalZoteroWriter(API_KEY, base_url="https://evil.example.com")


def test_load_local_key_missing_file_raises_clear_error(tmp_path):
    from src.llm_wiki.zotero.local import load_local_key

    with pytest.raises(LocalWriteError, match="zotero-local-auth"):
        load_local_key(tmp_path / "nonexistent.json")


def test_upsert_extra_lines_drops_duplicate_keys():
    from src.llm_wiki.zotero.local import _upsert_extra_lines

    extra = "LLM-Wiki DOI Status: missing\nLLM-Wiki DOI Status: stale"
    out = _upsert_extra_lines(extra, {"LLM-Wiki DOI Status": "verified"})
    assert out.splitlines().count("LLM-Wiki DOI Status: verified") == 1
    assert "stale" not in out
    assert "missing" not in out


def test_aclose_does_not_close_injected_client():
    http = httpx.AsyncClient(transport=make_transport([]))
    writer = LocalZoteroWriter(API_KEY, http=http)

    run(writer.aclose())

    assert not http.is_closed  # injected client is owned by the caller, not the writer



class _FakeCrossref:
    async def get_work(self, doi):
        return {}

    async def search_works(self, title, *, author="", rows=5):
        return []


class _FakeOpenAlex:
    async def get_work_by_doi(self, doi):
        return {}

    async def get_source(self, source_id):
        return {}


def test_run_live_refresh_local_backend_writes_via_local_writer(tmp_path, monkeypatch):
    """write_backend="local" must route the write to LocalZoteroWriter, not the MCP client.

    A shared dict models the hybrid reality: the local write lands in the same
    local database the MCP read path serves, so the existing verify loop sees it.
    """
    from src.llm_wiki.zotero import refresh as zr

    key = "ITEM0001"
    db = {
        key: {
            "key": key,
            "version": 1,
            "itemType": "journalArticle",
            "title": "Some Paper",
            "date": "2024",
            "tags": [],
            "extra": "",
            "url": "",
            "creators": [],
        }
    }

    class FakeMCP:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get_collection_item_keys(self, collection_key, *, limit=500):
            return ("Coll", [key])

        async def get_items(self, keys, *, concurrency=4):
            return [db[k] for k in keys]

        async def get_items_tolerant(self, keys, *, concurrency=4):
            return [db[k] for k in keys], []

        async def write_safe_mutation(self, item_key, **kwargs):
            raise AssertionError("MCP write path must NOT be used in local backend")

    class FakeLocalWriter:
        def __init__(self):
            self.calls = []

        @classmethod
        def from_store(cls, *a, **k):
            return cls()

        async def write_safe_mutation(self, item_key, *, set_keys=None, add_tags=(), remove_tags=(), fields=None):
            self.calls.append(item_key)
            data = db[item_key]
            tags = {t["tag"] for t in data.get("tags", [])}
            tags |= set(add_tags)
            tags -= set(remove_tags)
            data["tags"] = [{"tag": t} for t in sorted(tags)]
            extra = zr.parse_extra_keys(data.get("extra", ""))
            extra.update({k: str(v) for k, v in (set_keys or {}).items()})
            data["extra"] = "\n".join(f"{k}: {v}" for k, v in extra.items())
            data.update(fields or {})
            data["version"] += 1

        async def aclose(self):
            pass

    monkeypatch.setattr(zr, "ZoteroMCPClient", FakeMCP)
    monkeypatch.setattr(zr, "LocalZoteroWriter", FakeLocalWriter)
    monkeypatch.setattr(zr, "CrossrefProvider", lambda *a, **k: _FakeCrossref())
    monkeypatch.setattr(zr, "OpenAlexProvider", lambda *a, **k: _FakeOpenAlex())

    report = run(zr.run_live_refresh(
        tmp_path,
        collection_key="C1",
        settings=zr.RefreshSettings(),
        cache_path=tmp_path / "cache.sqlite",
        mcp_config_path=tmp_path / ".mcp.json",
        write_backend="local",
        local_store_path=tmp_path / "var" / "zotero-local.json",
        force=True,
        apply_safe=True,
    ))

    # a DOI-missing academic item yields a safe mutation, applied via the local writer
    assert report.applied_count == 1
    assert report.items[0].applied is True


def _items_state(source_relations=None, target_relations=None):
    target_key = "TARGET01"
    source_uri = f"http://zotero.org/users/1234/items/{ITEM_KEY}"
    target_uri = f"http://zotero.org/users/1234/items/{target_key}"
    items = {
        ITEM_KEY: {
            "key": ITEM_KEY, "version": 5, "library": {"type": "user", "id": 1234},
            "data": {"key": ITEM_KEY, "version": 5,
                     "relations": {"dc:relation": list(source_relations or [])}},
        },
        target_key: {
            "key": target_key, "version": 9, "library": {"type": "user", "id": 1234},
            "data": {"key": target_key, "version": 9,
                     "relations": {"dc:relation": list(target_relations or [])}},
        },
    }
    return items, target_key, source_uri, target_uri


def _relation_handler(items, captured, fail_patch_for=(), fail_times=None):
    """MockTransport handler; fail_patch_for keys get HTTP 500 on PATCH (fail_times bounds it)."""
    fails = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/":
            return httpx.Response(200, headers={"Zotero-Server-ID": SERVER_ID})
        key = request.url.path.rsplit("/", 1)[-1]
        if key not in items:
            return httpx.Response(404)
        if request.method == "GET":
            return httpx.Response(200, json=items[key])
        if request.method == "PATCH":
            captured.append((key, json.loads(request.content)))
            if key in fail_patch_for and (fail_times is None or fails["n"] < fail_times):
                fails["n"] += 1
                return httpx.Response(500, text="boom")
            body = json.loads(request.content)
            items[key]["data"].update(body)
            items[key]["version"] += 1
            items[key]["data"]["version"] = items[key]["version"]
            return httpx.Response(204)
        return httpx.Response(404)

    return handler


def test_write_retries_conflicts_with_bounded_backoff():
    state = {"item": json.loads(json.dumps(BASE_ITEM))}
    conflicts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/":
            return httpx.Response(200, headers={"Zotero-Server-ID": SERVER_ID})
        if request.method == "GET":
            return httpx.Response(200, json=state["item"])
        if request.method == "PATCH":
            if conflicts["n"] < 2:
                conflicts["n"] += 1
                return httpx.Response(412)
            body = json.loads(request.content)
            state["item"]["data"].update(body)
            state["item"]["version"] += 1
            state["item"]["data"]["version"] = state["item"]["version"]
            return httpx.Response(204)
        return httpx.Response(404)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    writer = LocalZoteroWriter(API_KEY, http=http, retry_delays=(0, 0, 0))

    result = run(writer.write_safe_mutation(ITEM_KEY, add_tags=["llm-wiki:ingested"]))

    assert result.status == "updated_verified"
    assert result.attempts == 3


def test_write_exhausts_bounded_retries():
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/":
            return httpx.Response(200, headers={"Zotero-Server-ID": SERVER_ID})
        if request.method == "GET":
            return httpx.Response(200, json=json.loads(json.dumps(BASE_ITEM)))
        if request.method == "PATCH":
            attempts["n"] += 1
            return httpx.Response(412)
        return httpx.Response(404)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    writer = LocalZoteroWriter(API_KEY, http=http, retry_delays=(0, 0))

    with pytest.raises(LocalWriteError, match="conflicted"):
        run(writer.write_safe_mutation(ITEM_KEY, add_tags=["llm-wiki:ingested"]))
    assert attempts["n"] == 3  # 1 次初始 + 2 次退避重试


def test_relation_pair_compensates_when_second_direction_fails():
    items, target_key, source_uri, target_uri = _items_state()
    captured = []
    handler = _relation_handler(items, captured, fail_patch_for={target_key})
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    writer = LocalZoteroWriter(API_KEY, http=http, retry_delays=(0,))

    with pytest.raises(LocalWriteError):
        run(writer.ensure_relation_pair(ITEM_KEY, target_key))

    # 第一次 source PATCH 添加 target_uri;第二次 source PATCH 补偿移除
    source_patches = [body for key, body in captured if key == ITEM_KEY]
    assert len(source_patches) == 2
    added = source_patches[0]["relations"]["dc:relation"]
    removed = source_patches[1]["relations"].get("dc:relation", [])
    assert target_uri in added
    assert target_uri not in removed
    final = items[ITEM_KEY]["data"]["relations"].get("dc:relation", [])
    assert target_uri not in final


def test_relation_pair_reports_residue_when_compensation_fails():
    items, target_key, source_uri, target_uri = _items_state()
    captured = []
    # target 永远 500;source 第二次 PATCH(补偿)也失败
    fail_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/":
            return httpx.Response(200, headers={"Zotero-Server-ID": SERVER_ID})
        key = request.url.path.rsplit("/", 1)[-1]
        if key not in items:
            return httpx.Response(404)
        if request.method == "GET":
            return httpx.Response(200, json=items[key])
        if request.method == "PATCH":
            captured.append((key, json.loads(request.content)))
            if key == target_key:
                return httpx.Response(500, text="boom")
            if key == ITEM_KEY:
                fail_calls["n"] += 1
                if fail_calls["n"] > 1:  # 补偿写入失败
                    return httpx.Response(500, text="boom")
            body = json.loads(request.content)
            items[key]["data"].update(body)
            items[key]["version"] += 1
            items[key]["data"]["version"] = items[key]["version"]
            return httpx.Response(204)
        return httpx.Response(404)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    writer = LocalZoteroWriter(API_KEY, http=http, retry_delays=(0,))

    with pytest.raises(LocalWriteError, match="compensation"):
        run(writer.ensure_relation_pair(ITEM_KEY, target_key))


def test_repoint_attachment_preserves_item_identity_and_protected_fields(tmp_path):
    item = json.loads(json.dumps(BASE_ITEM))
    item["data"].update(
        {
            "itemType": "attachment",
            "linkMode": "imported_file",
            "path": "storage:paper.pdf",
            "parentItem": "PARENT01",
            "filename": "paper.pdf",
            "contentType": "application/pdf",
            "relations": {"dc:relation": ["http://zotero.org/users/1/items/OTHER001"]},
        }
    )
    captured = []
    target = tmp_path / "managed" / "paper.pdf"
    http = httpx.AsyncClient(transport=make_transport(captured, item=item))
    writer = LocalZoteroWriter(API_KEY, http=http)

    result = run(writer.repoint_attachment(ITEM_KEY, str(target), expected_parent_item="PARENT01"))

    assert result.status.startswith("updated")
    assert result.before_link_mode == "imported_file"
    assert result.before_path == "storage:paper.pdf"
    body = json.loads(captured[0].content)
    assert body == {"linkMode": "linked_file", "path": str(target)}


def test_repoint_attachment_rejects_non_attachment_item(tmp_path):
    captured = []
    http = httpx.AsyncClient(transport=make_transport(captured))
    writer = LocalZoteroWriter(API_KEY, http=http)

    # tmp_path is absolute on every platform; the item-type check must be reached.
    with pytest.raises(LocalWriteError, match="not a Zotero attachment"):
        run(writer.repoint_attachment(ITEM_KEY, str(tmp_path / "paper.pdf")))


def _attachment_item():
    item = json.loads(json.dumps(BASE_ITEM))
    item["data"].update(
        {
            "itemType": "attachment",
            "linkMode": "imported_file",
            "path": "storage:paper.pdf",
            "parentItem": "PARENT01",
            "filename": "paper.pdf",
            "contentType": "application/pdf",
        }
    )
    return item


def test_repoint_attachment_accepts_base_relative_target():
    captured = []
    http = httpx.AsyncClient(transport=make_transport(captured, item=_attachment_item()))
    writer = LocalZoteroWriter(API_KEY, http=http)

    result = run(writer.repoint_attachment(
        ITEM_KEY, "attachments:Papers/paper.pdf", expected_parent_item="PARENT01"
    ))

    assert result.status.startswith("updated")
    body = json.loads(captured[0].content)
    assert body == {"linkMode": "linked_file", "path": "attachments:Papers/paper.pdf"}


def test_repoint_attachment_rejects_unsafe_base_relative_target():
    captured = []
    http = httpx.AsyncClient(transport=make_transport(captured, item=_attachment_item()))
    writer = LocalZoteroWriter(API_KEY, http=http)

    for bad in (
        "attachments:../evil.pdf",
        "attachments:",
        "attachments:C:\\evil.pdf",
        "attachments:/absolute/evil.pdf",
        "relative/no-prefix.pdf",
    ):
        with pytest.raises(LocalWriteError):
            run(writer.repoint_attachment(ITEM_KEY, bad))
    assert captured == []
