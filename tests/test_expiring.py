#!/usr/bin/env python3
"""止损雷达测试：分桶、沉默成本、结论文案。"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _util import check, finish, section  # noqa: E402

from mccanteen.expiring import expiring_report  # noqa: E402
from mccanteen.fixtures import load_fixtures  # noqa: E402
from mccanteen.models import Account, Coupon  # noqa: E402

NOW = datetime(2026, 10, 15, 12, 30)
fx = load_fixtures(now=NOW)
report = expiring_report(fx.coupons, fx.account, now=NOW)

section("分桶")
b24, b48, b7d = report.buckets
check(len(b24.coupons) == 1, "24h 内：1 张（免费甜筒 20h）")
check(len(b48.coupons) == 1, "48h 内：1 张（满30减5 40h）")
check(len(b7d.coupons) == 3, "7 天内：3 张（早餐券 68h + 薯条买一送一 120h + 9.9元券 150h）")
check(report.long_term_count == 2, "长期有效：2 张（300h / 400h）")

section("沉默成本")
check(report.silent_cost_yuan == 11.0, "48h 内沉默成本 = ¥6 + ¥5 = ¥11")
check("48 小时内过期" in report.verdict, "结论包含 48 小时口径")
check("¥11" in report.verdict, "结论包含金额")
check("1200 积分" in report.verdict, "结论包含即将过期积分")

section("边界")
empty = expiring_report([], Account(available_points=100), now=NOW)
check(empty.silent_cost_yuan == 0.0, "无券 → 沉默成本 0")
check("安心吃" in empty.verdict, "无券 → 安心吃")

only_points = expiring_report([], Account(available_points=100, expiring_points=500, expiring_in_hours=48), now=NOW)
check("500 积分" in only_points.verdict, "仅积分过期 → 提示积分")

long_only = expiring_report(
    [Coupon(id="x", title="长期券", kind="满减", value_fen=100, min_spend_fen=100, hours_left=None)],
    Account(available_points=0),
    now=NOW,
)
check(long_only.silent_cost_yuan == 0.0 and long_only.long_term_count == 1, "长期券不计入沉默成本")

finish()
