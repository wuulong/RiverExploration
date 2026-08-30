#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[metadata]
name: import_all_cached_rivers.py
title: 全台 150 條水系快取全量無損匯入與大一統註冊表寫入引擎 (CGS v2.0 & Spec v1.0)
description: 讀取 data/open-data/cache/rivers/ 全量 150 條水系快取資料夾 (02_llm_tree.json, 03_osm_raw.json, metadata.json)，自動計算親緣 topology_path 與民間延伸碼 (-C[nn])，對照整合水利署 837 筆官方庫與 Rich Attributes，無損寫入包含 1012 筆全台水脈的大一統 CSV 註冊表。
category: hydrology
manual: scripts/manuals/import_all_cached_rivers.md
dependencies: csv, json, os, sys, argparse, datetime
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

CACHE_DIR = os.path.join(BOOK_ROOT, "cache", "rivers")
CSV_PATH = os.path.join(BOOK_ROOT, "taiwan_river_topology_registry.csv")

# 引入已定義好的通用函式
from river_topology_importer import (
    load_official_wra_baseline,
    read_existing_csv,
    clean_river_name,
    compute_stream_order,
    STANDARD_HEADERS
)

def process_cached_folder(folder_name: str, official_wra_map: dict, existing_records: dict, existing_names: dict, civ_counter_map: dict) -> list:
    """處理單一快取資料夾的對照整合與落庫"""
    parts = folder_name.split("_", 1)
    main_code = parts[0]
    raw_basin_name = parts[1] if len(parts) > 1 else folder_name
    basin_name = clean_river_name(raw_basin_name)

    f_dir = os.path.join(CACHE_DIR, folder_name)
    llm_p = os.path.join(f_dir, "02_llm_tree.json")
    osm_p = os.path.join(f_dir, "03_osm_raw.json")
    meta_p = os.path.join(f_dir, "metadata.json")

    if not os.path.exists(llm_p):
        return []

    with open(llm_p, "r", encoding="utf-8") as f:
        structure = json.load(f)

    # 讀取 OSM 快取經緯度
    osm_geo_map = {}
    if os.path.exists(osm_p):
        try:
            with open(osm_p, "r", encoding="utf-8") as f:
                osm_data = json.load(f)
                for el in osm_data.get("elements", []):
                    tags = el.get("tags", {})
                    name = tags.get("name")
                    if name and name not in osm_geo_map:
                        lat = el.get("lat") or (el.get("bounds", {}).get("minlat") if "bounds" in el else "")
                        lon = el.get("lon") or (el.get("bounds", {}).get("minlon") if "bounds" in el else "")
                        osm_geo_map[name] = {
                            "lat": str(lat) if lat else "",
                            "lon": str(lon) if lon else "",
                            "w_type": tags.get("waterway", "stream")
                        }
        except Exception:
            pass

    today_str = datetime.now().strftime("%Y-%m-%d")
    new_rows = []

    # 確定根節點 root_path (初始 stack 空白，讓 level: 1 主流之 parent_code 設為 0)
    stack = []

    blacklist = ["地區", "橋", "截水溝", "排水路", "圳", "隧道", "http", "列表", "河川", "國道"]

    for item in structure:
        level = item["level"]
        raw_name = item["name"]
        name = clean_river_name(raw_name)

        if any(b in name for b in blacklist) and not name.endswith("溪") and not name.endswith("河"):
            continue
        if name in ["中央管河川", "台灣河流列表", "台灣河流長度列表"]:
            continue

        while stack and stack[-1][0] >= level:
            stack.pop()

        if not stack:
            parent_code = "0"
            parent_path = "0"
        else:
            parent_code = stack[-1][1]
            parent_path = stack[-1][2]

        # 1. 官方水利署權威對照整合優先（若在水利署 Baseline 中，強制採用權威 6 碼校正）
        if name in official_wra_map:
            off_code, off_parent, _ = official_wra_map[name]
            curr_code = off_code
            curr_path = f"{parent_path}@{curr_code}" if parent_path != "0" else f"0@{curr_code}"
            is_civ = "0"
            contrib = "WRA"
            desc = f"{basin_name}官方水系"
            s_type = "WRA"
            
            # 若舊 CSV 中有殘留舊測試碼，一律以官方編碼取代舊記錄
            old_code = existing_names.get(name)
            if old_code and old_code != curr_code and old_code in existing_records:
                del existing_records[old_code]

        # 2. 已存在於 CSV 中的民間延伸水脈 (更新與補齊 Rich Attributes)
        elif name in existing_names:
            curr_code = existing_names[name]
            curr_path = f"{parent_path}@{curr_code}" if parent_path != "0" else f"0@{curr_code}"
            
            # 取得既有紀錄並更新屬性
            row = existing_records[curr_code]
            lon = row[6].strip()
            lat = row[7].strip()
            is_civ = row[4].strip()
            
            # 若官方/既有水脈與 OSM 快取中有經緯度座標對照整合成功，賦予 Verified_Both (雙重認證)
            if name in osm_geo_map and (lon or osm_geo_map[name]["lon"]):
                if not lon and osm_geo_map[name]["lon"]: lon = osm_geo_map[name]["lon"]
                if not lat and osm_geo_map[name]["lat"]: lat = osm_geo_map[name]["lat"]
                w_type = osm_geo_map[name]["w_type"]
                s_type = "Verified_Both" if is_civ == "0" else "Wiki_OSM"
            else:
                s_type = "WRA" if is_civ == "0" else "Wiki"
                w_type = "river" if is_civ == "0" else "stream"
                
            has_geo = "1" if (lon and lat) else "0"
            parts = [p for p in curr_path.split("@") if p and p != "0"]
            order = str(len(parts))

            row[6] = lon
            row[7] = lat
            row[8] = s_type
            row[9] = w_type
            row[10] = order
            row[11] = has_geo

            stack.append((level, curr_code, curr_path))
            continue
        else:
            # 3. 民間延伸碼 -C[nn]
            c_idx = civ_counter_map.get(parent_code, 0) + 1
            civ_counter_map[parent_code] = c_idx
            curr_code = f"{parent_code}-C{c_idx:02d}"
            curr_path = f"{parent_path}@{curr_code}" if parent_path != "0" else f"0@{curr_code}"
            is_civ = "1"
            contrib = "wuulong@gmail.com"
            desc = f"{basin_name}水系民間支流"
            s_type = "Wiki"

        # OSM 地理資訊對對照整合
        lon, lat, w_type = "", "", "river" if is_civ == "0" else "stream"
        if name in osm_geo_map:
            lon = osm_geo_map[name]["lon"]
            lat = osm_geo_map[name]["lat"]
            w_type = osm_geo_map[name]["w_type"]
            
        has_geo = "1" if (lon and lat) else "0"
        
        # 精準判斷 source_type
        if is_civ == "0":
            s_type = "Verified_Both" if has_geo == "1" else "WRA"
        else:
            s_type = "Verified_Both" if has_geo == "1" else "Wiki"

        order = str(compute_stream_order(curr_path))

        row = [
            curr_code,                     # river_code
            name,                          # river_name
            parent_code,                   # parent_code
            curr_path,                     # topology_path
            is_civ,                        # is_civilian
            basin_name,                    # basin_name
            lon,                           # confluence_lon
            lat,                           # confluence_lat
            s_type,                        # source_type
            w_type,                        # waterway_type
            order,                         # stream_order
            has_geo,                       # has_osm_geo
            "",                            # wikidata_id
            desc,                          # description
            "{}",                          # meta_data
            contrib,                       # contributor
            today_str                      # updated_at
        ]

        new_rows.append(row)
        existing_records[curr_code] = row
        existing_names[name] = curr_code
        stack.append((level, curr_code, curr_path))

    return new_rows

