"""
Step 2 · 门头沟区村级行政区边界
================================

技术路线：``北京市村级行政区边界`` --按门头沟区代码110109检索--> ``门头沟区村级行政区边界``

实现：
  1. 读取北京市村级行政区边界 shapefile（含 XZQDM 代码、XZQMC 村名）
  2. 按 XZQDM 前缀 110109 筛出门头沟区村级行政区
  3. 输出 GeoJSON：output/mentougou_villages.geojson（同时落地村代码清单）
"""

from __future__ import annotations

import geopandas as gpd

import config
from common import banner, clean_village_name, log


def run() -> gpd.GeoDataFrame:
    banner("Step 2 · 检索门头沟区村级行政区边界（XZQDM 前缀 110109）")

    gdf = gpd.read_file(config.VILLAGE_BOUNDARIES)
    if gdf.crs is None:
        gdf = gdf.set_crs(config.TARGET_CRS)
    else:
        gdf = gdf.to_crs(config.TARGET_CRS)
    log(f"  北京市村级行政区总数：{len(gdf)}")

    gdf["XZQDM"] = gdf["XZQDM"].astype(str).str.strip()
    mtg = gdf[gdf["XZQDM"].str.startswith(config.MENTOUGOU_ADCODE)].copy()
    mtg = mtg.reset_index(drop=True)
    log(f"  门头沟区（110109）村级行政区：{len(mtg)}")

    # 整理输出字段：代码、原始村名、清洗后村名（供地理编码用）
    mtg["XZQMC"] = mtg["XZQMC"].astype(str).str.strip()
    mtg["village_name_clean"] = mtg["XZQMC"].apply(clean_village_name)

    keep = ["XZQDM", "XZQMC", "village_name_clean", "geometry"]
    if "BSM" in mtg.columns:
        keep.insert(0, "BSM")
    mtg = mtg[keep]

    mtg.to_file(config.VILLAGES_OUT, driver="GeoJSON")
    log(f"✅ 已输出：{config.VILLAGES_OUT}")
    return mtg


if __name__ == "__main__":
    run()
