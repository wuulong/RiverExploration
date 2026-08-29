#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[metadata]
name: river_topology_importer.py
title: WRA-Civ 河川拓樸自動化轉換與 CSV 批次註冊工具
description: 讀取 wiki_cli 產出之樹狀 JSON，自動計算 -[CivCode] 拓樸編碼與 topology_path，並安全無損寫入 CSV 註冊表。
category: hydrology
manual: scripts/manuals/river_topology_importer.md
dependencies: csv, json, os, sys
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

MANUAL_PATH = "scripts/manuals/river_topology_importer.md"

WRA_JSON_PATH = "data/open-data/downloads/wra_official_river_codes.json"
CSV_PATH = "events/AIBooks/RiverExploration/taiwan_river_topology_registry.csv"

def load_official_wra_baseline() -> dict:
    """
    讀取水利署全量官方開放資料集 wra_official_river_codes.json
    回傳以河川名稱為 Key 的權威官方程式碼對照表: {river_name: (code, parent_code, parent_name)}
    """
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
        
        # 1. 登記主流
        if b_name and b_code:
            official_map[b_name] = (b_code, "0", "")
            
        # 2. 登記一級支流
        if sub_name and sub_code and b_code:
            official_map[sub_name] = (sub_code, b_code, b_name)
            
        # 3. 登記二級次支流
        if sub2_name and sub2_code and sub_code:
            official_map[sub2_name] = (sub2_code, sub_code, sub_name)
            
    return official_map

def log_msg(level: str, message: str, verbose: bool = False, json_mode: bool = False):
    """CGS v2.0 結構化日誌輸出至 stderr"""
    if level.upper() == "DEBUG" and not verbose:
        return
    if json_mode:
        log_entry = {
            "time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "level": level.upper(),
            "script": "river_topology_importer.py",
            "message": message
        }
        print(json.dumps(log_entry, ensure_ascii=False), file=sys.stderr)
    else:
        prefix_map = {
            "INFO": "ℹ️ [INFO]",
            "WARN": "⚠️ [WARN]",
            "ERROR": "❌ [ERROR]",
            "DEBUG": "🔍 [DEBUG]",
            "SUCCESS": "✅ [SUCCESS]"
        }
        prefix = prefix_map.get(level.upper(), f"[{level.upper()}]")
        print(f"{prefix} {message}", file=sys.stderr)

def read_existing_csv(csv_file_path: str) -> tuple:
    """讀取既有 CSV 註冊表，回傳 (headers, existing_records_dict)"""
    if not os.path.exists(csv_file_path):
        headers = [
            "river_code", "river_name", "parent_code", "topology_path",
            "is_civilian", "basin_name", "confluence_lon", "confluence_lat",
            "wikidata_id", "description", "meta_data", "contributor", "updated_at"
        ]
        return headers, {}
        
    records = {}
    headers = []
    with open(csv_file_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader, [])
        for row in reader:
            if row:
                records[row[0].strip()] = row
    return headers, records

def clean_river_name(raw_name: str) -> str:
    """清洗 Wiki 抓取到的名稱，去除粗體標籤、說明文字與非河川雜訊"""
    # 移除 Wiki 粗體標籤
    name = re.sub(r"'''", "", raw_name)
    # 若有名稱加冒號說明的狀況（如「月桂溪：大同鄉...」），只取冒號前之溪流名稱
    if "：" in name:
        name = name.split("：")[0].strip()
    if ":" in name:
        name = name.split(":")[0].strip()
    return name.strip()

