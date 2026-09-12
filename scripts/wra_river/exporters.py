# -*- coding: utf-8 -*-
"""
wra_river.exporters
負責多格式水文資料轉譯：
- export_as_tree: 彩色 Terminal 水文階層樹
- export_as_geojson: 3D GeoJSON 點/線 FeatureCollection
- export_as_kml: 3D KML Google Earth 載入檔
- export_as_mermaid: Mermaid 流程與拓樸圖
- generate_profile_ascii: 3D 海拔縱剖面降落圖
- format_authority_links: 水脈權威外鏈面板
"""

import unicodedata

def export_as_tree(records: list) -> str:
    """轉譯為帶有 3D 海拔與實體幾何品質的豐富 Terminal 樹狀結構"""
    by_parent = {}
    record_map = {r["river_code"]: r for r in records}
    
    for r in records:
        p_code = r["parent_code"]
        by_parent.setdefault(p_code, []).append(r)
        
    roots = [r for r in records if r["parent_code"] not in record_map]
    
    lines = []
    def build_branch(node, prefix="", is_root=False):
        name = node["river_name"]
        code = node["river_code"]
        is_civ = str(node.get("is_civilian", 0)) == "1"
        tag = "\033[33m[民間]\033[0m" if is_civ else "\033[34m[官方]\033[0m"
        order = f"階層:{node.get('stream_order','?')}"
        
        ele = node.get("plugins", {}).get("elevation", {}).get("confluence_elevation_m")
        ele_str = f" ⛰️ \033[36m{ele}m\033[0m" if ele is not None else ""
        
        gis = node.get("plugins", {}).get("gis", {})
        c_type = gis.get("confluence_type")
        c_type_str = f" | 📍 \033[32m{c_type}\033[0m" if c_type else ""

        info_line = f"{name} ({code}) {tag} ({order}){ele_str}{c_type_str}"
        
        if is_root:
            lines.append(f"🌊 {info_line}")
        else:
            lines.append(f"{prefix}└── {info_line}")
        
        children = by_parent.get(code, [])
        for child in children:
            c_prefix = "" if is_root else prefix + "    "
            build_branch(child, c_prefix, is_root=False)
            
    for r in roots:
        build_branch(r, is_root=True)
        
    return "\n".join(lines)

def export_as_geojson(records: list) -> dict:
    """轉譯為標準 3D GeoJSON 點/線資產 (包含 [lon, lat, elevation_m] 3D Z軸)"""
    features = []
    for r in records:
        gis = r.get("plugins", {}).get("gis", {})
        ele = r.get("plugins", {}).get("elevation", {}).get("confluence_elevation_m")
        
        lon = gis.get("confluence_lon") or r.get("confluence_lon")
        lat = gis.get("confluence_lat") or r.get("confluence_lat")
        
        geometry = None
        if lon is not None and lat is not None:
            try:
                coords = [float(lon), float(lat)]
                if ele is not None:
                    coords.append(float(ele))
                geometry = {
                    "type": "Point",
                    "coordinates": coords
                }
            except (ValueError, TypeError):
                pass
                
        feature = {
            "type": "Feature",
            "properties": r,
            "geometry": geometry
        }
        features.append(feature)
        
    return {
        "type": "FeatureCollection",
        "features": features
    }

def export_as_kml(records: list) -> str:
    """轉譯為標準 3D KML 格式 (供 Google Earth 3D 擬真載入)"""
    kml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '  <Document>',
        '    <name>WRA-Civ 台灣水文拓樸註冊表 (3D Hydrological Spec)</name>'
    ]
    for r in records:
        gis = r.get("plugins", {}).get("gis", {})
        ele = r.get("plugins", {}).get("elevation", {}).get("confluence_elevation_m", 0.0)
        lon = gis.get("confluence_lon") or r.get("confluence_lon")
        lat = gis.get("confluence_lat") or r.get("confluence_lat")
        name = r.get("river_name", "")
        code = r.get("river_code", "")
        desc = r.get("description", "")
        
        if lon and lat:
            kml_lines.append('    <Placemark>')
            kml_lines.append(f'      <name>{name} ({code})</name>')
            kml_lines.append(f'      <description><![CDATA[{desc}<br>海拔: {ele}m]]></description>')
            kml_lines.append('      <Point>')
            kml_lines.append('        <altitudeMode>relativeToGround</altitudeMode>')
            kml_lines.append(f'        <coordinates>{lon},{lat},{ele}</coordinates>')
            kml_lines.append('      </Point>')
            kml_lines.append('    </Placemark>')
    kml_lines.append('  </Document>')
    kml_lines.append('</kml>')
    return "\n".join(kml_lines)

