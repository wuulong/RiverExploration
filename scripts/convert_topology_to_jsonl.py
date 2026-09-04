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

def load_existing_released_codes(jsonl_path: str) -> dict:
    """載入已釋出 JSONL 資料庫中的已確認 (confirmed) 主鍵程式碼 (PrimaryKey Protection)"""
    confirmed = {}
    if os.path.exists(jsonl_path):
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        d = json.loads(line)
                        attr = d.get("attribute_json", {})
                        if attr.get("code_status") == "confirmed" or d.get("code_status") == "confirmed":
                            confirmed[d["river_code"]] = d["river_name"]
                    except Exception:
                        pass
    return confirmed

def convert_topology_to_jsonl(csv_path: str, atlas_json_path: str, output_jsonl_path: str):
    """將 CSV 拓樸檔案轉譯為 Native JSONL 資料庫，包含程式碼生命週期狀態管理"""
    if not os.path.exists(csv_path):
        print(f"❌ 來源 CSV 不存在: {csv_path}", file=sys.stderr)
        return

    # 1. 載入已確認 (confirmed) 之主鍵防護帳本
    confirmed_codes = load_existing_released_codes(output_jsonl_path)

    # 1. 純讀取既有匯流點與高程 JSON 圖集及水利署權威 Wikicode 對照檔
    atlas_map = {}
    if os.path.exists(atlas_json_path):
        try:
            with open(atlas_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                atlas_map = data.get("confluence_atlas", {})
                print(f"  ├─ 💾 [純讀取快取] 成功載入已算好的 {len(atlas_map)} 筆匯流點與 3D 高程圖集資料 (0 網路連線, 防寫保護)", file=sys.stderr)
        except Exception as e:
            print(f"  ├─ ⚠️ 讀取快取警告: {e}", file=sys.stderr)

    # 1.1 載入內政部直轄市、縣市界線圖資做全量 Spatial Join 縣市自動推導
    county_gdf = None
    shp_path = os.path.abspath(os.path.join(BOOK_ROOT, "../../../external/流域情報開放地圖/00_基本圖資/7442-直轄市、縣市界線(TWD97經緯度)/COUNTY_MOI.shp"))
    if os.path.exists(shp_path):
        try:
            import geopandas as gpd
            county_gdf = gpd.read_file(shp_path).to_crs(epsg=4326)
            print(f"  ├─ 🗺️ [GIS 圖資載入] 成功載入內政部縣市邊界 Shapefile ({len(county_gdf)} 個縣市界線)", file=sys.stderr)
        except Exception as e:
            print(f"  ├─ ⚠️ 載入縣市圖資失敗: {e}", file=sys.stderr)

    # 水利署河川分署代碼對照表 (governmentunitidentifier -> 名稱 & 管轄縣市)
    river_office_dict = {
        "1": {"office_name": "第一河川分署", "counties": ["宜蘭縣"]},
        "2": {"office_name": "第二河川分署", "counties": ["桃園市", "新竹縣", "新竹市", "苗栗縣"]},
        "3": {"office_name": "第三河川分署", "counties": ["臺中市", "南投縣", "彰化縣"]},
        "4": {"office_name": "第四河川分署", "counties": ["彰化縣", "雲林縣", "南投縣"]},
        "5": {"office_name": "第五河川分署", "counties": ["雲林縣", "嘉義縣", "嘉義市", "臺南市"]},
        "6": {"office_name": "第六河川分署", "counties": ["臺南市", "高雄市"]},
        "7": {"office_name": "第七河川分署", "counties": ["高雄市", "屏東縣"]},
        "8": {"office_name": "第八河川分署", "counties": ["臺東縣"]},
        "9": {"office_name": "第九河川分署", "counties": ["花蓮縣"]},
        "10": {"office_name": "第十河川分署", "counties": ["基隆市", "臺北市", "新北市"]}
    }

    wra_wikicode_map = {}
    wra_office_map = {}
    wra_json_p = os.path.join(BOOK_ROOT, "wra_official_river_codes.json")
    if os.path.exists(wra_json_p):
        try:
            with open(wra_json_p, "r", encoding="utf-8") as f:
                wra_data = json.load(f)
                for item in wra_data:
                    code = item.get("subsubsubsubsidiarybasinrivercode") or item.get("subsubsubsidiarybasinrivercode") or item.get("subsubsidiarybasinrivercode") or item.get("subsidiarybasinrivercode") or item.get("basinrivercode")
                    wcode = item.get("wikicode", "").strip()
                    unit = item.get("governmentunitidentifier", "").strip()
                    if code:
                        if wcode and wcode.startswith("Q") and code not in wra_wikicode_map:
                            wra_wikicode_map[code] = wcode
                        if unit and code not in wra_office_map:
                            wra_office_map[code] = unit
        except Exception as e:
            print(f"  ├─ ⚠️ 讀取 WRA 官方資料庫警告: {e}", file=sys.stderr)

    # 2. 讀取 CSV 並拼裝成標準雙軌 JSONL
    with open(csv_path, "r", encoding="utf-8") as f:
        records = list(csv.DictReader(f))

    # 2. 硬性檢查 Confirmed Primary Key 完整性
    current_codes = {r["river_code"].strip(): r["river_name"].strip() for r in records}
    missing_codes = set(confirmed_codes.keys()) - set(current_codes.keys())
    if missing_codes:
        print(f"🚨 [程式碼鎖定警報] 檢測到 {len(missing_codes)} 筆已確認 (confirmed) 的 river_code 遭意外刪除或變動！", file=sys.stderr)
        for mc in list(missing_codes)[:5]:
            print(f"   ❌ 缺失鎖定程式碼: {mc} (原名: {confirmed_codes[mc]})", file=sys.stderr)
        print("🛑 轉換中止！已凍結 (confirmed) 之程式碼僅能轉為 deprecated 狀態，禁止直接刪除。", file=sys.stderr)
        sys.exit(1)

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
        
        # 安全推導 6 位數水系程式碼 basin_code
        b_code = code[:6] if len(code) >= 6 else code
        if p_code and p_code in code_map:
            root_code = p_code[:6]
            b_code = root_code

        # 解析 CSV 中的 attribute_json
        attr_json = {}
        if r.get("meta_data"):
            try:
                attr_json = json.loads(r["meta_data"])
            except Exception:
                pass

        # 疑慮備註與原始名稱保留至 attribute_json
        raw_name_entry = r.get("river_name", "")
        if "(" in raw_name_entry or "（" in raw_name_entry or "原名稱" in r.get("description", ""):
            attr_json["raw_river_name"] = raw_name_entry
        
        # 提取外鏈並從 attribute_json 中移除重複的 source_links 與 cross_ref
        source_links = attr_json.pop("source_links", {})
        cross_ref = attr_json.pop("cross_ref", {})
        wiki_url = source_links.get("wiki_url", "")
        osm_url = source_links.get("osm_url", "")
        wikidata_id = r.get("wikidata_id", "").strip() or cross_ref.get("wikidata_id", "")
        if not wikidata_id and code in wra_wikicode_map:
            wikidata_id = wra_wikicode_map[code]

        # 自動校正與補全主流 (is_civilian == 0) 的 Wiki 與 OSM 權威外鏈
        is_civ = int(r["is_civilian"]) if r.get("is_civilian") and r["is_civilian"].isdigit() else 0
        if is_civ == 0 and not wiki_url:
            wiki_url = f"https://zh.wikipedia.org/wiki/{name}"
        if is_civ == 0 and not osm_url:
            osm_url = f"https://www.openstreetmap.org/search?query={name}"

        # 自動修復 description 欄位
        raw_desc = r.get("description", "").strip()
        if is_civ == 0:
            correct_desc = f"{b_name}官方水系"
        else:
            correct_desc = f"{b_name}水系民間支流"
        
        if "官方水系" in raw_desc or "民間支流" in raw_desc or not raw_desc:
            desc = correct_desc
        else:
            desc = raw_desc

        # 程式碼生命週期狀態管理 (正名收納於 attribute_json 內部)
        code_status = attr_json.pop("code_status", r.get("code_status", "draft")).strip()
        deprecated_codes = attr_json.pop("deprecated_codes", [])
        replaced_by = attr_json.pop("replaced_by", "")

        # 全台水系主流縣市與 5 位數官方行政區劃程式碼 (County Code) 歸屬
        county_code_dict = {
            "臺北市": "63000", "高雄市": "64000", "新北市": "65000", "臺中市": "66000", "臺南市": "67000", "桃園市": "68000",
            "宜蘭縣": "10002", "新竹縣": "10004", "苗栗縣": "10005", "彰化縣": "10007", "南投縣": "10008", "雲林縣": "10009",
            "嘉義縣": "10010", "屏東縣": "10013", "臺東縣": "10014", "花蓮縣": "10015", "基隆市": "10017", "新竹市": "10018", "嘉義市": "10020",
            "澎湖縣": "10016", "金門縣": "09020", "連江縣": "09007"
        }

        # 特定權威雙縣市界河 Right Bank Arbitration 仲裁字典
        border_river_overrides = {
            "114000": ("新北市", "65000", ["新北市", "臺北市"]),
            "130000": ("新竹市", "10018", ["新竹市", "新竹縣"]),
            "151000": ("雲林縣", "10009", ["雲林縣", "彰化縣"]),
            "143000": ("臺中市", "66000", ["臺中市", "苗栗縣"]),
            "158000": ("嘉義縣", "10010", ["嘉義縣", "臺南市"]),
            "173000": ("屏東縣", "10013", ["屏東縣", "高雄市"])
        }

        # 水利署分署 (局) 代碼與名稱匹配
        office_id = wra_office_map.get(code) or wra_office_map.get(b_code) or ""
        office_info = river_office_dict.get(office_id, {})
        office_name = office_info.get("office_name", "")
        valid_counties = office_info.get("counties", [])

        # 預設歸屬變數
        primary_county = "未定縣市"
        primary_county_code = "00000"
        border_counties = []
        assignment_reason = "Unassigned_Fallback"
        derivation_tier = "Tier_4_Fallback"

        # Tier 1: 權威雙縣市界河 Right Bank Outfall 仲裁
        if code in border_river_overrides:
            primary_county, primary_county_code, border_counties = border_river_overrides[code]
            assignment_reason = f"Right_Bank_Border_Arbitration (界河右岸原則仲裁歸屬 {primary_county})"
            derivation_tier = "Tier_1_Border_Arbitration"

        # Tier 2: 出海口 / 匯流點 GPS 實體點位與 COUNTY_MOI.shp 空間疊合 (Spatial Join)
        elif code in atlas_map and atlas_map[code].get("confluence_lon") is not None:
            atlas_info = atlas_map[code]
            lon = atlas_info.get("confluence_lon")
            lat = atlas_info.get("confluence_lat")
            if lon is not None and lat is not None and county_gdf is not None:
                from shapely.geometry import Point
                pt = Point(lon, lat)
                target_gdf = county_gdf
                if valid_counties:
                    office_sub_gdf = county_gdf[county_gdf["COUNTYNAME"].isin(valid_counties)]
                    if not office_sub_gdf.empty:
                        target_gdf = office_sub_gdf

                match = target_gdf[target_gdf.contains(pt)]
                if not match.empty:
                    primary_county = match.iloc[0]["COUNTYNAME"]
                    primary_county_code = match.iloc[0]["COUNTYCODE"]
                    assignment_reason = f"Spatial_Join_Contains (出海口點位 {lon:.4f},{lat:.4f} 落入 {primary_county} 多邊形內)"
                    derivation_tier = "Tier_2_Spatial_Join_Contains"
                else:
                    dists = target_gdf.distance(pt)
                    min_idx = dists.idxmin()
                    nearest = target_gdf.loc[min_idx]
                    primary_county = nearest["COUNTYNAME"]
                    primary_county_code = nearest["COUNTYCODE"]
                    assignment_reason = f"Spatial_Join_Nearest (出海口點位 {lon:.4f},{lat:.4f} 最接近 {primary_county} 邊界)"
                    derivation_tier = "Tier_2_Spatial_Join_Nearest"
                border_counties = [primary_county]

        # Tier 3: 水系名稱與描述字串語意提取 (Text Entity Extraction)
        if primary_county == "未定縣市":
            search_text = f"{name} {desc}"
            # 依已知縣市名稱關鍵字匹配
            for c_name, c_code in county_code_dict.items():
                short_c = c_name.replace("臺", "台").replace("市", "").replace("縣", "")
                if c_name in search_text or (len(short_c) >= 2 and short_c in search_text):
                    primary_county = c_name
                    primary_county_code = c_code
                    border_counties = [c_name]
                    assignment_reason = f"Text_Entity_Extraction (從名稱/描述語意萃取出 {c_name})"
                    derivation_tier = "Tier_3_Text_Entity_Extraction"
                    break
            
            # 擴充全台沿海鄉鎮區與河川傳統地名語意對照庫
            if primary_county == "未定縣市":
                locality_map = {
                    "鹿港": ("彰化縣", "10007"), "公司田": ("新北市", "65000"), "淡水": ("新北市", "65000"),
                    "麻豆": ("臺南市", "67000"), "七股": ("臺南市", "67000"), "將軍": ("臺南市", "67000"),
                    "釣魚台": ("宜蘭縣", "10002"), "竹安": ("宜蘭縣", "10002"), "雙溪": ("新北市", "65000"),
                    "乾華": ("新北市", "65000"), "石門": ("新北市", "65000"), "埔坪": ("新北市", "65000"),
                    "興仁": ("新北市", "65000"), "水仙": ("新北市", "65000"), "八蓮": ("新北市", "65000"),
                    "八連": ("新北市", "65000"), "尖山腳": ("新北市", "65000"), "林子溪": ("新北市", "65000"),
                    "埔心": ("桃園市", "68000"), "福興": ("新竹縣", "10004"),
                    "萬寮": ("彰化縣", "10007"), "洋仔厝": ("彰化縣", "10007"), "萬興": ("彰化縣", "10007"), "麥嶼": ("彰化縣", "10007"),
                    "鹿草": ("嘉義縣", "10010"), "典寶": ("高雄市", "64000"), "山鹽": ("高雄市", "64000"), "鹽水港": ("高雄市", "64000"),
                    "牛埔": ("屏東縣", "10013"), "佳冬": ("屏東縣", "10013"), "牡丹": ("屏東縣", "10013"),
                    "旭海": ("屏東縣", "10013"), "里仁": ("屏東縣", "10013"), "港子": ("屏東縣", "10013"),
                    "十里": ("屏東縣", "10013"), "南州": ("屏東縣", "10013"), "溪洲代天府": ("屏東縣", "10013"),
                    "真柄": ("臺東縣", "10014"), "水連": ("花蓮縣", "10015"), "水璉": ("花蓮縣", "10015"),
                    "雪山山脈東側": ("宜蘭縣", "10002"), "雪山東麓": ("宜蘭縣", "10002"), "雪山": ("宜蘭縣", "10002")
                }
                for loc_k, (c_n, c_c) in locality_map.items():
                    if loc_k in search_text:
                        primary_county = c_n
                        primary_county_code = c_c
                        border_counties = [c_n]
                        assignment_reason = f"Locality_Keyword_Match (從傳統鄉鎮/地名關鍵字 '{loc_k}' 推導至 {c_n})"
                        derivation_tier = "Tier_3_Locality_Keyword_Match"
                        break

        # Tier 3.5: 母水系 (basin_name) 縣市親緣繼承 (Basin Inheritance)
        if primary_county == "未定縣市" and b_name and b_name in code_map:
            parent_mainstem = code_map[b_name]
            p_attr = parent_mainstem.get("attribute_json", {})
            p_county = p_attr.get("primary_county")
            p_county_code = p_attr.get("primary_county_code")
            if p_county and p_county != "未定縣市":
                primary_county = p_county
                primary_county_code = p_county_code
                border_counties = [primary_county]
                assignment_reason = f"Basin_County_Inheritance (繼承母水系 {b_name} 之歸屬縣市 {primary_county})"
                derivation_tier = "Tier_3.5_Basin_Inheritance"

        # Tier 4: 若仍未定，且有明確單一管轄縣市之河川局，由河川局預設推導
        if primary_county == "未定縣市" and valid_counties and len(valid_counties) == 1:
            primary_county = valid_counties[0]
            primary_county_code = county_code_dict.get(primary_county, "00000")
            border_counties = [primary_county]
            assignment_reason = f"River_Office_Single_County_Fallback (由 {office_name} 唯一管轄縣市 {primary_county} 推導)"
            derivation_tier = "Tier_4_River_Office_Fallback"

        # GPS 出海口/匯流點狀態
        has_outfall_gps = False
        outfall_lon = None
        outfall_lat = None
        if code in atlas_map:
            atlas_info = atlas_map[code]
            outfall_lon = atlas_info.get("confluence_lon")
            outfall_lat = atlas_info.get("confluence_lat")
            if outfall_lon is not None and outfall_lat is not None:
                has_outfall_gps = True

        # 雙重交叉檢核 (Cross Validation): 檢查 Spatial Join 結果是否在河川局管轄縣市清單內
        is_office_county_matched = True
        if office_name and primary_county != "未定縣市" and valid_counties:
            if primary_county not in valid_counties and not any(bc in valid_counties for bc in border_counties):
                is_office_county_matched = False

        attr_json["code_status"] = code_status
        attr_json["deprecated_codes"] = deprecated_codes
        attr_json["replaced_by"] = replaced_by
        attr_json["river_office_id"] = office_id
        attr_json["river_office_name"] = office_name
        attr_json["office_valid_counties"] = valid_counties
        attr_json["has_outfall_gps"] = has_outfall_gps
        attr_json["outfall_lon"] = outfall_lon
        attr_json["outfall_lat"] = outfall_lat
        attr_json["primary_county"] = primary_county
        attr_json["primary_county_code"] = primary_county_code
        attr_json["is_border_river"] = len(border_counties) > 1
        attr_json["border_counties"] = border_counties
        attr_json["arbitration_rule"] = "Right_Bank_Outfall"
        attr_json["county_assignment_reason"] = assignment_reason
        attr_json["county_derivation_tier"] = derivation_tier
        attr_json["is_office_county_matched"] = is_office_county_matched

        if "provenance" not in attr_json:
            attr_json["provenance"] = {"last_updated": datetime.now().strftime("%Y-%m-%d")}

        entry = {
            "river_code": code,
            "river_name": name,
            "parent_code": p_code,
            "parent_name": p_name,
            "basin_code": b_code,
            "basin_name": b_name,
            "topology_path": r.get("topology_path", ""),
            "is_civilian": is_civ,
            "source_type": r.get("source_type", ""),
            "waterway_type": r.get("waterway_type", ""),
            "stream_order": int(r["stream_order"]) if r.get("stream_order") and r["stream_order"].isdigit() else None,
            "description": desc,
            "contributor": r.get("contributor", ""),
            "links": {
                "walkgis_url": "",
                "wikipedia_url": wiki_url,
                "osm_url": osm_url,
                "wikidata_id": wikidata_id
            },
            "attribute_json": attr_json,
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
            
            # 手動/幾何補全大幹流 (油羅溪 130020 與 上坪溪 130010 雙溪口匯流點, 130000 頭前溪南寮出海口)
            if code == "130020" and (lon is None or ele is None):
                lon, lat, ele = 121.0944, 24.7300, 121.0
                atlas_info["confluence_type"] = "OSM_Shared_Node_TwinStreams"
            elif code == "130010" and (lon is None or ele is None):
                lon, lat, ele = 121.0940, 24.7295, 121.0
                atlas_info["confluence_type"] = "OSM_Shared_Node_TwinStreams"
            elif code == "130000" and (lon is None or ele is None):
                lon, lat, ele = 120.9315, 24.8488, 0.0
                atlas_info["confluence_type"] = "Outfall_Sea"

            if lon is not None and lat is not None:
                entry["plugins"]["gis"] = {
                    "confluence_id": atlas_info.get("confluence_id", f"J-{code}"),
                    "confluence_lon": lon,
                    "confluence_lat": lat,
                    "confluence_type": atlas_info.get("confluence_type", "Unknown"),
                    "estimated_length_km": atlas_info.get("estimated_length_km", 63.0),
                    "estimated_velocity_ms": None,
                    "osm_wikipedia_tag": atlas_info.get("name_wiki", "zh:頭前溪")
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
