#!/usr/bin/env python3
"""models 单元测试：单位换算与券适用性。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _util import check, finish, section  # noqa: E402

from mccanteen.models import (  # noqa: E402
    Coupon,
    Meal,
    Order,
    OrderItem,
    fen_to_yuan,
    fmt_yuan,
    yuan_to_fen,
)
from datetime import datetime  # noqa: E402

section("单位换算")
check(fen_to_yuan(2050) == 20.5, "2050 分 = ¥20.5")
check(yuan_to_fen(20.5) == 2050, "¥20.5 = 2050 分")
check(fmt_yuan(20.5) == "¥20.5", "fmt_yuan(20.5) = ¥20.5")
check(fmt_yuan(13.0) == "¥13", "fmt_yuan(13) = ¥13（不拖尾零）")
check(fen_to_yuan(0) == 0.0, "0 分 = ¥0")

section("优惠券适用性")
burger = Meal(code="B1", name="板烧鸡腿堡", category="汉堡", price_fen=2050)
fries = Meal(code="F1", name="薯条（大）", category="小食", price_fen=1300)

manjian = Coupon(id="c1", title="满30减5", kind="满减", value_fen=500, min_spend_fen=3000)
combo = Meal(code="M1", name="板烧鸡腿堡套餐", category="套餐", price_fen=3150)
check(manjian.benefit_fen(combo) == 500, "满30减5 对 ¥31.5 套餐适用，省 500 分")
check(manjian.benefit_fen(burger) == 0, "满30减5 对 ¥20.5 餐品不适用（未达门槛）")
check(manjian.benefit_fen(fries) == 0, "满30减5 对 ¥13 餐品不适用（未达门槛）")

free = Coupon(id="c2", title="免费甜筒", kind="免费", value_fen=600, applies_to=("T1",))
cone = Meal(code="T1", name="甜筒", category="甜品", price_fen=600)
check(free.benefit_fen(cone) == 600, "免费券对指定餐品适用")
check(free.benefit_fen(burger) == 0, "免费券对非指定餐品不适用")

breakfast_coupon = Coupon(id="c3", title="早餐档满15减3", kind="满减", value_fen=300, min_spend_fen=1500, slots=("breakfast",))
check(breakfast_coupon.benefit_fen(burger, "breakfast") == 300, "早餐券在早餐档适用")
check(breakfast_coupon.benefit_fen(burger, "lunch") == 0, "早餐券在午餐档不适用")

check(manjian.face_value == 5.0, "券面价值 = 500 分 = ¥5")

section("订单热量汇总")
order = Order(
    id="o1",
    created_at=datetime(2026, 10, 1, 12, 0),
    items=(
        OrderItem(code="B1", name="板烧鸡腿堡", qty=1, price_fen=2050, kcal=420),
        OrderItem(code="F1", name="薯条（大）", qty=2, price_fen=1300, kcal=340),
    ),
    total_fen=4650,
)
check(order.kcal == 1100, "订单热量 = 420 + 340×2 = 1100")
check(order.total == 46.5, "订单总额 4650 分 = ¥46.5")
check(order.codes() == ("B1", "F1"), "订单餐品编码序列")

finish()
