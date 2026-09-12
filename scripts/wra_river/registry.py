# -*- coding: utf-8 -*-
"""
wra_river.registry
負責水文拓樸註冊表資料載入、管道輸入讀取與多維度條件篩選。
"""

import os
import sys
import json
import csv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PKG_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
BOOK_ROOT = os.path.abspath(os.path.join(PKG_ROOT, ".."))

DEFAULT_JSONL_PATH = os.path.join(BOOK_ROOT, "taiwan_river_topology_registry.jsonl")
DEFAULT_CSV_PATH = os.path.join(BOOK_ROOT, "taiwan_river_topology_registry.csv")

def load_registry(data_path: str = None) -> list:
    """載入水文註冊表 (支援實體檔案路徑、stdin 管道輸入 '-'，或預設 Master DB)"""
    if data_path == "-":
        raw = sys.stdin.read().strip()
        if not raw:
            return []
        if raw.startswith("[") and raw.endswith("]"):
            try:
                return json.loads(raw)
            except Exception:
                pass
        records = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                pass
        return records

    target_path = data_path or (DEFAULT_JSONL_PATH if os.path.exists(DEFAULT_JSONL_PATH) else DEFAULT_CSV_PATH)
    
    if not os.path.exists(target_path):
        raise FileNotFoundError(f"找不到水文註冊表檔案: {target_path}")
        
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

def filter_records(records: list, query: str = None, basin: str = None, county: str = None,
                   max_order: int = None, official_only: bool = False, civ_only: bool = False, 
                   geo_only: bool = False) -> list:
    """依據多維度條件篩選水脈紀錄"""
    filtered = []
    
    for r in records:
        # 1. 流域篩選
        if basin and r.get("basin_name", "").strip() != basin.strip() and r.get("river_name", "").strip() != basin.strip():
            continue
            
        # 2. 縣市篩選
        if county:
            attr = r.get("attribute_json", {})
            r_county = attr.get("primary_county", "")
            if county not in r_county and county not in r.get("description", ""):
                continue

        # 3. 模糊關鍵字搜尋 (匹配名稱、程式碼、描述)
        if query:
            q = query.strip().lower()
            r_name = r.get("river_name", "").lower()
            r_code = r.get("river_code", "").lower()
            r_desc = r.get("description", "").lower()
            if q not in r_name and q not in r_code and q not in r_desc:
                continue
                
        # 4. Stream Order 階層限制 (主流頭節點放行)
        if max_order is not None and r.get("parent_code") != "0":
            try:
                order = int(r.get("stream_order", 99))
                if order > max_order:
                    continue
            except ValueError:
                pass
                
        # 5. 官方 vs 民間
        is_civ = str(r.get("is_civilian", 0)).strip() == "1"
        if official_only and is_civ:
            continue
        if civ_only and not is_civ:
            continue
            
        # 6. GPS 座標
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
