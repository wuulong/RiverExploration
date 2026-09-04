# 版本歷史

## v2.5 (Hierarchical Directory Tree Export & Right-Bank Border Arbitration) - 2026-09-04
*   **核心升級**：全台 1,403 個「縣市 ➔ 獨立水系 ➔ 支流親緣樹」實體目錄構造匯出（`data/river_tree/`）、右岸界河優先仲裁與 100% 縣市四階歸屬推導機制上線、水脈檔名極致淨化與備註/異名完整 `attribute_json` 落庫。
*   **方法論與技術進展**：
    *   **100% 全台縣市歸屬 (0 筆未定縣市)**：開發全台主流四階歸屬仲裁機制（Tier 1 右岸出海口界河仲裁 ➔ Tier 2 GPS 空間疊合與河川分署邊界防護 ➔ Tier 3 地名語意萃取 ➔ Tier 4 親緣樹繼承與分署 fallback），成功將全台 172 條獨立主流 100% 歸類至 16 個縣市目錄下。
    *   **實體樹狀目錄導出 (`data/river_tree/`)**：`river_cli.py export-dirs` 支援批次構建 1,403 個親緣樹目錄與 `record.json` 共用記憶體檔案。
    *   **極致檔名淨化規範**：全量掃描並剔除 59 筆水脈名稱中含有之括號、俗稱、異名與維基結構雜訊節點，保持資料庫與目錄名稱絕對簡明，原始備註與疑慮完備保留於 `attribute_json.raw_river_name` 中。
*   **專書與工具歸檔**：
    *   `scripts/convert_topology_to_jsonl.py` (v2.5)
    *   `scripts/river_cli.py` (v2.5)
    *   `data/river_tree/` 實體親緣目錄與萬用註冊庫 `taiwan_river_topology_registry.jsonl`

---

## v2.4 (3D Hydrological Elevation & AI-Native JSONL Migration) - 2026-08-30
*   **核心升級**：全台 1,418 條水脈 3D 水理拓樸大一統、AI-Native JSONL 雙軌格式上線、354 筆實體 3D 海拔高程與幾何厚化、全套 CGS v2.4/v2.0 腳本與手冊對齊釋出。
*   **方法論與技術進展**：
    *   全面升級專書資料庫至 **`taiwan_river_topology_registry.jsonl` (v2.4)**，並實裝方案 A（JSONL 為 Master，衍生唯讀相容 CSV 檔）。
    *   全量注入 354 筆實體經緯度、OSM 交點品質 (`OSM_Shared_Node` / 幾何吸附) 與 3D 海拔高程，整合 `links` 與 `plugins` 擴充架構。
    *   全套 CLI 工具版號對齊升級至 v2.4 / v2.0，並實裝 `--offline` 硬性離線防護模式，實現 0 秒秒讀與零對外連線風險。
*   **專書與工具歸檔**：
    *   `scripts/batch_extract_confluence_atlas.py` (v2.4)
    *   `scripts/convert_topology_to_jsonl.py` (v2.4)
    *   `scripts/elevation_hydrator.py` (v2.4)
    *   `scripts/manuals/batch_extract_confluence_atlas.md` 與 `scripts/manuals/elevation_hydrator.md`

---

## v2.3 (Taiwan-Wide All 150 Basins & Universal CLI Tools Alignment) - 2026-08-30
*   **核心升級**：全台灣 150 條主流水系大一統、全新萬用拓樸 CLI 工具 (`river_cli.py`) 釋出與 OpenStreetMap 物理水網對照整合。
*   **方法論與技術進展**：
    *   從原本 26 大中央管水系全面擴充為 **150 條全台獨立入海水系**，達成 **998 筆拓樸水脈全量落庫** (`taiwan_river_topology_registry.csv`)。
    *   進行 **全台主流基石校正體檢**：修正 18 筆獨立主流 Parent/Order 錯置，硬性對齊水利署 837 筆官方權威開放資料集 (`wra_official_river_codes.json`)。
    *   導入 **OpenStreetMap (OSM) 物理水網**，補齊實體幾何經緯度與 `Verified_Both` 雙重認證標籤。
    *   標準化 **17 個 Rich Attributes 欄位**（`source_type`, `waterway_type`, `stream_order`, `has_osm_geo`）。
    *   確立 **快取目錄持久化治理哲學 (`cache/rivers/`)**：留存 01 Wiki 原始檔、02 LLM 支流樹、03 OSM 幾何與 `metadata.json` 修復履歷。
    *   升級 **黑夜模式 (Dark Mode) 高對比雙色 Mermaid 拓樸圖**。
*   **專書與工具歸檔**：
    *   全新推出並歸檔 **萬用水文拓樸 CLI 工具 [`scripts/river_cli.py`](scripts/river_cli.py)**（支援多維度模糊搜尋、上下游雙向追溯、終端機彩色文字樹，以及 GeoJSON/KML/Mermaid 等 7 大格式一鍵轉譯）與說明書 [`scripts/manuals/river_cli.md`](scripts/manuals/river_cli.md)。
    *   新增 **Chapter 11.6** 記錄全台 150 水系大一統全景、`river_cli.py` SOP、OSM 整合與快取治理機制。
    *   專書自包含歸檔 `scripts/river_topology_importer.py`, `scripts/batch_import_taiwan_rivers.py`, `scripts/audit_and_repair_river_cache.py`, `scripts/import_all_cached_rivers.py` 等全套 CGS v2.0 治理工具。

