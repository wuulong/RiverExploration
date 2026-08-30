# import_all_cached_rivers.py 使用手冊 (CGS v2.0)

*   **腳本位置**：`scripts/import_all_cached_rivers.py`
*   **版本**：v2.0.0
*   **規格規範**：CLI Governance Spec (CGS v2.0) & Topology Alignment Spec (v1.0)

---

## 1. 工具簡介與核心職責

`import_all_cached_rivers.py` 是 WRA-Civ 水文拓樸架構中的 **「全量快取無損對照整合與大一統註冊表寫入引擎」**。

它負責讀取專書與系統快取目錄（`cache/rivers/`）下全台灣 **150 條主流水系** 的兩階段快取檔（`02_llm_tree.json`, `03_osm_raw.json`, `metadata.json`），自動執行以下硬性運算：

1. **水利署 837 筆官方庫硬性對對照整合**：優先強制綁定官方權威 6 碼（如 `130000` 頭前溪、`256000` 蘭陽溪、`256040` 粗坑溪），確保 0 幻覺。
2. **民間延伸編碼派發**：無官方編碼之野溪/溪谷，依據親緣樹 Stack 自動遞迴派發 `-C[nn]` 號碼。
3. **Rich Attributes 17 欄位全量寫入**：計算動態 `stream_order`（1~8 階），填補 `source_type` (`WRA`, `Wiki`, `Verified_Both`)、`waterway_type` 與經緯度座標。
4. **大一統 CSV 寫入**：無損更新並寫入 `taiwan_river_topology_registry.csv` 註冊表。

---

## 2. 命令列參數與用法 (CLI Interface)

遵循 CGS v2.0 規範，提供極簡 CLI 選項：

```bash
# 預設執行：讀取快取並寫入預設專書 CSV 註冊表
python3 scripts/import_all_cached_rivers.py

# 指定自訂 CSV 輸出路徑
python3 scripts/import_all_cached_rivers.py --csv custom_registry.csv

# 檢視工具版本資訊
python3 scripts/import_all_cached_rivers.py --version
```

### 常用 Flags 說明：
* `--csv <路徑>`：指定目標 CSV 註冊表路徑（預設：`taiwan_river_topology_registry.csv`）。
* `-h, --help`：顯示完整 Help 說明選單。

---

## 3. 輸入與輸出檔案結構

### 輸入資產 (Inputs)：
1. **快取目錄**：`cache/rivers/` (包含 150 個水系資料夾)
   * `02_llm_tree.json`：LLM 解析之相對縮排支流樹
   * `03_osm_raw.json`：Overpass QL 抓取之 OSM 幾何水線
   * `metadata.json`：審計人員與 Agentic AI 之判決與修復履歷
2. **水利署開放資料庫**：`wra_official_river_codes.json` (837 筆權威紀錄)

### 輸出資產 (Outputs)：
* **大一統 CSV 註冊表**：`taiwan_river_topology_registry.csv` (全量 998 筆拓樸水脈)

---

## 4. 異常排查與除錯 SOP

1. **若某水系筆數與預期不符**：
   請開啟專書快取目錄 `cache/rivers/[河川編號]_[水系名]/`，檢查 `02_llm_tree.json` 中的 `level` 縮排層級是否正確。
2. **若官方程式碼未正確綁定**：
   請確認該水系名稱是否精準出現在水利署開放資料集 `wra_official_river_codes.json` 的 `basinname` 或 `subsidiarybasinname` 欄位中。
