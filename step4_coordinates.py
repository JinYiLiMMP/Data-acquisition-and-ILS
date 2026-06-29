"""
Step 4 · 门头沟区各村级行政区经纬度
====================================

技术路线：``门头沟区村级行政区代码`` --高德API查询--> ``门头沟区各村级行政区经纬度``

实现：
  1. 取各村清洗后村名 + 门头沟区 adcode(110109) 调用高德地理编码 API
  2. 高德返回 GCJ-02 坐标，转回 WGS84
  3. 若 API 失败 / 未配置 Key / 匹配过粗，回退到村多边形质心坐标，
     并用 coord_source 列标注来源（amap / centroid）

注意：高德 Key 仅从环境变量 AMAP_KEY 读取，不写入仓库。
未设置 Key 时本步骤自动全部使用多边形质心，保证流程可跑通。
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
import requests

import config
from common import banner, gcj02_to_wgs84, haversine_m, log

# 视为"精确到村级"的高德匹配级别
PRECISE_LEVELS = {"村庄", "村委会"}


def _geocode(session: requests.Session, name: str) -> dict:
    """调用高德地理编码，返回 WGS84 坐标与匹配级别。"""
    params = {
        "key": config.AMAP_KEY,
        "address": name,
        "city": config.MENTOUGOU_ADCODE,
        "output": "json",
    }
    try:
        resp = session.get(config.AMAP_GEOCODE_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "1" and int(data.get("count", 0)) > 0:
            geo = data["geocodes"][0]
            lng_gcj, lat_gcj = map(float, geo["location"].split(","))
            lng, lat = gcj02_to_wgs84(lng_gcj, lat_gcj)
            return {
                "lon_amap": lng,
                "lat_amap": lat,
                "amap_level": geo.get("level", ""),
                "amap_address": geo.get("formatted_address", ""),
                "amap_status": "ok",
            }
        return {"amap_status": "no_result"}
    except Exception as exc:  # noqa: BLE001 - 单条失败不应中断整体
        return {"amap_status": f"error:{exc}"}


def run(villages: gpd.GeoDataFrame | None = None) -> pd.DataFrame:
    banner("Step 4 · 高德 API 查询各村经纬度（GCJ-02 → WGS84，质心兜底）")

    if villages is None:
        villages = gpd.read_file(config.VILLAGES_OUT)
    villages = villages.to_crs(config.TARGET_CRS)

    # 多边形质心（兜底坐标）。用等积投影算质心更稳，再转回经纬度。
    cent = villages.to_crs("EPSG:3857").geometry.centroid.to_crs(config.TARGET_CRS)
    villages = villages.assign(lon_centroid=cent.x.round(6),
                               lat_centroid=cent.y.round(6))

    use_api = bool(config.AMAP_KEY)
    if not use_api:
        log("  ⚠️ 未检测到环境变量 AMAP_KEY，本步骤全部使用多边形质心坐标。")

    records = []
    session = requests.Session()
    total = len(villages)
    import time

    for i, row in villages.reset_index(drop=True).iterrows():
        rec = {
            "XZQDM": row["XZQDM"],
            "XZQMC": row["XZQMC"],
            "lon_centroid": row["lon_centroid"],
            "lat_centroid": row["lat_centroid"],
            "lon_amap": None,
            "lat_amap": None,
            "amap_level": "",
            "amap_address": "",
            "amap_status": "skipped",
            "offset_m": None,
        }

        if use_api:
            res = _geocode(session, row["village_name_clean"])
            rec.update(res)
            if res.get("amap_status") == "ok":
                rec["offset_m"] = haversine_m(
                    row["lon_centroid"], row["lat_centroid"],
                    res["lon_amap"], res["lat_amap"],
                )
            time.sleep(config.AMAP_DELAY)

        # 最终坐标：高德精确到村级则用高德，否则回退质心
        if rec["amap_status"] == "ok" and rec["amap_level"] in PRECISE_LEVELS:
            rec["lon"], rec["lat"], rec["coord_source"] = (
                rec["lon_amap"], rec["lat_amap"], "amap")
        else:
            rec["lon"], rec["lat"], rec["coord_source"] = (
                row["lon_centroid"], row["lat_centroid"], "centroid")

        records.append(rec)
        if (i + 1) % 40 == 0 or (i + 1) == total:
            log(f"    进度 {i + 1}/{total}")

    df = pd.DataFrame(records)
    df.to_csv(config.COORDS_OUT, index=False, encoding="utf-8-sig")

    n_amap = (df["coord_source"] == "amap").sum()
    log(f"  高德村级精确匹配：{n_amap} / {total}，其余使用质心兜底")
    log(f"✅ 已输出：{config.COORDS_OUT}")
    return df


if __name__ == "__main__":
    run()