def export_as_mermaid(records: list) -> str:
    """轉譯為 Mermaid 拓樸關係圖"""
    lines = ["graph TD"]
    record_codes = {r["river_code"] for r in records}
    
    for r in records:
        code = r["river_code"]
        name = r["river_name"]
        p_code = r["parent_code"]
        
        node_shape = f'{code}["{name}"]' if str(r.get("is_civilian", 0)) == "0" else f'{code}(("{name}"))'
        lines.append(f"  {node_shape}")
        
        if p_code != "0" and p_code in record_codes:
            lines.append(f"  {p_code} --> {code}")
            
    return "\n".join(lines)

def get_display_width(text: str) -> int:
    """計算包含中文全形字元的 Terminal 顯示寬度"""
    w = 0
    for ch in text:
        if unicodedata.east_asian_width(ch) in ('F', 'W', 'A'):
            w += 2
        else:
            w += 1
    return w

def pad_display(text: str, target_width: int) -> str:
    """將含有中文字的字串補齊空格至指定的 Terminal 顯示寬度"""
    w = get_display_width(text)
    pad = target_width - w
    return text + " " * max(0, pad)

def generate_profile_ascii(records: list, query: str) -> str:
    """產出特定水系全體水脈的 3D 海拔 ASCII 剖面降落圖"""
    basin_records = [r for r in records if r.get("basin_name") == query or r.get("basin_code") == query]
    if not basin_records:
        basin_records = [r for r in records if query in r.get("basin_name", "") or query in r.get("river_name", "")]
        
    if not basin_records:
        return f"❌ 找不到水系/河流 [{query}] 的相關紀錄！"

    ele_records = [r for r in basin_records if r.get("plugins", {}).get("elevation", {}).get("confluence_elevation_m") is not None]
    no_ele_records = [r for r in basin_records if r.get("plugins", {}).get("elevation", {}).get("confluence_elevation_m") is None]

    lines = []
    lines.append(f"\n==========================================================================================")
    lines.append(f" ⛰️  【{query}】水系水脈海拔高度剖面降落圖 (3D Confluence Profile)")
    lines.append(f"==========================================================================================")

    if ele_records:
        sorted_ele = sorted(ele_records, key=lambda x: x["plugins"]["elevation"]["confluence_elevation_m"], reverse=True)
        max_ele = sorted_ele[0]["plugins"]["elevation"]["confluence_elevation_m"]
        min_ele = sorted_ele[-1]["plugins"]["elevation"]["confluence_elevation_m"]
        lines.append(f" 📊 統計摘要: 具高程水脈共 {len(sorted_ele)} 條 | 最高海拔: {max_ele}m | 最低海拔: {min_ele}m")
        lines.append(f"------------------------------------------------------------------------------------------")

        chart_width = 45
        for r in sorted_ele:
            name = r.get("river_name", "未知")
            order = r.get("stream_order", "?")
            ele = r["plugins"]["elevation"]["confluence_elevation_m"]
            is_civ = str(r.get("is_civilian", "0")) == "1"
            tag = "[民]" if is_civ else "[官]"

            ratio = ele / max_ele if max_ele > 0 else 0
            bar_len = int(ratio * chart_width)
            bar = "█" * bar_len

            label = f"{tag} {name} (階:{order})"
            lines.append(f" {pad_display(label, 24)} | {bar:<{chart_width}} {ele:6.1f}m")
    else:
        lines.append(f" ℹ️ 此水系所有水脈目前暫無實體匯流點高程資料。")

    if no_ele_records:
        lines.append(f"------------------------------------------------------------------------------------------")
        lines.append(f" ⏳ 待測量高程水脈 ({len(no_ele_records)} 條):")
        names = [f"{r.get('river_name')}" for r in no_ele_records[:20]]
        lines.append(f"    {', '.join(names)}" + (" ..." if len(no_ele_records) > 20 else ""))

    lines.append(f"==========================================================================================\n")
    return "\n".join(lines)

def format_authority_links(target: dict) -> str:
    """產出特定水脈的所有外部權威連結 (Links) 面板文字"""
    links = target.get("links", {})
    qid = links.get("wikidata_id", "")
    wikidata_url_str = f"{qid} (https://www.wikidata.org/wiki/{qid})" if qid else "無"

    res = [
        f"\n🔗 【{target['river_name']} ({target['river_code']}) 權威連結面板】",
        f"  ├─ 📌 Wikidata ID    : {wikidata_url_str}",
        f"  ├─ 📖 Wikipedia URL  : {links.get('wikipedia_url') or '無'}",
        f"  ├─ 🗺️ OpenStreetMap : {links.get('osm_url') or '無'}",
        f"  └─ 🌐 WalkGIS URL    : {links.get('walkgis_url') or '無'}\n"
    ]
    return "\n".join(res)
