"""
一键运行全流程 / Run the whole pipeline
========================================

按技术路线图顺序执行 step1 ~ step5，并在开始前检查输入数据完整性。
中间产物在各步之间通过内存对象传递（同时也会落地到 output/）。

用法：
    python run_all.py
"""

from __future__ import annotations

import sys

import config
import step1_elevation
import step2_villages
import step3_population
import step4_coordinates
import step5_merge
import step6_loss_probability
from common import banner, log


def main() -> int:
    banner("门头沟区 村级人口——经纬度 数据生成流程")

    missing = config.check_inputs()
    if missing:
        log("❌ 缺失以下输入数据，请检查 data 目录：")
        for p in missing:
            log(f"   - {p}")
        return 1
    log(f"  输入数据目录：{config.DATA_DIR}")
    log(f"  输出目录：    {config.OUTPUT_DIR}")
    if not config.AMAP_KEY:
        log("  提示：未设置 AMAP_KEY，step4 将使用多边形质心坐标（流程仍可完成）。")

    # 上半支：高程
    step1_elevation.run()

    # 下半支：村界 → 人口 / 坐标 → 合并
    villages = step2_villages.run()
    pop = step3_population.run(villages)
    coords = step4_coordinates.run(villages)
    final_df = step5_merge.run(pop, coords)

    # 应用：海拔 → 洪灾失联概率（含数据清洗）
    step6_loss_probability.run(final_df)

    banner("✅ 全流程完成，成果见 output/ 目录")
    return 0


if __name__ == "__main__":
    sys.exit(main())
