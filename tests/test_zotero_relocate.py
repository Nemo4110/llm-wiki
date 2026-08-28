"""Tests for controlled Zotero attachment relocation."""

from __future__ import annotations

import asyncio
import copy
from pathlib import Path

import pytest
import yaml

from src.llm_wiki.zotero_local import AttachmentRepointResult, LocalItem
from src.llm_wiki.zotero_relocate import (
    MetadataStore,
    RelocationError,
    RelocationSettings,
    relocate,
)


def run(coro):
    return asyncio.run(coro)


class FakeAttachmentAdapter:
    def __init__(self, item: LocalItem):
        self.items = {item.key: item}
        self.versions = {item.key: item.version}
        self.repoint_calls = []

    async def get_item(self, item_key: str) -> LocalItem:
        item = self.items[item_key]
        return LocalItem(
            key=item.key,
            version=item.version,
            data=copy.deepcopy(item.data),
            library_type=item.library_type,
            library_id=item.library_id,
        )

    async def repoint_attachment(
        self,
        item_key: str,
        target_path: str,
        *,
        expected_parent_item: str | None = None,
    ) -> AttachmentRepointResult:
        item = self.items[item_key]
        if expected_parent_item and item.data.get("parentItem") != expected_parent_item:
            raise AssertionError("fake adapter received the wrong parent")
        before_mode = item.data.get("linkMode", "")
        before_path = item.data.get("path", "")
        self.repoint_calls.append((item_key, target_path))
        item.data["linkMode"] = "linked_file"
        item.data["path"] = target_path
        self.versions[item_key] += 1
        return AttachmentRepointResult(
            item_key,
            "updated",
            1,
            before_mode,
            before_path,
            target_path,
        )


