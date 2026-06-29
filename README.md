# 门头沟区村级行政区「人口——经纬度」数据生成流程

依据技术路线图，从原始公开数据出发，生成北京市门头沟区（行政区划代码 `110109`）
各村级行政区的 **常住人口估计值 + 经纬度** 数据，并附带门头沟区高程数据。
全流程纯 Python，路径相对化，便于复现与上传。

## 技术路线

```
高程数据(2片SRTM) ┐
                  ├─ 裁剪 ─→ 门头沟区高程数据 (step1)
门头沟区行政边界  ┘

北京市村级行政区边界 ─按110109检索→ 门头沟区村级行政区边界 (step2)
                                          │
中国人口网格数据 ──────分区统计──────────→ 各行政村常住人口估计值 (step3) ┐
                                          │                                ├─ 合并 →
                                          └─代码→高德API→ 各村经纬度 (step4) ┘   最终成果 (step5)
```

## 目录结构

```
mentougou_pipeline/
├── config.py            # 路径、参数、Key 读取（含零依赖 .env 加载）
├── common.py            # 日志、GCJ02→WGS84 纠偏、Haversine、村名清洗
├── step1_elevation.py   # SRTM 镶嵌 + 区界裁剪 → mentougou_dem.tif
├── step2_villages.py    # 按 110109 检索村界 → mentougou_villages.geojson
├── step3_population.py  # 人口网格分区求和 → village_population.csv
├── step4_coordinates.py # 高德 API 查询经纬度（质心兜底）→ village_coords.csv
├── step5_merge.py       # 合并 → mentougou_village_population_coords.csv / .geojson
├── step6_loss_probability.py  # 数据清洗 + 海拔→洪灾失联概率 → village_loss_probability.csv
├── run_all.py           # 一键运行 step1~6
├── requirements.txt
├── .env.example         # Key 模板（真实 .env 不入库）
└── output/              # 全部成果（不入库）
```

## 准备数据

将原始数据放在与本项目同级的 `data_acquiration/` 目录（或用环境变量
`MENTOUGOU_DATA_DIR` 指定）。所需文件：

| 用途 | 路径 |
|---|---|
| 高程 SRTM | `source_altitude_data/srtm_60_04.img`, `srtm_60_05.img` |
| 区界 | `mentougou_district_boundary.geojson` |
| 人口网格 | `source_population_grid_data_China/population_total_pop.tif` |
| 村界 | `village-level_administrative_units_boundaries/boundaries.shp`（含 .shx/.dbf/.prj/.cpg） |

> 原始数据体积较大，未随仓库提供；请自行下载放置。

## 安装与配置

```bash
pip install -r requirements.txt

# 配置高德 Key（仅本地，不入库）
cp .env.example .env        # 然后编辑 .env 填入 AMAP_KEY
# 或直接设置环境变量：
#   export AMAP_KEY=你的Key            (Linux/macOS)
#   $env:AMAP_KEY="你的Key"            (Windows PowerShell)
```

> 未配置 `AMAP_KEY` 时，step4 自动改用村多边形质心作为坐标，全流程仍可完成。

## 运行

```bash
python run_all.py            # 一键全流程
# 或单步运行：
python step1_elevation.py
python step2_villages.py
python step3_population.py
python step4_coordinates.py
python step5_merge.py
```

## 输出成果（output/）

| 文件 | 内容 |
|---|---|
| `mentougou_dem.tif` | 门头沟区高程数据（GeoTIFF, WGS84） |
| `mentougou_villages.geojson` | 门头沟区村级行政区边界（含代码/村名） |
| `village_population.csv` | 各村常住人口估计值 |
| `village_coords.csv` | 各村经纬度（含高德/质心来源标注） |
| `mentougou_village_population_coords.csv` | **最终成果**：村代码、村名、人口、经纬度 |
| `mentougou_village_population_coords.geojson` | 最终成果的点图层 |
| `village_loss_probability.csv` | **应用成果**：清洗后村庄的海拔、洪灾失联概率、抽样权重 |
| `village_loss_probability.geojson` | 失联概率点图层 |

## 方法说明

- **坐标系**：全部统一为 WGS84（EPSG:4326）。
- **人口估计**：人口网格为「每像元常住人口数」，对各村多边形覆盖像元求和；
  网格 nodata 与非正值不计入。
- **坐标纠偏**：高德返回 GCJ-02 坐标，已转回 WGS84；仅当匹配级别为
  「村庄/村委会」时采用高德坐标，否则回退多边形质心，并用 `coord_source` 标注。
- **村名编码**：村界 DBF 为 UTF-8，`geopandas` 直接读取即为正确中文。
- **失联概率（step6）**：先做三道数据清洗——①剔除高德无地理编码结果的村、
  ②剔除落在门头沟区边界外的村（点-面判定）、③剔除无有效高程的村；再按指数衰减
  `P = p_min + (p_max-p_min)·exp(-elev/H)` 赋概率（海拔越低越易失联），`H` 默认取
  有效村庄海拔中位数。另输出归一化抽样权重 `selection_weight`（Σ=1）。
