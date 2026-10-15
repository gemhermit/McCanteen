#!/usr/bin/env python3
"""决断引擎测试：打分、券加权、反重复、摇一摇确定性。"""
import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _util import check, finish, section  # noqa: E402

from mccanteen.decide import Context, _best_coupon, _score_option, decide  # noqa: E402
from mccanteen.fixtures import load_fixtures  # noqa: E402
from mccanteen.models import Coupon, Meal, Order, OrderItem  # noqa: E402

NOW = datetime(2026, 10, 15, 12, 30)  # 周四午餐档，固定时间保证可复现
fx = load_fixtures(now=NOW)

section("沉默成本识别")
d = decide(fx.meals, fx.coupons, fx.orders, now=NOW)
check(d.urgent_coupon_count == 2, "48h 内过期券 = 2 张（免费甜筒 20h + 满30减5 40h）")
check(d.silent_cost_yuan == 11.0, "沉默成本 = ¥11.00")
check("48 小时内过期" in d.verdict, "结论中提示沉默成本")

section("基础输出")
check(len(d.options) == 3, "返回 3 个候选")
check(all("lunch" in o.meal.slots for o in d.options), "午餐档只推午餐档可售餐品")
check(all(o.score > 0 for o in d.options), "候选均有正分")

section("预算硬过滤")
db = decide(fx.meals, fx.coupons, fx.orders, ctx=Context(budget=13), now=NOW)
check(all(o.meal.price <= 13 for o in db.options), "预算 ¥13 内只推 ¥13 以下餐品")

section("券加权与过期加急")
cone = fx.meal_by_code("99000015")
free_coupon = next(c for c in fx.coupons if c.id == "C2026-001")
score, reasons = _score_option(cone, free_coupon, Context(), "lunch", set(), {"99000015"}, set())
check(score >= 40, "免费甜筒券（20h 过期）得分 ≥ 40（券 25 + 过期加急 15）")
check(any("过期" in r for r in reasons), "理由中说明「用了就是止损」")
check(_best_coupon(cone, fx.coupons, "lunch")[0].id == "C2026-001", "甜筒命中免费甜筒券")

section("反重复惩罚")
burger = fx.meal_by_code("99000001")
recent = {"99000001"}  # 4 天前和 1 天前都点过板烧鸡腿堡
score_r, reasons_r = _score_option(burger, None, Context(avoid_repeat=True), "lunch", recent, {"99000001"}, set())
check(any("换换口味" in r for r in reasons_r), "7 天内吃过 → 换换口味")
score_nr, reasons_nr = _score_option(burger, None, Context(avoid_repeat=False), "lunch", recent, {"99000001"}, set())
check(score_nr > score_r, "关闭反重复后分数回升")
novel = fx.meal_by_code("99000006")  # 不素之霸，44 天前点过 → 不在 7 天窗口
score_n, reasons_n = _score_option(novel, None, Context(), "lunch", set(), {"99000006"}, set())
check(not any("换换口味" in r for r in reasons_n), "窗口外订单不触发反重复")

section("处境匹配")
dlight = decide(fx.meals, fx.coupons, fx.orders, ctx=Context(text="刚健完身，想低卡"), now=NOW)
check(
    any(("低卡" in r or "高蛋白" in r) for o in dlight.options for r in o.reasons),
    "「低卡」处境 → 候选出现低卡/高蛋白理由",
)
dcoffee = decide(fx.meals, fx.coupons, fx.orders, ctx=Context(text="困了想喝咖啡提神"), now=NOW)
check(
    any("咖啡" in o.meal.name for o in dcoffee.options[:2]),
    "「咖啡」处境 → 前二出现咖啡",
)

section("摇一摇确定性（可注入随机源）")
ctx = Context()
p1 = decide(fx.meals, fx.coupons, fx.orders, ctx=ctx, now=NOW, rng=random.Random(42), shake=True)
p2 = decide(fx.meals, fx.coupons, fx.orders, ctx=ctx, now=NOW, rng=random.Random(42), shake=True)
check(p1.options[0].meal.code == p2.options[0].meal.code, "同一随机种子 → 同一结果（可测试）")
check(p1.shake is True, "shake 模式标记")
candidates = {m.code for m in fx.meals if "lunch" in m.slots}
check(p1.options[0].meal.code in candidates, "摇一摇结果在合格候选池内")

section("时段覆盖")
dtea = decide(fx.meals, fx.coupons, fx.orders, ctx=Context(slot="breakfast"), now=NOW)
check(dtea.slot.key == "breakfast", "可覆盖时段为早餐")
check(all("breakfast" in o.meal.slots for o in dtea.options), "早餐档只推早餐档餐品")

finish()
