"""决断引擎：3 秒回答「今天吃什么」。

打分逻辑（权重见 references/decide-rules.md）：
1. 券加权：能用上的券 +25，其中 48 小时内过期的再加 +15（用了就是止损）
2. 反重复：7 天内吃过 -20；从没点过 +5（舒适区挑战）
3. 处境匹配：处境关键词 → 餐品方向（低卡 / 慰藉 / 解渴 / 分享 / 提神）
4. 预算与时段为硬过滤；预算内无解时自动放宽并如实说明

所有价格来自 MCP 真实计价或 fixtures 演示数据，引擎不猜价格。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Sequence, Set

from . import timeslots
from .models import Coupon, Meal, Order, fen_to_yuan, fmt_yuan

REPEAT_WINDOW_DAYS = 7
URGENT_HOURS = 48

# 处境关键词 → 餐品方向
CONTEXT_RULES = [
    (("健身", "减脂", "减肥", "低卡", "控卡", "轻食", "沙拉"), "light"),
    (("累", "加班", "熬夜", "emo", "低落", "烦躁", "垮", "心累"), "comfort"),
    (("渴", "热", "喝水", "饮料", "可乐", "想喝", "喝点", "喝什么", "喝啥"), "drink"),
    (("请客", "聚餐", "团建", "分享", "聚会"), "share"),
    (("困", "提神", "咖啡", "犯困"), "coffee"),
]


@dataclass
class Context:
    text: str = ""                 # 处境自然语言，如「加班到九点好累」
    budget: Optional[float] = None  # 元
    slot: Optional[str] = None      # 覆盖时段，缺省按当前时间
    avoid_repeat: bool = True


@dataclass
class Option:
    meal: Meal
    coupon: Optional[Coupon]
    net_price: float                # 用券后实付（元）
    score: float
    reasons: List[str] = field(default_factory=list)


@dataclass
class Decision:
    slot: timeslots.Slot
    persona: str
    options: List[Option]
    shake: bool
    silent_cost_yuan: float
    urgent_coupon_count: int
    verdict: str
    unknown_face_count: int = 0
    budget_relaxed: bool = False


def match_wants(text: str) -> Set[str]:
    wants: Set[str] = set()
    for words, want in CONTEXT_RULES:
        if any(w in text for w in words):
            wants.add(want)
    return wants


def _score_option(
    meal: Meal,
    coupon: Optional[Coupon],
    ctx: Context,
    slot_key: str,
    recent_codes: Set[str],
    tried_codes: Set[str],
    wants: Set[str],
) -> "tuple[float, List[str]]":
    score = 0.0
    reasons: List[str] = []

    if coupon is not None:
        benefit = fen_to_yuan(coupon.benefit_fen(meal, slot_key))
        if benefit > 0:
            score += 25
            reasons.append(f"可用「{coupon.title}」，省 {fmt_yuan(benefit)}")
            if coupon.hours_left is not None and coupon.hours_left <= URGENT_HOURS:
                score += 15
                reasons.append(f"该券 {int(coupon.hours_left)} 小时内过期，用了就是止损")

    if ctx.avoid_repeat and meal.code in recent_codes:
        score -= 20
        reasons.append("最近 7 天吃过了，换换口味")
    elif ctx.avoid_repeat and meal.code not in tried_codes:
        score += 5
        reasons.append("没点过，试试新菜单")

    if "light" in wants:
        if meal.kcal and meal.kcal <= 450:
            score += 12
            reasons.append("低卡")
        if meal.protein_g >= 15:
            score += 8
            reasons.append("高蛋白")
    if "comfort" in wants:
        if meal.kcal >= 400 or meal.is_combo:
            score += 8
            reasons.append("热量管够，抚慰加班魂")
    if "drink" in wants and meal.category == "饮品":
        score += 50
        reasons.append("解渴")
    if "share" in wants and (meal.is_combo or meal.category in ("小食", "甜品")):
        score += 10
        reasons.append("适合分享")
    if "coffee" in wants and "咖啡" in meal.name:
        score += 50
        reasons.append("提神")

    return score, reasons


def _best_coupon(meal: Meal, coupons: Sequence[Coupon], slot_key: str) -> "tuple[Optional[Coupon], int]":
    best: Optional[Coupon] = None
    best_benefit = 0
    for c in coupons:
        b = c.benefit_fen(meal, slot_key)
        if b > best_benefit:
            best, best_benefit = c, b
    return best, best_benefit


def decide(
    meals: Sequence[Meal],
    coupons: Sequence[Coupon],
    orders: Sequence[Order],
    ctx: Optional[Context] = None,
    now: Optional[datetime] = None,
    rng=None,
    shake: bool = False,
) -> Decision:
    import secrets

    now = now or datetime.now()
    ctx = ctx or Context()
    slot = timeslots.slot_by_key(ctx.slot) if ctx.slot else timeslots.slot_for(now)

    urgent = [c for c in coupons if c.hours_left is not None and c.hours_left <= URGENT_HOURS]
    silent_cost = sum(c.face_value for c in urgent if c.face_known)
    unknown_face = sum(1 for c in urgent if not c.face_known)

    recent_cutoff = now - timedelta(days=REPEAT_WINDOW_DAYS)
    recent_codes = {code for o in orders if o.created_at >= recent_cutoff for code in o.codes()}
    tried_codes = {code for o in orders for code in o.codes()}

    candidates = [m for m in meals if slot.key in m.slots]
    budget_relaxed = False
    if ctx.budget:
        in_budget = [m for m in candidates if m.price <= ctx.budget]
        if in_budget:
            candidates = in_budget
        else:
            budget_relaxed = True  # 预算内无解，如实放宽

    wants = match_wants(ctx.text)
    scored: List[Option] = []
    for m in candidates:
        coupon, benefit = _best_coupon(m, coupons, slot.key)
        score, reasons = _score_option(m, coupon, ctx, slot.key, recent_codes, tried_codes, wants)
        scored.append(
            Option(
                meal=m,
                coupon=coupon,
                net_price=round(m.price - fen_to_yuan(benefit), 2),
                score=score,
                reasons=reasons,
            )
        )
    scored.sort(key=lambda o: (-o.score, o.meal.price))

    if shake:
        pool = scored[:5] or scored
        pick = (rng or secrets.SystemRandom()).choice(pool)
        top = [pick] + [o for o in scored if o is not pick][:2]
    else:
        top = scored[:3]

    if not top:
        verdict = "这个时段门店没有可售餐品，先看看活动日历吧。"
    else:
        winner = top[0].meal.name
        verdict = f"食堂大叔拍板：{winner}。{slot.persona}".rstrip("。")
        if urgent:
            parts = [f"你有 {len(urgent)} 张券 48 小时内过期"]
            if silent_cost > 0:
                parts.append(f"已核实面值 {fmt_yuan(silent_cost)}")
            if unknown_face:
                parts.append(f"{unknown_face} 张面值待核实")
            verdict += "（另外，" + "，".join(parts) + "，别让它蒸发了）"
        if budget_relaxed:
            verdict += "（预算内没有可点的，已放宽预算，量力而行）"

    return Decision(
        slot=slot,
        persona=slot.persona,
        options=top,
        shake=shake,
        silent_cost_yuan=round(silent_cost, 2),
        urgent_coupon_count=len(urgent),
        unknown_face_count=unknown_face,
        verdict=verdict,
        budget_relaxed=budget_relaxed,
    )
