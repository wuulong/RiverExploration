## 2.5 [v2.0 增補] 實戰應用：引入與使用「台灣歷史地圖資料庫」(taiwan-history-atlas)

理解了 Layer 0-1-2 的方法論後，本節將帶領你直接進入實戰。我們將介紹如何下載與使用目前最具代表性的開源專案：**「台灣歷史地圖資料庫」(taiwan-history-atlas)**。這個專案不僅包含了《臺灣通史》的全文，更有數千筆已經結構化的地理實體與 AI 合成的知識洞察。

### 1. 獲取資源與環境準備

該專案已在 GitHub 公開，你只需要獲取其中的核心資料庫檔案即可開始：
*   **專案位址**：`https://github.com/wuulong/taiwan-history-atlas`
*   **核心檔案**：`data/taiwan_history.db` (這是一個 SQLite 檔案，可直接用 DB Browser for SQLite 或 Python 開啟)。

### 2. 資料庫核心表結構 (Tables) 解析

當你開啟資料庫，會看到以下關鍵表格，它們分別對應了不同的知識層級：

| 表格名稱 | 所屬層級 | 內容說明 |
| :--- | :--- | :--- |
| `volumes` / `contents` | **Layer 0** | 包含《臺灣通史》37 卷全文，支援 FTS5 全文檢索（`content_fts`）。 |
| `entities` | **Layer 1** | 已標註類型的實體（如 `Irrigation`, `Location`, `Person`）。包含 JSON 格式的元資料。 |
| `mentions` | **Layer 1** | 每個實體在原文中出現的**具體段落 (Snippet)**。這是「有圖有真相」的關鍵。 |
| `ai_knowledge_atlas` | **Layer 2** | AI 合成的專題模型。其中 `Toponym_Ref` 分項是 HGIS 空間對比的聖經。 |
| `moi_settlements` | **Layer 1.5** | 整合自內政部的 37,000+ 筆古地名點位，提供經緯度座標。 |

### 3. 三個經典的查詢範例 (SQL)

不需要會寫複雜程式，透過簡單的 SQL 指令，你就能瞬間從幾十萬字史料中萃取流域地圖所需的資訊：

#### **案例 A：尋找特定河流的所有卷次記載**
```sql
SELECT volume_title, snippet 
FROM mentions 
WHERE snippet LIKE '%二層行%';
```
這能讓你看到「二仁溪 (古稱二層行)」在《疆域志》、《軍備志》中所有的出沒紀錄。

#### **案例 B：撈取流域內的開發實體 (埤圳群)**
```sql
SELECT name, meta_data 
FROM entities 
WHERE type = 'Irrigation' AND meta_data LIKE '%彰化%';
```
你可以瞬間撈出該地區在清代的所有水利設施 DNA。

#### **案例 C：古今地名座標聯動**
```sql
SELECT name, lat, lon 
FROM moi_settlements 
WHERE name LIKE '%蘇厝%';
```
這是將書本中的「蘇厝」文字，轉化為地圖上「座標點」的最後一里路。

---

### 4. 與 AI 協作的高階操作

如果你使用的是具備資料庫操作能力的 AI 助理（如 Antigravity），你可以直接下指令，讓它替你「閱讀資料庫」：

> **最佳實踐指令 (Prompt)**：
> 「請查詢 `taiwan_history.db` 中的 `ai_knowledge_atlas` 表。找出關於『曾文溪水利開發』的 Layer 2 總結，並隨後下鑽到 `mentions` 表，找出 3 個最能展現其『改道歷史』的原文摘要。」

### 結語：從「閱讀者」變身「資料建築師」

引入 `taiwan-history-atlas` 之後，你的河流探索將不再是從零開始的採集，而是站在前人的肩膀上進行「二次開發」。你所產出的每一份田野紀錄，都將與這套龐大的島嶼知識底盤產生動態連結。

下一章，我們將暫時合上書本與資料庫，開啟地理資訊系統（GIS），學習如何將這些萃取出的座標與歷史，疊合在真正的「時空地圖」上。
