#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[metadata]
name: river_cli.py
title: WRA-Civ 全台水文拓樸 3D 萬用查詢與多格式轉譯 CLI 工具 (CGS v2.4)
description: 提供全台 1,418 筆水脈之 3D 海拔縱剖面、權威外鏈、多維度模糊搜尋、上下游拓樸追溯，並支援管道 (Pipe) 動態注入 (hydrate)、共同祖先切片 (slice)、幾何聚合 (stats) 與拓樸完整檢核 (lint)。
category: hydrology
manual: scripts/manuals/river_cli.md
dependencies: csv, json, os, sys, argparse, re
cgs_version: 2.4
spec: scripts/specs/river_cli.spec.md
bman: RiverExploration:ch11_6
seman: tw-wra-db:2
"""

import os
import sys
import json
import argparse
from datetime import datetime

__cli_spec_version__ = "2.4"

# 將所在目錄加入 sys.path 以載入 wra_river 模組
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from wra_river import (
    load_registry,
    filter_records,
    trace_topology,
    compute_lca,
    slice_subgraph,
    compute_topology_stats,
    lint_topology,
    export_as_tree,
    export_as_geojson,
    export_as_kml,
    export_as_mermaid,
    generate_profile_ascii,
    format_authority_links,
    hydrate_external_data,
    build_physical_directory_tree
)

def log_msg(level: str, msg: str):
    tag_map = {'INFO': 'ℹ️ [INFO]', 'WARN': '⚠️ [WARN]', 'ERROR': '❌ [ERROR]'}
    print(f"{tag_map.get(level, f'[{level}]')} {msg}", file=sys.stderr)

def output_result(content: str, out_path: str = None):
    """標準管道友善輸出：支援寫入指定檔案或輸出 stdout"""
    if out_path and out_path != '-':
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(content + '\n')
        log_msg('INFO', f'已輸出至: {out_path}')
    else:
        print(content)

def format_records_output(records: list, fmt: str) -> str:
    """依指定格式轉譯紀錄集"""
    if fmt == "tree":
        return export_as_tree(records)
    elif fmt == "json":
        return json.dumps(records, ensure_ascii=False, indent=2)
    elif fmt == "jsonl":
        return "\n".join([json.dumps(r, ensure_ascii=False) for r in records])
    elif fmt == "geojson":
        return json.dumps(export_as_geojson(records), ensure_ascii=False, indent=2)
    elif fmt == "kml":
        return export_as_kml(records)
    elif fmt == "mermaid":
        return export_as_mermaid(records)
    return str(records)

def add_common_flags(p):
    p.add_argument("-i", "--input", default=None, help="輸入檔案路徑 (支援 '-' 代表 stdin 管道)")
    p.add_argument("-o", "--output", default=None, help="輸出檔案路徑 (預設 stdout)")
    p.add_argument("-j", "--json", action="store_true", help="單行緊湊 JSON 輸出")
    p.add_argument("-q", "--quiet", action="store_true", help="極簡輸出模式 (純 river_code)")
    p.add_argument("-v", "--verbose", action="store_true", help="輸出詳細日誌")

def main():
    parser = argparse.ArgumentParser(description="WRA-Civ 全台水文拓樸 3D 萬用查詢與多格式轉譯 CLI 工具 (CGS v2.4)")
    add_common_flags(parser)
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # search
    p_search = subparsers.add_parser("search", help="模糊搜尋水脈")
    add_common_flags(p_search)
    p_search.add_argument("query", nargs="?", default=None, help="搜尋關鍵字")
    p_search.add_argument("-b", "--basin", help="指定水系名稱")
    p_search.add_argument("-c", "--county", help="指定歸屬縣市名稱")
    p_search.add_argument("-n", "--max-order", type=int, help="限制最大河階順序")
    p_search.add_argument("-f", "--format", default="tree", choices=["tree", "csv", "json", "jsonl", "geojson", "kml", "mermaid"])

    # trace
    p_trace = subparsers.add_parser("trace", help="上下游拓樸追溯")
    add_common_flags(p_trace)
    p_trace.add_argument("query", help="目標河流名稱或程式碼")
    p_trace.add_argument("--direction", choices=["up", "down"], default="up", help="追溯方向 (up: 出海口/父系, down: 子孫)")
    p_trace.add_argument("-f", "--format", default="tree", choices=["tree", "csv", "json", "jsonl", "geojson", "kml", "mermaid"])

    # hydrate
    p_hydrate = subparsers.add_parser("hydrate", help="動態外部資料注入器 (Pipe Hydrator)")
    add_common_flags(p_hydrate)
    p_hydrate.add_argument("--namespace", required=True, help="外掛命名空間 (plugins.<namespace>)")
    p_hydrate.add_argument("--key", help="對應鍵名稱 (預設依 river_code 或 river_name)")

    # slice
    p_slice = subparsers.add_parser("slice", help="拓樸動態切片與最小連通子圖提取器 (Subgraph Slicer)")
    add_common_flags(p_slice)
    p_slice.add_argument("targets", nargs="*", help="目標河流名稱或程式碼")
    p_slice.add_argument("--lca", action="store_true", help="計算 LCA 共同祖先連通子圖")
    p_slice.add_argument("-f", "--format", default="tree", choices=["tree", "json", "jsonl", "mermaid"])

    # stats
    p_stats = subparsers.add_parser("stats", help="水文拓樸幾何聚合計算器")
    add_common_flags(p_stats)

    # lint
    p_lint = subparsers.add_parser("lint", help="水文拓樸完整迴路檢核器")
    add_common_flags(p_lint)
    p_lint.add_argument("--strict", action="store_true", help="嚴格模式 (包含警告即失敗)")

    # links
    p_links = subparsers.add_parser("links", help="查詢水脈權威外鏈面板")
    add_common_flags(p_links)
    p_links.add_argument("query", help="目標河流名稱或程式碼")

    # profile
    p_profile = subparsers.add_parser("profile", help="印出 3D 海拔縱剖面降落圖")
    add_common_flags(p_profile)
    p_profile.add_argument("query", help="水系或河流名稱")

    # export-dirs
    p_exp = subparsers.add_parser("export-dirs", help="自動匯出 [縣市]/[代號_溪名]/... 實體目錄樹")
    add_common_flags(p_exp)
    p_exp.add_argument("--target-dir", default="data/river_tree", help="目標目錄樹根路徑")

    # CGS 标准命令: version, schema, manual
    p_ver = subparsers.add_parser("version", help="顯示 CLI 版本資訊")
    add_common_flags(p_ver)
    p_schema = subparsers.add_parser("schema", help="輸出註冊表資料 Schema")
    add_common_flags(p_schema)
    p_man = subparsers.add_parser("manual", help="查看詳細使用說明手冊")
    add_common_flags(p_man)

    args = parser.parse_args()

    # 1. 處理無須載入註冊表的快速指令
    if args.command == "version":
        ver_info = {
            "name": "river_cli.py",
            "cli_spec_version": __cli_spec_version__,
            "cgs_compliance": "2.4",
            "features": ["3D-profile", "LCA-slice", "pipe-hydrate", "geo-export", "lint", "stats"]
        }
        output_result(json.dumps(ver_info, ensure_ascii=False, indent=2) if not args.quiet else __cli_spec_version__, args.output)
        return

    if args.command == "schema":
        schema_info = {
            "entity": "TaiwanRiverRecord",
            "primary_key": "river_code",
            "fields": ["river_code", "river_name", "basin_name", "basin_code", "parent_code", "stream_order", "topology_path", "plugins", "links"]
        }
        output_result(json.dumps(schema_info, ensure_ascii=False, indent=2), args.output)
        return

    if args.command == "manual":
        man_path = os.path.join(BOOK_ROOT, "scripts", "manuals", "river_cli.md")
        if os.path.exists(man_path):
            with open(man_path, "r", encoding="utf-8") as f:
                output_result(f.read(), args.output)
        else:
            output_result("請參閱 scripts/manuals/river_cli.md", args.output)
        return

    # 2. 載入資料 (優先讀取 -i/--input，若為 '-' 則自 stdin 讀取)
    input_source = getattr(args, 'input', None)
    records = load_registry(input_source)

    # 3. 子命令路由分流
    if args.command in ["search", "query"]:
        matched = filter_records(records, query=args.query, basin=args.basin, county=args.county, max_order=args.max_order)
        if args.quiet:
            output_result("\n".join([r["river_code"] for r in matched]), args.output)
        else:
            output_result(format_records_output(matched, args.format), args.output)

    elif args.command == "trace":
        try:
            matched = trace_topology(records, args.query, direction=args.direction)
            output_result(format_records_output(matched, args.format), args.output)
        except ValueError as e:
            log_msg('ERROR', str(e))
            sys.exit(1)

    elif args.command == "hydrate":
        # 讀取 stdin 或外部 JSON 檔案作為注入源
        raw_ext = sys.stdin.read().strip()
        if not raw_ext:
            log_msg('WARN', '未自 stdin 接收到外部注入資料')
            return
        try:
            ext_items = json.loads(raw_ext)
            if isinstance(ext_items, dict):
                ext_items = [ext_items]
        except Exception as e:
            log_msg('ERROR', f'外部注入資料 JSON 解析失敗: {e}')
            sys.exit(1)

        updated_records, cnt = hydrate_external_data(records, ext_items, args.namespace, args.key)
        log_msg('INFO', f'已成功將外部資料注入至 {cnt} 筆水脈的 plugins.{args.namespace} 命名空間')
        output_result("\n".join([json.dumps(r, ensure_ascii=False) for r in updated_records]), args.output)

    elif args.command == "slice":
        if not args.targets:
            log_msg('ERROR', '請指定至少一個水脈目標進行切片')
            sys.exit(1)
        sliced = slice_subgraph(records, args.targets, use_lca=args.lca)
        output_result(format_records_output(sliced, args.format), args.output)

    elif args.command == "stats":
        st = compute_topology_stats(records)
        if args.json:
            output_result(json.dumps(st, ensure_ascii=False), args.output)
        else:
            output_result(json.dumps(st, ensure_ascii=False, indent=2), args.output)

    elif args.command == "lint":
        res = lint_topology(records, strict=args.strict)
        log_msg('INFO', f"=== 水文拓樸完整迴路檢核 (驗證數: {res['checked_count']}) ===")
        for w in res['warnings']:
            log_msg('WARN', w)
        for e in res['errors']:
            log_msg('ERROR', e)
        if not res['passed']:
            log_msg('ERROR', f"❌ 檢核失敗：共檢測出 {len(res['errors'])} 個致命錯誤")
            sys.exit(1)
        log_msg('INFO', '🎉 拓樸檢核通過！無環狀依賴與孤兒節點')

    elif args.command == "links":
        target = next((r for r in records if args.query.lower() in r.get("river_name", "").lower() or args.query.lower() in r.get("river_code", "").lower()), None)
        if not target:
            log_msg('ERROR', f"找不到符合條件的水脈: {args.query}")
            sys.exit(1)
        output_result(format_authority_links(target), args.output)

    elif args.command == "profile":
        output_result(generate_profile_ascii(records, args.query), args.output)

    elif args.command == "export-dirs":
        res = build_physical_directory_tree(records, args.target_dir)
        log_msg('INFO', f"🎉 實體目錄樹建構完成: 共建立 {res['created_dirs_count']} 個目錄於 {res['root_dir']}")

    else:
        # 預設無參數時印出頂層前 20 筆
        output_result(export_as_tree(records[:20]), args.output)

if __name__ == "__main__":
    main()
