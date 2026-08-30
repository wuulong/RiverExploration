# audit_and_repair_river_cache.py 使用手冊 (CGS v2.0)

*   **腳本位置**：`scripts/audit_and_repair_river_cache.py`
*   **版本**：v2.0.0
*   **規格規範**：CLI Governance Spec (CGS v2.0) & Cache Governance Spec (v1.1)

---

## 1. 工具簡介與核心職責

`audit_and_repair_river_cache.py` 是全台 150 條水系快取資料庫之 **「精準健檢、瑕疵排查與標靶修復工具」**。

它能防範整個快取庫因為少數幾條河流的 Wiki 空白或 LLM Timeout 影響全盤資料品質：

1. **`audit` 命令（零風險審計）**：全自動掃描 150 條快取資料夾，讀取 `metadata.json` 履歷，劃分為「健康正常」、「Wiki 0 bytes」與「LLM Timeout 失敗」，僅輸出健檢報告，絕不修改硬碟內容。
2. **`repair` 命令（標靶修復）**：僅針對審計出的瑕疵標靶河流發動修復：
   * **Wiki 多重備選名稱搜尋**：自動嘗試副名/簡稱（例：`將軍溪排水(將軍溪)` ➔ 搜尋 `將軍溪`），若無條目則自動發動 Wikipedia Search API（例：`八蓮溪` ➔ 自動匹配 `八連溪 (三芝區)`）。
   * **LLM 重試機制**：帶有 3 次 Retry 機制與自動冷卻，解決 Network Timeout。
   * **實時終端機進度條**：顯示河川 6 碼程式碼、水系名稱與修復筆數。
   * **100% 斷點續傳**：修復成功者自動注入 `metadata.json`，再次執行自動跳過。

---

## 2. 命令列參數與用法 (CLI Interface)

```bash
# 1. 執行快取健康審計 (僅輸出報告，不改動資料)
python3 scripts/audit_and_repair_river_cache.py audit

# 2. 發動標靶修復 (僅修正瑕疵水系，100% 續傳)
python3 scripts/audit_and_repair_river_cache.py repair

# 檢視工具版本資訊
python3 scripts/audit_and_repair_river_cache.py --version
```

---

## 3. 審計與修復狀態判定表

| 狀態類別 | 判定條件 | 處置方式 |
| :--- | :--- | :--- |
| **健康正常 (Healthy)** | `metadata.json` 已審定 或 `01_raw_wiki.txt` > 0 且 `02_llm_tree.json` 完整 | 保留，100% 不重複處理 |
| **Wiki 空檔案 (Zero Wiki)** | `01_raw_wiki.txt` 不存在或長度為 0 | 發動多重備選名稱與 Search API 重抓 |
| **LLM 失敗 (LLM Timeout)** | Wiki 有文字但 `02_llm_tree.json` 只有 1 筆主流 | 發動 Gemini API 3-Retry 重試 |
