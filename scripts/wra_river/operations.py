# -*- coding: utf-8 -*-
"""
wra_river.operations
負責水文資料實體操作與注入：
- hydrate_external_data: 依程式碼或名稱將外部資料注入 plugins.<namespace>
- build_physical_directory_tree: 依流域/縣市拓樸階層建立本地實體目錄樹 (export-dirs)
"""

import os
import sys

def hydrate_external_data(records: list, external_items: list, namespace: str, key_field: str = None) -> tuple:
    """將外部資料注入至 records 的 plugins.<namespace> 命名空間中，回傳 (更新後 records, 注入成功的筆數)"""
    by_code = {r['river_code']: r for r in records}
    by_name = {r['river_name']: r for r in records}
    cnt = 0
    
    for item in external_items:
        k = item.get(key_field) if key_field else (item.get('river_code') or item.get('river_name') or item.get('name'))
        if not k:
            continue
        rec = by_code.get(k) or by_name.get(k)
        if rec:
            ns = rec.setdefault('plugins', {}).setdefault(namespace, {})
            for attr_k, attr_v in item.items():
                if attr_k not in ['river_code', 'river_name', 'name']:
                    ns[attr_k] = attr_v
            cnt += 1
            
    return records, cnt

def build_physical_directory_tree(records: list, target_dir: str = "data/river_tree") -> dict:
    """自動匯出 [縣市]/[代號_溪名]/... 實體目錄樹"""
    abs_target = os.path.abspath(target_dir)
    os.makedirs(abs_target, exist_ok=True)
    created_dirs_cnt = 0

    def build_dir_recursive(node, parent_dir_path):
        nonlocal created_dirs_cnt
        code = node["river_code"]
        name = node["river_name"]
        clean_name = name.replace("/", "_").replace("\\", "_").replace(" ", "_")
        dir_name = f"{code}_{clean_name}"
        curr_dir = os.path.join(parent_dir_path, dir_name)

        if not os.path.exists(curr_dir):
            os.makedirs(curr_dir, exist_ok=True)
            created_dirs_cnt += 1

        readme_path = os.path.join(curr_dir, "README.md")
        if not os.path.exists(readme_path):
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(f"# {name} ({code})\n\n")
                f.write(f"- **河川代號**: `{code}`\n")
                f.write(f"- **上游父代號**: `{node.get('parent_code')}`\n")
                f.write(f"- **水系名稱**: {node.get('basin_name')}\n")
                f.write(f"- **階層**: {node.get('stream_order')}\n")
                f.write(f"- **性質**: {'民間河川' if str(node.get('is_civilian')) == '1' else '官方公告水系'}\n\n")
                f.write(f"## 拓樸路徑\n`{node.get('topology_path')}`\n\n")
                f.write(f"## 描述\n{node.get('description') or '暫無描述'}\n")

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

    return {
        "root_dir": abs_target,
        "created_dirs_count": created_dirs_cnt
    }
