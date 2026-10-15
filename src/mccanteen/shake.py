"""摇一摇：让食堂替你决定（真随机）。

选择困难症发作时，不要问十个人，让 secrets 替你选。
随机源可注入，测试时可传 seeded random 保证可复现。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from .decide import Context, Decision, decide
from .models import Coupon, Meal, Order


def shake(
    meals: Sequence[Meal],
    coupons: Sequence[Coupon],
    orders: Sequence[Order],
    ctx: Optional[Context] = None,
    now: Optional[datetime] = None,
    rng=None,
) -> Decision:
    """真随机摇一摇。rng 缺省使用 secrets.SystemRandom（密码学级随机）。"""
    return decide(meals, coupons, orders, ctx=ctx, now=now, rng=rng, shake=True)
