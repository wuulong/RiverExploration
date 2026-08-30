# WRA-Civ meta_data JSON 規格說明書 (Spec v1.0)

*   **欄位名稱**：`meta_data`
*   **資料類型**：JSON 字串（預設空物件 `{}`）
*   **用途**：儲存水脈實體之可追溯性連結 (Provenance URLs)、GIS 空間延伸資訊、跨系統對照 ID 與維護紀錄。

---

## 1. JSON 欄位結構規格 (Schema Specification)

`meta_data` 物件預設支援以下 **4 大類、8 個標準 Key**：

```json
{
  "source_links": {
    "wiki_url": "https://zh.wikipedia.org/wiki/%E6%B7%A1%E6%B0%B4%E6%B2%B3",
    "osm_url": "https://www.openstreetmap.org/way/25887259"
  },
  "gis_attributes": {
    "osm_way_id": 25887259,
    "osm_relation_id": null,
    "confluence_coords": [121.4332, 25.1764]
  },
  "cross_ref": {
    "wikidata_id": "Q2420747",
    "alt_names": ["淡江", "Tamsui River"]
  },
  "provenance": {
    "cache_folder": "114000_淡水河",
    "last_parsed_at": "2026-08-30T08:00:00Z"
  }
}
```

---

## 2. 欄位明細說明 (Key Definitions)

### 🔹 1. `source_links` (來源網址對照)
* **`wiki_url`** (`string | null`)：該條河流對應的中文維基百科條目網址。
* **`osm_url`** (`string | null`)：OpenStreetMap 實體線條/節點網址（格式：`https://www.openstreetmap.org/way/{id}` 或座標定位網址）。
* **`wra_code_url`** (`string | null`)：經濟部水利署開放資料集對應記錄網址。

### 🔹 2. `gis_attributes` (GIS 空間延伸屬性)
* **`osm_way_id`** (`integer | null`)：OpenStreetMap 中的實體 `way` 唯一識別碼（例：`25887259`）。
* **`osm_relation_id`** (`integer | null`)：若屬大型水系 Relation，留存其 `relation` 識別碼。
* **`confluence_coords`** (`array[float] | null`)：匯流口經緯度陣列 `[lon, lat]`。

### 🔹 3. `cross_ref` (跨系統對號碼與別名)
* **`wikidata_id`** (`string | null`)：Wikidata 全球實體 ID（例：`Q2420747`）。
* **`alt_names`** (`array[string]`)：歷史別名、原住民語名稱或英文名稱（例：`["淡江", "Tamsui River"]`）。

### 🔹 4. `provenance` (修復與快取履歷)
* **`cache_folder`** (`string`)：專書快取目錄對應名稱（例：`114000_淡水河`）。
* **`last_parsed_at`** (`string`)：最後一次發動 Agentic AI 解析與修復的 ISO 8601 時間戳記。

---

## 3. CLI 工具讀寫相容性

`river_cli.py` 在輸出 `export -f json` 或 `export -f geojson` 時，會自動將 `meta_data` 字串解析為 JSON 物件，讓前端 Web 地圖、QGIS 外掛或 LLM Agent 能夠零摩擦直接取用連結與別名。