def main():
    parser = argparse.ArgumentParser(description="全台 150 條水系快取全量無損匯入引擎 (CGS v2.0)")
    parser.add_argument("--csv", default=CSV_PATH, help="指定 CSV 註冊表路徑")
    args = parser.parse_args()

    official_wra_map = load_official_wra_baseline()
    headers, existing_records = read_existing_csv(args.csv)

    existing_names = {row[1].strip(): row[0].strip() for row in existing_records.values()}
    civ_counter_map = {}

    for r_code, r_row in existing_records.items():
        p_code = r_row[2].strip()
        if "-C" in r_code:
            parts = r_code.split("-C")
            if len(parts) > 1:
                try:
                    c_num = int(parts[-1][:2])
                    civ_counter_map[p_code] = max(civ_counter_map.get(p_code, 0), c_num)
                except ValueError:
                    pass

    folders = sorted([f for f in os.listdir(CACHE_DIR) if os.path.isdir(os.path.join(CACHE_DIR, f))])
    total_folders = len(folders)

    print(f"============================================================", file=sys.stderr)
    print(f"🚀 全台 {total_folders} 條水系快取全量匯入引擎發動", file=sys.stderr)
    print(f"📄 目標 CSV 註冊表: {args.csv}", file=sys.stderr)
    print(f"============================================================", file=sys.stderr)

    total_new = 0
    for idx, folder in enumerate(folders, 1):
        new_rows = process_cached_folder(folder, official_wra_map, existing_records, existing_names, civ_counter_map)
        total_new += len(new_rows)
        sys.stderr.write(f"\r📥 匯入進度: [{idx}/{total_folders}] {folder:<25} | 新增: +{len(new_rows)} 筆")
        sys.stderr.flush()

    print(f"\n\n✅ 全量快取無損對照整合完成！共新增 {total_new} 筆全新節點記錄。", file=sys.stderr)

    # 寫入 CSV
    with open(args.csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(STANDARD_HEADERS)
        for row in existing_records.values():
            writer.writerow(row)

    print(f"🎉 成功寫入大一統 CSV 註冊表！目前資料庫全量總筆數: {len(existing_records)} 筆水脈。", file=sys.stderr)

if __name__ == "__main__":
    main()
