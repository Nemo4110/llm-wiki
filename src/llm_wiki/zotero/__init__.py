"""
LLM-Wiki Zotero Subsystem

Layered architecture:
- Backends & MCP: local, mcp_client
- Providers & Cache: providers, cache
- Domain Services: plan, refresh, relocate, heal, ingest_verify, writeback
"""

from .cache import EnrichmentCache
from .heal import apply_heal_plan, match_stale_binding, plan_heal, plan_to_heal_manifest
from .ingest_verify import (
    IngestVerificationError,
    IngestVerificationReport,
    ingest_report_to_manifest,
    load_allocation_ledger,
    verify_collection_ingest,
)
from .local import LocalZoteroWriter, authorize_local
from .mcp_client import ZoteroMCPClient
from .plan import (
    SnapshotItem,
    ZoteroBinding,
    ZoteroPlan,
    build_retired_binding_removal_plan,
    build_zotero_plan,
    collect_zotero_bindings,
    load_snapshot,
    normalize_doi,
    plan_to_manifest,
)
from .providers import CrossrefProvider, OpenAlexProvider
from .refresh import (
    RefreshItem,
    RefreshMutation,
    RefreshReport,
    RefreshSettings,
    build_refresh_report,
    parse_extra_keys,
    report_to_manifest as refresh_report_to_manifest,
    run_live_refresh,
    settings_from_config as refresh_settings_from_config,
)
from .relocate import relocate
from .writeback import apply_write_plan, audit_write_plan, verify_write_plan

__all__ = [
    "EnrichmentCache",
    "apply_heal_plan",
    "match_stale_binding",
    "plan_heal",
    "plan_to_heal_manifest",
    "IngestVerificationError",
    "IngestVerificationReport",
    "load_allocation_ledger",
    "verify_collection_ingest",
    "ingest_report_to_manifest",
    "LocalZoteroWriter",
    "authorize_local",
    "ZoteroMCPClient",
    "SnapshotItem",
    "ZoteroBinding",
    "ZoteroPlan",
    "build_retired_binding_removal_plan",
    "build_zotero_plan",
    "collect_zotero_bindings",
    "load_snapshot",
    "normalize_doi",
    "plan_to_manifest",
    "CrossrefProvider",
    "OpenAlexProvider",
    "RefreshItem",
    "RefreshMutation",
    "RefreshReport",
    "RefreshSettings",
    "build_refresh_report",
    "parse_extra_keys",
    "refresh_report_to_manifest",
    "run_live_refresh",
    "refresh_settings_from_config",
    "relocate",
    "apply_write_plan",
    "audit_write_plan",
    "verify_write_plan",
]
