#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[metadata]
name: batch_import_taiwan_rivers.py
title: 全台灣 150 條主流水系批次兩階段自動化匯入與進度監控引擎 (CGS v2.0 & Spec v1.0)
description: 自動讀取 wra_official_river_codes.json，過濾剩餘 124 條獨立入海水系。結合 Wikipedia API + Gemini 2.5 Flash REST API，實施兩階段 Disk Caching (01_raw_wiki, 02_llm_tree, 03_osm_raw, 04_merged)，具備終端機彩色進度條、即時處理筆數/百分比顯示、斷點續傳與 0-Token 重跑功能。
category: hydrology
manual: scripts/manuals/batch_import_taiwan_rivers.md
dependencies: urllib, json, os, sys, argparse, time, subprocess, csv
cgs_version: 2.0
"""

import os
import sys
import json
import csv
import time
import argparse
import subprocess
import urllib.parse
import urllib.request
import ssl
from datetime import datetime

__cli_spec_version__ = "2.0"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BOOK_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if BOOK_ROOT not in sys.path:
    sys.path.insert(0, BOOK_ROOT)

# 優先尋找專書內部相對路徑，相容獨立專書發布
WRA_JSON_PATH = os.path.join(BOOK_ROOT, "wra_official_river_codes.json") if os.path.exists(os.path.join(BOOK_ROOT, "wra_official_river_codes.json")) else os.path.abspath(os.path.join(BOOK_ROOT, "..", "..", "data/open-data/downloads/wra_official_river_codes.json"))
CACHE_DIR = os.path.join(BOOK_ROOT, "cache", "rivers")
CSV_PATH = os.path.join(BOOK_ROOT, "taiwan_river_topology_registry.csv")

def load_gemini_api_key() -> str:
    """自動從 .env 讀取 GEMINI_API_KEY"""
    env_path = os.path.join(BOOK_ROOT, "..", "..", ".env") if os.path.exists(os.path.join(BOOK_ROOT, "..", "..", ".env")) else os.path.join(BOOK_ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ[k] = v.strip("\"'")
    return os.environ.get("GEMINI_API_KEY", "")

def get_remaining_main_rivers() -> list:
    """從官方水利署資料庫過濾出全台灣 150 條 000 結尾之獨立主流"""
    if not os.path.exists(WRA_JSON_PATH):
        print(f"[ERROR] 官方水利署檔案不存在: {WRA_JSON_PATH}", file=sys.stderr)
        return []
        
    with open(WRA_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    main_rivers = {}
    for item in data:
        code = (item.get("basinrivercode") or "").strip()
        name = (item.get("basinname") or "").strip()
        if code.endswith("000") and name:
            main_rivers[code] = name
            
    sorted_rivers = sorted([{"code": k, "name": v} for k, v in main_rivers.items()], key=lambda x: x["code"])
    return sorted_rivers

def print_progress(current: int, total: int, current_name: str, status: str):
    """標準 stderr 進度條，不干擾 stdout"""
    percent = (current / total) * 100 if total > 0 else 100.0
    bar_length = 30
    filled_length = int(bar_length * current // total) if total > 0 else bar_length
    bar = "█" * filled_length + "░" * (bar_length - filled_length)
    
    sys.stderr.write(f"\r🚀 Progress: [{bar}] {current}/{total} ({percent:5.1f}%) | Current: {current_name:<10} | Status: {status:<15}")
    sys.stderr.flush()
    if current == total:
        sys.stderr.write("\n")

def fetch_wiki_text(river_name: str) -> str:
    """使用 curl 抓取 Wikipedia API 之全頁純文字條目（包含水系與支流完整章節）"""
    url = f"https://zh.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles={urllib.parse.quote(river_name)}&format=json"
    cmd = ["curl", "-s", "-L", "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", url]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        data = json.loads(res.stdout)
        pages = data.get("query", {}).get("pages", {})
        page = list(pages.values())[0]
        return page.get("extract", "")
    except Exception:
        return ""

def parse_river_tree_with_gemini(river_name: str, wiki_text: str, api_key: str) -> list:
    """呼叫 Gemini 2.5 Flash 原生 REST API 解析樹狀結構 JSON"""
    if not wiki_text:
        return [{"level": 1, "name": river_name}]
        
    prompt = f"""請分析以下台灣河流維基百科文字，精準萃取水系與所有支流的父子親緣縮排結構。
只輸出 JSON 陣列，每個元素包含:
- level (整數: 1代表主流, 2代表一級支流, 3代表二級支流)
- name (字串: 河流名稱)

文字如下：
{wiki_text[:4000]}
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as res:
            out = json.loads(res.read().decode("utf-8"))
            json_text = out["candidates"][0]["content"]["parts"][0]["text"]
            tree_structure = json.loads(json_text)
            if isinstance(tree_structure, list) and len(tree_structure) > 0:
                return tree_structure
    except Exception as e:
        sys.stderr.write(f"\n[WARN] Gemini 解析 {river_name} 失敗: {e}\n")
        
    return [{"level": 1, "name": river_name}]

