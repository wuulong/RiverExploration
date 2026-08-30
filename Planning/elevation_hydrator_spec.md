# ⛰️ 全球實體高程與水文縱剖面厚化 CLI (`elevation_hydrator.py`) 規劃書

## 📌 一、目標與核心理念
本工具旨在為 BMAD-PA 水文與地理資料庫提供 **3D 實體高程 (Z/Elevation)** 注入能力。遵循 CGS v2.0 規格，整合全球開放高程 API (Open-Elevation API)，並**極致善用本地圖資快取**（如 `cache/osm_geoms/` 與 `cache/confluence_atlas.json`），達成毫秒級的高程查詢、匯流點厚化與河道縱剖面採樣。

---

## 🛠️ 二、4 大核心功能與指令介面 (CLI Interfaces)

### 1. 單點與多點座標高程查詢 (`query`)
* **用途**：給定單一或多組 2D 經緯度 ($Lat, Lon$)，回傳精準的海拔高度 ($Elevation, Z$)。
* **CLI 指令**：
  ```bash
  # 單點查詢
  ./pa elevation query --lat 24.76367 --lon 121.13452
  
  # 多點批量查詢
  ./pa elevation query --locations "24.76367,121.13452|24.61645,121.1769"
  ```
* **輸出範例 (JSON)**：
  ```json
  [
    {"latitude": 24.76367, "longitude": 121.13452, "elevation_m": 356.0},
    {"latitude": 24.61645, "longitude": 121.1769, "elevation_m": 1025.0}
  ]
  ```

---

### 2. 匯流點圖集高程自動厚化 (`hydrate-atlas`)
* **用途**：讀取 `cache/confluence_atlas.json`，對已算出匯流點 GPS 的河流，批量發送 API 查詢，將海拔高度注入至 JSON。
* **CLI 指令**：
  ```bash
  ./pa elevation hydrate-atlas --input events/AIBooks/RiverExploration/cache/confluence_atlas.json
  ```
* **注入欄位**：
  * `confluence_elevation_m`: `356.0` (海拔米數)

---

### 3. 河流沿線縱剖面高程採樣 (`profile`) — 💡 **善用本地 Cache**
* **用途**：給定河川名稱（例如 `頭前溪` 或 `油羅溪`），分析其縱深高程變化，生成河道縱剖面與平均坡降。
* **本地 Cache 優先架構**：
  1. 優先讀取本地 `cache/osm_geoms/basin_{b_code}_{b_name}_raw.json` 或 `cache/osm_geoms/{r_name}.json` 中的折線幾何。
  2. 依據折線節點 (Nodes) 進行固定距離（如每 500 公尺或 1000 公尺）精確採樣。
  3. 優先查詢本地 `cache/elevation_cache.json`；若無快取才發動 API 並即時存檔。
* **CLI 指令**：
  ```bash
  ./pa elevation profile --river 油羅溪 --basin 頭前溪 --step-m 500
  ```
* **輸出範例 (JSON & 終端文字剖面圖)**：
  ```text
  📈 【油羅溪】河道縱剖面採樣 (總長: 26.5 km, 海拔差: 1,450m ➔ 80m):
  1,450m █ 
  1,100m █ ▄
    750m █ █ ▄
    320m █ █ █ ▄
     80m █ █ █ █ █ ▄ ▄
  ```

---

### 4. 兩點落差與即時水力坡降計算 (`slope`)
* **用途**：計算任意兩點間的高程落差 $\Delta H$、水平球面距離 $L$ 以及千分之幾的水力坡降 $S = \Delta H / L$。
* **CLI 指令**：
  ```bash
  ./pa elevation slope --p1 24.61645,121.1769 --p2 24.76367,121.13452
  ```
* **輸出範例**：
  ```text
  ⛰️ 上游點高程: 1025.0 m | 下游點高程: 356.0 m | 高程差: 669.0 m
  📏 水平球面距離: 16.94 km
  🌊 水力平均坡降: 39.49 ‰ (3.95%)
  ```

---

## 🛠️ 三、技術架構與落庫快取機制

```
[使用者 / ./pa elevation]
        │
        ├── 1. 讀取本地 Cache (cache/osm_geoms/ & cache/elevation_cache.json) (0秒秒讀)
        │
        └── 2. 若本地無高程 ➔ 發動 Open-Elevation API 批次查詢
                │
                └── 3. 第一秒實時落庫硬碟 cache/elevation_cache.json (零重複連線)
```

1. **零重複下載原則**：維護全庫 `cache/elevation_cache.json` (格式: `"24.76367,121.13452": 356.0`)。只要查過一次的座標，第二次讀取毫秒級快取。
2. **CGS v2.0 CLI 規範**：支援 `--json`、`--quiet`、`-m` (Token 限制)、`version` 與 `schema` 等標準旗標。
