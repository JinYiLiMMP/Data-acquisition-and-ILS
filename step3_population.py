"""
Step 3 · 门头沟区各行政村常住人口估计值
========================================

技术路线：``中国人口网格数据`` + ``门头沟区村级行政区边界``
            --分区统计--> ``门头沟区各行政村常住人口估计值``

实现（zonal statistics，无需 rasterstats 依赖）：
  对每个村多边形，用 rasterio.mask 从 100m 人口网格中裁出该村范围的像元，
  把"每像元常住人口数"求和，即为该村常住人口估计值。
  人口网格 nodata = -inf，统计时仅累加有限且 >0 的像元。
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask as rio_mask

import config
from common import banner, log


def _zonal_sum(src: rasterio.io.DatasetReader, geom) -> tuple[float, int]:
    """裁出 geom 范围像元并求和，返回 (人口和, 有效像元数)。"""
    out, _ = rio_mask(src, [geom], crop=True, filled=True, nodata=np.nan)
    band = out[0].astype("float64")
    valid = band[np.isfinite(band) & (band > 0)]
    return float(valid.sum()), int(valid.size)


def run(villages: gpd.GeoDataFrame | None = None) -> pd.DataFrame:
    banner("Step 3 · 统计各行政村常住人口估计值（人口网格分区求和）")

    if villages is None:
        villages = gpd.read_file(config.VILLAGES_OUT)
    villages = villages.to_crs(config.TARGET_CRS)

    records = []
    with rasterio.open(config.POPULATION_GRID) as src:
        log(f"  人口网格：{src.width}x{src.height}  res={src.res[0]:.6f}°  "
            f"crs={src.crs}")
        total = len(villages)
        for i, row in villages.iterrows():
            pop, ncell = _zonal_sum(src, row.geometry)
            records.append(
                {
                    "XZQDM": row["XZQDM"],
                    "XZQMC": row["XZQMC"],
                    "population_est": round(pop, 2),
                    "n_cells": ncell,
                }
            )
            if (i + 1) % 40 == 0 or (i + 1) == total:
                log(f"    进度 {i + 1}/{total}")

    df = pd.DataFrame(records)
    df.to_csv(config.POPULATION_OUT, index=False, encoding="utf-8-sig")

    log(f"  门头沟区常住人口估计合计：{df['population_est'].sum():,.0f} 人")
    log(f"  人口最多村：{df.loc[df['population_est'].idxmax(), 'XZQMC']} "
        f"= {df['population_est'].max():,.0f} 人")
    log(f"✅ 已输出：{config.POPULATION_OUT}")
    return df


if __name__ == "__main__":
    run()
