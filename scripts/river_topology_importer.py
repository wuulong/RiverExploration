#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[metadata]
name: river_topology_importer.py
title: WRA-Civ 河川拓樸自動化轉換、 Rich Attributes 擴充與 CSV 批次註冊工具 (CGS v2.0 & Spec v1.0)
description: 讀取樹狀 JSON，自動計算 -[CivCode] 拓樸編碼與 topology_path，支援對接 OSM 導航補充經緯度與 Rich Attributes (source_type, waterway_type, stream_order, has_osm_geo)，並提供靈活過濾器。
category: hydrology
manual: scripts/manuals/river_topology_importer.md
dependencies: csv, json, os, sys, argparse
cgs_version: 2.0
"""

import os
import sys
import json
import csv
import re
import argparse
import urllib.parse
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

BOOK_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
MANUAL_PATH = os.path.join(SCRIPT_DIR, "manuals", "river_topology_importer.md")
WRA_JSON_PATH = os.path.join(BOOK_DIR, "wra_official_river_codes.json")
CSV_PATH = os.path.join(BOOK_DIR, "taiwan_river_topology_registry.csv")

# Spec v1.0 標準欄位表
STANDARD_HEADERS = [
    "river_code", "river_name", "parent_code", "topology_path", "is_civilian",
    "basin_name", "confluence_lon", "confluence_lat", "source_type", "waterway_type",
    "stream_order", "has_osm_geo", "wikidata_id", "description", "meta_data",
    "contributor", "updated_at"
]

def log_msg(level: str, msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{level}] {msg}", file=sys.stderr)

def clean_river_name(name: str) -> str:
    name = re.sub(r"<[^>]+>", "", name)
    name = re.sub(r"\[\[[^\]]*\|([^\]]+)\]\]", r"\1", name)
    name = re.sub(r"\[\[([^\]]+)\]\]", r"\1", name)
    name = re.sub(r"'''(.*?)'''", r"\1", name)
    name = re.sub(r"''*(.*?)''*", r"\1", name)
    name = name.split("：")[0].split(":")[-1].strip()
    return name

def load_official_wra_baseline() -> dict:
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    abs_json_path = os.path.abspath(os.path.join(workspace_root, WRA_JSON_PATH))
    
    if not os.path.exists(abs_json_path):
        log_msg("WARN", f"官方水利署資料庫不存在: {abs_json_path}")
        return {}
        
    official_map = {}
    with open(abs_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for item in data:
        b_name = (item.get("basinname") or "").strip()
        b_code = (item.get("basinrivercode") or "").strip()
        sub_name = (item.get("subsidiarybasinname") or "").strip()
        sub_code = (item.get("subsidiarybasinrivercode") or "").strip()
        sub2_name = (item.get("subsubsidiarybasinname") or "").strip()
        sub2_code = (item.get("subsubsidiarybasinrivercode") or "").strip()
        
        if b_name and b_code:
            official_map[b_name] = (b_code, "0", "")
        if sub_name and sub_code and b_code:
            official_map[sub_name] = (sub_code, b_code, b_name)
        if sub2_name and sub2_code and sub_code:
            official_map[sub2_name] = (sub2_code, sub_code, sub_name)
            
    return official_map

def read_existing_csv(csv_path: str):
    if not os.path.exists(csv_path):
        return STANDARD_HEADERS, {}
        
    records = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            raw_headers = next(reader)
        except StopIteration:
            return STANDARD_HEADERS, {}
            
        for row in reader:
            if not row:
                continue
            r_code = row[0].strip()
            # 填補可能缺少的欄位至長度與 STANDARD_HEADERS 對齊
            while len(row) < len(STANDARD_HEADERS):
                row.append("")
            records[r_code] = row
            
    return STANDARD_HEADERS, records

def compute_stream_order(topology_path: str) -> int:
    """從 topology_path (例: 0@114000@114020@114021) 計算階層感 (Stream Order)"""
    if not topology_path:
        return 1
    parts = [p for p in topology_path.split("@") if p and p != "0"]
    return max(1, len(parts))

def enrich_existing_records_with_osm(existing_records: dict):
    """呼叫 osm_navigator 補齊已落庫 573 筆記錄之經緯度座標與 Rich Attributes"""
    import subprocess
    
    basin_bboxes = {
        "頭前溪": (24.70, 121.00, 24.85, 121.35),
        "淡水河": (24.80, 121.20, 25.20, 121.80),
        "鳳山溪": (24.80, 121.00, 24.95, 121.30),
        "中港溪": (24.60, 120.80, 24.75, 121.10),
        "後龍溪": (24.45, 120.80, 24.60, 121.10),
        "大安溪": (24.30, 120.60, 24.45, 121.10),
        "大甲溪": (24.20, 120.55, 24.35, 121.30),
        "烏溪": (23.95, 120.50, 24.15, 121.10),
        "濁水溪": (23.70, 120.20, 23.90, 121.20),
        "北港溪": (23.50, 120.10, 23.70, 120.60),
        "朴子溪": (23.40, 120.10, 23.60, 120.60),
        "八掌溪": (23.30, 120.10, 23.50, 120.70),
        "急水溪": (23.20, 120.10, 23.40, 120.50),
        "曾文溪": (23.00, 120.00, 23.30, 120.70),
        "鹽水溪": (23.00, 120.10, 23.15, 120.40),
        "二仁溪": (22.90, 120.15, 23.05, 120.50),
        "高屏溪": (22.45, 120.30, 23.20, 120.90),
        "卑南溪": (22.75, 121.00, 23.15, 121.30),
        "秀姑巒溪": (23.10, 121.10, 23.60, 121.50),
        "花蓮溪": (23.50, 121.40, 24.00, 121.65),
        "立霧溪": (24.12, 121.31, 24.19, 121.67),
        "和平溪": (24.25, 121.40, 24.40, 121.75),
        "冬山河": (24.60, 121.70, 24.70, 121.85),
        "蘭陽溪": (24.50, 121.30, 24.80, 121.85),
        "新城溪": (24.55, 121.75, 24.65, 121.88)
    }

    log_msg("INFO", "開始為既有記錄發動 OSM 地理經緯度與 Rich Attributes 補全...")
    
    osm_cache = {}
    for basin_name, bbox in basin_bboxes.items():
        s, w, n, e = bbox
        ql = f'[out:json][timeout:30];way[waterway]({s},{w},{n},{e});out tags;'
        url = f"https://overpass-api.de/api/interpreter?data={urllib.parse.quote(ql)}"
        cmd = ["curl", "-s", "-A", "BMAD-PA-Osm-Navigator/2.0", url]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            data = json.loads(res.stdout)
            for el in data.get("elements", []):
                tags = el.get("tags", {})
                name = tags.get("name")
                if name and name not in osm_cache:
                    lat = el.get("lat") or (el.get("bounds", {}).get("minlat") if "bounds" in el else "")
                    lon = el.get("lon") or (el.get("bounds", {}).get("minlon") if "bounds" in el else "")
                    osm_cache[name] = {
                        "lat": str(lat) if lat else "",
                        "lon": str(lon) if lon else "",
                        "w_type": tags.get("waterway", "stream")
                    }
        except Exception as e:
            log_msg("WARN", f"抓取 {basin_name} 之 OSM 資料失敗: {e}")

    updated_cnt = 0
    for r_code, row in existing_records.items():
        name = row[1].strip()
        topology_path = row[3].strip()
        is_civ = row[4].strip()
        
        # 計算 Stream Order
        order = str(compute_stream_order(topology_path))
        
        # STANDARD_HEADERS 索引對照:
        # 0: river_code
        # 1: river_name
        # 2: parent_code
        # 3: topology_path
        # 4: is_civilian
        # 5: basin_name
        # 6: confluence_lon
        # 7: confluence_lat
        # 8: source_type
        # 9: waterway_type
        # 10: stream_order
        # 11: has_osm_geo
        # 12: wikidata_id
        # 13: description
        # 14: meta_data
        # 15: contributor
        # 16: updated_at
        
        row[10] = order  # stream_order
        
        if name in osm_cache:
            info = osm_cache[name]
            if not row[6] and info["lon"]: row[6] = info["lon"]
            if not row[7] and info["lat"]: row[7] = info["lat"]
            row[8] = "Verified_Both" if is_civ == "0" else "OSM"
            row[9] = info["w_type"]
            row[11] = "1"
            updated_cnt += 1
        else:
            if not row[8] or row[8] in ["WRA", "Wiki", "OSM", "Verified_Both"]:
                row[8] = "WRA" if is_civ == "0" else "Wiki"
            if not row[9] or row[9] in ["river", "stream", "canal"]:
                row[9] = "river" if is_civ == "0" else "stream"
            row[11] = "1" if (row[6] and row[7]) else "0"

    log_msg("SUCCESS", f"已成功為 {updated_cnt} 筆紀錄補齊 OSM 實體經緯度與 Rich Attributes！")

def export_filtered_records(records: dict, min_order: int = 5, exclude_osm_only: bool = False, geo_only: bool = False, target_basin: str = None) -> list:
    """依據 Spec v1.0 屬性條件進行極致過濾"""
    filtered = []
    for r_code, row in records.items():
        name = row[1].strip()
        basin = row[5].strip()
        s_type = row[8].strip()
        s_order = int(row[10].strip()) if row[10].strip().isdigit() else 1
        has_geo = row[11].strip() == "1"

        if target_basin and basin != target_basin:
            continue
        if s_order > min_order:
            continue
        if exclude_osm_only and s_type == "OSM":
            continue
        if geo_only and not has_geo:
            continue

        filtered.append(row)
    return filtered

def generate_mermaid_diagram(records: dict, target_basin: str = None) -> str:
    """從紀錄產出 Mermaid 雙色拓樸關係圖 (藍色官方, 橘色民間)"""
    lines = ["graph TD"]
    styles = []
    
    for r_code, row in records.items():
        name = row[1].strip()
        p_code = row[2].strip()
        basin = row[5].strip()
        is_civ = row[4].strip() == "1"
        
        if target_basin and basin != target_basin:
            continue
            
        node_id = f"N_{r_code.replace('-', '_')}"
        lines.append(f'    {node_id}["{name} ({r_code})"]')
        
        if is_civ:
            styles.append(f"    style {node_id} fill:#e67e22,stroke:#d35400,stroke-width:2px,color:#ffffff")
        else:
            styles.append(f"    style {node_id} fill:#2980b9,stroke:#1f618d,stroke-width:2px,color:#ffffff")
            
        if p_code != "0":
            p_node_id = f"N_{p_code.replace('-', '_')}"
            lines.append(f"    {p_node_id} --> {node_id}")
            
    lines.extend(styles)
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="WRA-Civ 河川拓樸自動化轉換與 Spec v1.0 富屬性管理工具 (CGS v2.0)")
    parser.add_argument("command", choices=["import", "enrich", "export", "mermaid", "schema", "version"], default="import", help="執行命令")
    parser.add_argument("-i", "--input", help="輸入 JSON 結構檔案路徑")
    parser.add_argument("-p", "--parent-code", help="根父節點河川程式碼")
    parser.add_argument("-b", "--basin", help="水系流域名稱 (例: 頭前溪)")
    parser.add_argument("-c", "--contributor", default="wuulong@gmail.com", help="貢獻者標記")
    parser.add_argument("--csv", default=CSV_PATH, help="指定 CSV 註冊表路徑")
    
    # Spec v1.0 過濾參數
    parser.add_argument("--min-stream-order", type=int, default=5, help="過濾允許最大拓樸深度 (例: 2 只留主流與一級支流)")
    parser.add_argument("--exclude-osm-only", action="store_true", help="排除僅 OSM 抓取到的微小溪流")
    parser.add_argument("--geo-only", action="store_true", help="僅留存具備 OSM 地理經緯度之水線")

    parser.add_argument("-j", "--json", action="store_true", help="以 JSON 格式輸出")
    parser.add_argument("-v", "--verbose", action="store_true", help="詳細日誌")

    args = parser.parse_args()

    if args.command == "version":
        print(f"river_topology_importer.py v2.0.0 (CGS Spec v{__cli_spec_version__})")
        sys.exit(0)

    if os.path.isabs(args.csv):
        abs_csv_path = args.csv
    else:
        abs_csv_path = os.path.abspath(args.csv) if os.path.exists(os.path.abspath(args.csv)) else os.path.abspath(os.path.join(WORKSPACE_ROOT, args.csv))
        
    headers, existing_records = read_existing_csv(abs_csv_path)

    if args.command == "enrich":
        enrich_existing_records_with_osm(existing_records)
        with open(abs_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(STANDARD_HEADERS)
            for row in existing_records.values():
                writer.writerow(row)
        log_msg("SUCCESS", f"全量舊記錄 Spec v1.0 屬性補全完成，寫入: {abs_csv_path}")
        sys.exit(0)

    if args.command == "mermaid":
        mermaid_code = generate_mermaid_diagram(existing_records, target_basin=args.basin)
        print(mermaid_code)
        sys.exit(0)

    if args.command == "export":
        filtered = export_filtered_records(
            existing_records,
            min_order=args.min_stream_order,
            exclude_osm_only=args.exclude_osm_only,
            geo_only=args.geo_only,
            target_basin=args.basin
        )
        log_msg("INFO", f"屬性過濾完成，共符合 {len(filtered)} / {len(existing_records)} 筆記錄")
        if args.json:
            print(json.dumps(filtered, ensure_ascii=False, indent=2))
        else:
            writer = csv.writer(sys.stdout)
            writer.writerow(STANDARD_HEADERS)
            for r in filtered:
                writer.writerow(r)
        sys.exit(0)

if __name__ == "__main__":
    main()
