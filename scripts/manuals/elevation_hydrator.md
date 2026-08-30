# 手冊：elevation_hydrator.py (全球高程 API 厚化與水文縱剖面分析 CLI)

`elevation_hydrator.py` 是符合 CGS v2.0 規範的高程厚化與水力剖面分析工具，整合 Open-Elevation API 並極致善用本地 OSM 幾何與高程快取檔 (`cache/elevation_cache.json`)。

---

## 1. 核心功能 (Core Features)

* **單點與多點座標高程查詢 (`query`)**：傳入經緯度，毫秒級回傳海拔高度 ($Z, Elevation$)。
* **匯流點圖集高程自動厚化 (`hydrate-atlas`)**：讀取 `confluence_atlas.json`，對全台匯流點批次注入海拔高程。
* **河道沿線縱剖面高程採樣 (`profile`)**：讀取本地 `cache/osm_geoms/` 幾何，沿河道進行定距採樣，產出海拔縱剖面與落差。
* **兩點落差與水力坡降計算 (`slope`)**：計算球面距離、垂直落差 $\Delta H$ 與千分比水力坡降 ($S = \Delta H / L$)。
* **零重複連線快取 (Zero-Duplicate Cache)**：自動維持 `cache/elevation_cache.json`，查詢過的座標 100% 0 秒秒讀本地檔。

---

## 2. CLI 使用說明 (CLI Usage)

```bash
# 1. 查詢單點或多點高程
python scripts/gis/elevation_hydrator.py query -l "24.76367,121.13452|24.61645,121.1769"

# 2. 自動厚化匯流點 JSON 圖集
python scripts/gis/elevation_hydrator.py hydrate-atlas

# 3. 分析油羅溪河道縱剖面 (定距 2000m 採樣)
python scripts/gis/elevation_hydrator.py profile --river 油羅溪 --step-m 2000

# 4. 計算兩點間水力坡降
python scripts/gis/elevation_hydrator.py slope --p1 "24.61645,121.1769" --p2 "24.76367,121.13452"

# 5. 以 JSON 格式輸出結果
python scripts/gis/elevation_hydrator.py slope --p1 "24.61645,121.1769" --p2 "24.76367,121.13452" --json
```
