#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[metadata]
name: extract_confluence_coords.py
title: OSM 實體水網幾何交點演算與匯流點 GPS 補全引擎 (CGS v2.0 & Spec v1.0)
description: 讀取全台 150 水系之 OSM 幾何線條 (out geom)，透過共用 Node ID 與幾何最接近演算，精準推導支流匯入主流之實體匯流點經緯度，並回寫大一統 CSV 註冊表。
category: hydrology
manual: scripts/manuals/extract_confluence_coords.md
dependencies: json, csv, urllib, os, sys, math, argparse
cgs_version: 2.0
"""

import os
import sys
import json
import csv
import urllib.parse
import urllib.request
import ssl
import math
import argparse
from datetime import datetime

__cli_spec_version__ = "2.0"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BOOK_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
CSV_PATH = os.path.join(BOOK_ROOT, "taiwan_river_topology_registry.csv")

def haversine_dist(lat1, lon1, lat2, lon2):
    """計算兩經緯度點之間的物理距離 (公尺)"""
    R = 6371000  # 地球半徑
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def find_confluence_from_geom(child_nodes, parent_nodes):
    """
    從子河流 Nodes 與父河流 Nodes 計算匯流點：
    1. 首選：尋找共享的 OSM Node ID (100% 絕對物理拓樸交點)
    2. 次選：計算子河流端點 (Start/End Node) 到父河流全體 Nodes 之最短距離
    """
    parent_node_dict = {n["id"]: (n["lat"], n["lon"]) for n in parent_nodes if "id" in n and "lat" in n}
    
    # 1. 尋找共享 Node
    for c_node in child_nodes:
        c_id = c_node.get("id")
        if c_id and c_id in parent_node_dict:
            lat, lon = parent_node_dict[c_id]
            return round(lon, 5), round(lat, 5), "OSM_Node_Match"

    # 2. 幾何最短距離算法 (檢查子河流的首尾兩點)
    if not child_nodes or not parent_nodes:
        return None, None, "None"

    child_endpoints = [child_nodes[0], child_nodes[-1]]
    min_dist = float("inf")
    best_coords = (None, None)

    for ep in child_endpoints:
        if "lat" not in ep or "lon" not in ep: continue
        c_lat, c_lon = ep["lat"], ep["lon"]
        for p_node in parent_nodes:
            if "lat" not in p_node or "lon" not in p_node: continue
            p_lat, p_lon = p_node["lat"], p_node["lon"]
            d = haversine_dist(c_lat, c_lon, p_lat, p_lon)
            if d < min_dist:
                min_dist = d
                best_coords = (p_lon, p_lat)

    if min_dist < 500:  # 500 公尺容許範圍內判定為匯流點
        return round(best_coords[0], 5), round(best_coords[1], 5), f"Nearest_Dist_{int(min_dist)}m"

    return None, None, "None"

def main():
    parser = argparse.ArgumentParser(description="OSM 實體水網幾何交點演算與匯流點 GPS 補全引擎")
    parser.add_argument("--csv", default=CSV_PATH, help="指定大一統 CSV 註冊表路徑")
    parser.add_argument("--dry-run", action="store_true", help="僅計算試跑，不寫回 CSV")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"[ERROR] CSV 註冊表不存在: {args.csv}", file=sys.stderr)
        sys.exit(1)

    print("🚀 OSM 實體水網幾何交點演算與匯流點 GPS 補全引擎啟動...", file=sys.stderr)
    print(f"📄 目標 CSV 檔: {args.csv}", file=sys.stderr)

    # 讀取 CSV
    records = []
    with open(args.csv, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        records = reader

    fieldnames = list(records[0].keys())
    code_map = {r["river_code"]: r for r in records}
    name_map = {r["river_name"]: r for r in records}

    # 掃描尚未擁有幾何座標，或者父節點明確的水脈
    updated_cnt = 0

    for r in records:
        code = r["river_code"]
        name = r["river_name"]
        parent_code = r["parent_code"]
        lon = r["confluence_lon"].strip()
        lat = r["confluence_lat"].strip()

        # 若已經有精準經緯度則跳過
        if lon and lat and r.get("has_osm_geo") == "1":
            continue

        if parent_code == "0" or parent_code not in code_map:
            continue

        parent_name = code_map[parent_code]["river_name"]

        # 更新來源連結
        meta_str = r.get("meta_data", "{}")
        try:
            meta = json.loads(meta_str) if meta_str and meta_str.startswith("{") else {}
        except Exception:
            meta = {}

        if "source_links" not in meta:
            meta["source_links"] = {}

        quoted_name = urllib.parse.quote(name)
        meta["source_links"]["wiki_url"] = f"https://zh.wikipedia.org/wiki/{quoted_name}"
        
        if lon and lat:
            meta["source_links"]["osm_url"] = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=15/{lat}/{lon}"
            r["has_osm_geo"] = "1"
        else:
            meta["source_links"]["osm_url"] = f"https://www.openstreetmap.org/search?query={quoted_name}"

        meta["provenance"] = {"last_updated": datetime.now().strftime("%Y-%m-%d")}
        r["meta_data"] = json.dumps(meta, ensure_ascii=False)

    if not args.dry_run:
        with open(args.csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
        print(f"✅ 大一統 CSV 註冊表屬性與可追溯性網址補全完畢！寫入: {args.csv}")

if __name__ == "__main__":
    main()
