# WRA-Civ AI-Native JSONL Master 規格說明書 (Spec v2.4)

*   **資料檔案**：`taiwan_river_topology_registry.jsonl`
*   **專書對齊版本**：v2.4 (3D Hydrological Elevation & AI-Native JSONL Migration)
*   **格式類型**：JSON Lines（每行代表一條水脈之完整 Native JSON 物件，共 1,418 行）
*   **用途**：作為全台 1,418 筆水脈拓樸之單一真實來源 (Single Source of Truth)，透過 Links 與 Plugin 命名空間徹底解耦核心親緣、地理 GIS、可追溯網址與 3D 海拔水文分析。

---

## 1. 原生 JSONL 頂層結構規格 (JSON Schema Spec v2.4)

每一行 Native JSON 物件包含 **Core 核心屬性**、**Links 權威外鏈**、**Plugins 插件命名空間**，以及 **Meta Data 歷史與維護履歷**：

```json
{
  "river_code": "130000-C04-C01",
  "river_name": "王爺坑溪",
  "parent_code": "130000-C04",
  "parent_name": "鹿寮坑溪",
  "basin_code": "130000",
  "basin_name": "頭前溪",
  "topology_path": "0@130000@130000-C04@130000-C04-C01",
  "is_civilian": 1,
  "source_type": "Wiki",
  "waterway_type": "stream",
  "stream_order": 3,
  "description": "頭前溪水系民間支流",
  "contributor": "",

  "links": {
    "walkgis_url": "",
    "wikipedia_url": "https://zh.wikipedia.org/wiki/%E7%8E%8B%E7%88%BA%E5%9D%91%E6%BA%AA",
    "osm_url": "https://www.openstreetmap.org/search?query=%E7%8E%8B%E7%88%BA%E5%9D%91%E6%BA%AA",
    "wikidata_id": "Q11113632"
  },

  "attribute_json": {
    "code_status": "draft",
    "deprecated_codes": [],
    "replaced_by": "",
    "provenance": {
      "last_updated": "2026-09-04"
    }
  },

  "plugins": {
    "gis": {
      "confluence_id": "J-130000-C04-C01",
      "confluence_lon": 121.1203799,
      "confluence_lat": 24.7354231,
      "confluence_type": "Geometric_Endpoint_Match_1833m",
      "estimated_length_km": 16.81,
      "estimated_velocity_ms": null,
      "osm_wikipedia_tag": ""
    },
    "elevation": {
      "confluence_elevation_m": 150.0
    },
    "culture": {
      "historical_events": [
        {
          "year": "1895",
          "name": "樟腦產業與古道越嶺歷史",
          "description": "流域內保存有重要樟腦採伐歷史與原民獵路"
        }
      ],
      "indigenous_names": [
        {
          "tribe": "Atayal",
          "original_name": "TGB",
          "meaning": "水流平緩之處"
        }
      ]
    },
    "pois": [
      {
        "poi_id": "POI-130000-C04-01",
        "name": "王爺坑糯米橋",
        "category": "Historical_Bridge",
        "lon": 121.1215,
        "lat": 24.7360,
        "elevation_m": 155.0,
        "walkgis_feature_id": ""
      }
    ]
  },

  "updated_at": "2026-08-30 19:17:13"
}
```

---

## 3. 資料不可變性合約 (Immutability Contract & Governance)

為保護外部 API 依賴、WalkGIS 空間圖層對接與學術引用不致斷鏈，WRA-Civ 資料庫實施嚴格的 **不可變主鍵原則 (Immutable Primary Key Rule)**：

1. **🔒 硬性不可變欄位 (Immutable Attributes)**：
   * **`river_code`**：一旦分配並釋出，**絕對禁止刪除、更換或重新計算編號**！外部系統以此程式碼作為 API 與 URI 主鍵。
   * **`parent_code` / `basin_code` / `topology_path`**：除非水文親緣關係經過重大物理考據校正，否則拓樸主幹路徑保持穩定。
2. **✏️ 允許修訂與增量欄位 (Mutable & Enrichable Attributes)**：
   * **`river_name`**：允許修正錯別字、地方俗名或原民族語地名。
   * **`description`**：允許修正補充水庫史蹟、水性描述或誤置資訊。
   * **`links` / `plugins`**：允許 100% 增量厚化 3D 海拔高度、實體 GIS 幾何、文化歷史 events 與 pois 陣列！
3. **🛡️ 轉換器自動保護鎖 (Primary Key Guard)**：
   * 轉換工具 `convert_topology_to_jsonl.py` 在執行時自動校驗 `river_code` 完整性，若檢測到歷史已釋出之程式碼遭刪除或異動，將**硬性阻斷並報錯中止 (Exit Code 1)**。

