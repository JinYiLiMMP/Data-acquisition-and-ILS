"""
Step 1 · 门头沟区高程数据
==========================

技术路线：``高程数据(2片SRTM)`` + ``门头沟区行政边界`` --裁剪--> ``门头沟区高程数据``

实现：
  1. 用 rasterio.merge 把 srtm_60_04 / srtm_60_05 两片 DEM 镶嵌成一张覆盖门头沟的 DEM
  2. 用门头沟区行政边界对镶嵌结果做掩膜裁剪（区界外置为 nodata）
  3. 输出 GeoTIFF：output/mentougou_dem.tif
"""

from __future__ import annotations

import geopandas as gpd
import rasterio
from rasterio.mask import mask as rio_mask
from rasterio.merge import merge as rio_merge

import config
from common import banner, log


def run() -> None:
    banner("Step 1 · 生成门头沟区高程数据（SRTM 镶嵌 + 区界裁剪）")

    # 1) 读取两片 SRTM 并镶嵌
    srcs = [rasterio.open(p) for p in config.SRTM_TILES]
    try:
        for p, s in zip(config.SRTM_TILES, srcs):
            log(f"  读取 DEM：{p.name}  size={s.width}x{s.height}  crs={s.crs}")
        mosaic, mosaic_transform = rio_merge(srcs)
        meta = srcs[0].meta.copy()
        nodata = srcs[0].nodata
    finally:
        for s in srcs:
            s.close()
    log(f"  镶嵌完成：mosaic shape={mosaic.shape}")

    # 2) 读取门头沟区界（与 DEM 同为 EPSG:4326）
    district = gpd.read_file(config.DISTRICT_BOUNDARY).to_crs(config.TARGET_CRS)
    geoms = list(district.geometry)

    # 3) 用区界裁剪镶嵌结果
    meta.update(
        height=mosaic.shape[1],
        width=mosaic.shape[2],
        transform=mosaic_transform,
        count=mosaic.shape[0],
        crs=config.TARGET_CRS,
    )
    # rio_mask 需要一个打开的 dataset，这里写入内存数据集再裁剪
    from rasterio.io import MemoryFile

    with MemoryFile() as memfile:
        with memfile.open(**meta) as tmp:
            tmp.write(mosaic)
        with memfile.open() as tmp:
            clipped, clip_transform = rio_mask(
                tmp, geoms, crop=True, nodata=nodata
            )

    out_meta = meta.copy()
    out_meta.update(
        height=clipped.shape[1],
        width=clipped.shape[2],
        transform=clip_transform,
        nodata=nodata,
        compress="lzw",
    )

    with rasterio.open(config.DEM_OUT, "w", **out_meta) as dst:
        dst.write(clipped)

    # 简单统计
    band = clipped[0]
    valid = band[band != nodata]
    log(f"  裁剪后高程范围：{int(valid.min())} ~ {int(valid.max())} m"
        f"（有效像元 {valid.size}）")
    log(f"✅ 已输出：{config.DEM_OUT}")


if __name__ == "__main__":
    run()
