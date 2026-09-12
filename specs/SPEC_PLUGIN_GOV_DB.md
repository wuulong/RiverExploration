# 🌊 WRA-Civ ↔ tw-gov-db 外掛協同規格書 (SPEC_WRA_CIV_PLUGIN_GOV_DB.md)

* **協同合約代號**：`SYN-WRA-CIV-PLUGINS-001`
* **版本號**：`v1.0.1` (對齊 WRA-Civ Spec v2.4 & tw-gov-db CGS v2.4)
* **受控路徑**：`events-2026Q3/gov-db-in/tw-gov-db/docs/specs/SPEC_WRA_CIV_PLUGIN_GOV_DB.md`
* **發布方 (Provider)**：`tw-gov-db` (GOV-300 / 基石三 `g30_hydrology_indexer`)
* **對接方 (Consumer / Upstream SSOT)**：`RiverExploration` / WRA-Civ 水系親緣拓樸體系

---

## 1. 核心哲學：主結構不可變與命名空間隔離 (Zero Pollution Principle)

依據 WRA-Civ 規範 `specs/jsonl_topology_schema_spec.md`：
1. **主體不可變性 (Core Immutability)**：
   * `river_code`, `parent_code`, `topology_path`, `stream_order`, `is_civilian`, `attribute_json` 屬於 WRA-Civ 核心親緣與物理屬性，任何政府基石注入均**嚴禁覆寫、刪除或重新命名**。
2. **命名空間絕對隔離 (Namespace Isolation)**：
   * `tw-gov-db` 的所有注水（Hydration）與跨部會對照資訊，100% 收斂於 **`plugins.gov_db`** 命名空間內。
   * 與 WRA-Civ 既有的 `plugins.gis`, `plugins.elevation`, `plugins.culture`, `plugins.pois` 平行並存，互不干涉。

---

## 2. `plugins.gov_db` 完整 JSON Schema 定義

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "WraCivGovDbPlugin",
  "type": "object",
  "properties": {
    "spec_version": {
      "type": "string",
      "description": "gov_db 外掛規格版本，目前固定為 '1.0.1'",
      "example": "1.0.1"
    },
    "hydrated_at": {
      "type": "string",
      "format": "date-time",
      "description": "注水時間戳記 (ISO-8601 UTC+8)",
      "example": "2026-09-13T07:05:00+08:00"
    },
    "g10_competent_agency": {
      "type": "object",
      "description": "對齊 G10 (機關組織基石) 之水利權責管轄單位",
      "properties": {
        "agency_name": { "type": "string", "example": "經濟部水利署第二河川分署" },
        "agency_oid": { "type": "string", "example": "2.16.886.101.20003.20007.20015" },
        "official_org_code": { "type": "string", "example": "315080000A" }
      },
      "required": ["agency_name", "agency_oid"]
    },
    "g20_spatial": {
      "type": "object",
      "description": "對齊 G20 (空間地籍基石) 之國家標準行政區劃與地碼",
      "properties": {
        "primary_county": { "type": "string", "example": "新竹縣" },
        "primary_county_code": { "type": "string", "example": "10004" },
        "admin_code": { "type": "string", "example": "10004080", "description": "8 碼國家標準行政區碼 (如 芎林鄉)" },
        "confluence_cadastral_id": { "type": ["string", "null"], "example": "E10004080_0123-0000" }
      },
      "required": ["primary_county", "admin_code"]
    },
    "g30_topology_meta": {
      "type": "object",
      "description": "對齊 G30 (水系基石) 之微拓樸特徵與親緣摘要",
      "properties": {
        "stream_order": { "type": "integer", "example": 3 },
        "is_civilian": { "type": "boolean", "example": true },
        "direct_ancestor_code": { "type": "string", "example": "130000-C04" },
        "root_basin_code": { "type": "string", "example": "130000" },
        "root_basin_name": { "type": "string", "example": "頭前溪" }
      },
      "required": ["stream_order", "is_civilian", "root_basin_code"]
    },
    "g30_sensor_network": {
      "type": "object",
      "description": "沿此水脈或鄰近之全政府水情測站網 (中央氣象署/水利署/環境部)",
      "properties": {
        "associated_stations_count": { "type": "integer", "example": 2 },
        "stations": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "station_id": { "type": "string", "example": "C0A980" },
              "station_name": { "type": "string", "example": "芎林雨量站" },
              "station_type": { "type": "string", "enum": ["RAINFALL", "WATER_LEVEL", "WATER_QUALITY", "WEATHER"] },
              "agency_name": { "type": "string", "example": "中央氣象署" },
              "latitude": { "type": "number", "example": 24.7744 },
              "longitude": { "type": "number", "example": 121.0772 }
            },
            "required": ["station_id", "station_name", "station_type", "agency_name"]
          }
        }
      },
      "required": ["associated_stations_count", "stations"]
    },
    "g40_agriculture_association": {
      "type": "object",
      "description": "對齊 G40 (法人與農漁會基石) 之灌區農會/產銷對位",
      "properties": {
        "fa_code": { "type": "string", "example": "FA_HSZ_003" },
        "fa_name": { "type": "string", "example": "新竹縣芎林鄉農會" },
        "ban": { "type": "string", "example": "46803206" }
      }
    }
  },
  "required": ["spec_version", "g10_competent_agency", "g20_spatial", "g30_topology_meta", "g30_sensor_network"]
}
```

---

## 3. 實體注入前後對照範例 (Before & After Payload)

### 3.1 注入前 (Raw WRA-Civ JSONL)
```json
{
  "river_code": "130000-C04-C01",
  "river_name": "王爺坑溪",
  "parent_code": "130000-C04",
  "topology_path": "0@130000@130000-C04@130000-C04-C01",
  "is_civilian": 1,
  "plugins": {
    "gis": { "confluence_lon": 121.12038, "confluence_lat": 24.73542 },
    "elevation": { "confluence_elevation_m": 150.0 }
  }
}
```

### 3.2 注入後 (`g30_cli.py hydrate -j`)
```json
{
  "river_code": "130000-C04-C01",
  "river_name": "王爺坑溪",
  "parent_code": "130000-C04",
  "topology_path": "0@130000@130000-C04@130000-C04-C01",
  "is_civilian": 1,
  "plugins": {
    "gis": { "confluence_lon": 121.12038, "confluence_lat": 24.73542 },
    "elevation": { "confluence_elevation_m": 150.0 },
    "gov_db": {
      "spec_version": "1.0.1",
      "hydrated_at": "2026-09-13T07:05:00+08:00",
      "g10_competent_agency": {
        "agency_name": "經濟部水利署第二河川分署",
        "agency_oid": "2.16.886.101.20003.20007.20015",
        "official_org_code": "315080000A"
      },
      "g20_spatial": {
        "primary_county": "新竹縣",
        "primary_county_code": "10004",
        "admin_code": "10004080",
        "confluence_cadastral_id": null
      },
      "g30_topology_meta": {
        "stream_order": 3,
        "is_civilian": true,
        "direct_ancestor_code": "130000-C04",
        "root_basin_code": "130000",
        "root_basin_name": "頭前溪"
      },
      "g30_sensor_network": {
        "associated_stations_count": 1,
        "stations": [
          {
            "station_id": "C0A980",
            "station_name": "芎林雨量站",
            "station_type": "RAINFALL",
            "agency_name": "中央氣象署",
            "latitude": 24.7744,
            "longitude": 121.0772
          }
        ]
      },
      "g40_agriculture_association": {
        "fa_code": "FA_HSZ_003",
        "fa_name": "新竹縣芎林鄉農會",
        "ban": "46803206"
      }
    }
  }
}
```

---

## 4. 公開呼叫與跨專案整合規範 (Public CLI & API Interop)

本規範提供兩套公開且標準的串接方式，供 WRA-Civ 團隊或外部資料分析師使用：

### 4.1 管道方式：標準 CLI 管線串接 (Standard UNIX Pipeline)
使用公開的開源腳本進入點 `g30_cli.py` 進行注水，不依賴任何私有中繼路由器：

```bash
# 1. 透過標準輸入將 WRA-Civ JSONL 注入 gov_db 基石中繼屬性
cat taiwan_river_topology_registry.jsonl | \
  python src/modules/g30_hydrology_indexer/g30_cli.py hydrate -j > taiwan_rivers_hydrated.jsonl