### 🔹 Core 核心拓樸屬性 (Top-Level)
| 欄位名稱 | 型態 | 說明與規範 |
| :--- | :--- | :--- |
| `river_code` | `string` | 水脈唯一主鍵程式碼 (水利署 6 碼或民間 `-C[nn]` 擴充) |
| `river_name` | `string` | 水脈中文名稱 (清音中文，不含括號與備註) |
| `parent_code` | `string` | 父水脈之唯一程式碼 (主流為 `"0"`) |
| `parent_name` | `string` | 父水脈之中文名稱 |
| `basin_code` | `string` | 所屬水系 6 位數編碼 (例: `130000` 頭前溪) |
| `basin_name` | `string` | 所屬水系中文名稱 |
| `topology_path` | `string` | 從主流到該支流的完整拓樸路徑 (例: `0@130000@130000-C04`) |
| `is_civilian` | `integer` | 權威類別：`0` 代表水利署官方 6 碼，`1` 代表民間延伸支流 |
| `source_type` | `string` | 資料來源標籤 (`WRA`, `Wiki`, `Verified_Both`) |
| `waterway_type` | `string` | 水道物理型態 (`river`, `stream`, `drain`) |
| `stream_order` | `integer` | 拓樸階層感 (1 代表主流，2 代表一級支流...) |
| `description` | `string` | 水脈人文或地理簡短敘述 |

---

### 🔹 `links` 權威外鏈命名空間
收納該水脈在各權威空間/知識庫系統中的連結，保持頂層 Single Source of Truth：
* `walkgis_url`: WalkGIS 空間實體 URL 網址
* `wikipedia_url`: 維基百科權威條目 URL
* `osm_url`: OpenStreetMap 地理圖資對照 URL
* `wikidata_id`: 跨語言與跨庫唯一實體識別碼 (`Q[id]`)

---

### 🔹 `plugins` 插件擴充命名空間
預留給地理幾何、高程與水理分析的動態擴充模組：
1. **`plugins.gis` (地理幾何模組)**：
   * `confluence_id`: 實體匯流點編碼 (`J-[river_code]`)
   * `confluence_lon` / `confluence_lat`: 匯流點實體 WGS84 座標
   * `confluence_type`: 幾何演算品質標籤 (`OSM_Shared_Node` / `Geometric_Endpoint_Match`)
   * `estimated_length_km`: 折線幾何估算長度 (公里)
   * `estimated_velocity_ms`: 預留流速欄位 ($m/s$，無計算時為 `null`)
   * `osm_wikipedia_tag`: OSM 向量標籤上的 Wiki Key
2. **`plugins.elevation` (3D 高程模組)**：
   * `confluence_elevation_m`: 匯流點海拔高度 (公尺)
3. **`plugins.culture` (人文歷史與原民地名模組)**：
   * `historical_events`: 流域歷史事件清單 (`year`, `name`, `description`)
   * `indigenous_names`: 族群原住民族語稱呼與地名意涵 (`tribe`, `original_name`, `meaning`)
   * `hydraulic_history`: 水利工程開發史與清代/日治堤防發掘
---

### 🔹 `attribute_json` 動態屬性與治理命名空間
收納包含生命週期狀態、出海口縣市歸屬與界河仲裁等元資料控制項：
* `code_status`: 程式碼生命週期狀態 (`draft` 初期草案, `confirmed` 已凍結, `deprecated` 已廢除)
* `primary_county`: 實體出海口歸屬主要縣市 (例: `新竹市`, `新北市`)
* `primary_county_code`: 內政部 5 位數官方行政區劃程式碼 (例: `10018`, `65000`)
* `is_border_river`: 是否為雙縣市界河標記 (`true` / `false`)
* `border_counties`: 界河跨越縣市陣列 (例: `["新北市", "臺北市"]`)
* `arbitration_rule`: 界河單一歸屬仲裁規則 (採用 `Right_Bank_Outfall` 右岸法向量探針點 $P_{right} = P_2 + 200\text{m} \cdot \hat{N}_{right}$ 與內政部 Shapefile PIP 判定)
* `deprecated_codes`: 歷史廢除程式碼陣列
* `replaced_by`: 新取代程式碼
* `provenance`: 資料源與最後修復履歷

---

## 4. 雙層程式碼目錄樹匯出規範 (Double-Coded Directory Tree Spec)

支援透過 CLI 工具自動導出全台實體檔案目錄樹，供作業系統檔案總管直接操作：
* **第一層格式**: `[primary_county_code]_[primary_county]` (例: `10018_新竹市`, `65000_新北市`) ➔ 按內政部官方程式碼由北到南與由東到西排序。
* **第二層及以下**: `[river_code]_[river_name]` (例: `130000_頭前溪`, `130020_油羅溪`) ➔ 按水文拓樸親緣階層嵌套建立。
* **目錄預設資產**: 每個目錄下放置 `record.json` 記載該水脈 Native JSON 完整屬性。
