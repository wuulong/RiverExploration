# 《流域導航》v2.1 實作計畫與進度日誌 (Implementation Plan & Log)

## 1. 實作計畫 (Implementation Plan)

### PHASE 1: 目錄與架構調整 (Total Alignment)
- [x] **1.1 更新 `toc.md`**：將 v2.1 提案中的新章節（2.6, 5.5, 10.4, 13）正式納入目錄架構。
- [x] **1.2 更新 `VERSION.md`**：記錄 v2.1 的變更摘要。

### PHASE 2: 核心方法論撰寫 (Core Methodology)
- [x] **2.1 第 5.5 章撰寫**：建立 Layer 3 演義法則，包含能源平衡與決策模擬邏輯。
- [x] **2.2 整合南科案例**：將 `CaseStudy_Nanke_L3_Simulation.md` 轉化為書中教學內容。
- [x] **2.3 空間分析範例撰寫**：於 5.5 章加入「離河距離 (HRD) 聚類分析圖」與「高程位能模型」的視覺化案例，解釋其對生存劇本的支撐。

### PHASE 3: 遺跡資料庫 (Relic DB) 整合
- [x] **3.1 遺跡標級化實作**：定義 Rank 1-3 遺跡並建立與 HGIS 的對合規範。（已於 Ch 2.6 中詳述規範）
- [x] **3.2 資料結構與 `taiwan-history-atlas` 對合**：落實 `relic_master` 中 `for_ai` 與 `meta_data` 欄位的應用說明。
- [x] **3.3 一鍵產製 QGIS 專案**：將專用 SQL 查詢與 `.qgs` 渲染範本寫入附錄。（已於 Ch 10.4 說明流程並指向附錄集）
- [x] **3.4 Sidecars 規範建立**：落實 Markdown 與 DB 勾稽的技術細節說明。
- [x] **3.5 空間分析代碼與 SOP**：提供產出上述分析範例的 Python/SQL 範本，確保讀者可重製。

---

## 2. 進度日誌 (Implementation Log)

| 日期 | 進度描述 | 產出/狀態 |
| :--- | :--- | :--- |
| 2026-03-09 | 初始化 v2.1 改寫任務，建立提案、南科案例，並完成 Ch 2.6, 5.4, 5.5, 10.4, 13 之撰寫。 | `upgrade_proposal_v2.1.md`, `Chapter_2_6.md`, `Chapter_5_4.md`, `Chapter_5_5.md`, `Chapter_10_4.md`, `Chapter_13.md` |

---
*Created as part of RiverExploration v2.1 Project Management*
