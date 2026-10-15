#!/usr/bin/env python3
"""时段判断测试：边界值全覆盖。"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _util import check, finish, section  # noqa: E402

from mccanteen import timeslots  # noqa: E402

CASES = [
    (datetime(2026, 10, 15, 5, 0), "breakfast", "05:00 早餐档开始"),
    (datetime(2026, 10, 15, 8, 30), "breakfast", "08:30 早餐"),
    (datetime(2026, 10, 15, 10, 29), "breakfast", "10:29 早餐档最后一分钟"),
    (datetime(2026, 10, 15, 10, 30), "lunch", "10:30 切午餐档"),
    (datetime(2026, 10, 15, 12, 0), "lunch", "12:00 午餐"),
    (datetime(2026, 10, 15, 13, 59), "lunch", "13:59 午餐档最后一分钟"),
    (datetime(2026, 10, 15, 14, 0), "tea", "14:00 切下午茶"),
    (datetime(2026, 10, 15, 15, 30), "tea", "15:30 下午茶"),
    (datetime(2026, 10, 15, 16, 59), "tea", "16:59 下午茶最后一分钟"),
    (datetime(2026, 10, 15, 17, 0), "dinner", "17:00 切晚餐档"),
    (datetime(2026, 10, 15, 20, 59), "dinner", "20:59 晚餐档最后一分钟"),
    (datetime(2026, 10, 15, 21, 0), "latenight", "21:00 切夜宵档"),
    (datetime(2026, 10, 15, 23, 59), "latenight", "23:59 夜宵"),
    (datetime(2026, 10, 15, 2, 0), "latenight", "02:00 跨午夜夜宵"),
    (datetime(2026, 10, 15, 4, 59), "latenight", "04:59 夜宵档最后一分钟"),
]

section("时段边界")
for dt, expect, msg in CASES:
    check(timeslots.slot_for(dt).key == expect, msg)

section("工具函数")
check(timeslots.slot_by_key("tea").label == "下午茶", "slot_by_key(tea).label = 下午茶")
check(len(timeslots.all_slots()) == 5, "共 5 个时段")
check(timeslots.slot_for(datetime(2026, 10, 15, 12, 0)).persona != "", "每个时段都有台词")

finish()
