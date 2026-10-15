"""麦门人生：从真实订单生成的 RPG 档案。

你的每一笔麦当劳订单，都是麦门生涯的经验值。
本模块只做统计与映射，不编造任何订单数据。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Sequence, Tuple

from . import timeslots
from .models import Order, fen_to_yuan

# (订单数下限, 称号)
LEVELS: Tuple[Tuple[int, str], ...] = (
    (0, "麦芽"),
    (5, "麦苗"),
    (15, "麦农"),
    (30, "麦场主"),
    (60, "麦香居士"),
    (100, "麦门长老"),
    (200, "麦门之主"),
)


def level_for(order_count: int) -> Tuple[int, str]:
    no, name = 1, LEVELS[0][1]
    for i, (threshold, title) in enumerate(LEVELS, start=1):
        if order_count >= threshold:
            no, name = i, title
    return no, name


@dataclass
class Attributes:
    食力: int = 0
    财力: int = 0
    广度: int = 0
    信仰: int = 0


@dataclass
class LifeProfile:
    total_orders: int
    total_yuan: float
    avg_order_yuan: float
    maling_days: int
    first_order_day: str
    last_order_day: str
    unique_items: int
    line_items: int
    top_items: List[Tuple[str, int]]
    dominant_slot: str
    dominant_slot_label: str
    level_no: int
    level_name: str
    attrs: Attributes
    achievements: List[str]
    serial: str


def _achievements(
    orders: Sequence[Order],
    slot_counts: dict,
    unique_items: int,
    maling_days: int,
    max_order_yuan: float,
    distinct_weeks: int,
) -> List[str]:
    got: List[str] = []
    if slot_counts.get(timeslots.BREAKFAST, 0) >= 3:
        got.append("晨型人")
    if slot_counts.get(timeslots.TEA, 0) >= 3:
        got.append("三点几达人")
    if slot_counts.get(timeslots.LATENIGHT, 0) >= 2:
        got.append("守夜人")
    if unique_items >= 15:
        got.append("探店家")
    if maling_days >= 60:
        got.append("麦门元老")
    if max_order_yuan >= 80:
        got.append("团建担当")
    if distinct_weeks >= 6:
        got.append("稳定输出")
    return got


def life_profile(orders: Sequence[Order], now: Optional[datetime] = None) -> LifeProfile:
    now = now or datetime.now()
    if not orders:
        return LifeProfile(
            total_orders=0, total_yuan=0.0, avg_order_yuan=0.0, maling_days=0,
            first_order_day="-", last_order_day="-", unique_items=0, line_items=0,
            top_items=[], dominant_slot=timeslots.LUNCH, dominant_slot_label="午餐",
            level_no=1, level_name="麦芽", attrs=Attributes(),
            achievements=[], serial="MCN-2026-0000",
        )

    ordered = sorted(orders, key=lambda o: o.created_at)
    first, last = ordered[0].created_at, ordered[-1].created_at
    maling_days = max(1, (last.date() - first.date()).days + 1)

    total_fen = sum(o.total_fen for o in ordered)
    total_yuan = round(fen_to_yuan(total_fen), 2)
    avg_yuan = round(total_yuan / len(ordered), 2)

    item_counter = {}
    line_items = 0
    slot_counts = {}
    kcal_sum = 0
    for o in ordered:
        for it in o.items:
            item_counter[it.name] = item_counter.get(it.name, 0) + it.qty
            line_items += it.qty
        kcal_sum += o.kcal
        slot = timeslots.slot_for(o.created_at)
        slot_counts[slot.key] = slot_counts.get(slot.key, 0) + 1

    unique_items = len(item_counter)
    top_items = sorted(item_counter.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    dominant_key = max(slot_counts, key=lambda k: slot_counts[k])
    dominant_label = timeslots.slot_by_key(dominant_key).label

    level_no, level_name = level_for(len(ordered))
    avg_kcal = kcal_sum / len(ordered)
    monthly_freq = len(ordered) / maling_days * 30
    attrs = Attributes(
        食力=min(100, round(avg_kcal / 700 * 100)),
        财力=min(100, round(total_yuan / 1500 * 100)),
        广度=round(unique_items / line_items * 100) if line_items else 0,
        信仰=min(100, round(monthly_freq / 30 * 100)),
    )

    max_order_yuan = max(fen_to_yuan(o.total_fen) for o in ordered)
    distinct_weeks = len({(o.created_at.isocalendar()[0], o.created_at.isocalendar()[1]) for o in ordered})
    achievements = _achievements(ordered, slot_counts, unique_items, maling_days, max_order_yuan, distinct_weeks)

    digest = hashlib.md5(f"{len(ordered)}-{unique_items}-{maling_days}-{total_fen}".encode()).hexdigest()
    serial = f"MCN-2026-{digest[:4].upper()}"

    return LifeProfile(
        total_orders=len(ordered),
        total_yuan=total_yuan,
        avg_order_yuan=avg_yuan,
        maling_days=maling_days,
        first_order_day=first.strftime("%Y-%m-%d"),
        last_order_day=last.strftime("%Y-%m-%d"),
        unique_items=unique_items,
        line_items=line_items,
        top_items=top_items,
        dominant_slot=dominant_key,
        dominant_slot_label=dominant_label,
        level_no=level_no,
        level_name=level_name,
        attrs=attrs,
        achievements=achievements,
        serial=serial,
    )
