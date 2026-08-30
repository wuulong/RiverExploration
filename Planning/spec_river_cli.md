# WRA-Civ 水文拓樸靈活查詢與多格式轉換 CLI 工具設計規格 (spec_functional.md)

*   **工具名稱**：`river_cli.py` (或透過 `./pa river` 進入)
*   **定位**：專用水文拓樸探索、模糊查詢、階層過濾與多格式 (CSV, JSON, GeoJSON, KML, Mermaid, Tree) 轉換 CLI 工具。
*   **遵循規範**：CLI Governance Spec (CGS v2.0)

---

## 1. 核心需求與設計理念

整理資料庫是一回事，**隨心所欲地「查詢與轉換資料」是另一回事**！
使用者需要一個極速、直覺且多功能的 CLI，能做到：

1. **想查什麼就查什麼 (Flexible Query & Search)**：
   * **模糊搜尋 (`search`)**：輸入「頭前」、「油羅」、「霞喀羅」或程式碼 `130020`，秒級比對名稱、程式碼、描述與 Wikidata ID。
   * **水系/流域查詢 (`basin`)**：指定流域（如「淡水河」、「頭前溪」、「卑南溪」），一鍵看全水系。
   * **階層過濾 (`filter`)**：可依 `stream_order`（預設過濾野溪）、`is_civilian`（僅看官方或民間）、`has_osm_geo`（僅看有 GPS 座標者）、`source_type` 自由組合。
   * **樹狀與上下游追溯 (`tree` / `trace`)**：指定任意河段，向上追溯源頭或向下追溯至出海口。

2. **格式怎麼轉都方便 (Multi-Format Exporters)**：
   * 📊 **CSV / TSV**：經典表格，支援特定欄位挑選。
   * 🤖 **JSON / JSONL**：極速 API/LLM 結構（支援 Positional Array 陣列或 Dictionary 物件）。
   * 🗺️ **GeoJSON / KML**：地理空間圖資格式，直接匯入 QGIS、Google Earth 或 WalkGIS 地圖！
   * 🎨 **Mermaid**：高對比雙色關係圖（直接貼入 Markdown / Mermaid Live Editor）。
   * 🌳 **Text Tree (樹狀圖)**：終端機彩色美麗文字樹（如 `tree` 命令）。

---

## 2. CLI 命令列結構設計 (Command Blueprint)

```bash
python3 scripts/river_cli.py <subcommand> [options]
```

### 🔹 子命令 1: `query` 或 `search`（多維度靈活查詢）
```bash
# 1. 模糊搜尋「霞喀羅」
python3 scripts/river_cli.py search "霞喀羅"

# 2. 查詢「頭前溪」水系中 stream_order <= 2 的一級支流
python3 scripts/river_cli.py search -b "頭前溪" --max-order 2

# 3. 尋找全台有經緯度座標的官方河流
python3 scripts/river_topology_importer.py search --official-only --geo-only
```

### 🔹 子命令 2: `export` 或 `convert`（多格式一鍵轉譯）
```bash
# 導出為 GeoJSON (供 QGIS / 導航 App 直接載入)
python3 scripts/river_cli.py export -b "頭前溪" -f geojson -o touqian.geojson

# 導出為 KML (供 Google Earth / 登山 Garmin 檢視)
python3 scripts/river_cli.py export -b "淡水河" -f kml -o tamsui.kml

# 導出為文字樹狀圖 (終端機直接看關係)
python3 scripts/river_cli.py export -b "頭前溪" -f tree

# 導出高對比黑夜模式 Mermaid
python3 scripts/river_cli.py export -b "頭前溪" -f mermaid
```

### 🔹 子命令 3: `trace`（上下游拓樸追溯）
```bash
# 追溯 130020 (油羅溪) 一路回溯到出海口的所有親緣幹流
python3 scripts/river_cli.py trace 130020 --direction down

# 追溯 130000 (頭前溪) 向上發散的所有子孫支流
python3 scripts/river_cli.py trace 130000 --direction up
```

---

## 3. CLI 參數設計對照表 (Flags Summary)

| Flag | 長名稱 | 描述 |
| :--- | :--- | :--- |
| `-b` | `--basin` | 指定水系/流域名稱（例：`頭前溪`） |
| `-f` | `--format` | 輸出格式：`csv`, `json`, `jsonl`, `geojson`, `kml`, `mermaid`, `tree` |
| `-n` | `--max-order` | 限制最大拓樸階層感（預設不限，`2` 代表僅保留主流與一級大支流） |
| `-g` | `--geo-only` | 僅篩選具備 GPS 經緯度座標之河流 |
| `--official-only` | `--official-only` | 僅篩選水利署官方 6 碼河流 (`is_civilian=0`) |
| `--civ-only` | `--civ-only` | 僅篩選民間延伸下鑽野溪 (`is_civilian=1`) |
| `-o` | `--output` | 輸出檔案路徑（若不指定則直接輸出至 stdout 標準輸出） |