---

## v2.2 (WRA-Civ Grand Topology & Zero-Hallucination Pipeline) - 2026-08-29
*   **核心升級**：全台灣四大水資源區 (北/中/南/東) WRA-Civ 水文拓樸大一統。
*   **方法論與技術進展**：
    *   導入 **水利署 110 年全量官方開放資料集 (`wra_official_river_codes.json`)**，達成 837 筆官方權威 6 碼與維基 ID 的 100% 零幻覺對照整合 (is_civilian=0)。
    *   確立 **兩階段 AI-CLI 協作產製 SOP**（LLM 語意理解探勘 ➔ 中間態樹狀 JSON ➔ 確定性程式寫入）。
    *   完成 **573 筆全台水文拓樸實體落庫** (`taiwan_river_topology_registry.csv`)，並通過親緣路徑與唯一性 100% 盲檢驗證。
*   **專書與工具歸檔**：
    *   更新 **Chapter 11.5** 為四大水資源區大一統全景與 Mermaid 雙色拓樸圖。
    *   專書目錄內實體歸檔核心寫入引擎 `scripts/river_topology_importer.py` 及真實 JSON 範本 `templates/touqian_tree_real.json`。

---

## v2.1 (Relic & Deep-Time Modeling) - 2026-03-09
*   **核心升級**：從「HGIS 對照整合」邁向「跨時空模型化與遺蹟導航」。
*   **方法論增補**：
    *   導入 **OO-History (物件導向歷史)**：建立 Root-Spec-Entity 三層繼承架構，降低考古資料厚化成本。
    *   建立 **Layer 3 演義法則**：引入「生存第一原理」、「能源平衡模型」與「遷徙演演演演演演演演演演演演演演演演演演演演演演演演演演演演演算法」發想生活樣態。
    *   定義 **Layer 4 空間驗證**：利用離河距離 (HRD) 聚類分析與高程位能模型作為物理證據。
*   **章節增改**：
    *   新增 2.6 (考古遺跡讀取與 ID 勾稽)、5.4 (OO-History 立論)、5.5 (劇本演義與南科案例)、10.4 (預測-驗證-修正工作流)、13 (未來展望)。
    *   第 5 章架構重整為二階段：數位賦能(現在) vs 深度模型化(跨時空)。
*   **技術整合**：對齊 `taiwan-history-atlas` 之 `relic_master` 資料結構與 `qgis-project-architect` 一鍵產製流程。

---

## [v2.0] - 2026-02-23
### Added
- **Layer 0-1-2 知識工程**：導入流域歷史資料庫 (History DB) 方法論，建立史料、地圖與邏輯模型的數位對照整合架構 (Chapter 2.4, 2.5)。
- **時光羅盤與 HGIS**：新增 1920 空間錨定與座標修正技術，實現「歷史河道顯影」與古圖座標化實務 (Chapter 3.3)。
- **AI Skill 封裝**：導入「技能優先」(Skill-First) 工作流，將研究 SOP 封裝成可復用的 AI 數位裝備 (Chapter 10.3)。
- **厚資料標註實務 (Thick Tagging)**：最佳化 WalkGIS 標註邏輯，將現場「驚訝 (M::)」轉化為具備脈絡的研究素材 (Chapter 11.4)。
- **HGIS 數位工具箱**：新增附錄 B，整合 `hgis-atlas-architect` 核心腳本與 SQL Snippets。

### Changed
- **考證層次升級**：於頭前溪、濁水溪、曾文溪與二仁溪章節，全面導入 [Layer 2 考證] 的邏輯模型與地景敘事。
- **整體架構最佳化**：維持 v1.7 核心，並完成全書 AI 擴增探索工作流之對齊。

---

## [v1.7] - 2026-01-30
### Added
- **知識座標體系**：在 11 條河流章節中補充「博物館與教育園區」清單，強化田野與知識整理的連結。
- **關鍵博物館補充**：新增淡水古蹟博物館、蘭陽博物館、沈默的石岡壩、南科考古館、奇美原住民文物館等 25 處專業解讀節點。

### Changed
- **研究深度強化**：完成 11 條河流深度研究報告（Research/）與實踐指南章節的全面整合。
- **導航框架升級**：統一採用「三維度分析」與「分區水文地景」寫作框架，提升專業分析厚度。
- **全書匯整**：同步更新 `RiverExploration_FullBook.md`。

---

## [v1.6] - 2026-01-22
### Added
- **動態檔案櫃**：導入 `FieldLogs/` 架構，解耦實境紀錄與靜態章節。
- **AI 探索工作流**：新增第 10 章與第 11 章，定義 AI 作為分析師與 WalkGIS 集體共創的流程。

---

## [v1.5] - 2026-01-15
### Changed
- **核心方法論升級**：最佳化第一部分「探索基本功」，加入 GIS 透視眼與田野心法。

---

## [v1.0] - 2026-01-01
### Added
- **初始版本**：建立台灣 11 條主要流域的初步導覽架構。
