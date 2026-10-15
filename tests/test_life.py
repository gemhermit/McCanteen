#!/usr/bin/env python3
"""麦门人生测试：统计、等级、属性、成就。"""
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _util import check, finish, section  # noqa: E402

from mccanteen.fixtures import load_fixtures  # noqa: E402
from mccanteen.life import level_for, life_profile  # noqa: E402

NOW = datetime(2026, 10, 15, 12, 30)
fx = load_fixtures(now=NOW)
p = life_profile(fx.orders, now=NOW)

section("基础统计")
check(p.total_orders == 26, "26 笔订单")
check(p.maling_days == 88, "麦龄 88 天")
check(p.total_yuan == 722.0, "总消费 ¥722")
check(p.avg_order_yuan == 27.77, "客单价 ¥27.77")
check(p.unique_items == 23, "23 个不同单品")
check(p.line_items == 43, "43 件次")
check(("板烧鸡腿堡", 5) in p.top_items, "板烧鸡腿堡 ×5 进入 TOP3")
check(len(p.top_items) == 3, "TOP3 共 3 项")

section("等级与属性")
check(p.level_no == 3 and p.level_name == "麦农", "26 单 → Lv.3 麦农")
check(level_for(0) == (1, "麦芽"), "0 单 → Lv.1 麦芽")
check(level_for(200) == (7, "麦门之主"), "200 单 → Lv.7 麦门之主")
check(level_for(199) == (6, "麦门长老"), "199 单 → Lv.6 麦门长老")
check(0 <= p.attrs.食力 <= 100 and p.attrs.食力 == 87, "食力 87")
check(p.attrs.财力 == 48, "财力 48")
check(p.attrs.广度 == 53, "广度 53")
check(0 <= p.attrs.信仰 <= 100, "信仰在 0-100 区间")
check(re.fullmatch(r"MCN-2026-[0-9A-F]{4}", p.serial) is not None, "编号格式 MCN-2026-XXXX")

section("成就")
for a in ["晨型人", "三点几达人", "守夜人", "探店家", "麦门元老", "团建担当", "稳定输出"]:
    check(a in p.achievements, f"解锁「{a}」")

section("空档案")
e = life_profile([], now=NOW)
check(e.total_orders == 0 and e.level_no == 1, "无订单 → Lv.1 麦芽")
check(e.serial == "MCN-2026-0000", "无订单 → 默认编号")
check(e.achievements == [], "无订单 → 无成就")

finish()
