"""止损雷达：券和积分，是另一种有保质期的钱。

视角来自一个反直觉的事实：名义面值加总 ≠ 你能拿到的价值，
而「即将过期」的券，是每一分钟都在缩水的资产。
本模块只做一件事：把正在蒸发的钱，量化给你看。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Sequence

from .models import Account, Coupon, fmt_yuan

URGENT_HOURS = 48

_BUCKETS = [
    ("24 小时内", 24),
    ("48 小时内", 48),
    ("7 天内", 24 * 7),
]


@dataclass
class Bucket:
    label: str
    hours: Optional[int]
    coupons: List[Coupon] = field(default_factory=list)

    @property
    def face_value(self) -> float:
        return round(sum(c.face_value for c in self.coupons if c.face_known), 2)

    @property
    def unknown_count(self) -> int:
        return sum(1 for c in self.coupons if not c.face_known)


@dataclass
class ExpiringReport:
    buckets: List[Bucket]
    long_term_count: int          # 长期有效券数量（不计入沉默成本）
    expiring_points: int
    points_in_hours: Optional[float]
    silent_cost_yuan: float       # 48 小时内过期券的已核实面值合计
    unknown_face_count: int       # 48 小时内过期但面值待核实的券数
    verdict: str


def _bucket_for(hours_left: float) -> Optional[str]:
    for label, limit in _BUCKETS:
        if hours_left <= limit:
            return label
    return None


def expiring_report(
    coupons: Sequence[Coupon],
    account: Optional[Account] = None,
    now: Optional[datetime] = None,
) -> ExpiringReport:
    buckets = [Bucket(label, hours) for label, hours in _BUCKETS]
    by_label = {b.label: b for b in buckets}
    long_term = 0

    for c in coupons:
        if c.hours_left is None:
            long_term += 1
            continue
        label = _bucket_for(c.hours_left)
        if label:
            by_label[label].coupons.append(c)
        else:
            long_term += 1

    urgent = by_label["24 小时内"].coupons + by_label["48 小时内"].coupons
    silent = round(sum(c.face_value for c in urgent if c.face_known), 2)
    unknown = sum(1 for c in urgent if not c.face_known)

    points = 0
    points_hours: Optional[float] = None
    if account and account.expiring_points:
        points = account.expiring_points
        points_hours = account.expiring_in_hours

    if urgent:
        parts = [f"{len(urgent)} 张券将在 48 小时内过期"]
        if silent > 0:
            parts.append(f"已核实面值合计 {fmt_yuan(silent)}")
        if unknown:
            parts.append(f"另有 {unknown} 张面值待核实（菜单无原价对照，同样在蒸发）")
        if points:
            when = f"{int(points_hours)} 小时内" if points_hours is not None else "不久后"
            parts.append(f"另有 {points} 积分将在{when}过期")
        verdict = "沉默成本：" + "；".join(parts) + "。这是正在蒸发的钱，别让它蒸发了。"
    elif points:
        verdict = f"券没有近忧，但 {points} 积分即将过期，抽奖或商城看看？"
    else:
        verdict = "券和积分都安好，安心吃。"

    return ExpiringReport(
        buckets=buckets,
        long_term_count=long_term,
        expiring_points=points,
        points_in_hours=points_hours,
        silent_cost_yuan=silent,
        unknown_face_count=unknown,
        verdict=verdict,
    )
