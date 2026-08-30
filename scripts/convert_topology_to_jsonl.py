#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[metadata]
name: convert_topology_to_jsonl.py
title: 大一統河川拓樸 CSV 轉 AI-Native JSONL 與 Plugin 高程匯流點整合器 (CGS v2.0)
description: 純讀取本地既有之 taiwan_river_topology_registry.csv 與 confluence_atlas.json 快取，絕不發動任何對外網路請求。自動將實體經緯度、OSM 交點品質、河道長度與 3D 海拔高程全量整合注入至 plugins.gis 與 plugins.elevation，並預留極簡版 links.walkgis 規格。
category: hydrology
manual: scripts/manuals/batch_extract_confluence_atlas.md
dependencies: json, csv, os, sys
cgs_version: 2.0
"""

import os
import sys
import json
import csv
from datetime import datetime

__cli_spec_version__ = "2.0"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BOOK_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
CSV_PATH = os.path.join(BOOK_ROOT, "taiwan_river_topology_registry.csv")
ATLAS_JSON_PATH = os.path.join(BOOK_ROOT, "cache/confluence_atlas.json")
OUTPUT_JSONL_PATH = os.path.join(BOOK_ROOT, "taiwan_river_topology_registry.jsonl")

def convert_topology_to_jsonl(csv_path: str, atlas_json_path: str, output_jsonl_path: str):
    if not os.path.exists(csv_path):
        print(f"❌ 來源 CSV 不存在: {csv_path}", file=sys.stderr)
        return

    # 1. 純讀取既有匯流點與高程 JSON 圖集
    atlas_map = {}
    if os.path.exists(atlas_json_path):
        try:
            with open(atlas_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                atlas_map = data.get("confluence_atlas", {})
                print(f"  ├─ 💾 [純讀取快取] 成功載入已算好的 {len(atlas_map)} 筆匯流點與 3D 高程圖集數據 (0 網路連線, 防寫保護)", file=sys.stderr)
        except Exception as e:
            print(f"  ├─ ⚠️ 讀取快取警告: {e}", file=sys.stderr)

    # 2. 讀取 CSV 並拼裝成標準雙軌 JSONL
    with open(csv_path, "r", encoding="utf-8") as f:
        records = list(csv.DictReader(f))

    code_map = {r["river_code"]: r for r in records}
    jsonl_entries = []
    hydrated_gis_cnt = 0
    hydrated_ele_cnt = 0

    for r in records:
        code = r["river_code"].strip()
        name = r["river_name"].strip()
        p_code = r["parent_code"].strip()
        p_name = code_map[p_code]["river_name"].strip() if p_code in code_map else ""
        b_name = r.get("basin_name", "").strip()
        if code.startswith("130000"):
            b_name = "頭前溪"
        
        # 安全推導 6 位數水系代碼 basin_code
        b_code = code[:6] if len(code) >= 6 else code
        if p_code and p_code in code_map:
            root_code = p_code[:6]
            b_code = root_code

        # 解析 CSV 中的 meta_data JSON 字串
        meta_json = {}
        if r.get("meta_data"):
            try:
                meta_json = json.loads(r["meta_data"])
            except Exception:
                pass
        
        # 提取外鏈並從 meta_data 中移除重複的 source_links 與 cross_ref 以維持頂層單一真實來源
        source_links = meta_json.pop("source_links", {})
        cross_ref = meta_json.pop("cross_ref", {})
        wiki_url = source_links.get("wiki_url", "")
        osm_url = source_links.get("osm_url", "")
        wikidata_id = r.get("wikidata_id", "").strip() or cross_ref.get("wikidata_id", "")

        # 頂層結構：全量保留原始 CSV 屬性、極簡版 links 規範與不重複的 meta_data
        entry = {
            "river_code": code,
            "river_name": name,
            "parent_code": p_code,
            "parent_name": p_name,
            "basin_code": b_code,
            "basin_name": b_name,
            "topology_path": r.get("topology_path", ""),
            "is_civilian": int(r["is_civilian"]) if r.get("is_civilian") and r["is_civilian"].isdigit() else 0,
            "source_type": r.get("source_type", ""),
            "waterway_type": r.get("waterway_type", ""),
            "stream_order": int(r["stream_order"]) if r.get("stream_order") and r["stream_order"].isdigit() else None,
            "description": r.get("description", ""),
            "contributor": r.get("contributor", ""),
            "links": {
                "walkgis_url": "",
                "wikipedia_url": wiki_url,
                "osm_url": osm_url,
                "wikidata_id": wikidata_id
            },
            "meta_data": meta_json,
            "plugins": {
                "gis": {},
                "elevation": {}
            },
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # 整合讀取自 confluence_atlas.json 的 GIS 與高程 Plugin 資料
        if code in atlas_map:
            atlas_info = atlas_map[code]
            lon = atlas_info.get("confluence_lon")
            lat = atlas_info.get("confluence_lat")
            ele = atlas_info.get("confluence_elevation_m")
            
            # 手動/幾何補全大幹流 (油羅溪 130020 與 上坪溪 130010 雙溪口匯流點)
            if code == "130020" and (lon is None or ele is None):
                lon, lat, ele = 121.0944, 24.7300, 121.0
                atlas_info["confluence_type"] = "OSM_Shared_Node_TwinStreams"
            elif code == "130010" and (lon is None or ele is None):
                lon, lat, ele = 121.0940, 24.7295, 121.0
                atlas_info["confluence_type"] = "OSM_Shared_Node_TwinStreams"

            if lon is not None and lat is not None:
                entry["plugins"]["gis"] = {
                    "confluence_id": atlas_info.get("confluence_id", f"J-{code}"),
                    "confluence_lon": lon,
                    "confluence_lat": lat,
                    "confluence_type": atlas_info.get("confluence_type", "Unknown"),
                    "estimated_length_km": atlas_info.get("estimated_length_km", 0.0),
                    "estimated_velocity_ms": None,
                    "osm_wikipedia_tag": atlas_info.get("name_wiki", "")
                }
                hydrated_gis_cnt += 1

            if ele is not None:
                entry["plugins"]["elevation"] = {
                    "confluence_elevation_m": ele
                }
                hydrated_ele_cnt += 1

        jsonl_entries.append(entry)

    # 3. 寫入單一 JSONL 檔案
    with open(output_jsonl_path, "w", encoding="utf-8") as f_out:
        for entry in jsonl_entries:
            f_out.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"\n🎉【全台河川拓樸 JSONL 轉換完成】", file=sys.stderr)
    print(f"📄 產出 JSONL 檔案: {output_jsonl_path}", file=sys.stderr)
    print(f"🔢 總水脈筆數: {len(jsonl_entries)} 筆", file=sys.stderr)
    print(f"📍 實體 GIS 幾何厚化: {hydrated_gis_cnt} 筆", file=sys.stderr)
    print(f"⛰️ 3D 海拔高程厚化: {hydrated_ele_cnt} 筆", file=sys.stderr)

def export_jsonl_to_csv(jsonl_path: str, output_csv_path: str):
    """
    方案 A: 從 Master JSONL 單向自動導出相容的唯讀 CSV 檔案 (Derived Read-Only CSV)
    確保舊有依賴 CSV 的相容工具 100% 可用，同時徹底消除雙頭馬車維護問題。
    """
    if not os.path.exists(jsonl_path):
        print(f"❌ 來源 JSONL 不存在: {jsonl_path}", file=sys.stderr)
        return

    fieldnames = [
        "river_code", "river_name", "parent_code", "topology_path", "is_civilian",
        "basin_name", "confluence_lon", "confluence_lat", "source_type", "waterway_type",
        "stream_order", "has_osm_geo", "wikidata_id", "description", "meta_data",
        "contributor", "updated_at"
    ]

    csv_rows = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            data = json.loads(line)
            
            gis = data.get("plugins", {}).get("gis", {})
            lon = gis.get("confluence_lon")
            lat = gis.get("confluence_lat")
            has_osm = 1 if lon is not None else 0

            # 還原 meta_data
            meta = data.get("meta_data", {})
            links = data.get("links", {})
            if links.get("wikipedia_url") or links.get("osm_url"):
                meta["source_links"] = {
                    "wiki_url": links.get("wikipedia_url", ""),
                    "osm_url": links.get("osm_url", "")
                }
            if links.get("wikidata_id"):
                meta["cross_ref"] = {"wikidata_id": links.get("wikidata_id", "")}

            row = {
                "river_code": data.get("river_code", ""),
                "river_name": data.get("river_name", ""),
                "parent_code": data.get("parent_code", ""),
                "topology_path": data.get("topology_path", ""),
                "is_civilian": data.get("is_civilian", 0),
                "basin_name": data.get("basin_name", ""),
                "confluence_lon": lon if lon is not None else "",
                "confluence_lat": lat if lat is not None else "",
                "source_type": data.get("source_type", ""),
                "waterway_type": data.get("waterway_type", ""),
                "stream_order": data.get("stream_order", ""),
                "has_osm_geo": has_osm,
                "wikidata_id": links.get("wikidata_id", ""),
                "description": data.get("description", ""),
                "meta_data": json.dumps(meta, ensure_ascii=False) if meta else "{}",
                "contributor": data.get("contributor", ""),
                "updated_at": data.get("updated_at", "")
            }
            csv_rows.append(row)

    with open(output_csv_path, "w", encoding="utf-8", newline="") as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f"\n✅ [方案 A 相容導出成功] 已從 Master JSONL 單向自動產出唯讀相容 CSV 檔: {output_csv_path} (共 {len(csv_rows)} 行)", file=sys.stderr)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="大一統河川拓樸 JSONL 轉換與 CSV 自動導出器 (方案 A - Master JSONL)")
    parser.add_argument("--export-csv", action="store_true", help="從 Master JSONL 單向反向自動產出唯讀相容 CSV 檔案")
    args = parser.parse_args()

    if args.export_csv:
        export_jsonl_to_csv(OUTPUT_JSONL_PATH, CSV_PATH)
    else:
        convert_topology_to_jsonl(CSV_PATH, ATLAS_JSON_PATH, OUTPUT_JSONL_PATH)

if __name__ == "__main__":
    main()
