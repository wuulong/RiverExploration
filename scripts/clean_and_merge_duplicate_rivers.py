#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WRA-Civ 重複程式碼治理與草案期合併更新腳本 (clean_and_merge_duplicate_rivers.py)
依據「官方 6 碼唯一權威」原則，在 attribute_json.code_status == 'draft' 規範下：
1. 將同流域同河段的民間延伸程式碼（如 114020-C01、114010-C03 等）與幽靈水系（0-C18、0-C19、0-C23）合併至官方 6 碼。
2. 屬性融資整合對接：將民間採集之 GIS、高程、描述、外鏈安全注入官方節點。
3. 履歷留存：在官方節點之 attribute_json 中留下 deprecated_codes 與 merged_draft_codes 歷史追溯紀錄。
4. 子樹遷移：將民間節點轄下的子支流 parent_code 與 topology_path 自動平移至官方節點。
5. 根主流校準：校正主流與支流之 basin_name 為根出海口主流之正確名稱。
"""

import os
import sys
import json
import csv
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BOOK_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
JSONL_PATH = os.path.join(BOOK_ROOT, "taiwan_river_topology_registry.jsonl")
CSV_PATH = os.path.join(BOOK_ROOT, "taiwan_river_topology_registry.csv")

def main():
    if not os.path.exists(JSONL_PATH):
        print(f"❌ 找不到資料庫檔案: {JSONL_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    print(f"📦 載入現有水文紀錄: {len(records)} 筆")
    by_code = {r["river_code"]: r for r in records}

    # 1. 建立合併對照清單 (Civ Code -> Official Code)
    merge_map = {
        "114020-C01": "114022",  # 北勢溪
        "0-C18": "114022",       # 北勢溪
        "0-C19": "114022",       # 北勢溪
        "114010-C03": "114011",  # 三峽河 -> 三峽溪 (官方 6 碼)
        "256000-C01": "256020",  # 宜蘭河
        "135000-C05": "135040",  # 鹽水坑溪
        "154010-C02": "154012",  # 大埔溪
        "154010-C01": "154014",  # 乾溪
        "140000-C09": "140020",  # 雪山溪
        "143000-C02": "143010",  # 北港溪 (烏溪水系)
        "154010-C03": "154011",  # 石榴班溪
        "166000-C02": "166030",  # 松子腳溪
        "173010-C03": "173011",  # 濁口溪
        "237000-C03": "2370D0",  # 阿眉溪
        "114010-C01": "114014",  # 塔克金溪
        "237000-C11": "237020",  # 樂樂溪
        "0-C23": "241000",       # 水連溪 -> 水璉溪
    }

    print(f"🎯 預定合併對照數: {len(merge_map)} 組重複節點")

    # 2. 進行屬性融資整合對接 (Attribute & Plugin Fusion)
    for civ_code, off_code in merge_map.items():
        civ_rec = by_code.get(civ_code)
        off_rec = by_code.get(off_code)
        if not civ_rec or not off_rec:
            print(f"⚠️ 警告: 找不到 {civ_code} 或 {off_code}")
            continue

        # 留存歷史程式碼追溯 (在官方節點留下記錄)
        attr = off_rec.setdefault("attribute_json", {})
        dep_codes = attr.setdefault("deprecated_codes", [])
        if civ_code not in dep_codes:
            dep_codes.append(civ_code)
        
        merged_draft = attr.setdefault("merged_draft_codes", [])
        if civ_code not in merged_draft:
            merged_draft.append({
                "code": civ_code,
                "name": civ_rec.get("river_name"),
                "merged_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "reason": "OFFICIAL_6CODE_UNIFICATION"
            })

        # 融資整合對接 plugins.gis
        off_gis = off_rec.setdefault("plugins", {}).setdefault("gis", {})
        civ_gis = civ_rec.get("plugins", {}).get("gis", {})
        for k, v in civ_gis.items():
            if v is not None and off_gis.get(k) is None:
                off_gis[k] = v

        # 融資整合對接 plugins.elevation
        off_ele = off_rec.setdefault("plugins", {}).setdefault("elevation", {})
        civ_ele = civ_rec.get("plugins", {}).get("elevation", {})
        if off_ele.get("confluence_elevation_m") is None and civ_ele.get("confluence_elevation_m") is not None:
            off_ele["confluence_elevation_m"] = civ_ele["confluence_elevation_m"]

        # 融資整合對接 links
        off_links = off_rec.setdefault("links", {})
        civ_links = civ_rec.get("links", {})
        for k, v in civ_links.items():
            if v and not off_links.get(k):
                off_links[k] = v

        # 若三峽溪 (114011) 別名稱為三峽河，於 attribute_json 記錄別名
        if off_code == "114011":
            aliases = attr.setdefault("aliases", [])
            if "三峽河" not in aliases:
                aliases.append("三峽河")

    # 3. 子樹遷移 (Subtree Re-parenting)
    reparent_count = 0
    for r in records:
        curr_parent = r.get("parent_code")
        if curr_parent in merge_map:
            new_parent = merge_map[curr_parent]
            r["parent_code"] = new_parent
            r["parent_name"] = by_code[new_parent]["river_name"]
            
            # 更新 topology_path
            parent_path = by_code[new_parent].get("topology_path", f"0@{new_parent}")
            r["topology_path"] = f"{parent_path}@{r['river_code']}"
            reparent_count += 1
            print(f"  └── 遷移子節點: [{r['river_code']} {r['river_name']}] 改掛至 [{new_parent} {r['parent_name']}]")

    print(f"🌿 完成 {reparent_count} 筆下屬子節點的父系親緣遷移")

    # 4. 移除重複的民間節點
    clean_records = [r for r in records if r["river_code"] not in merge_map]
    removed_count = len(records) - len(clean_records)
    print(f"🗑️ 移除草案期重複定義民間節點: {removed_count} 筆 (剩餘 {len(clean_records)} 筆)")

    # 5. 主流與全流域 basin_name 校準
    clean_by_code = {r["river_code"]: r for r in clean_records}
    root_names = {r["river_code"]: r["river_name"] for r in clean_records if r.get("parent_code") == "0"}
    
    # 手動補齊重要官方主流自身名稱作為 basin_name
    root_basin_overrides = {
        "114000": "淡水河",
        "151000": "濁水溪",
        "142000": "大甲溪",
        "140000": "大安溪",
        "135000": "後龍溪",
        "128000": "新豐溪",
        "129000": "鳳山溪",
        "163000": "曾文溪",
        "166000": "二仁溪",
        "220000": "卑南溪",
        "255000": "冬山河",
        "262000": "雙溪",
        "241000": "水璉溪"
    }
    for c, name in root_basin_overrides.items():
        if c in clean_by_code:
            clean_by_code[c]["basin_name"] = name
            root_names[c] = name

    fixed_basin_count = 0
    for r in clean_records:
        path = r.get("topology_path", "").split("@")
        root_code = None
        for c in path:
            if c and c != "0" and c in root_names:
                root_code = c
                break
        if root_code and root_code in root_names:
            correct_basin = root_names[root_code]
            if r.get("basin_name") != correct_basin:
                r["basin_name"] = correct_basin
                fixed_basin_count += 1

    print(f"🌊 校準水系 basin_name: {fixed_basin_count} 筆水脈完成與根主流對齊")

    # 6. 寫回 JSONL
    with open(JSONL_PATH, "w", encoding="utf-8") as f:
        for r in clean_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"💾 成功寫入最新純淨 JSONL: {JSONL_PATH}")

    # 7. 同步寫回相容 CSV
    fieldnames = [
        "river_code", "river_name", "parent_code", "parent_name", "basin_name",
        "stream_order", "is_civilian", "topology_path", "source_type", "waterway_type",
        "description", "has_osm_geo", "wikidata_id", "meta_data"
    ]
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in clean_records:
            writer.writerow({
                "river_code": r.get("river_code", ""),
                "river_name": r.get("river_name", ""),
                "parent_code": r.get("parent_code", ""),
                "parent_name": r.get("parent_name", ""),
                "basin_name": r.get("basin_name", ""),
                "stream_order": r.get("stream_order", ""),
                "is_civilian": r.get("is_civilian", ""),
                "topology_path": r.get("topology_path", ""),
                "source_type": r.get("source_type", ""),
                "waterway_type": r.get("waterway_type", ""),
                "description": r.get("description", ""),
                "has_osm_geo": r.get("has_osm_geo", 0),
                "wikidata_id": r.get("links", {}).get("wikidata_id", ""),
                "meta_data": json.dumps(r.get("attribute_json", {}), ensure_ascii=False)
            })
    print(f"💾 成功同步更新相容 CSV: {CSV_PATH}")

if __name__ == "__main__":
    main()
