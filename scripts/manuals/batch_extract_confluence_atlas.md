# 全台 150 水系實體水網幾何匯流點全量分析腳本使用說明書 (Spec v1.0)

`batch_extract_confluence_atlas.py` 是一隻符合 **CLI Governance Spec (CGS) v2.0** 規範的幾何運算腳本。它透過 OpenStreetMap Overpass API 抓取實體水脈折線與 Node ID，全自動計算全台 2,132 筆水脈之 **實體匯流點 GPS (Confluence Coords)**、**OSM 共享交點 ID (Confluence Node ID)**、**幾何線條長度 (estimated_length_km)** 與 **交點品質標籤 (confluence_type)**。

---

## 🛠️ CLI 常用命令與用法 (Usage)

所有指令必須使用指定 Python 環境執行：
```bash
/Users/wuulong/opt/anaconda3/envs/m2504/bin/python events/AIBooks/RiverExploration/scripts/batch_extract_confluence_atlas.py [FLAGS]
```

### 1. 📊 查詢目前計算進度與狀態 (Status)
```bash
./bin/py events/AIBooks/RiverExploration/scripts/batch_extract_confluence_atlas.py --status
```
* **效果**：印出目前已計算的水脈數量、100% 共享 Node 數量、端點匹配數量與出海口統計。

---

### 2. 🚀 發動全量計算與中斷點續做 (Run & Resume)
```bash
./bin/py events/AIBooks/RiverExploration/scripts/batch_extract_confluence_atlas.py --resume
```
* **效果**：
  * 每計算完一個水系，即時存入 `cache/confluence_atlas.json`。
  * 中途若按 `Ctrl+C` 中斷，再次執行此命令會**自動跳過已處理過的水系，從中斷處無縫續做**！

---

### 3. 📄 產出檔案位置
計算完成後，完全不影響原有的 CSV 註冊表，全量結構化資料會獨立落庫於：
👉 [`events/AIBooks/RiverExploration/cache/confluence_atlas.json`](file:///Users/wuulong/github/bmad-pa/events/AIBooks/RiverExploration/cache/confluence_atlas.json)
