"""
公共工具 / Shared utilities
============================

- 统一的日志打印（带步骤标题）
- GCJ-02（高德/火星坐标）→ WGS84 坐标纠偏
- WGS84 两点球面距离（Haversine，单位米）
- 村名清洗（用于高德地理编码查询）
"""

from __future__ import annotations

import math
import re
import sys


# ── 日志 ──────────────────────────────────────────────────────────────
def banner(title: str) -> None:
    """打印步骤标题分隔线。"""
    line = "=" * 64
    print(f"\n{line}\n{title}\n{line}", flush=True)


def log(msg: str) -> None:
    print(msg, flush=True)


# ── GCJ-02 → WGS84 坐标纠偏 ───────────────────────────────────────────
# 高德返回的是 GCJ-02（国测局加密）坐标，需转回 WGS84 真实经纬度。
_A = 6378245.0                      # 克拉索夫斯基椭球长半轴
_EE = 0.00669342162296594323        # 偏心率平方


def _transform_lat(lng: float, lat: float) -> float:
    ret = (-100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat
           + 0.1 * lng * lat + 0.2 * math.sqrt(abs(lng)))
    ret += (20.0 * math.sin(6.0 * lng * math.pi)
            + 20.0 * math.sin(2.0 * lng * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * math.pi)
            + 40.0 * math.sin(lat / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * math.pi)
            + 320 * math.sin(lat * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(lng: float, lat: float) -> float:
    ret = (300.0 + lng + 2.0 * lat + 0.1 * lng * lng
           + 0.1 * lng * lat + 0.1 * math.sqrt(abs(lng)))
    ret += (20.0 * math.sin(6.0 * lng * math.pi)
            + 20.0 * math.sin(2.0 * lng * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * math.pi)
            + 40.0 * math.sin(lng / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * math.pi)
            + 300.0 * math.sin(lng / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def gcj02_to_wgs84(lng: float, lat: float) -> tuple[float, float]:
    """GCJ-02 经纬度 → WGS84 经纬度。"""
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = 1 - _EE * math.sin(radlat) ** 2
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (_A / sqrtmagic * math.cos(radlat) * math.pi)
    return round(lng - dlng, 6), round(lat - dlat, 6)


# ── 球面距离 ──────────────────────────────────────────────────────────
def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """两 WGS84 坐标点间球面距离（米）。"""
    r = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return round(2 * r * math.asin(math.sqrt(a)), 1)


# ── 村名清洗 ──────────────────────────────────────────────────────────
# 部分村名带省/市/区/镇前缀，去掉后用最短村名查询高德更准。
_PREFIX_RE = re.compile(
    r"^(北京市)?门头沟区"
    r"(东辛房街道|大峪街道|城子街道|永定镇|龙泉镇|军庄镇|潭柘寺镇|王平地区|"
    r"妙峰山镇|雁翅镇|斋堂镇|清水镇|大台街道|王平镇|斋堂地区|清水地区)?"
)


def clean_village_name(raw: str) -> str:
    """去掉行政前缀，保留最短村名（用于地理编码查询）。"""
    name = str(raw).strip()
    cleaned = _PREFIX_RE.sub("", name).strip()
    return cleaned or name
