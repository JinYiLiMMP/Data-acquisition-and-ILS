"""
Step 5 · 门头沟区各村级行政区人口——经纬度数据
==============================================

技术路线：``各行政村常住人口估计值`` + ``各村级行政区经纬度``
            --合并--> ``门头沟区各村级行政区人口——经纬度数据``

实现：按村代码 XZQDM 合并 step3 人口与 step4 坐标，输出最终成果（CSV + GeoJSON 点图层）。
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

import config
from common import banner, log


def run(pop: pd.DataFrame | None = None, coords: pd.DataFrame | None = None) -> pd.DataFrame:
    banner("Step 5 · 合并人口与经纬度，生成最终成果")

    if pop is None:
        pop = pd.read_csv(config.POPULATION_OUT, dtype={"XZQDM": str})
    if coords is None:
        coords = pd.read_csv(config.COORDS_OUT, dtype={"XZQDM": str})

    pop["XZQDM"] = pop["XZQDM"].astype(str)
    coords["XZQDM"] = coords["XZQDM"].astype(str)

    merged = coords.merge(
        pop[["XZQDM", "population_est", "n_cells"]],
        on="XZQDM",
        how="left",
    )

    # 整理输出列顺序
    cols = [
        "XZQDM", "XZQMC", "population_est",
        "lon", "lat", "coord_source",
        "lon_amap", "lat_amap", "amap_level", "amap_address", "offset_m",
        "lon_centroid", "lat_centroid", "n_cells",
    ]
    cols = [c for c in cols if c in merged.columns]
    merged = merged[cols]

    merged.to_csv(config.FINAL_CSV, index=False, encoding="utf-8-sig")

    # GeoJSON 点图层（用最终推荐坐标 lon/lat）
    gdf = gpd.GeoDataFrame(
        merged,
        geometry=[Point(xy) for xy in zip(merged["lon"], merged["lat"])],
        crs=config.TARGET_CRS,
    )
    gdf.to_file(config.FINAL_GEOJSON, driver="GeoJSON")

    missing_pop = merged["population_est"].isna().sum()
    log(f"  村级记录：{len(merged)}  总人口估计：{merged['population_est'].sum():,.0f} 人")
    if missing_pop:
        log(f"  ⚠️ 有 {missing_pop} 个村缺失人口（代码未匹配上），请检查。")
    log(f"✅ 已输出：{config.FINAL_CSV}")
    log(f"✅ 已输出：{config.FINAL_GEOJSON}")
    return merged


if __name__ == "__main__":
    run()
