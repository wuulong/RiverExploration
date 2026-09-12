# -*- coding: utf-8 -*-
"""
wra_river.topology
負責核心水文拓樸演算：
- 上下游親緣追溯 (trace_topology)
- 最近共同祖先計算 (compute_lca)
- 拓樸連通子圖動態切片 (slice_subgraph)
- 拓樸幾何聚合統計 (compute_topology_stats)
- 拓樸物理完整迴路檢核 (lint_topology)
"""

import sys

def trace_topology(records: list, target_code_or_name: str, direction: str = "down") -> list:
    """追溯指定河流之上下游拓樸親緣"""
    records_by_code = {r["river_code"]: r for r in records}
    records_by_name = {r["river_name"]: r for r in records}
    
    start_node = records_by_code.get(target_code_or_name) or records_by_name.get(target_code_or_name)
    if not start_node:
        raise ValueError(f"找不到指定的目標河流: {target_code_or_name}")
        
    result = []
    if direction == "up":
        # 向上追溯至出海口主流 (由源頭往出海口或父節點)
        path_codes = [c for c in start_node.get("topology_path", "").split("@") if c and c != "0"]
        for c in path_codes:
            if c in records_by_code:
                result.append(records_by_code[c])
    else:
        # 向下擴展所有子孫溪流
        root_code = start_node["river_code"]
        for r in records:
            path = r.get("topology_path", "")
            if root_code in path.split("@"):
                result.append(r)
    return result

def compute_lca(records: list, target_codes_or_names: list) -> str:
    """計算給定多個水脈節點的最近共同祖先 (Lowest Common Ancestor, LCA) 程式碼"""
    by_code = {r['river_code']: r for r in records}
    by_name = {r['river_name']: r for r in records}
    
    matched = [by_code.get(q) or by_name.get(q) for q in target_codes_or_names if (by_code.get(q) or by_name.get(q))]
    if len(matched) < 2:
        return matched[0]["river_code"] if matched else None
        
    paths = [[c for c in n.get('topology_path', '').split('@') if c and c != '0'] for n in matched]
    common = None
    for tup in zip(*paths):
        if len(set(tup)) == 1:
            common = tup[0]
        else:
            break
    return common

def slice_subgraph(records: list, query_targets: list, use_lca: bool = False) -> list:
    """拓樸動態切片與最小連通子圖提取器"""
    by_code = {r['river_code']: r for r in records}
    by_name = {r['river_name']: r for r in records}
    matched = [by_code.get(q) or by_name.get(q) for q in query_targets if (by_code.get(q) or by_name.get(q))]
    if not matched:
        return []
        
    sub_codes = set()
    if use_lca and len(matched) >= 2:
        common = compute_lca(records, query_targets)
        paths = [[c for c in n.get('topology_path', '').split('@') if c and c != '0'] for n in matched]
        if common:
            for p in paths:
                if common in p:
                    sub_codes.update(p[p.index(common):])
        else:
            for p in paths:
                sub_codes.update(p)
    else:
        for n in matched:
            sub_codes.update([c for c in n.get('topology_path', '').split('@') if c and c != '0'])
            
    return [by_code[c] for c in sub_codes if c in by_code]

def compute_topology_stats(records: list) -> dict:
    """水文拓樸幾何聚合計算器 (Map-Reduce 串流聚合)"""
    total = len(records)
    if total == 0:
        return {'stream_count': 0}
        
    civ = sum(1 for r in records if str(r.get('is_civilian', 0)).strip() == '1')
    off = total - civ
    elevs = []
    has_geo = 0
    orders = {}
    
    for r in records:
        ele = r.get('plugins', {}).get('elevation', {}).get('confluence_elevation_m')
        if ele is not None:
            try:
                elevs.append(float(ele))
            except (ValueError, TypeError):
                pass
        if r.get('plugins', {}).get('gis', {}).get('confluence_lon') is not None or str(r.get('has_osm_geo', 0)) == '1':
            has_geo += 1
        ord_val = str(r.get('stream_order', '?'))
        orders[ord_val] = orders.get(ord_val, 0) + 1
        
    elev_stats = {}
    if elevs:
        elev_stats = {
            'max_m': max(elevs),
            'min_m': min(elevs),
            'delta_h_m': round(max(elevs) - min(elevs), 2),
            'avg_m': round(sum(elevs) / len(elevs), 2)
        }
        
    return {
        'stream_count': total,
        'official_streams': off,
        'civilian_streams': civ,
        'official_ratio': round(off / total, 3),
        'geo_hydration_rate': round(has_geo / total, 3),
        'elevation_coverage': round(len(elevs) / total, 3),
        'elevation_stats': elev_stats,
        'stream_orders': orders
    }

def lint_topology(records: list, strict: bool = False) -> dict:
    """水文拓樸完整迴路檢核器 (Cycle, Gravity, Orphan)"""
    errors = []
    warnings = []
    by_code = {r['river_code']: r for r in records}
    
    # 1. 孤兒節點檢查
    for r in records:
        p_code = r.get('parent_code', '0')
        if p_code != '0' and p_code not in by_code:
            errors.append(f"孤兒節點: 水脈 [{r['river_code']} {r.get('river_name','')}] 的 parent_code [{p_code}] 不存在")
            
    # 2. 環狀依賴檢查 (DFS)
    def check_cycle(code, path_set):
        if code in path_set:
            return True
        if code not in by_code or code == '0':
            return False
        path_set.add(code)
        res = check_cycle(by_code[code].get('parent_code', '0'), path_set)
        path_set.remove(code)
        return res
        
    for r in records:
        if check_cycle(r['river_code'], set()):
            errors.append(f"環狀依賴錯誤: 水脈 [{r['river_code']} {r.get('river_name','')}] 形成完整迴路")
            break
            
    # 3. 重力守恆檢核 (下游匯流點高程應低於或等於上游高程)
    for r in records:
        p_code = r.get('parent_code', '0')
        if p_code in by_code:
            p = by_code[p_code]
            ele_curr = r.get('plugins', {}).get('elevation', {}).get('confluence_elevation_m')
            ele_parent = p.get('plugins', {}).get('elevation', {}).get('confluence_elevation_m')
            if ele_curr is not None and ele_parent is not None:
                try:
                    if float(ele_parent) > float(ele_curr) + 50.0:  # 容許 50m 測量與平原微小誤差
                        warnings.append(f"重力守恆疑慮: 上游 [{r['river_name']} ({ele_curr}m)] 高於其匯入點父節點 [{p['river_name']} ({ele_parent}m)]")
                except (ValueError, TypeError):
                    pass

    passed = len(errors) == 0 and (not strict or len(warnings) == 0)
    return {
        'passed': passed,
        'checked_count': len(records),
        'errors': errors,
        'warnings': warnings
    }
