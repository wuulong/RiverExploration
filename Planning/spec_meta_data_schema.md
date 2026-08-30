# WRA-Civ JSONL 大一統模組化外掛規格說明書 (Spec v2.0)

*   **資料檔案**：`taiwan_river_topology_registry.jsonl`
*   **格式類型**：JSON Lines（每行代表一條水脈之完整 Native JSON 物件，共 2,132 行）
*   **用途**：作為全台 2,132 筆水脈拓樸之單一真實來源 (Single Source of Truth)，透過 Plugin Namespace 徹底解耦核心親緣、地理 GIS、可追溯網址與水文分析。

---

## 1. 原生 JSONL 結構規格 (Schema Specification v2.0)

每一行 Native JSON 物件包含 **Core 核心屬性**、**Provenance 維護履歷**，以及 **Plugin 模組命名空間 (Namespaces)**：

```json
{
  "river_code": "130020",
  "river_name": "油羅溪",
  "parent_code": "130000",
  "topology_path": "0@130000@130020",
  "stream_order": 2,
  "is_civilian": "0",
  "basin_name": "頭前溪",

  "plugin_links": {
    "wiki_url": "https://zh.wikipedia.org/wiki/%E6%B2%B9%E7%7E%85%E6% stream",
    "osm_url": "https://www.openstreetmap.org/node/3724291408",
    "wra_code_url": "https://data.gov.tw/dataset/25732"
  },

  "plugin_gis": {
    "confluence_id": "J-130020",
    "confluence_coords": [121.24625, 24.73303],
    "confluence_node_id": 3724291408,
    "confluence_type": "OSM_Shared_Node",
    "elevation_m": 441.0,
    "segment_slope_percent": 1.39,
    "estimated_length_km": 26.4
  },

  "plugin_hydrology": {
    "basin_stream_count": 55,
    "direct_tributary_count": 4,
    "bed_material": null,
    "channel_width_type": null,
    "has_upstream_dam": false,
    "risk_level": "Medium"
  },

  "plugin_cross_ref": {
    "wikidata_id": "Q2420747",
    "alt_names": ["Youluo River"]
  },

  "provenance": {
    "contributor": "WRA-Civ-Agent",
    "last_updated": "2026-08-30"
  }
}
```

---

## 2. 模組命名空間說明 (Namespace Definitions)

### 🔹 1. Core (頂層核心親緣)
* **`river_code`** (`string`)：河流唯一識別碼（水利署 6 碼或民間 `-C[nn]` 延伸碼）。
* **`river_name`** (`string`)：河流中文標準名稱。
* **`parent_code`** (`string`)：直屬父層河流代碼（`0` 代表獨立入海主流）。
* **`topology_path`** (`string`)：從出海口到該河流的完整親緣路徑（例：`0@130000@130020`）。
* **`stream_order`** (`integer`)：河川階數 (Stream Order)。
* **`is_civilian`** (`string`)：官方 (`0`) 或民間延伸 (`1`)。
* **`basin_name`** (`string`)：所屬獨立水系名稱。

### 🔹 2. `plugin_links` (來源對照與可追溯網址外掛)
* **`wiki_url`** (`string | null`)：中文維基百科條目網址。
* **`osm_url`** (`string | null`)：OpenStreetMap 實體 Node / Way 直達網址。
* **`wra_code_url`** (`string | null`)：經濟部水利署開放資料對照網址。

### 🔹 3. `plugin_gis` (空間地理與實體匯流點外掛)
* **`confluence_id`** (`string`)：實體匯流點唯一代號（標準：`J-[river_code]`，例 `J-130020`）。
* **`confluence_coords`** (`array[float] | null`)：匯流點經緯度 `[lon, lat]`。
* **`confluence_node_id`** (`integer | null`)：與主流共有之 OSM Node 實體識別碼。
* **`confluence_type`** (`string`)：交點品質標籤（`OSM_Shared_Node` / `Geometric_Endpoint_Match` / `Outfall_Sea`）。
* **`elevation_m`** (`float | null`)：匯流點海拔高度（公尺）。
* **`segment_slope_percent`** (`float | null`)：河段估算坡度百分比 (%)。
* **`estimated_length_km`** (`float`)：OSM 圖資向量折線長度 (km)。

### 🔹 4. `plugin_hydrology` (水理與水性規模外掛)
* **`basin_stream_count`** (`integer`)：所屬水系家族總水脈筆數。
* **`direct_tributary_count`** (`integer`)：直屬子支流數量（水系樞紐度 Hub Degree）。
* **`has_upstream_dam`** (`boolean`)：上游是否有水庫/攔河堰。
* **`risk_level`** (`string`)：水性險峻度等級。

### 🔹 5. `plugin_cross_ref` & `provenance` (跨系統與履歷)
* **`wikidata_id`** & **`alt_names`**：全球對照 ID 與別名。
* **`provenance`**：資料修復與解析時間戳記。
