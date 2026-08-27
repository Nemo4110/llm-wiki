"""Tests for authorized Zotero collection write-back manifests and verification."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from src.llm_wiki.zotero_local import (
    LocalItem,
    LocalMutationResult,
    RelationAudit,
    RelationWriteResult,
)
from src.llm_wiki.zotero_writeback import (
    WritePlanError,
    apply_write_plan,
    audit_write_plan,
    load_write_plan,
    report_to_manifest,
    verify_write_plan,
)


def run(coro):
    return asyncio.run(coro)


def write_plan(path, *, extra="", mode="authorized-write"):
    path.write_text(
        f"""version: 1
mode: {mode}
library_id: "0"
collection:
  key: COLL0001
  name: blogs/DeepLearning
policy:
  preserve_existing_tags: true
  replace_tags: false
  write_notes: false
  change_collections: false
  change_metadata: false
  relation_policy: reviewed-only
items:
  - item_key: ITEM0001
    expected_collections: [COLL0001]
    desired_managed_tags:
      - llm-wiki:ingested
      - llm-wiki:Deep-Learning
    reviewed_relations: [ITEM0002]
  - item_key: ITEM0002
    expected_collections: [COLL0001]
    desired_managed_tags: [llm-wiki:ingested]
    reviewed_relations: [ITEM0001]
{extra}""",
        encoding="utf-8",
    )


class FakeWriter:
    def __init__(self):
        self.items = {
            "ITEM0001": LocalItem(
                "ITEM0001",
                1,
                {
                    "key": "ITEM0001",
                    "tags": [{"tag": "manual", "type": 1}],
                    "collections": ["COLL0001"],
                },
                "user",
                "1234",
            ),
            "ITEM0002": LocalItem(
                "ITEM0002",
                2,
                {
                    "key": "ITEM0002",
                    "tags": [{"tag": "llm-wiki:ingested"}],
                    "collections": ["COLL0001"],
                },
                "user",
                "1234",
            ),
        }
        self.reciprocal = False
        self.write_calls = []
        self.relation_calls = []

    async def get_item(self, key):
        return self.items[key]

    async def write_safe_mutation(self, key, *, add_tags=(), **kwargs):
        self.write_calls.append((key, tuple(add_tags)))
        item = self.items[key]
        tags = list(item.data.get("tags") or [])
        names = {tag["tag"] for tag in tags}
        for tag in add_tags:
            if tag not in names:
                tags.append({"tag": tag})
        data = dict(item.data)
        data["tags"] = tags
        self.items[key] = replace(item, version=item.version + 1, data=data)
        status = "updated_verified" if add_tags else "skipped_current"
        return LocalMutationResult(key, status, 1, ("tags",))

    async def audit_relation_pair(self, source, target):
        return RelationAudit(source, target, self.reciprocal, self.reciprocal)

    async def ensure_relation_pair(self, source, target):
        self.relation_calls.append((source, target))
        self.reciprocal = True
        return RelationWriteResult(source, target, (source, target))



def test_load_write_plan_accepts_restricted_authorized_schema(tmp_path):
    path = tmp_path / "plan.yaml"
    write_plan(path)

    plan = load_write_plan(path)

    assert plan.collection_key == "COLL0001"
    assert [item.item_key for item in plan.items] == ["ITEM0001", "ITEM0002"]
    assert plan.policy.relation_policy == "reviewed-only"


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        ("api_key: do-not-store\n", "credential"),
        ("", "mode"),
    ],
)
def test_load_write_plan_rejects_secrets_and_review_only_mode(tmp_path, extra, message):
    path = tmp_path / "plan.yaml"
    write_plan(path, extra=extra, mode="review-only" if not extra else "authorized-write")

    with pytest.raises(WritePlanError, match=message):
        load_write_plan(path)


def test_load_write_plan_rejects_unmanaged_tags(tmp_path):
    path = tmp_path / "plan.yaml"
    write_plan(path)
    text = path.read_text(encoding="utf-8").replace(
        "llm-wiki:Deep-Learning", "Deep Learning"
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(WritePlanError, match="managed tag"):
        load_write_plan(path)


def test_load_write_plan_rejects_unknown_mutation_fields(tmp_path):
    path = tmp_path / "plan.yaml"
    write_plan(path)
    text = path.read_text(encoding="utf-8").replace(
        "    reviewed_relations: [ITEM0002]",
        "    reviewed_relations: [ITEM0002]\n    remove_tags: [manual]",
        1,
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(WritePlanError, match="unknown fields"):
        load_write_plan(path)


def test_load_write_plan_rejects_unsafe_policy_widening(tmp_path):
    path = tmp_path / "plan.yaml"
    write_plan(path)
    text = path.read_text(encoding="utf-8").replace(
        "change_metadata: false", "change_metadata: true"
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(WritePlanError, match="change_metadata"):
        load_write_plan(path)


def test_audit_reports_missing_tags_and_relation_without_writes(tmp_path):
    path = tmp_path / "plan.yaml"
    write_plan(path)
    plan = load_write_plan(path)
    writer = FakeWriter()

    report = run(audit_write_plan(plan, writer))

    by_key = {item.item_key: item for item in report.items}
    assert by_key["ITEM0001"].status == "ready"
    assert by_key["ITEM0001"].missing_tags == (
        "llm-wiki:Deep-Learning",
        "llm-wiki:ingested",
    )
    assert writer.write_calls == []
    assert writer.relation_calls == []


def test_apply_adds_only_missing_managed_tags_and_verifies_relations(tmp_path):
    path = tmp_path / "plan.yaml"
    write_plan(path)
    plan = load_write_plan(path)
    writer = FakeWriter()

    report = run(apply_write_plan(plan, writer))

    by_key = {item.item_key: item for item in report.items}
    assert by_key["ITEM0001"].status == "updated_verified"
    assert by_key["ITEM0002"].status == "updated_verified"
    assert writer.write_calls == [
        ("ITEM0001", ("llm-wiki:Deep-Learning", "llm-wiki:ingested")),
    ]
    assert writer.relation_calls == [("ITEM0001", "ITEM0002")]
    assert report.failed_count == 0


def test_apply_refuses_item_outside_expected_collection(tmp_path):
    path = tmp_path / "plan.yaml"
    write_plan(path)
    plan = load_write_plan(path)
    writer = FakeWriter()
    first = writer.items["ITEM0001"]
    writer.items["ITEM0001"] = replace(first, data={**first.data, "collections": []})

    report = run(apply_write_plan(plan, writer))

    by_key = {item.item_key: item for item in report.items}
    assert by_key["ITEM0001"].status == "failed"
    assert "expected collection" in by_key["ITEM0001"].errors[0]
    assert all(call[0] != "ITEM0001" for call in writer.write_calls)


def test_verify_reports_exact_plan_state(tmp_path):
    path = tmp_path / "plan.yaml"
    write_plan(path)
    plan = load_write_plan(path)
    writer = FakeWriter()
    run(apply_write_plan(plan, writer))

    report = run(verify_write_plan(plan, writer))
    manifest = report_to_manifest(report)

    assert report.failed_count == 0
    assert {item.status for item in report.items} == {"updated_verified"}
    assert manifest["summary"]["failed"] == 0
    assert "api_key" not in str(manifest).lower()