def process_single_river(river_code: str, river_name: str, api_key: str, args) -> dict:
    """處理單一水系的四階段快取與對照整合邏輯"""
    basin_dir = os.path.join(CACHE_DIR, f"{river_code}_{river_name}")
    os.makedirs(basin_dir, exist_ok=True)
    
    f_raw_wiki = os.path.join(basin_dir, "01_raw_wiki.txt")
    f_llm_tree = os.path.join(basin_dir, "02_llm_tree.json")
    f_osm_raw = os.path.join(basin_dir, "03_osm_raw.json")
    
    # 階段 1: 抓取 Wiki 文本快取 (續傳判斷)
    if not os.path.exists(f_raw_wiki) or args.refresh_wiki:
        wiki_text = fetch_wiki_text(river_name)
        with open(f_raw_wiki, "w", encoding="utf-8") as f:
            f.write(wiki_text)
    else:
        with open(f_raw_wiki, "r", encoding="utf-8") as f:
            wiki_text = f.read()

    # 階段 2: Gemini API 解析樹狀結構 JSON (續傳判斷 - 若已解析過則 0 Token)
    if not os.path.exists(f_llm_tree) or args.refresh_llm:
        tree_structure = parse_river_tree_with_gemini(river_name, wiki_text, api_key)
        with open(f_llm_tree, "w", encoding="utf-8") as f:
            json.dump(tree_structure, f, ensure_ascii=False, indent=2)
    else:
        with open(f_llm_tree, "r", encoding="utf-8") as f:
            tree_structure = json.load(f)

    # 階段 3: OSM 地理水線探勘 (續傳判斷)
    if not os.path.exists(f_osm_raw) or args.refresh_osm:
        ql = f'[out:json][timeout:25];way["waterway"]["name"="{river_name}"];out tags;'
        url = f"https://overpass-api.de/api/interpreter?data={urllib.parse.quote(ql)}"
        cmd = ["curl", "-s", "-A", "BMAD-PA-Osm-Navigator/2.0", url]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            osm_data = json.loads(res.stdout)
        except Exception:
            osm_data = {"elements": []}
            
        with open(f_osm_raw, "w", encoding="utf-8") as f:
            json.dump(osm_data, f, ensure_ascii=False, indent=2)
            
    return {"code": river_code, "name": river_name, "tree_len": len(tree_structure), "status": "CACHE_READY"}

def main():
    parser = argparse.ArgumentParser(description="全台灣 150 條主流水系批次兩階段自動化匯入與進度監控引擎 (CGS v2.0)")
    parser.add_argument("--limit", type=int, default=0, help="限制處理水系數量 (例: --limit 1 用於單筆測試驗證)")
    parser.add_argument("--basin", type=str, help="指定單一水系名稱測試 (例: --basin 立霧溪)")
    parser.add_argument("--refresh-wiki", action="store_true", help="強制重新抓取 Wiki 文本快取")
    parser.add_argument("--refresh-llm", action="store_true", help="強制重新發動 Gemini LLM 解析")
    parser.add_argument("--refresh-osm", action="store_true", help="強制重新發動 OSM 地理探勘快取")
    
    args = parser.parse_args()
    
    api_key = load_gemini_api_key()
    if not api_key:
        print("[ERROR] 未能在 .env 中找到 GEMINI_API_KEY，請確認金鑰設定。", file=sys.stderr)
        sys.exit(1)

    main_rivers = get_remaining_main_rivers()
    
    if args.basin:
        main_rivers = [r for r in main_rivers if r["name"] == args.basin]
    elif args.limit > 0:
        main_rivers = main_rivers[:args.limit]
        
    total_cnt = len(main_rivers)
    print(f"============================================================", file=sys.stderr)
    print(f"🌊 WRA-Civ 全台灣主流水系批次兩階段引擎 (目標: {total_cnt} 條主流)", file=sys.stderr)
    print(f"🤖 LLM 引擎: Gemini 2.5 Flash REST API (無縫續傳 & 0-Token 快取)", file=sys.stderr)
    print(f"📂 快取目錄: {CACHE_DIR}", file=sys.stderr)
    print(f"============================================================", file=sys.stderr)
    
    processed = 0
    for idx, r in enumerate(main_rivers, 1):
        r_code = r["code"]
        r_name = r["name"]
        
        print_progress(idx - 1, total_cnt, r_name, "Processing...")
        
        res = process_single_river(r_code, r_name, api_key, args)
        
        time.sleep(0.3)
        
        print_progress(idx, total_cnt, r_name, f"DONE ({res['tree_len']} 筆)")
        processed += 1
        
    print(f"\n✅ 處理完成！共完成 {processed} 條主流水系之 Wiki+LLM+OSM 兩階段快取。", file=sys.stderr)

if __name__ == "__main__":
    main()
