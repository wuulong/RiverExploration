# -*- coding: utf-8 -*-
"""
WRA-Civ 核心水文函式庫 (wra_river)
提供拓樸演演算法、多格式轉譯、註冊表載入過濾與資料注入等核心模組。
"""

from .registry import load_registry, filter_records
from .topology import (
    trace_topology,
    compute_lca,
    slice_subgraph,
    compute_topology_stats,
    lint_topology
)
from .exporters import (
    export_as_tree,
    export_as_geojson,
    export_as_kml,
    export_as_mermaid,
    generate_profile_ascii,
    format_authority_links
)
from .operations import (
    hydrate_external_data,
    build_physical_directory_tree
)

__all__ = [
    "load_registry",
    "filter_records",
    "trace_topology",
    "compute_lca",
    "slice_subgraph",
    "compute_topology_stats",
    "lint_topology",
    "export_as_tree",
    "export_as_geojson",
    "export_as_kml",
    "export_as_mermaid",
    "generate_profile_ascii",
    "format_authority_links",
    "hydrate_external_data",
    "build_physical_directory_tree"
]
