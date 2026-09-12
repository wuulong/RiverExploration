# WRA-Civ 專題手冊：民間河川水文拓樸體系與 AI 開發白皮書

> **一句話定義**：**WRA-Civ (Civilian Water Resources Agency Hydrology System)** 是台灣首套相容經濟部水利署官方 6 碼編碼、並向上延伸擴充全島高山溪谷、地方人文支流與 3D 匯流點幾何的「開源民間水文拓樸註冊表與 AI 智慧控制平面」。

---

## 1. 為什麼需要 WRA-Civ？（核心背景與痛點）

在台灣的水資源與河流研究中，長期存在以下斷層：
1. **官方編碼止於重要幹流**：水利署官方公告水系程式碼（837 筆）非常權威，但許多人文走讀、古道溪谷、高山源頭與地方小支流（如冷水坑溪、豆子埔溪、各圳路源頭）並無官方程式碼，導致資料庫斷鏈。
2. **缺乏 3D 水理幾何與匯流點拓樸**：傳統官方名冊多為純文字表格，缺少上游出海口親緣路徑（Topology Path）、匯流點 GPS 座標、海拔落差（Elevation）與下游支流相交關係。
3. **AI Agent 無法進行程序化水理推論**：當 AI 或研究者想要詢問「油羅溪與上坪溪在哪裡交會？」、「某污染源順流會經過哪些鄉鎮？」、「特定流域全體支流的總落差是多少？」時，傳統資料庫無法以 Pipeline 方式進行計算。

**WRA-Civ 就是為了解決這三大斷層而生。**

---

## 2. WRA-Civ 核心資產與資料庫規模

WRA-Civ 目前由以下實體資產支撐：

| 資產專案 | 檔案路徑 | 說明 |
| :--- | :--- | :--- |
| **AI-Native Master 資料庫** | `taiwan_river_topology_registry.jsonl` | 1,397+ 筆水脈完整記錄，包含 17 個標準屬性與外掛空間 |
| **唯讀相容 CSV** | `taiwan_river_topology_registry.csv` | 供傳統 Excel / GIS 軟體向下相容讀取 |
| **水文拓樸 CLI 工具** | `scripts/river_cli.py` | 符合 CGS v2.4 規範之萬用查詢與 Pipe 串流命令工具 |
| **核心 Python 函式庫** | `scripts/wra_river/` | 模組化水文拓樸、LCA、轉譯與過濾套件 |
| **官方原始碼對照表** | `wra_official_river_codes.json` | 837 筆水利署官方權威程式碼與水系對照檔 |

### 關鍵資料指標：
- **全台水脈總量**：**1,397 筆**
- **官方公告水脈 (`is_civilian=0`)**：**727 筆 (52.0%)** —— 100% 繼承水利署 6 碼體系。
- **民間延伸水脈 (`is_civilian=1`)**：**670 筆 (48.0%)** —— 以 `-C[nn]` 拓樸演演算法派發編碼。
- **3D 匯流點與海拔涵蓋**：全量整合 OpenStreetMap 實體交點 Node 與 3D 海拔高程。

---

## 3. 編碼規範與拓樸規則

### ① 繼承與延伸編碼 (`river_code`)
- **官方水脈**：維持 6 碼大寫英數（如頭前溪 `130000`、油羅溪 `130020`、上坪溪 `130010`）。
- **民間支流**：在父水脈程式碼後加上 `-C[序號]`（如頭前溪一級支流豆子埔溪為 `130000-C01`，其再細分支流則為 `130000-C01-C01`）。

### ② 親緣路徑 (`topology_path`)
以 `@` 分隔由源頭向出海口主流的完整迴路程式碼，例如：
`0@130000@130020` 代表：`出海口/父根 (0)` ➔ `頭前溪 (130000)` ➔ `油羅溪 (130020)`。
任何程式皆可依此路徑在 $O(1)$ 時間內判定水脈間的上下游親緣。

---

## 4. CGS v2.4 深度管道 (Pipeline) 與水理運算

WRA-Civ CLI 工具 (`river_cli.py`) 原生支援 Unix 管道串流（Pipeline-Native），具備以下高級水理計算能力：

### ① LCA 最近共同祖先連通子圖抽取 (`slice --lca`)
自動在拓樸樹中找出兩條支流的交會節點，並抽取出最小連通子圖：
```bash
python3 scripts/river_cli.py slice 油羅溪 上坪溪 --lca -f mermaid
```
*輸出結果*：自動識別主流「頭前溪 (130000)」為交會點，繪出三節點 Mermaid 關係圖。

### ② 管道串流幾何統計聚合 (`stats`)
透過管道接收任意篩選或切片結果，進行 Map-Reduce 串流統計：
```bash
python3 scripts/river_cli.py search -b "頭前溪" -f jsonl | python3 scripts/river_cli.py stats -i -
```
*計算產出*：水系支流總數、官方/民間比例、各河階分佈、最高最低海拔與總落差 $\Delta H$。

### ③ 外部感測/走讀資料動態注入 (`hydrate`)
零碰撞 Master DB，在記憶體管道中將外部 IoT 水質、流量或田野走讀資料動態注入至目標水脈的 `plugins.<namespace>` 命名空間：
```bash
cat sensor.json | python3 scripts/river_cli.py hydrate --namespace iot_flow
```

### ④ 拓樸物理完整迴路檢核 (`lint`)
自動檢查拓樸是否有完整迴路循環依賴 (Cycle)、重力守恆逆流 (Gravity violation) 或無效父程式碼之孤兒節點 (Orphan nodes)：
```bash
python3 scripts/river_cli.py lint
```

---

## 5. 如何與外界介紹或整合 WRA-Civ？

當向不同角色或系統介紹 WRA-Civ 時，建議切入角度：

1. **對水利/政府研究者**：
   > 「WRA-Civ 是水利署官方編碼的民間開源補完計畫。我們將官方名冊沒有涵蓋的地方人文野溪與高山支流，以嚴謹的階層拓樸演演算法完成編碼，並補足 3D 匯流點經緯度與海拔。」
2. **對 GIS / 開發者**：
   > 「WRA-Civ 提供 100% 管道相容（Pipeline-Native）的 CLI 與 Python 套件 `wra_river`，可一鍵轉譯 3D GeoJSON、3D KML 與 Mermaid，支援 LCA 切片與 Map-Reduce 幾何運算。」
3. **對 AI / 語意網路開發者**：
   > 「WRA-Civ 是 AI-Native 水文大腦。每個水脈節點均配備跨庫識別碼（Wikidata QID、Wikipedia URL、OpenStreetMap Node、WalkGIS ID）與 Plugin 外掛機制，適合做為空間 RAG 與圖譜推理的地標錨定底盤。」

---

## 6. 關聯專書章節與手冊連結

- **專書深度實作章節**：[Chapter_11_6.md](../Chapter_11_6.md)（記錄全台 150 主流水系大一統、AI-Native 雙軌 JSONL 與四階縣市仲裁）
- **官方 CLI 使用手冊**：[scripts/manuals/river_cli.md](../../../../scripts/manuals/river_cli.md)
- **CGS v2.4 規格書**：[scripts/specs/river_cli.spec.md](../../../../scripts/specs/river_cli.spec.md)
- **核心套件原始碼**：[events/AIBooks/RiverExploration/scripts/wra_river/](../scripts/wra_river/)
