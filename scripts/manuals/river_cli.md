# river_cli.py 使用手冊 (專書 v2.4 / CGS v2.0)

*   **腳本位置**：`scripts/river_cli.py`
*   **專書對齊版本**：v2.4 (3D Hydrological Elevation & AI-Native JSONL Migration)
*   **規格規範**：CLI Governance Spec (CGS v2.0) & AI-Native JSONL Spec (v2.4)

---

## 1. 工具簡介與核心職責

`river_cli.py` 是專為探索者、GIS 分析師與 AI Agent 設計的 **全台水文拓樸 3D 萬用查詢與多格式轉譯工具**。

專書升級至 v2.4 後，`river_cli.py` 預設直接讀取 Master 資料庫 `taiwan_river_topology_registry.jsonl`，全面解鎖 3D 海拔地形降落分析與多維權威外鏈，提供以下 5 大核心能力：

1. **⛰️ 3D 海拔縱剖面與降落圖 (Profile)**：直接在終端機繪製水系主流與支流的 3D 海拔 ASCII 降落趨勢圖。
2. **🔗 權威外鏈面板 (Links)**：結構化查詢並顯示特定水脈的 Wikipedia、OSM、WalkGIS 與 Wikidata 跨庫識別連結。
3. **🌲 豐富 3D 彩色文字樹 (Tree)**：樹狀圖除呈現官方/民間屬性與階層外，更自動帶入 **3D 海拔高度 (`⛰️ 150m`)** 與 **📍 OSM 幾何交點品質標籤**。
4. **🗺️ 3D 空間幾何轉譯 (3D GeoJSON / 3D KML)**：匯出包含 `[lon, lat, elevation_m]` 3D Z軸座標，供 Google Earth 3D 擬真與 QGIS 透視。
5. **親緣鏈雙向追溯 (Trace)**：指定任意河段，一鍵「向上回溯至出海口主流」或「向下散發所有子孫溪流」。

---

## 2. 命令列參數與使用 SOP (CLI Interface)

### 🔹 1. 3D 海拔縱剖面分析 (Profile)
```bash
# 繪製「頭前溪」水系的 3D 海拔降落趨勢圖
python3 scripts/river_cli.py profile 頭前溪
```

### 🔹 2. 查詢水脈權威外鏈 (Links)
```bash
# 查詢「桶後溪」的 Wikipedia, OSM, WalkGIS 與 Wikidata 面板
python3 scripts/river_cli.py links 桶後溪
```

### 🔹 3. 關鍵字搜尋與 3D 彩色文字樹 (Search)
```bash
# 搜尋「王爺坑溪」並列出帶有高程與幾何品質標籤的家族樹
python3 scripts/river_cli.py search 王爺坑溪

# 查詢「頭前溪」水系中 stream_order <= 2 的主流與一級大支流
python3 scripts/river_cli.py search -b "頭前溪" -n 2
```

### 🔹 4. 上下游拓樸親緣追溯 (Trace)
```bash
# 追溯「油羅溪 (130020)」一路回溯至出海口的主流親緣鏈
python3 scripts/river_cli.py trace 130020 --direction up

# 追溯「頭前溪 (130000)」向下擴展的所有子孫支流
python3 scripts/river_cli.py trace 130000 --direction down
```

### 🔹 5. 3D 圖資導出 (3D GeoJSON / 3D KML / Mermaid)
```bash
# 導出頭前溪 3D GeoJSON (包含 Z 軸高程)
python3 scripts/river_cli.py search -b "頭前溪" -f geojson -o touqian_3d.geojson

# 導出淡水河 3D KML (供 Google Earth 3D 檢視)
python3 scripts/river_cli.py search -b "淡水河" -f kml -o tamsui_3d.kml

# 轉譯頭前溪為黑夜模式 Mermaid 關係圖
python3 scripts/river_cli.py search -b "頭前溪" -f mermaid
```

---

## 3. CLI 參數對照表 (Flags Reference)

| Flag | 長名稱 | 預設值 | 說明 |
| :--- | :--- | :--- | :--- |
| `-b` | `--basin` | `None` | 指定水系/流域名稱（例：`頭前溪`、`淡水河`） |
| `-n` | `--max-order` | `None` | 限制最大拓樸階層感（例：`2` 僅保留主流與一級大支流） |
| `-g` | `--geo-only` | `False` | 僅篩選具備 GPS 經緯度座標之河流 |
| `--official-only` | `--official-only` | `False` | 僅篩選水利署官方 6 碼河流 (`is_civilian=0`) |
| `--civ-only` | `--civ-only` | `False` | 僅篩選民間延伸野溪 (`is_civilian=1`) |
| `-f` | `--format` | `tree` | 輸出格式：`tree`, `csv`, `json`, `jsonl`, `geojson`, `kml`, `mermaid` |
| `-o` | `--output` | `stdout` | 指定輸出檔案路徑 (不指定則輸出於終端機) |
| `--direction` | `--direction` | `down` | 追溯方向：`up` 向上追出海口, `down` 向下散發支流 |
