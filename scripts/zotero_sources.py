"""
Materialize private Zotero source metadata into sources/zotero symlinks.

This helper does not talk to Zotero. Agents populate sources/zotero/metadata.yaml
from a Zotero-capable MCP tool, then this script creates local symlink aliases.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import NamedTuple

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_METADATA = Path("sources") / "zotero" / "metadata.yaml"
ALLOWED_ALIAS_ROOT = Path("sources") / "zotero"


class ZoteroAttachment(NamedTuple):
    collection_name: str
    collection_key: str
    item_title: str
    item_key: str
    attachment_key: str
    local_path: Path
    source_alias: Path
    content_type: str
    filename: str


class MaterializeResult(NamedTuple):
    created: int
    skipped: int
    errors: list[str]


def iter_attachments(metadata_path: Path):
    """Yield Zotero attachments from private metadata."""
    data = yaml.safe_load(metadata_path.read_text(encoding="utf-8")) or {}
    if data.get("version") != 1:
        raise ValueError("metadata.yaml must declare version: 1")

    for collection in data.get("collections", []):
        collection_name = str(collection.get("name", ""))
        collection_key = str(collection.get("zotero_collection_key", ""))
        for item in collection.get("items", []):
            item_title = str(item.get("title", ""))
            item_key = str(item.get("zotero_item_key", ""))
            for attachment in item.get("attachments", []):
                yield ZoteroAttachment(
                    collection_name=collection_name,
                    collection_key=collection_key,
                    item_title=item_title,
                    item_key=item_key,
                    attachment_key=str(attachment.get("zotero_attachment_key", "")),
                    local_path=Path(str(attachment.get("local_path", ""))),
                    source_alias=Path(str(attachment.get("source_alias", ""))),
                    content_type=str(attachment.get("content_type", "")),
                    filename=str(attachment.get("filename", "")),
                )


def _resolve_alias(project_root: Path, source_alias: Path) -> Path:
    if source_alias.is_absolute():
        raise ValueError("source_alias must be relative to the project root")

    normalized = Path(os.path.normpath(source_alias.as_posix()))
    allowed = ALLOWED_ALIAS_ROOT.as_posix()
    if normalized.as_posix() == allowed or not normalized.as_posix().startswith(f"{allowed}/"):
        raise ValueError("source_alias must stay under sources/zotero")

    target = (project_root / normalized).absolute()
    allowed_root = (project_root / ALLOWED_ALIAS_ROOT).absolute()
    if allowed_root not in target.parents:
        raise ValueError("source_alias must stay under sources/zotero")
    return target


def _link_matches(link_path: Path, source_path: Path) -> bool:
    return link_path.is_symlink() and link_path.resolve() == source_path.resolve()


def materialize(
    metadata_path: Path,
    project_root: Path = PROJECT_ROOT,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> MaterializeResult:
    """Create symlinks declared by metadata.yaml."""
    project_root = project_root.resolve()
    metadata_path = metadata_path if metadata_path.is_absolute() else project_root / metadata_path
    created = 0
    skipped = 0
    errors: list[str] = []

    for attachment in iter_attachments(metadata_path):
        source_path = attachment.local_path
        link_path = _resolve_alias(project_root, attachment.source_alias)

        if not source_path.exists():
            errors.append(f"missing source: {source_path}")
            continue

        if link_path.exists() or link_path.is_symlink():
            if _link_matches(link_path, source_path):
                skipped += 1
                continue
            if not force:
                errors.append(f"existing alias differs: {link_path}")
                continue
            if not link_path.is_symlink():
                errors.append(f"refusing to replace non-symlink: {link_path}")
                continue
            if not dry_run:
                link_path.unlink()

        if not dry_run:
            link_path.parent.mkdir(parents=True, exist_ok=True)
            link_path.symlink_to(source_path)
        created += 1

    return MaterializeResult(created=created, skipped=skipped, errors=errors)


def cmd_materialize(args: argparse.Namespace) -> int:
    result = materialize(
        Path(args.metadata),
        Path(args.project_root),
        dry_run=args.dry_run,
        force=args.force,
    )
    prefix = "DRY-RUN " if args.dry_run else ""
    print(f"{prefix}created: {result.created}")
    print(f"{prefix}skipped: {result.skipped}")
    if result.errors:
        print("errors:")
        for error in result.errors:
            print(f"- {error}")
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialize Zotero source symlinks.")
    parser.add_argument(
        "--metadata",
        default=str(DEFAULT_METADATA),
        help="Path to private sources/zotero/metadata.yaml",
    )
    parser.add_argument(
        "--project-root",
        default=str(PROJECT_ROOT),
        help="Project root used to resolve source_alias paths",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report actions without creating links")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing symlinks that point at a different source",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return cmd_materialize(args)


if __name__ == "__main__":
    raise SystemExit(main())
