"""
全局配置 / Global configuration
================================

集中管理输入数据路径、输出路径、关键参数（门头沟区代码、坐标系、高德 Key 等）。
所有路径默认相对本仓库，便于上传 GitHub 后复现。

数据目录默认指向与本项目同级的 ``data_acquiration`` 文件夹，可用环境变量
``MENTOUGOU_DATA_DIR`` 覆盖。高德 API Key **不写入仓库**，仅从环境变量
``AMAP_KEY`` 读取（见 README）。
"""

from __future__ import annotations

import os
from pathlib import Path

# ── 目录 ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """零依赖加载 .env（仅 KEY=VALUE 行），不覆盖已存在的环境变量。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv(PROJECT_ROOT / ".env")

# 原始数据目录：默认与本项目同级的 data_acquiration；可用环境变量覆盖
DATA_DIR = Path(
    os.environ.get("MENTOUGOU_DATA_DIR", PROJECT_ROOT.parent / "data_acquiration")
).resolve()

# 所有中间与最终成果统一输出到此目录
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 输入数据文件 ──────────────────────────────────────────────────────
# 高程：两片 SRTM 90m DEM（覆盖门头沟需南北两片镶嵌）
SRTM_TILES = [
    DATA_DIR / "source_altitude_data" / "srtm_60_04.img",  # 40–45°N
    DATA_DIR / "source_altitude_data" / "srtm_60_05.img",  # 35–40°N
]

# 门头沟区行政边界（adcode 110109）
DISTRICT_BOUNDARY = DATA_DIR / "mentougou_district_boundary.geojson"

# 全国 100m 人口网格（WorldPop 风格，像元值=该格常住人口数）
POPULATION_GRID = DATA_DIR / "source_population_grid_data_China" / "population_total_pop.tif"

# 北京市村级行政区边界（完整 shapefile，含 XZQDM/XZQMC 属性）
VILLAGE_BOUNDARIES = (
    DATA_DIR / "village-level_administrative_units_boundaries" / "boundaries.shp"
)

# ── 输出数据文件 ──────────────────────────────────────────────────────
DEM_OUT = OUTPUT_DIR / "mentougou_dem.tif"                       # step1
VILLAGES_OUT = OUTPUT_DIR / "mentougou_villages.geojson"         # step2
POPULATION_OUT = OUTPUT_DIR / "village_population.csv"           # step3
COORDS_OUT = OUTPUT_DIR / "village_coords.csv"                   # step4
FINAL_CSV = OUTPUT_DIR / "mentougou_village_population_coords.csv"      # step5
FINAL_GEOJSON = OUTPUT_DIR / "mentougou_village_population_coords.geojson"

LOSS_CSV = OUTPUT_DIR / "village_loss_probability.csv"          # step6
LOSS_GEOJSON = OUTPUT_DIR / "village_loss_probability.geojson"  # step6

# ── 关键参数 ──────────────────────────────────────────────────────────
MENTOUGOU_ADCODE = "110109"        # 门头沟区行政区划代码前缀
TARGET_CRS = "EPSG:4326"           # 统一坐标系（WGS84 经纬度）

# step6 失联概率模型参数（指数衰减：prob = p_min + (p_max-p_min)·exp(-elev/H)）
LOSS_P_MIN = 0.05                  # 海拔极高时的失联概率下限
LOSS_P_MAX = 0.95                  # 海拔接近 0 时的失联概率上限
LOSS_H = None                      # 海拔尺度参数(m)；None=自动取有效村庄海拔中位数

# 高德 API 配置（Key 仅从环境变量读取，不入库）
AMAP_KEY = os.environ.get("AMAP_KEY", "")
AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
AMAP_DELAY = 0.25                  # 请求间隔（秒），尊重高德 QPS 限制


def check_inputs() -> list[Path]:
    """返回缺失的输入文件列表（空列表表示数据完整）。"""
    required = [
        *SRTM_TILES,
        DISTRICT_BOUNDARY,
        POPULATION_GRID,
        VILLAGE_BOUNDARIES,
    ]
    return [p for p in required if not p.exists()]
