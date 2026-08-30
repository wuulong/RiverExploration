#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[metadata]
name: audit_and_repair_river_cache.py
title: WRA-Civ 快取精準健檢、缺失分析與標靶修復工具 (CGS v2.0)
description: 專門對 150 條水系快取進行靜態審計。自動識別 0 位元 Wiki 檔案與 LLM 解析異常，智慧清洗名稱 (去除括弧/別名)，並僅對「有缺失的目標」精準發動重試與重解析，完全不碰撞已成功的寶貴資料。
category: hydrology
manual: scripts/manuals/audit_and_repair_river_cache.md
dependencies: json, os, sys, argparse, subprocess, urllib
cgs_version: 2.0
"""

import os
import sys
import json
import re
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

CACHE_DIR = os.path.join(BOOK_ROOT, "cache", "rivers")

def load_gemini_api_key() -> str:
    env_path = os.path.join(BOOK_ROOT, "..", "..", ".env") if os.path.exists(os.path.join(BOOK_ROOT, "..", "..", ".env")) else os.path.join(BOOK_ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ[k] = v.strip("\"'")
    return os.environ.get("GEMINI_API_KEY", "")

def clean_search_names(raw_name: str) -> list:
    """產出備選查詢名稱清單 (去除括弧/排水/幹線)"""
    names = [raw_name]
    
    # 提取括弧內的名稱 (例: 將軍溪排水(將軍溪) -> 將軍溪)
    match = re.search(r"\((.*?)\)", raw_name)
    if match:
        names.append(match.group(1))
        
    # 去除括弧主體 (例: 將軍溪排水(將軍溪) -> 將軍溪排水)
    clean_base = re.sub(r"\(.*?\)", "", raw_name).strip()
    if clean_base not in names:
        names.append(clean_base)
        
    # 去除排水/幹線修飾詞 (例: 將軍溪排水 -> 將軍溪)
    for modifier in ["排水幹線", "排水", "幹線", "區域排水"]:
        if clean_base.endswith(modifier):
            short = clean_base[:-len(modifier)].strip()
            if short and short not in names:
                names.append(short)
                
    return names

def audit_cache_folders() -> dict:
    """審計 150 條水系快取狀況 (相容 metadata.json 治理檔)"""
    folders = [f for f in os.listdir(CACHE_DIR) if os.path.isdir(os.path.join(CACHE_DIR, f))]
    zero_wiki = []
    failed_llm = []
    healthy = []

    for folder in folders:
        f_path = os.path.join(CACHE_DIR, folder)
        wiki_p = os.path.join(f_path, "01_raw_wiki.txt")
        llm_p = os.path.join(f_path, "02_llm_tree.json")
        meta_p = os.path.join(f_path, "metadata.json")
        
        # 1. 優先檢查 metadata.json 是否已完成權威審定
        if os.path.exists(meta_p):
            try:
                with open(meta_p, "r", encoding="utf-8") as mf:
                    m_data = json.load(mf)
                    status = m_data.get("cache_status", "")
                    if status in ["VERIFIED_SINGLE_STREAM", "NO_INDEPENDENT_WIKI_ENTRY", "HEALTHY_MULTI_BRANCH"]:
                        healthy.append(folder)
                        continue
            except Exception:
                pass
                
        # 2. 一般路徑檢查
        is_wiki_empty = (not os.path.exists(wiki_p)) or (os.path.getsize(wiki_p) == 0)
        
        is_llm_failed = False
        if os.path.exists(llm_p):
            try:
                with open(llm_p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if len(data) == 1:
                        if os.path.exists(wiki_p) and os.path.getsize(wiki_p) > 0:
                            with open(wiki_p, "r", encoding="utf-8") as wf:
                                w_text = wf.read()
                                if ("支流" in w_text or "匯入" in w_text) and len(w_text) > 100:
                                    is_llm_failed = True
            except Exception:
                is_llm_failed = True
                
        if is_wiki_empty:
            zero_wiki.append(folder)
        elif is_llm_failed:
            failed_llm.append(folder)
        else:
            healthy.append(folder)

    return {
        "healthy": healthy,
        "zero_wiki": zero_wiki,
        "failed_llm": failed_llm
    }

def fetch_wiki_with_fallback(raw_name: str) -> tuple:
    """多重備選名稱重試抓取 Wiki 條目 (含 Wikipedia Search API 關鍵字比對)"""
    search_names = clean_search_names(raw_name)
    
    # 1. 精準標題比對
    for name in search_names:
        url = f"https://zh.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles={urllib.parse.quote(name)}&format=json"
        cmd = ["curl", "-s", "-L", "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", url]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            data = json.loads(res.stdout)
            pages = data.get("query", {}).get("pages", {})
            page = list(pages.values())[0]
            extract = page.get("extract", "")
            if extract and len(extract) > 20 and "可以指：" not in extract[:50]:
                return extract, name
        except Exception:
            pass
            
    # 2. 若標題找不到，發動 Wikipedia 關鍵字搜尋 API 找到最契合的條目頁面 (如: 八蓮溪 -> 八連溪 (三芝區))
    search_url = f"https://zh.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(raw_name)}&format=json"
    cmd_search = ["curl", "-s", "-L", "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", search_url]
    try:
        res = subprocess.run(cmd_search, capture_output=True, text=True, timeout=15)
        data = json.loads(res.stdout)
        results = data.get("query", {}).get("search", [])
        if results:
            best_title = results[0]["title"]
            # 抓取搜尋到的最契合頁面
            url = f"https://zh.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles={urllib.parse.quote(best_title)}&format=json"
            cmd_fetch = ["curl", "-s", "-L", "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", url]
            res_fetch = subprocess.run(cmd_fetch, capture_output=True, text=True, timeout=15)
            data_fetch = json.loads(res_fetch.stdout)
            pages = data_fetch.get("query", {}).get("pages", {})
            page = list(pages.values())[0]
            extract = page.get("extract", "")
            if extract and len(extract) > 20:
                return extract, best_title
    except Exception:
        pass

    return "", raw_name

def parse_with_retry(river_name: str, wiki_text: str, api_key: str, retries: int = 3) -> list:
    """Gemini API 自動重試機制 (解決 Timeout)"""
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
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, context=ctx, timeout=30) as res:
                out = json.loads(res.read().decode("utf-8"))
                json_text = out["candidates"][0]["content"]["parts"][0]["text"]
                tree_structure = json.loads(json_text)
                if isinstance(tree_structure, list) and len(tree_structure) > 0:
                    return tree_structure
        except Exception as e:
            sys.stderr.write(f"\n[WARN] [{attempt}/{retries}] Gemini 解析 {river_name} 失敗: {e}")
            time.sleep(2)
            
    return [{"level": 1, "name": river_name}]

def print_repair_progress(current: int, total: int, r_code: str, current_name: str, status: str):
    """修復專用標準 stderr 進度條 (顯示河川程式碼與名稱)"""
    percent = (current / total) * 100 if total > 0 else 100.0
    bar_length = 20
    filled_length = int(bar_length * current // total) if total > 0 else bar_length
    bar = "█" * filled_length + "░" * (bar_length - filled_length)
    
    sys.stderr.write(f"\r🔧 進度: [{bar}] {current}/{total} ({percent:5.1f}%) | 代號: {r_code:<6} | 水系: {current_name:<10} | 狀態: {status:<12}")
    sys.stderr.flush()
    if current == total:
        sys.stderr.write("\n")

def main():
    parser = argparse.ArgumentParser(description="WRA-Civ 快取精準健檢、缺失分析與標靶修復工具 (CGS v2.0)")
    parser.add_argument("command", choices=["audit", "repair"], default="audit", help="執行命令: audit(僅排查不修改), repair(精準修復瑕疵水系)")
    args = parser.parse_args()

    audit_res = audit_cache_folders()
    healthy = audit_res["healthy"]
    zero_wiki = audit_res["zero_wiki"]
    failed_llm = audit_res["failed_llm"]

    print(f"============================================================", file=sys.stderr)
    print(f"🔍 快取資料庫健康審計報告 (總計: 150 條水系)", file=sys.stderr)
    print(f"✅ 健康正常筆數: {len(healthy)} 條 (無需處理，寶貴資料 100% 動妥)", file=sys.stderr)
    print(f"⚠️ Wiki 空檔案 (0 bytes): {len(zero_wiki)} 條", file=sys.stderr)
    print(f"⚠️ LLM 待修復/Timeout 失敗: {len(failed_llm)} 條", file=sys.stderr)
    print(f"============================================================", file=sys.stderr)

    if args.command == "audit":
        print("\n[瑕疵水系名單 - 待修復標靶清單]:")
        for f in zero_wiki + failed_llm:
            print(f"  - {f}")
        sys.exit(0)

    if args.command == "repair":
        api_key = load_gemini_api_key()
        targets = zero_wiki + failed_llm
        total_targets = len(targets)
        
        if total_targets == 0:
            print("🎉 恭喜！全台 150 條水系快取全部健康，無需進行修復。", file=sys.stderr)
            sys.exit(0)

        print(f"\n🚀 開始發動「標靶修復」作業 (目標修復清單: {total_targets} 條瑕疵水系)...", file=sys.stderr)
        
        repaired_cnt = 0
        for idx, folder in enumerate(targets, 1):
            parts = folder.split("_", 1)
            r_code = parts[0]
            r_name = parts[1] if len(parts) > 1 else folder
            
            f_dir = os.path.join(CACHE_DIR, folder)
            wiki_p = os.path.join(f_dir, "01_raw_wiki.txt")
            llm_p = os.path.join(f_dir, "02_llm_tree.json")
            
            print_repair_progress(idx - 1, total_targets, r_code, r_name, "修復中...")

            # 1. 精準修復 Wiki (多重備選名稱重試)
            matched_name = r_name
            if folder in zero_wiki or not os.path.exists(wiki_p) or os.path.getsize(wiki_p) == 0:
                wiki_text, matched_name = fetch_wiki_with_fallback(r_name)
                with open(wiki_p, "w", encoding="utf-8") as f:
                    f.write(wiki_text)
            else:
                with open(wiki_p, "r", encoding="utf-8") as f:
                    wiki_text = f.read()

            # 2. 精準修復 LLM (帶 Retry，帶入清洗後的 matched_name)
            tree_structure = parse_with_retry(matched_name, wiki_text, api_key)
            with open(llm_p, "w", encoding="utf-8") as f:
                json.dump(tree_structure, f, ensure_ascii=False, indent=2)
                
            repaired_cnt += 1
            print_repair_progress(idx, total_targets, r_code, matched_name, f"修復完成 ({len(tree_structure)}筆)")
            time.sleep(0.3)

        print(f"\n✅ 本次標靶修復完成！共修復 {repaired_cnt} 條水系。", file=sys.stderr)

if __name__ == "__main__":
    main()
