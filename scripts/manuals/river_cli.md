# river_cli.py 使用手冊 (CGS v2.0)

*   **腳本位置**：`scripts/river_cli.py`
*   **版本**：v2.0.0
*   **規格規範**：CLI Governance Spec (CGS v2.0) & WRA-Civ Topology Spec (v1.0)

---

## 1. 工具簡介與核心職責

`river_cli.py` 是專為探索者、GIS 分析師與 AI Agent 設計的 **全台水文拓樸萬用查詢與多格式轉譯工具**。

整理資料庫是一回事，**隨心所欲地「查詢與轉換資料」是另一回事**！`river_cli.py` 解決了傳統 CSV 難以直觀閱讀、追溯親緣與轉譯地圖資產的痛點，提供以下核心能力：

1. **多維度模糊查詢 (Search / Query)**：關鍵字比對名稱、程式碼、描述；可組合流域名稱、官方/民間屬性、GPS 座標有無與 Stream Order 階層。
2. **親緣鏈雙向追溯 (Trace)**：指定任意河段，一鍵「向上回溯至出海口主流」或「向下散發所有子孫溪流」。
3. **7 大格式一鍵轉譯 (Multi-Format Export)**：
   * 🌳 `tree`：終端機彩色文字樹。
   * 🗺️ `geojson`：空間點/線資產（供 QGIS / 導航 App 開啟）。
   * 🗺️ `kml`：三維圖資（供 Google Earth / 登山 Garmin 檢視）。
   * 🎨 `mermaid`：黑夜模式高對比雙色關係圖。
   * 📊 `csv` / 🤖 `json` / `jsonl`：極速 API 與資料處理格式。

---

## 2. 命令列參數與使用 SOP (CLI Interface)

### 🔹 1. 關鍵字模糊搜尋與文字樹
```bash
# 搜尋名稱包含「霞喀羅」的河流
python3 scripts/river_cli.py search "霞喀羅"

# 查詢「頭前溪」水系中 stream_order <= 2 的主流與一級大支流 (文字樹)
python3 scripts/river_cli.py search -b "頭前溪" -n 2
```

### 🔹 2. 上下游拓樸親緣追溯
```bash
# 追溯「油羅溪 (130020)」一路回溯至出海口的主流親緣鏈
python3 scripts/river_cli.py trace 130020 --direction up

# 追溯「頭前溪 (130000)」向下擴展的所有子孫支流
python3 scripts/river_cli.py trace 130000 --direction down
```

### 🔹 3. 多格式一鍵轉譯與檔案匯出
```bash
# 轉譯「頭前溪」為 GeoJSON 空間圖資檔 (供 QGIS 直接開啟)
python3 scripts/river_cli.py export -b "頭前溪" -f geojson -o touqian.geojson

# 轉譯「淡水河」為 KML 檔 (供 Google Earth 載入)
python3 scripts/river_cli.py export -b "淡水河" -f kml -o tamsui.kml

# 轉譯「頭前溪」為高對比雙色 Mermaid 圖 (直接貼入 Markdown)
python3 scripts/river_cli.py export -b "頭前溪" -f mermaid
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
