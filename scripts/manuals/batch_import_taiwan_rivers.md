# batch_import_taiwan_rivers.py 使用手冊 (CGS v2.0)

*   **腳本位置**：`scripts/batch_import_taiwan_rivers.py`
*   **版本**：v2.0.0
*   **規格規範**：CLI Governance Spec (CGS v2.0) & Disk Caching Spec (v1.0)

---

## 1. 工具簡介與核心職責

`batch_import_taiwan_rivers.py` 是全台灣 **150 條主流水系之批次兩階段快取建置引擎**。

它負責從水利署開放資料庫中萃取 150 條主流名單，並發動以下自動化流程：

1. **第一階段（Wiki 文字抓取）**：呼叫 MediaWiki API 抓取條目全頁內文（排除 `exintro` 限制），自動留存為 `01_raw_wiki.txt`。
2. **第二階段（Gemini 2.5 Flash API 樹狀解析）**：將 Wiki 文本送入 Gemini REST API，萃取出縮排層級支流 JSON，留存為 `02_llm_tree.json`。
3. **終端機動態進度條**：實時顯示當前處理筆數、百分比與水系名稱。
4. **0-Token 斷點續傳**：已完成快取的河流自動跳過，不重複消耗 API Token。

---

## 2. 命令列參數與用法 (CLI Interface)

```bash
# 預設執行：對 150 條水系建立全量快取 (已存在者自動跳過)
python3 scripts/batch_import_taiwan_rivers.py

# 強制重新抓取 Wiki 文本 (忽略既有 01_raw_wiki.txt)
python3 scripts/batch_import_taiwan_rivers.py --refresh-wiki

# 強制重新呼叫 LLM 解析支流樹 (忽略既有 02_llm_tree.json)
python3 scripts/batch_import_taiwan_rivers.py --refresh-llm

# 檢視工具版本資訊
python3 scripts/batch_import_taiwan_rivers.py --version
```

---

## 3. 快取輸出目錄結構

所有產物統一儲存於 `cache/rivers/` 目錄：

```text
cache/rivers/130000_頭前溪/
├── 01_raw_wiki.txt      # 原始維基百科完整文本
└── 02_llm_tree.json     # LLM 萃取之相對縮排支流樹
```
