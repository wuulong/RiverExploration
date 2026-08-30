#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[metadata]
name: elevation_hydrator.py
title: 全球高程 API 厚化與水文縱剖面分析 CLI 工具 (CGS v2.0)
description: 整合 Open-Elevation API，極致善用本地 OSM 幾何快取 (cache/osm_geoms/ 與 cache/confluence_atlas.json)，提供點位高程查詢、匯流點高程厚化、河道縱剖面 (profile) 採樣與水力坡降 (slope) 計算。
category: gis
manual: scripts/manuals/elevation_hydrator.md
dependencies: urllib, json, os, sys, math, ssl, argparse
cgs_version: 2.0
"""

import os
import sys
import json
import ssl
import math
import time
import argparse
import urllib.request
import urllib.parse
from datetime import datetime

__cli_spec_version__ = "2.0"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BOOK_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
ELEVATION_CACHE_FILE = os.path.join(BOOK_ROOT, "cache/elevation_cache.json")
GEOM_CACHE_DIR = os.path.join(BOOK_ROOT, "cache/osm_geoms")
MANUAL_PATH = "scripts/manuals/elevation_hydrator.md"

def haversine_dist(lat1, lon1, lat2, lon2):
    """計算兩點經緯度的半正矢球面距離 (公尺)"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def load_elevation_cache():
    """載入全庫高程快取小檔"""
    if os.path.exists(ELEVATION_CACHE_FILE):
        try:
            with open(ELEVATION_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_elevation_cache(cache_data):
    """實時落庫高程快取檔"""
    os.makedirs(os.path.dirname(ELEVATION_CACHE_FILE), exist_ok=True)
    try:
        with open(ELEVATION_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def fetch_elevations_from_api(lat_lon_tuples: list):
    """
    對 Open-Elevation API 發動批量高程查詢，優先讀取與落庫本地 cache
    lat_lon_tuples: [(lat1, lon1), (lat2, lon2), ...]
    """
    cache = load_elevation_cache()
    results = {}
    missing_pts = []

    # 1. 優先查本地快取
    for lat, lon in lat_lon_tuples:
        key = f"{round(lat, 5)},{round(lon, 5)}"
        if key in cache:
            results[(lat, lon)] = cache[key]
        else:
            missing_pts.append((lat, lon))

    # 2. 若有未快取的點，分批 (Batch 50) 打 Overpass Open-Elevation API
    if missing_pts:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        batch_size = 50
        for i in range(0, len(missing_pts), batch_size):
            chunk = missing_pts[i:i+batch_size]
            loc_param = "|".join(f"{lat},{lon}" for lat, lon in chunk)
            url = f"https://api.open-elevation.com/api/v1/lookup?locations={loc_param}"
            req = urllib.request.Request(url, headers={"User-Agent": "BMAD-PA-GIS/ElevationHydrator"})

            try:
                with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                    res_json = json.loads(resp.read().decode("utf-8"))
                    res_list = res_json.get("results", [])
                    for idx_item, item in enumerate(res_list):
                        ele = item.get("elevation")
                        orig_lat, orig_lon = chunk[idx_item]
                        key = f"{round(orig_lat, 5)},{round(orig_lon, 5)}"
                        cache[key] = ele
                        results[(orig_lat, orig_lon)] = ele
            except Exception as e:
                print(f"⚠️ API 高程查詢警告: {e}", file=sys.stderr)

        # 3. 查詢完成立刻實時落庫硬碟
        save_elevation_cache(cache)

    return results

def cmd_query(locations_str: str, json_mode: bool = False):
    """功能 1: 單點與多點高程查詢"""
    pts = []
    for item in locations_str.split("|"):
        parts = item.split(",")
        if len(parts) == 2:
            try:
                pts.append((float(parts[0].strip()), float(parts[1].strip())))
            except ValueError:
                pass

    if not pts:
        print("❌ 座標格式錯誤，範例: --locations '24.76367,121.13452|24.61645,121.1769'", file=sys.stderr)
        return

    ele_map = fetch_elevations_from_api(pts)
    out_list = [{"latitude": lat, "longitude": lon, "elevation_m": ele_map.get((lat, lon))} for lat, lon in pts]

    if json_mode:
        print(json.dumps(out_list, ensure_ascii=False, indent=2))
    else:
        print(f"⛰️ 高程查詢結果 ({len(pts)} 個點):")
        for item in out_list:
            print(f"  📍 GPS: ({item['latitude']}, {item['longitude']}) ➔ 海拔高度: {item['elevation_m']} 公尺")

def cmd_hydrate_atlas(atlas_json_path: str, json_mode: bool = False):
    """功能 2: confluence_atlas.json 匯流點高程厚化"""
    if not os.path.exists(atlas_json_path):
        print(f"❌ 檔案不存在: {atlas_json_path}", file=sys.stderr)
        return

    with open(atlas_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    atlas = data.get("confluence_atlas", {})
    pts_to_fetch = []

    for k, v in atlas.items():
        lon, lat = v.get("confluence_lon"), v.get("confluence_lat")
        if lon is not None and lat is not None:
            pts_to_fetch.append((lat, lon))

    print(f"🌐 [Elevation Hydrator] 準備為 Atlas 中 {len(pts_to_fetch)} 個實體匯流點注入 3D 海拔高程...", file=sys.stderr)
    ele_map = fetch_elevations_from_api(pts_to_fetch)

    hydrated_cnt = 0
    for k, v in atlas.items():
        lon, lat = v.get("confluence_lon"), v.get("confluence_lat")
        if lon is not None and lat is not None:
            ele = ele_map.get((lat, lon))
            v["confluence_elevation_m"] = ele
            hydrated_cnt += 1

    # 寫回 JSON 檔
    with open(atlas_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"🎉【高程厚化完成】已成功將高程注入至 {atlas_json_path} (共厚化 {hydrated_cnt} 筆匯流點)！", file=sys.stderr)

def cmd_profile(river_name: str, basin_name: str = None, step_m: float = 1000.0, json_mode: bool = False):
    """功能 3: 河道沿線縱剖面高程採樣 (善用本地 cache/osm_geoms/)"""
    # 尋找本地 OSM 幾何快取
    target_geoms = []
    if os.path.exists(GEOM_CACHE_DIR):
        for f_name in os.listdir(GEOM_CACHE_DIR):
            if f_name.endswith(".json"):
                f_path = os.path.join(GEOM_CACHE_DIR, f_name)
                try:
                    with open(f_path, "r", encoding="utf-8") as f:
                        elements = json.load(f)
                        for el in elements:
                            n = el.get("tags", {}).get("name", "")
                            if river_name in n or n in river_name:
                                target_geoms.append(el)
                except Exception:
                    pass

    if not target_geoms:
        print(f"❌ 本地 cache/osm_geoms/ 找不到河流 [{river_name}] 的折線幾何！", file=sys.stderr)
        print(f"ℹ️ [提示] 請先執行幾何擷取工具: python scripts/batch_extract_confluence_atlas.py -b 某水系名稱", file=sys.stderr)
        return

    # 提取折線經緯度座標
    all_coords = []
    for g in target_geoms:
        all_coords.extend(g.get("geometry", []))

    if not all_coords:
        print(f"❌ 河流 [{river_name}] 無有效折線點。", file=sys.stderr)
        return

    # 沿線距離採樣
    sampled_pts = []
    cum_dist = 0.0
    last_pt = all_coords[0]
    sampled_pts.append((last_pt["lat"], last_pt["lon"], 0.0))

    next_target = step_m
    for i in range(1, len(all_coords)):
        curr_pt = all_coords[i]
        d = haversine_dist(last_pt["lat"], last_pt["lon"], curr_pt["lat"], curr_pt["lon"])
        cum_dist += d
        if cum_dist >= next_target:
            sampled_pts.append((curr_pt["lat"], curr_pt["lon"], round(cum_dist / 1000.0, 2)))
            next_target += step_m
        last_pt = curr_pt

    # 最後一點
    last_coord = all_coords[-1]
    sampled_pts.append((last_coord["lat"], last_coord["lon"], round(cum_dist / 1000.0, 2)))

    # 批次查詢高程
    lat_lon_list = [(pt[0], pt[1]) for pt in sampled_pts]
    ele_map = fetch_elevations_from_api(lat_lon_list)

    profile_data = []
    for lat, lon, dist_km in sampled_pts:
        ele = ele_map.get((lat, lon))
        profile_data.append({"distance_km": dist_km, "latitude": lat, "longitude": lon, "elevation_m": ele})

    if json_mode:
        print(json.dumps({"river_name": river_name, "total_length_km": round(cum_dist/1000.0, 2), "profile": profile_data}, ensure_ascii=False, indent=2))
        return

    # 印出文字版縱剖面分析
    elevations = [p["elevation_m"] for p in profile_data if p["elevation_m"] is not None]
    max_e = max(elevations) if elevations else 0
    min_e = min(elevations) if elevations else 0
    total_km = round(cum_dist/1000.0, 2)
    slope_promille = round(((max_e - min_e) / cum_dist) * 1000, 2) if cum_dist > 0 else 0

    print(f"\n📈【{river_name}】河道縱剖面採樣與水力分析 (善用本地 OSM 快取):")
    print(f"📏 河道採樣長度: {total_km} km | 採樣間距: {int(step_m)}m | 採樣點數: {len(profile_data)} 個")
    print(f"⛰️ 最高海拔: {max_e}m ➔ 最低海拔: {min_e}m | 落差: {max_e - min_e}m | 平均水力坡降: {slope_promille} ‰\n")

    print(" 採樣點位細節:")
    for p in profile_data[:15]:
        e_val = p["elevation_m"] if p["elevation_m"] is not None else 0.0
        bar = "█" * int(e_val / max(max_e, 1) * 20)
        print(f"  - [{p['distance_km']:>5.2f} km] 海拔 {e_val:>4.0f}m | {bar}")

def cmd_slope(p1_str: str, p2_str: str, json_mode: bool = False):
    """功能 4: 兩點落差與水力坡降計算"""
    try:
        p1 = [float(x.strip()) for x in p1_str.split(",")]
        p2 = [float(x.strip()) for x in p2_str.split(",")]
    except Exception:
        print("❌ 座標格式錯誤，範例: --p1 24.61645,121.1769 --p2 24.76367,121.13452", file=sys.stderr)
        return

    pts = [(p1[0], p1[1]), (p2[0], p2[1])]
    ele_map = fetch_elevations_from_api(pts)

    e1 = ele_map.get(pts[0], 0.0)
    e2 = ele_map.get(pts[1], 0.0)
    dist_m = haversine_dist(p1[0], p1[1], p2[0], p2[1])

    delta_h = abs(e1 - e2)
    slope_promille = round((delta_h / dist_m) * 1000, 2) if dist_m > 0 else 0
    slope_percent = round((delta_h / dist_m) * 100, 2) if dist_m > 0 else 0

    res = {
        "point1": {"lat": p1[0], "lon": p1[1], "elevation_m": e1},
        "point2": {"lat": p2[0], "lon": p2[1], "elevation_m": e2},
        "elevation_drop_m": delta_h,
        "distance_km": round(dist_m / 1000.0, 2),
        "hydraulic_slope_promille": slope_promille,
        "hydraulic_slope_percent": slope_percent
    }

    if json_mode:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(f"\n⛰️ 【兩點水力坡降與高程分析】:")
        print(f"  📍 點 1: ({p1[0]}, {p1[1]}) ➔ 海拔 {e1} m")
        print(f"  📍 點 2: ({p2[0]}, {p2[1]}) ➔ 海拔 {e2} m")
        print(f"  📏 水平球面距離: {res['distance_km']} km ({int(dist_m)} m)")
        print(f"  📉 垂直落差 $\\Delta H$: {delta_h} m")
        print(f"  🌊 平均水力坡降: {slope_promille} ‰ (千分之 {slope_promille}) | {slope_percent} %")

def main():
    parser = argparse.ArgumentParser(description="全球高程 API 厚化與水文縱剖面分析 CLI 工具 (CGS v2.0)")
    subparsers = parser.add_subparsers(dest="command", help="子命令路由")

    # query
    p_query = subparsers.add_parser("query", help="單點與多點高程查詢")
    p_query.add_argument("-l", "--locations", required=True, help="經緯度對，格式: 'lat1,lon1|lat2,lon2'")

    # hydrate-atlas
    p_hydrate = subparsers.add_parser("hydrate-atlas", help="confluence_atlas.json 匯流點高程厚化")
    p_hydrate.add_argument("-i", "--input", default=os.path.join(BOOK_ROOT, "cache/confluence_atlas.json"), help="confluence_atlas.json 檔案路徑")

    # profile
    p_profile = subparsers.add_parser("profile", help="河道沿線縱剖面高程採樣 (善用本地 cache)")
    p_profile.add_argument("-r", "--river", required=True, help="目標河流名稱 (如: 油羅溪)")
    p_profile.add_argument("-b", "--basin", default=None, help="水系名稱")
    p_profile.add_argument("--step-m", type=float, default=1000.0, help="採樣距離間距 (公尺)")

    # slope
    p_slope = subparsers.add_parser("slope", help="兩點落差與水力坡降計算")
    p_slope.add_argument("--p1", required=True, help="起點座標 'lat1,lon1'")
    p_slope.add_argument("--p2", required=True, help="終點座標 'lat2,lon2'")

    parser.add_argument("-j", "--json", action="store_true", help="以 JSON 格式輸出")
    parser.add_argument("-q", "--quiet", action="store_true", help="靜音模式")

    args = parser.parse_args()

    if args.command == "query":
        cmd_query(args.locations, json_mode=args.json)
    elif args.command == "hydrate-atlas":
        cmd_hydrate_atlas(args.input, json_mode=args.json)
    elif args.command == "profile":
        cmd_profile(args.river, basin_name=args.basin, step_m=args.step_m, json_mode=args.json)
    elif args.command == "slope":
        cmd_slope(args.p1, args.p2, json_mode=args.json)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
