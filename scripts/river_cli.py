#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[metadata]
name: river_cli.py
title: WRA-Civ 全台水文拓樸萬用查詢與多格式轉譯 CLI 工具 (CGS v2.0)
description: 提供全台 998 筆水脈之多維度模糊搜尋、階層/屬性過濾、上下游拓樸追溯，並支援 CSV, JSON, JSONL, GeoJSON, KML, Mermaid, 彩色文字樹 (Tree) 一鍵轉譯匯出。
category: hydrology
manual: scripts/manuals/river_cli.md
dependencies: csv, json, os, sys, argparse, re
cgs_version: 2.0
"""

import os
import sys
import json
import csv
import re
import argparse
from datetime import datetime

__cli_spec_version__ = "2.0"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BOOK_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if BOOK_ROOT not in sys.path:
    sys.path.insert(0, BOOK_ROOT)

CSV_PATH = os.path.join(BOOK_ROOT, "taiwan_river_topology_registry.csv")

STANDARD_HEADERS = [
    "river_code", "river_name", "parent_code", "topology_path", "is_civilian",
    "basin_name", "confluence_lon", "confluence_lat", "source_type", "waterway_type",
    "stream_order", "has_osm_geo", "wikidata_id", "description", "meta_data",
    "contributor", "updated_at"
]

def load_registry(csv_path: str = CSV_PATH) -> list:
    """載入 CSV 註冊表並轉為字典物件列表"""
    if not os.path.exists(csv_path):
        print(f"[ERROR] 找不到水文註冊表檔案: {csv_path}", file=sys.stderr)
        sys.exit(1)
        
    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    return records

def filter_records(records: list, query: str = None, basin: str = None, max_order: int = None, 
                   official_only: bool = False, civ_only: bool = False, geo_only: bool = False) -> list:
    """依據多維度條件篩選水脈紀錄"""
    filtered = []
    
    # 建立全庫索引便於自動補齊主流頭節點
    records_by_code = {r["river_code"]: r for r in records}
    
    for r in records:
        # 1. 流域篩選
        if basin and r.get("basin_name", "").strip() != basin.strip() and r.get("river_name", "").strip() != basin.strip():
            continue
            
        # 2. 模糊關鍵字搜尋 (匹配名稱、程式碼、描述)
        if query:
            q = query.strip().lower()
            r_name = r.get("river_name", "").lower()
            r_code = r.get("river_code", "").lower()
            r_desc = r.get("description", "").lower()
            if q not in r_name and q not in r_code and q not in r_desc:
                continue
                
        # 3. Stream Order 階層限制 (主流頭節點放行)
        if max_order is not None and r.get("parent_code") != "0":
            try:
                order = int(r.get("stream_order", 99))
                if order > max_order:
                    continue
            except ValueError:
                pass
                
        # 4. 官方 vs 民間
        is_civ = r.get("is_civilian", "0").strip() == "1"
        if official_only and is_civ:
            continue
        if civ_only and not is_civ:
            continue
            
        # 5. GPS 座標
        has_geo = r.get("has_osm_geo", "0").strip() == "1"
        if geo_only and not has_geo:
            continue
            
        filtered.append(r)
        
    # 若指定 basin，確保該流域的主流根節點 (parent_code == 0) 被包含在最頂層
    if basin:
        filtered_codes = {r["river_code"] for r in filtered}
        for r in records:
            if (r.get("river_name", "").strip() == basin.strip() or r.get("basin_name", "").strip() == basin.strip()) and r.get("parent_code") == "0":
                if r["river_code"] not in filtered_codes:
                    filtered.insert(0, r)
                break
                
    return filtered

def trace_topology(records: list, target_code_or_name: str, direction: str = "down") -> list:
    """追溯指定河流之上下游拓樸親緣"""
    records_by_code = {r["river_code"]: r for r in records}
    records_by_name = {r["river_name"]: r for r in records}
    
    start_node = records_by_code.get(target_code_or_name) or records_by_name.get(target_code_or_name)
    if not start_node:
        print(f"[ERROR] 找不到指定的目標河流: {target_code_or_name}", file=sys.stderr)
        return []
        
    result = []
    if direction == "up":
        # 向上追溯至出海口
        path_codes = [c for c in start_node["topology_path"].split("@") if c and c != "0"]
        for c in path_codes:
            if c in records_by_code:
                result.append(records_by_code[c])
    else:
        # 向下擴展所有子孫溪流
        root_code = start_node["river_code"]
        for r in records:
            path = r.get("topology_path", "")
            if root_code in path.split("@"):
                result.append(r)
    return result

def export_as_tree(records: list) -> str:
    """將紀錄繪製為彩色 ASCII 文字樹狀圖"""
    by_parent = {}
    node_map = {}
    for r in records:
        code = r["river_code"]
        p_code = r["parent_code"]
        node_map[code] = r
        by_parent.setdefault(p_code, []).append(r)
        
    # 定位頂層根節點
    roots = [r for r in records if r["parent_code"] == "0" or r["parent_code"] not in node_map]
    if not roots and records:
        roots = [records[0]]
        
    lines = []
    def build_branch(node, prefix="", is_root=False):
        name = node["river_name"]
        code = node["river_code"]
        is_civ = node.get("is_civilian") == "1"
        tag = "\033[33m[民間]\033[0m" if is_civ else "\033[34m[官方]\033[0m"
        order = f"階層:{node.get('stream_order','?')}"
        
        if is_root:
            lines.append(f"🌊 {name} ({code}) {tag} ({order})")
        else:
            lines.append(f"{prefix}└── {name} ({code}) {tag} ({order})")
        
        children = by_parent.get(code, [])
        for child in children:
            c_prefix = "" if is_root else prefix + "    "
            build_branch(child, c_prefix, is_root=False)
            
    for r in roots:
        build_branch(r, is_root=True)
        
    return "\n".join(lines)

def export_as_geojson(records: list) -> dict:
    """轉譯為標準 GeoJSON 點/線資產 (供 QGIS / 導航 Map 直接開啟)"""
    features = []
    for r in records:
        lon_str = r.get("confluence_lon", "").strip()
        lat_str = r.get("confluence_lat", "").strip()
        
        geometry = None
        if lon_str and lat_str:
            try:
                geometry = {
                    "type": "Point",
                    "coordinates": [float(lon_str), float(lat_str)]
                }
            except ValueError:
                pass
                
        feature = {
            "type": "Feature",
            "properties": r,
            "geometry": geometry
        }
        features.append(feature)
        
    return {
        "type": "FeatureCollection",
        "features": features
    }

def export_as_kml(records: list) -> str:
    """轉譯為標準 KML 格式 (供 Google Earth 載入)"""
    kml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '  <Document>',
        '    <name>WRA-Civ 台灣水文拓樸註冊表</name>'
    ]
    for r in records:
        lon = r.get("confluence_lon", "").strip()
        lat = r.get("confluence_lat", "").strip()
        name = r.get("river_name", "")
        code = r.get("river_code", "")
        desc = r.get("description", "")
        
        if lon and lat:
            kml_lines.extend([
                '    <Placemark>',
                f'      <name>{name} ({code})</name>',
                f'      <description>{desc}</description>',
                '      <Point>',
                f'        <coordinates>{lon},{lat},0</coordinates>',
                '      </Point>',
                '    </Placemark>'
            ])
    kml_lines.extend([
        '  </Document>',
        '</kml>'
    ])
    return "\n".join(kml_lines)

def export_as_mermaid(records: list) -> str:
    """轉譯為黑夜模式高對比雙色 Mermaid 拓樸圖"""
    lines = ["graph TD"]
    styles = []
    
    # 建立目前記錄清單對照表
    record_map = {r["river_code"]: r for r in records}
    defined_nodes = set()
    
    for r in records:
        code = r["river_code"]
        name = r["river_name"]
        p_code = r["parent_code"]
        is_civ = r.get("is_civilian") == "1"
        
        node_id = f"N_{code.replace('-', '_')}"
        if node_id not in defined_nodes:
            lines.append(f'    {node_id}["{name} ({code})"]')
            defined_nodes.add(node_id)
        
        if is_civ:
            styles.append(f"    style {node_id} fill:#e67e22,stroke:#d35400,stroke-width:2px,color:#ffffff")
        else:
            styles.append(f"    style {node_id} fill:#2980b9,stroke:#1f618d,stroke-width:2px,color:#ffffff")
            
        if p_code != "0":
            p_node_id = f"N_{p_code.replace('-', '_')}"
            # 若父節點也在目前的篩選範疇內，確保父節點的名稱標籤也被正確定義
            if p_code in record_map and p_node_id not in defined_nodes:
                p_name = record_map[p_code]["river_name"]
                p_is_civ = record_map[p_code].get("is_civilian") == "1"
                lines.append(f'    {p_node_id}["{p_name} ({p_code})"]')
                defined_nodes.add(p_node_id)
                if p_is_civ:
                    styles.append(f"    style {p_node_id} fill:#e67e22,stroke:#d35400,stroke-width:2px,color:#ffffff")
                else:
                    styles.append(f"    style {p_node_id} fill:#2980b9,stroke:#1f618d,stroke-width:2px,color:#ffffff")
            lines.append(f"    {p_node_id} --> {node_id}")
            
    lines.extend(styles)
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="WRA-Civ 全台水文拓樸萬用查詢與多格式轉譯 CLI 工具 (CGS v2.0)")
    parser.add_argument("command", nargs="?", default="search", choices=["search", "query", "export", "trace", "version"], help="執行子命令")
    parser.add_argument("query", nargs="?", help="關鍵字或目標河流程式碼")
    
    # 篩選 Flag
    parser.add_argument("-b", "--basin", help="水系/流域名稱 (例: 頭前溪)")
    parser.add_argument("-n", "--max-order", type=int, help="限制最大拓樸階層感 (例: 2 僅保留主流與一級大支流)")
    parser.add_argument("-g", "--geo-only", action="store_true", help="僅篩選具備 GPS 座標之河流")
    parser.add_argument("--official-only", action="store_true", help="僅篩選水利署官方 6 碼河流")
    parser.add_argument("--civ-only", action="store_true", help="僅篩選民間延伸野溪")
    
    # 輸出與轉譯 Flag
    parser.add_argument("-f", "--format", default="tree", choices=["tree", "csv", "json", "jsonl", "geojson", "kml", "mermaid"], help="輸出轉譯格式 (預設: tree)")
    parser.add_argument("-o", "--output", help="指定輸出檔案路徑 (預設: stdout)")
    parser.add_argument("--csv", default=CSV_PATH, help="指定輸入水文註冊表 CSV 路徑")
    parser.add_argument("--direction", default="down", choices=["up", "down"], help="trace 追溯方向: up 向上追出海口, down 向下散發支流")
    
    args = parser.parse_args()

    if args.command == "version":
        print(f"river_cli.py v2.0.0 (CGS Spec v{__cli_spec_version__})")
        sys.exit(0)
        
    records = load_registry(args.csv)
    
    # 子命令處理
    if args.command in ["search", "query"]:
        target_query = args.query or args.basin
        matched = filter_records(
            records,
            query=args.query,
            basin=args.basin,
            max_order=args.max_order,
            official_only=args.official_only,
            civ_only=args.civ_only,
            geo_only=args.geo_only
        )
    elif args.command == "trace":
        if not args.query:
            print("[ERROR] trace 命令需提供目標河流名稱或程式碼 (例: river_cli.py trace 油羅溪)", file=sys.stderr)
            sys.exit(1)
        matched = trace_topology(records, args.query, direction=args.direction)
    elif args.command == "export":
        matched = filter_records(
            records,
            query=args.query,
            basin=args.basin,
            max_order=args.max_order,
            official_only=args.official_only,
            civ_only=args.civ_only,
            geo_only=args.geo_only
        )
    else:
        matched = records

    # 多格式轉譯器處理 (自動解析 meta_data JSON 字串為原生態系系物件)
    fmt = args.format.lower()
    
    # 針對 JSON 相關格式解開 meta_data 字串
    parsed_matched = []
    for r in matched:
        r_copy = dict(r)
        if r_copy.get("meta_data"):
            try:
                r_copy["meta_data"] = json.loads(r_copy["meta_data"])
            except Exception:
                pass
        parsed_matched.append(r_copy)

    output_str = ""
    
    if fmt == "tree":
        output_str = export_as_tree(matched)
    elif fmt == "json":
        output_str = json.dumps(parsed_matched, ensure_ascii=False, indent=2)
    elif fmt == "jsonl":
        output_str = "\n".join([json.dumps(r, ensure_ascii=False) for r in parsed_matched])
    elif fmt == "geojson":
        output_str = json.dumps(export_as_geojson(parsed_matched), ensure_ascii=False, indent=2)
    elif fmt == "kml":
        output_str = export_as_kml(matched)
    elif fmt == "mermaid":
        output_str = export_as_mermaid(matched)
    elif fmt == "csv":
        import io
        s = io.StringIO()
        writer = csv.DictWriter(s, fieldnames=STANDARD_HEADERS)
        writer.writeheader()
        writer.writerows(matched)
        output_str = s.getvalue()

    # 輸出機制
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_str)
        print(f"✅ 成功將 {len(matched)} 筆轉譯結果導出至: {args.output}", file=sys.stderr)
    else:
        print(output_str)

if __name__ == "__main__":
    main()