def _write_metadata(project_root: Path, source: Path, *, alias="sources/zotero/paper.pdf") -> Path:
    metadata_path = project_root / "sources" / "zotero" / "metadata.yaml"
    metadata_path.parent.mkdir(parents=True)
    metadata_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "collections": [
                    {
                        "name": "Papers",
                        "zotero_collection_key": "COLL0001",
                        "items": [
                            {
                                "title": "A Paper",
                                "zotero_item_key": "ITEM0001",
                                "attachments": [
                                    {
                                        "zotero_attachment_key": "ATTACH01",
                                        "local_path": str(source),
                                        "source_alias": alias,
                                        "filename": source.name,
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return metadata_path


def _linked_item(source: Path) -> LocalItem:
    return LocalItem(
        key="ATTACH01",
        version=4,
        data={
            "key": "ATTACH01",
            "version": 4,
            "itemType": "attachment",
            "linkMode": "linked_file",
            "path": str(source),
            "parentItem": "ITEM0001",
            "filename": source.name,
            "contentType": "application/pdf",
            "title": "A Paper",
            "date": "2024-03-01",
            "creators": [
                {"creatorType": "author", "firstName": "Alice", "lastName": "Smith"}
            ],
        },
    )


def _settings(project_root: Path, managed_root: Path, **overrides) -> RelocationSettings:
    values = {
        "enabled": True,
        "root": str(managed_root),
        "path_template": "%c/%y-%a-%t",
        "max_component_bytes": 120,
        "collision_policy": "suffix",
        "max_collision_attempts": 5,
        "delete_source": False,
        "allowed_source_roots": [],
        "update_metadata": True,
        "materialize_aliases": True,
        "on_symlink_error": "metadata",
    }
    values.update(overrides)
    return RelocationSettings.from_mapping(values, project_root=project_root)


def test_apply_relocates_file_and_keeps_local_layers_consistent(tmp_path):
    project_root = tmp_path / "project"
    source = tmp_path / "original" / "paper.pdf"
    source.parent.mkdir()
    source.write_bytes(b"pdf bytes")
    metadata_path = _write_metadata(project_root, source)
    managed_root = tmp_path / "managed"
    adapter = FakeAttachmentAdapter(_linked_item(source))

    report = run(relocate(
        metadata_path,
        project_root,
        _settings(project_root, managed_root),
        adapter,
        apply=True,
    ))

    assert report.failed_count == 0
    assert report.results[0]["status"] == "complete"
    target = managed_root / "Papers" / "2024-Alice-Smith-A-Paper.pdf"
    assert target.read_bytes() == b"pdf bytes"
    assert source.exists()
    assert adapter.items["ATTACH01"].data["path"] == str(target)
    stored = MetadataStore.load(metadata_path)
    assert stored.bindings()[0].local_path == target
    alias = project_root / "sources" / "zotero" / "paper.pdf"
    assert alias.is_symlink()
    assert alias.resolve() == target


def test_dry_run_does_not_change_files_metadata_or_zotero(tmp_path):
    project_root = tmp_path / "project"
    source = tmp_path / "original" / "paper.pdf"
    source.parent.mkdir()
    source.write_bytes(b"pdf bytes")
    metadata_path = _write_metadata(project_root, source)
    before_metadata = metadata_path.read_text(encoding="utf-8")
    managed_root = tmp_path / "managed"
    adapter = FakeAttachmentAdapter(_linked_item(source))

    report = run(relocate(
        metadata_path,
        project_root,
        _settings(project_root, managed_root),
        adapter,
        apply=False,
    ))

    assert report.results[0]["status"] == "ready"
    assert not managed_root.exists()
    assert metadata_path.read_text(encoding="utf-8") == before_metadata
    assert adapter.repoint_calls == []
    assert adapter.items["ATTACH01"].data["path"] == str(source)


def test_collision_uses_bounded_non_overwriting_suffix(tmp_path):
    project_root = tmp_path / "project"
    source = tmp_path / "original" / "paper.pdf"
    source.parent.mkdir()
    source.write_bytes(b"new bytes")
    metadata_path = _write_metadata(project_root, source)
    managed_root = tmp_path / "managed"
    collision = managed_root / "Papers" / "2024-Alice-Smith-A-Paper.pdf"
    collision.parent.mkdir(parents=True)
    collision.write_bytes(b"existing bytes")
    adapter = FakeAttachmentAdapter(_linked_item(source))

    report = run(relocate(
        metadata_path,
        project_root,
        _settings(project_root, managed_root),
        adapter,
        apply=True,
    ))

    assert report.results[0]["status"] == "complete"
    target = managed_root / "Papers" / "2024-Alice-Smith-A-Paper 2.pdf"
    assert target.read_bytes() == b"new bytes"
    assert collision.read_bytes() == b"existing bytes"
    assert adapter.items["ATTACH01"].data["path"] == str(target)


def test_imported_attachment_requires_explicit_storage_root(tmp_path):
    project_root = tmp_path / "project"
    source = tmp_path / "storage" / "ATTACH01" / "paper.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"stored bytes")
    metadata_path = _write_metadata(project_root, source)
    item = _linked_item(source)
    item.data["linkMode"] = "imported_file"
    item.data["path"] = "storage:paper.pdf"
    adapter = FakeAttachmentAdapter(item)

    without_root = run(relocate(
        metadata_path,
        project_root,
        _settings(project_root, tmp_path / "managed"),
        adapter,
        apply=False,
    ))
    assert without_root.plans[0].status == "missing-storage-root"

    with_root = run(relocate(
        metadata_path,
        project_root,
        _settings(project_root, tmp_path / "managed", storage_root=str(tmp_path / "storage")),
        adapter,
        apply=True,
    ))
    assert with_root.results[0]["status"] == "complete"


def test_source_cleanup_is_scoped_and_removes_only_verified_source(tmp_path):
    project_root = tmp_path / "project"
    source = tmp_path / "original" / "paper.pdf"
    source.parent.mkdir()
    source.write_bytes(b"pdf bytes")
    metadata_path = _write_metadata(project_root, source)
    managed_root = tmp_path / "managed"
    adapter = FakeAttachmentAdapter(_linked_item(source))

    report = run(relocate(
        metadata_path,
        project_root,
        _settings(
            project_root,
            managed_root,
            delete_source=True,
            allowed_source_roots=[str(source.parent)],
        ),
        adapter,
        apply=True,
    ))

    assert report.results[0]["status"] == "complete"
    assert report.results[0]["cleanup"] == "removed"
    assert not source.exists()


def test_managed_root_inside_sources_is_rejected(tmp_path):
    project_root = tmp_path / "project"
    with pytest.raises(RelocationError, match="inside project sources"):
        _settings(project_root, project_root / "sources" / "attachments")


def test_storage_root_is_not_an_implicit_cleanup_allowlist(tmp_path):
    project_root = tmp_path / "project"
    settings = _settings(
        project_root,
        tmp_path / "managed",
        storage_root=str(tmp_path / "storage"),
        delete_source=True,
    )
    assert settings.allowed_source_roots == ()


def test_same_target_is_never_deleted_during_cleanup(tmp_path):
    project_root = tmp_path / "project"
    source = tmp_path / "managed" / "Papers" / "2024-Alice-Smith-A-Paper.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"pdf bytes")
    metadata_path = _write_metadata(project_root, source)
    adapter = FakeAttachmentAdapter(_linked_item(source))

    report = run(relocate(
        metadata_path,
        project_root,
        _settings(
            project_root,
            tmp_path / "managed",
            delete_source=True,
            allowed_source_roots=[str(source.parent)],
        ),
        adapter,
        apply=True,
    ))

    assert report.results[0]["status"] == "complete"
    assert report.results[0]["cleanup"] == "same-target"
    assert source.exists()
