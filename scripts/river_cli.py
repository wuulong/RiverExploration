#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[metadata]
name: river_cli.py
title: WRA-Civ 全台水文拓樸 3D 萬用查詢與多格式轉譯 CLI 工具 (Spec v2.4 / CGS v2.0)
description: 提供全台 1,418 筆水脈之 3D 海拔縱剖面 (profile)、權威外鏈 (links)、多維度模糊搜尋、階層/屬性過濾、上下游拓樸追溯，並支援 CSV, JSON, JSONL, 3D GeoJSON, 3D KML, Mermaid, 豐富彩樹 (Tree) 一鍵轉譯匯出。
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

JSONL_PATH = os.path.join(BOOK_ROOT, "taiwan_river_topology_registry.jsonl")
CSV_PATH = os.path.join(BOOK_ROOT, "taiwan_river_topology_registry.csv")

def load_registry(data_path: str = None) -> list:
    """載入水文註冊表 (預設優先讀取 Master JSONL 檔案)"""
    target_path = data_path or (JSONL_PATH if os.path.exists(JSONL_PATH) else CSV_PATH)
    
    if not os.path.exists(target_path):
        print(f"[ERROR] 找不到水文註冊表檔案: {target_path}", file=sys.stderr)
        sys.exit(1)
        
    records = []
    if target_path.endswith(".jsonl"):
        with open(target_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
    else:
        with open(target_path, "r", encoding="utf-8") as f:
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
        is_civ = str(r.get("is_civilian", 0)).strip() == "1"
        if official_only and is_civ:
            continue
        if civ_only and not is_civ:
            continue
            
        # 5. GPS 座標
        has_geo = str(r.get("has_osm_geo", 0)).strip() == "1" or r.get("plugins", {}).get("gis", {}).get("confluence_lon") is not None
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
    """轉譯為帶有 3D 海拔與實體幾何品質的豐富 Terminal 樹狀結構"""
    by_parent = {}
    record_map = {r["river_code"]: r for r in records}
    
    for r in records:
        p_code = r["parent_code"]
        by_parent.setdefault(p_code, []).append(r)
        
    roots = [r for r in records if r["parent_code"] not in record_map]
    
    lines = []
    def build_branch(node, prefix="", is_root=False):
        name = node["river_name"]
        code = node["river_code"]
        is_civ = str(node.get("is_civilian", 0)) == "1"
        tag = "\033[33m[民間]\033[0m" if is_civ else "\033[34m[官方]\033[0m"
        order = f"階層:{node.get('stream_order','?')}"
        
        # 提取 3D 高程與 GIS 幾何品質資訊
        ele = node.get("plugins", {}).get("elevation", {}).get("confluence_elevation_m")
        ele_str = f" ⛰️ \033[36m{ele}m\033[0m" if ele is not None else ""
        
        gis = node.get("plugins", {}).get("gis", {})
        c_type = gis.get("confluence_type")
        c_type_str = f" | 📍 \033[32m{c_type}\033[0m" if c_type else ""

        info_line = f"{name} ({code}) {tag} ({order}){ele_str}{c_type_str}"
        
        if is_root:
            lines.append(f"🌊 {info_line}")
        else:
            lines.append(f"{prefix}└── {info_line}")
        
        children = by_parent.get(code, [])
        for child in children:
            c_prefix = "" if is_root else prefix + "    "
            build_branch(child, c_prefix, is_root=False)
            
    for r in roots:
        build_branch(r, is_root=True)
        
    return "\n".join(lines)

def export_as_geojson(records: list) -> dict:
    """轉譯為標準 3D GeoJSON 點/線資產 (包含 [lon, lat, elevation_m] 3D Z軸)"""
    features = []
    for r in records:
        gis = r.get("plugins", {}).get("gis", {})
        ele = r.get("plugins", {}).get("elevation", {}).get("confluence_elevation_m")
        
        lon = gis.get("confluence_lon") or r.get("confluence_lon")
        lat = gis.get("confluence_lat") or r.get("confluence_lat")
        
        geometry = None
        if lon is not None and lat is not None:
            try:
                coords = [float(lon), float(lat)]
                if ele is not None:
                    coords.append(float(ele))
                geometry = {
                    "type": "Point",
                    "coordinates": coords
                }
            except (ValueError, TypeError):
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
    """轉譯為標準 3D KML 格式 (供 Google Earth 3D 擬真載入)"""
    kml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '  <Document>',
        '    <name>WRA-Civ 台灣水文拓樸註冊表 (3D Hydrological Spec)</name>'
    ]
    for r in records:
        gis = r.get("plugins", {}).get("gis", {})
        ele = r.get("plugins", {}).get("elevation", {}).get("confluence_elevation_m", 0.0)
        lon = gis.get("confluence_lon") or r.get("confluence_lon")
        lat = gis.get("confluence_lat") or r.get("confluence_lat")
        name = r.get("river_name", "")
        code = r.get("river_code", "")
        desc = r.get("description", "")
        
        if lon and lat:
            kml_lines.extend([
                '    <Placemark>',
                f'      <name>{name} ({code})</name>',
                f'      <description>{desc}</description>',
                '      <Point>',
                f'        <coordinates>{lon},{lat},{ele}</coordinates>',
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
    
    record_map = {r["river_code"]: r for r in records}
    defined_nodes = set()
    
    for r in records:
        code = r["river_code"]
        name = r["river_name"]
        p_code = r["parent_code"]
        is_civ = str(r.get("is_civilian")) == "1"
        
        node_id = f"N_{code.replace('-', '_')}"
        if node_id not in defined_nodes:
            lines.append(f'    {node_id}["{name} ({code})"]')
            defined_nodes.add(node_id)
            
        if p_code and p_code in record_map:
            p_node_id = f"N_{p_code.replace('-', '_')}"
            lines.append(f'    {p_node_id} --> {node_id}')
            
    return "\n".join(lines)

def cmd_links(records: list, query: str):
    """查詢並印出特定水脈的所有外部權威連結 (Links)"""
    target = next((r for r in records if query.lower() in r.get("river_name", "").lower() or query.lower() in r.get("river_code", "").lower()), None)
    if not target:
        print(f"❌ 找不到符合條件的水脈: {query}", file=sys.stderr)
        return

    links = target.get("links", {})
    qid = links.get("wikidata_id", "")
    wikidata_url_str = f"{qid} (https://www.wikidata.org/wiki/{qid})" if qid else "無"

    print(f"\n🔗 【{target['river_name']} ({target['river_code']}) 權威連結面板】")
    print(f"  ├─ 📌 Wikidata ID    : {wikidata_url_str}")
    print(f"  ├─ 📖 Wikipedia URL  : {links.get('wikipedia_url') or '無'}")
    print(f"  ├─ 🗺️ OpenStreetMap : {links.get('osm_url') or '無'}")
    print(f"  └─ 🌐 WalkGIS URL    : {links.get('walkgis_url') or '無'}\n")

def get_display_width(text: str) -> int:
    """計算包含中文全形字元的 Terminal 顯示寬度"""
    import unicodedata
    w = 0
    for ch in text:
        if unicodedata.east_asian_width(ch) in ('F', 'W', 'A'):
            w += 2
        else:
            w += 1
    return w

def pad_display(text: str, target_width: int) -> str:
    """將含有中文字的字串補齊空格至指定的 Terminal 顯示寬度"""
    w = get_display_width(text)
    pad = target_width - w
    return text + " " * max(0, pad)

def cmd_profile_ascii(records: list, query: str):
    """產出特定水系全體水脈的 3D 海拔 ASCII 剖面降落圖 (具備無高程水脈之 Graceful Fallback)"""
    basin_records = [r for r in records if r.get("basin_name") == query or r.get("basin_code") == query]
    if not basin_records:
        basin_records = [r for r in records if query in r.get("basin_name", "") or query in r.get("river_name", "")]
        
    if not basin_records:
        print(f"❌ 找不到水系/河流 [{query}] 的相關紀錄！", file=sys.stderr)
        return

    # 分離有高程與無高程紀錄
    ele_records = [r for r in basin_records if r.get("plugins", {}).get("elevation", {}).get("confluence_elevation_m") is not None]
    no_ele_records = [r for r in basin_records if r.get("plugins", {}).get("elevation", {}).get("confluence_elevation_m") is None]

    sorted_ele = sorted(ele_records, key=lambda x: x["plugins"]["elevation"]["confluence_elevation_m"], reverse=True)
    max_ele = sorted_ele[0]["plugins"]["elevation"]["confluence_elevation_m"] if sorted_ele else 1.0
    min_ele = sorted_ele[-1]["plugins"]["elevation"]["confluence_elevation_m"] if sorted_ele else 0.0

    print(f"\n⛰️ 【{query} 水系全體水脈 3D 海拔縱剖面與降落趨勢圖】")
    print(f"📊 已獲取高程: {len(ele_records)} 筆 (最高: {max_ele}m | 最低: {min_ele}m) | 待厚化高程: {len(no_ele_records)} 筆")
    print("=" * 80)
    
    # 動態計算水系中最長名稱與程式碼寬度
    max_code_w = max(len(r['river_code']) for r in basin_records) + 2  # 包含括號 ()
    
    # 1. 輸出已知高程水脈
    for r in sorted_ele:
        ele = r["plugins"]["elevation"]["confluence_elevation_m"]
        bar_len = int((ele / (max_ele or 1)) * 30)
        bar = "█" * bar_len
        r_name_padded = pad_display(r['river_name'], 22)
        code_str_padded = f"({r['river_code']})".ljust(max_code_w)
        print(f"  {r_name_padded} {code_str_padded} | {bar:<30} {ele:>6.1f} m")

    # 2. 全容性顯示待厚化高程水脈 (Graceful Fallback)
    if no_ele_records:
        print("-" * 85)
        print("  📋 [待厚化高程水脈清單]:")
        for r in no_ele_records:
            r_name_padded = pad_display(r['river_name'], 22)
            code_str_padded = f"({r['river_code']})".ljust(max_code_w)
            print(f"  {r_name_padded} {code_str_padded} | {'░' * 5:<30}    ? m (待測量)")
            
    print("=" * 80 + "\n")

def cmd_export_dirs(records: list, target_dir: str):
    """將全台水脈按 [縣市]/[代號_溪名]/... 自動建立階層目錄並發放 record.json"""
    import os, json
    abs_target = os.path.abspath(target_dir)
    print(f"📁 準備構建實體目錄樹至: {abs_target} ...", file=sys.stderr)

    record_map = {r["river_code"]: r for r in records}
    created_dirs_cnt = 0

    def build_dir_recursive(rec, parent_path):
        nonlocal created_dirs_cnt
        code = rec["river_code"]
        name = rec["river_name"]
        dir_name = f"{code}_{name}"
        curr_dir = os.path.join(parent_path, dir_name)
        os.makedirs(curr_dir, exist_ok=True)
        created_dirs_cnt += 1

        # 寫入 record.json
        record_file = os.path.join(curr_dir, "record.json")
        with open(record_file, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)

        # 找出直屬子支流並遞迴建立
        children = [r for r in records if r.get("parent_code") == code]
        for child in children:
            build_dir_recursive(child, curr_dir)

    office_dir_names = {
        "1": "01_第一河川分署", "2": "02_第二河川分署", "3": "03_第三河川分署",
        "4": "04_第四河川分署", "5": "05_第五河川分署", "6": "06_第六河川分署",
        "7": "07_第七河川分署", "8": "08_第八河川分署", "9": "09_第九河川分署",
        "10": "10_第十河川分署"
    }

    # 找出所有獨立主流 (parent_code == "0")
    mainstems = [r for r in records if r.get("parent_code") == "0"]
    for mainstem in mainstems:
        attr = mainstem.get("attribute_json", {})
        county = attr.get("primary_county", "未定縣市")
        county_code = attr.get("primary_county_code", "00000")
        office_id = attr.get("river_office_id", "")
        
        if county_code != "00000" and county != "未定縣市":
            top_dir_name = f"{county_code}_{county}"
        elif office_id in office_dir_names:
            top_dir_name = office_dir_names[office_id]
        else:
            top_dir_name = "99999_未定縣市"

        county_dir = os.path.join(abs_target, top_dir_name)
        build_dir_recursive(mainstem, county_dir)

    print(f"🎉【實體目錄樹建構完成】", file=sys.stderr)
    print(f"📂 總建構目錄數: {created_dirs_cnt} 個", file=sys.stderr)
    print(f"📍 目錄樹根路徑: {abs_target}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="WRA-Civ 全台水文拓樸 3D 萬用查詢與多格式轉譯 CLI 工具 (CGS v2.0)")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # search / query
    p_search = subparsers.add_parser("search", help="模糊搜尋水脈")
    p_search.add_argument("query", nargs="?", default=None, help="搜尋關鍵字")
    p_search.add_argument("-b", "--basin", help="指定水系名稱")
    p_search.add_argument("-n", "--max-order", type=int, help="限制最大河階順序")
    p_search.add_argument("-f", "--format", default="tree", choices=["tree", "csv", "json", "jsonl", "geojson", "kml", "mermaid"])
    p_search.add_argument("-o", "--output", help="輸出檔案路徑")

    # trace
    p_trace = subparsers.add_parser("trace", help="上下游拓樸追溯")
    p_trace.add_argument("query", help="目標河流名稱或程式碼")
    p_trace.add_argument("--direction", choices=["up", "down"], default="up", help="追溯方向")
    p_trace.add_argument("-f", "--format", default="tree", choices=["tree", "csv", "json", "jsonl", "geojson", "kml", "mermaid"])
    p_trace.add_argument("-o", "--output", help="輸出檔案路徑")

    # links
    p_links = subparsers.add_parser("links", help="查詢水脈權威外鏈面板")
    p_links.add_argument("query", help="目標河流名稱或程式碼")

    # profile
    p_profile = subparsers.add_parser("profile", help="印出 3D 海拔縱剖面與降落圖")
    p_profile.add_argument("query", help="水系或河流名稱")

    # export-dirs
    p_exp = subparsers.add_parser("export-dirs", help="自動匯出 [縣市]/[代號_溪名]/... 實體目錄樹")
    p_exp.add_argument("--target-dir", default="data/river_tree", help="目標目錄樹根路徑")

    args = parser.parse_args()

    records = load_registry()

    if args.command in ["search", "query"]:
        matched = filter_records(records, query=args.query, basin=args.basin, max_order=args.max_order)
        if args.format == "tree":
            print(export_as_tree(matched))
        elif args.format == "geojson":
            print(json.dumps(export_as_geojson(matched), ensure_ascii=False, indent=2))
        elif args.format == "kml":
            print(export_as_kml(matched))
        elif args.format == "mermaid":
            print(export_as_mermaid(matched))
        elif args.format == "json":
            print(json.dumps(matched, ensure_ascii=False, indent=2))
        elif args.format == "jsonl":
            print("\n".join([json.dumps(r, ensure_ascii=False) for r in matched]))
    elif args.command == "trace":
        matched = trace_topology(records, args.query, direction=args.direction)
        print(export_as_tree(matched))
    elif args.command == "links":
        cmd_links(records, args.query)
    elif args.command == "profile":
        cmd_profile_ascii(records, args.query)
    elif args.command == "export-dirs":
        cmd_export_dirs(records, args.target_dir)
    else:
        print(export_as_tree(records[:20]))

if __name__ == "__main__":
    main()