def process_tree_structure(structure: list, root_parent_code: str, root_parent_path: str, basin_name: str, contributor: str, existing_records: dict, official_wra_map: dict) -> list:
    """
    將 Wiki 扁平樹狀結構轉換為 WRA-Civ 拓樸註冊資料。
    優先使用 100% 官方水利署開放資料集 (wra_official_river_codes.json) 進行真實程式碼對照整合；
    僅對官方未收錄之野溪自動計算 -C[nn] 民間延伸程式碼。
    """
    new_rows = []
    stack = [(0, root_parent_code, root_parent_path)]  # [(level, parent_code, parent_path)]
    
    civ_counter_map = {}  # parent_code -> current_c_index
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 預先計算既有 parent 已經佔用的最大 C 號碼
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

    # 建立已存在之 river_name 對照以防重複
    existing_names = {row[1].strip(): row[0].strip() for row in existing_records.values()}
    
    # 排除關鍵字黑名單
    blacklist = ["地區", "橋", "高速公路", "台鐵", "http", "列表", "河川", "國道", "噶瑪蘭", "泰雅", "牛鬥", "葫蘆堵"]
    
    for item in structure:
        level = item["level"]
        raw_name = item["name"]
        name = clean_river_name(raw_name)
        
        # 排除無關條目與分類
        if any(b in name for b in blacklist) and not name.endswith("溪") and not name.endswith("河"):
            continue
        if name in ["中央管河川", "台灣河流列表", "台灣河流長度列表"]:
            continue
            
        # 調整 stack 找出正確的 parent
        while stack and stack[-1][0] >= level:
            stack.pop()
            
        if not stack:
            parent_code = root_parent_code
            parent_path = root_parent_path
        else:
            parent_code = stack[-1][1]
            parent_path = stack[-1][2]
            
        # 1. 若該河流名稱已存在於 CSV 中，則沿用其程式碼
        if name in existing_names:
            curr_code = existing_names[name]
            curr_path = f"{parent_path}@{curr_code}"
            stack.append((level, curr_code, curr_path))
            continue
            
        # 2. 強制規範對照整合：若該河流存在於 100% 官方水利署資料庫中，直接使用官方真實 6 碼 (is_civilian = 0)
        if name in official_wra_map:
            off_code, off_parent, _ = official_wra_map[name]
            curr_code = off_code
            curr_path = f"{parent_path}@{curr_code}"
            is_civ = "0"
            contrib = "WRA"
            desc = f"{basin_name}官方水系"
            log_msg("INFO", f"🎯 [官方對照整合] 找到水利署權威 6 碼: {name} ➔ {curr_code}")
        else:
            # 3. 官方無紀錄之野溪，分配新 WRA-Civ 民間延伸程式碼 (is_civilian = 1)
            c_idx = civ_counter_map.get(parent_code, 0) + 1
            civ_counter_map[parent_code] = c_idx
            
            curr_code = f"{parent_code}-C{c_idx:02d}"
            curr_path = f"{parent_path}@{curr_code}"
            is_civ = "1"
            contrib = contributor
            desc = f"{basin_name}水系民間支流"
        
        row = [
            curr_code,                     # river_code
            name,                          # river_name
            parent_code,                   # parent_code
            curr_path,                     # topology_path
            is_civ,                        # is_civilian
            basin_name,                    # basin_name
            "",                            # confluence_lon (留空 TODO)
            "",                            # confluence_lat (留空 TODO)
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

def generate_mermaid_diagram(records: dict, target_basin: str = None) -> str:
    """從 CSV 紀錄生成 Mermaid 拓樸圖語法"""
    lines = [
        "graph TD",
        "    classDef official fill:#e1f5fe,stroke:#0288d1,stroke-width:1px;",
        "    classDef civilian fill:#fff3e0,stroke:#f57c00,stroke-width:1px;",
        ""
    ]
    
    official_nodes = []
    civilian_nodes = []
    
    for r_code, r_row in records.items():
        name = r_row[1].strip()
        p_code = r_row[2].strip()
        basin = r_row[5].strip()
        is_civ = r_row[4].strip() == "1"
        
        if target_basin and basin != target_basin:
            continue
            
        node_id = f"R_{r_code.replace('-', '_')}"
        label = f'"{name} ({r_code})"'
        
        if is_civ:
            civilian_nodes.append(node_id)
        else:
            official_nodes.append(node_id)
            
        if p_code != "0" and p_code in records:
            p_node_id = f"R_{p_code.replace('-', '_')}"
            link_symbol = "-.->" if is_civ else "-->"
            lines.append(f"    {p_node_id} {link_symbol} {node_id}[{label}]")
            
    lines.append("")
    if official_nodes:
        lines.append(f"    class {','.join(official_nodes)} official;")
    if civilian_nodes:
        lines.append(f"    class {','.join(civilian_nodes)} civilian;")
        
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="WRA-Civ 河川拓樸自動化轉換與 CSV 批次註冊工具 (CGS v2.0)")
    parser.add_argument("command", choices=["import", "mermaid", "validate", "schema", "version"], default="import", help="執行命令")
    parser.add_argument("-i", "--input", help="輸入 JSON 結構檔案路徑 (來自 wiki_cli)")
    parser.add_argument("-p", "--parent-code", help="根父節點河川程式碼 (例如: 蘭陽溪 114001, 濁水溪 121005)")
    parser.add_argument("-b", "--basin", help="水系流域名稱 (例如: 蘭陽溪, 濁水溪)")
    parser.add_argument("-c", "--contributor", default="wuulong@gmail.com", help="貢獻者標記")
    parser.add_argument("--csv", default=CSV_PATH, help="指定 CSV 註冊表路徑")
    parser.add_argument("-j", "--json", action="store_true", help="以 JSON 格式輸出處理結果")
    parser.add_argument("-v", "--verbose", action="store_true", help="詳細日誌")
    
    args = parser.parse_args()
    
    if args.command == "version":
        print(f"river_topology_importer.py v1.1.0 (CGS Spec v{__cli_spec_version__})")
        sys.exit(0)
        
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    abs_csv_path = os.path.abspath(os.path.join(workspace_root, args.csv))
    headers, existing_records = read_existing_csv(abs_csv_path)
    
    if args.command == "mermaid":
        mermaid_code = generate_mermaid_diagram(existing_records, args.basin)
        print(mermaid_code)
        sys.exit(0)
        
    if args.command == "import":
        if not args.input or not os.path.exists(args.input):
            log_msg("ERROR", f"輸入 JSON 檔案不存在: {args.input}")
            sys.exit(1)
            
        log_msg("INFO", f"讀取 Wiki 樹狀 JSON: {args.input}")
        with open(args.input, "r", encoding="utf-8") as f:
            structure = json.load(f)
            
        workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        abs_csv_path = os.path.abspath(os.path.join(workspace_root, args.csv))
        
        headers, existing_records = read_existing_csv(abs_csv_path)
        
        if args.parent_code not in existing_records:
            log_msg("WARN", f"父節點程式碼 {args.parent_code} 未在 CSV 中找到，請確認根節點已存在。")
            root_path = f"0@{args.parent_code}"
        else:
            root_path = existing_records[args.parent_code][3]
            
        official_wra_map = load_official_wra_baseline()
        log_msg("INFO", f"已加載水利署全量官方開放資料集，包含 {len(official_wra_map)} 個權威程式碼對")
        
        new_rows = process_tree_structure(
            structure,
            args.parent_code,
            root_path,
            args.basin,
            args.contributor,
            existing_records,
            official_wra_map
        )
        
        log_msg("SUCCESS", f"拓樸計算完成，共生成 {len(new_rows)} 條全新 WRA-Civ 節點記錄")
        
        # 寫回 CSV
        with open(abs_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in existing_records.values():
                writer.writerow(row)
                
        log_msg("SUCCESS", f"成功寫入 CSV 註冊表: {abs_csv_path}")
        
        if args.json:
            print(json.dumps(new_rows, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