# 2. 結合 jq 進行跨機關地緣快速過濾（例如：找出第二河川分署管轄之所有野溪）
cat taiwan_rivers_hydrated.jsonl | \
  jq -c 'select(.plugins.gov_db.g10_competent_agency.agency_name | contains("第二河川分署")) | {river_code, river_name, stations: .plugins.gov_db.g30_sensor_network.associated_stations_count}'
```

### 4.2 程式碼方式：Python API Direct Import
若要在 Python 腳本或排程中直接進行記憶體內注水，可直接引入核心函式：

```python
from modules.g30_hydrology_indexer.river_topology import RiverTopologyEngine

# 初始化本機微拓樸引擎 (預設讀取 universal_keys.sqlite)
engine = RiverTopologyEngine()

# 針對單筆水脈資料進行基石注水
river_record = {
    "river_code": "130000-C04-C01",
    "river_name": "王爺坑溪"
}
stations = engine.get_stations_for_river(river_record["river_code"])
river_info = engine.get_river(river_record["river_code"])

river_record.setdefault("plugins", {})["gov_db"] = {
    "spec_version": "1.0.1",
    "g10_competent_agency": {
        "agency_name": river_info.get("river_office"),
        "agency_oid": "2.16.886.101.20003.20007.20015"
    },
    "g20_spatial": {
        "primary_county": river_info.get("primary_county"),
        "admin_code": river_info.get("admin_code")
    },
    "g30_sensor_network": {
        "associated_stations_count": len(stations),
        "stations": stations
    }
}
```

---

## 5. 雙向通知與相容性保證 (Notice & Backward Compatibility)

1. **對 WRA-Civ 端的影響**：
   * **完全零破壞性**：WRA-Civ 若不讀取 `plugins.gov_db`，原有資料結構、GIS 計算、高程分析、OSM 與 Wikipedia 爬蟲邏輯 100% 不受任何影響。
   * **增值能力**：WRA-Civ 若在專書產製、遊記地圖生成或 Web 視覺化時需標註「主管機關分署 OID」或「鄰近水利署測站」，可直接自 `plugins.gov_db` 取得，無需額外連線資料庫。
2. **版本變更通知機制**：
   * 當 `tw-gov-db` 升級 `plugins.gov_db` 結構時，將依據語意化版本號（`spec_version`）進行推進。次版本升級（如 `1.1.0`）保證向前相容；主版本更迭將提前透過 Task Report 與協同規格書通知 WRA-Civ 團隊。
