"""
Step 6 · 村庄海拔 → 洪灾失联概率（含数据清洗）
================================================

在 step5 最终成果基础上，按村庄海拔反推「洪灾失联概率」（海拔越低概率越高），
并在建模前做数据清洗。

数据清洗（依次执行，逐条记录剔除原因）：
  ① 剔除"没查到经纬度"的村：高德未返回任何地理编码结果（lon_amap 为空）
  ② 剔除不在门头沟区行政边界内的村：用最终坐标做点-面内含判定
  ③ 剔除无有效高程的村：采样落在 DEM 栅格外或为 nodata

失联概率模型（指数衰减）：
    prob = p_min + (p_max - p_min) * exp(-elev / H)
    p_min=0.05, p_max=0.95, H 默认取有效村庄海拔中位数（见 config）

另输出抽样权重 selection_weight = exp(-elev/H) 归一化（Σ=1），
可用于 np.random.choice 加权抽取 k 个失联村。
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import Point

import config
from common import banner, log


def _sample_elevation(coords, dem_path):
    """在给定经纬度处采样 DEM 高程，返回 (elev数组, nodata, bounds)。"""
    with rasterio.open(dem_path) as src:
        elev = np.array([v[0] for v in src.sample(coords)], dtype="float64")
        return elev, src.nodata, src.bounds


def run(final_df: pd.DataFrame | None = None) -> pd.DataFrame:
    banner("Step 6 · 数据清洗 + 海拔反推洪灾失联概率")

    if final_df is None:
        final_df = pd.read_csv(config.FINAL_CSV, dtype={"XZQDM": str})
    df = final_df.copy()
    n0 = len(df)
    log(f"  输入村庄：{n0} 个")

    # ── 清洗① 剔除没查到经纬度（高德无地理编码结果）的村 ──────────────
    has_geocode = df["lon_amap"].notna() & df["lat_amap"].notna()
    dropped1 = df[~has_geocode]
    df = df[has_geocode].copy()
    log(f"  ① 剔除无地理编码结果：{len(dropped1)} 个 → 剩 {len(df)}")

    # ── 清洗② 剔除不在门头沟区边界内的村（点-面内含判定）──────────────
    district = gpd.read_file(config.DISTRICT_BOUNDARY).to_crs(config.TARGET_CRS)
    area = district.geometry.union_all() if hasattr(district.geometry, "union_all") \
        else district.geometry.unary_union
    pts = gpd.GeoSeries(
        [Point(xy) for xy in zip(df["lon"], df["lat"])], crs=config.TARGET_CRS
    )
    inside = pts.within(area).values
    dropped2 = df[~inside]
    df = df[inside].copy()
    log(f"  ② 剔除门头沟区边界外：{len(dropped2)} 个 → 剩 {len(df)}")

    # ── 采样高程 + 清洗③ 剔除无有效高程的村 ──────────────────────────
    coords = list(zip(df["lon"], df["lat"]))
    elev, nodata, bounds = _sample_elevation(coords, config.DEM_OUT)
    elev[elev == nodata] = np.nan
    in_raster = (
        (df["lon"] >= bounds.left) & (df["lon"] <= bounds.right)
        & (df["lat"] >= bounds.bottom) & (df["lat"] <= bounds.top)
    ).values
    elev[~in_raster] = np.nan
    df["elevation_m"] = elev
    dropped3 = df[df["elevation_m"].isna()]
    df = df[df["elevation_m"].notna()].copy()
    log(f"  ③ 剔除无有效高程：{len(dropped3)} 个 → 剩 {len(df)}")

    # ── 失联概率（指数衰减）──────────────────────────────────────────
    h = config.LOSS_H if config.LOSS_H else float(np.median(df["elevation_m"]))
    p_min, p_max = config.LOSS_P_MIN, config.LOSS_P_MAX
    log(f"  模型参数：p_min={p_min}, p_max={p_max}, H={h:.1f} m"
        f"（{'config 指定' if config.LOSS_H else '自动=海拔中位数'}）")

    df["loss_probability"] = (
        p_min + (p_max - p_min) * np.exp(-df["elevation_m"] / h)
    ).round(4)

    # 抽样权重：脆弱性分数归一化（Σ=1）
    score = np.exp(-df["elevation_m"] / h)
    df["selection_weight"] = (score / score.sum()).round(8)

    df["elevation_m"] = df["elevation_m"].round(0).astype(int)

    # 人口数据向上取整（人数为整数，估计值偏向保守取上界）
    df["population_est"] = np.ceil(df["population_est"]).astype("Int64")

    # ── 输出 ─────────────────────────────────────────────────────────
    out_cols = [
        "XZQDM", "XZQMC", "population_est",
        "lon", "lat", "coord_source",
        "elevation_m", "loss_probability", "selection_weight",
    ]
    out = df[out_cols].copy()
    out.to_csv(config.LOSS_CSV, index=False, encoding="utf-8-sig")

    gdf = gpd.GeoDataFrame(
        out,
        geometry=[Point(xy) for xy in zip(out["lon"], out["lat"])],
        crs=config.TARGET_CRS,
    )
    gdf.to_file(config.LOSS_GEOJSON, driver="GeoJSON")

    # ── 概况 ─────────────────────────────────────────────────────────
    log(f"  清洗汇总：{n0} → {len(out)}（共剔除 {n0 - len(out)} 个）")
    log(f"  海拔  min/median/max: {out.elevation_m.min()} / "
        f"{int(out.elevation_m.median())} / {out.elevation_m.max()} m")
    log(f"  失联概率 min/median/max: {out.loss_probability.min():.3f} / "
        f"{out.loss_probability.median():.3f} / {out.loss_probability.max():.3f}")
    log(f"  抽样权重之和：{out.selection_weight.sum():.6f}")
    log("  最易失联(海拔最低) 5 村：")
    top = out.nlargest(5, "loss_probability")[
        ["XZQMC", "elevation_m", "loss_probability"]]
    for _, r in top.iterrows():
        log(f"    {r['XZQMC']:<16s} {r['elevation_m']:>5d} m  "
            f"P={r['loss_probability']:.3f}")
    log(f"✅ 已输出：{config.LOSS_CSV}")
    log(f"✅ 已输出：{config.LOSS_GEOJSON}")
    return out


if __name__ == "__main__":
    run()
