"""时段判断：麦当劳的一天，从早餐到夜宵。

时段不仅决定「什么能点」（早餐档只卖早餐品），也决定食堂的语气：
下午三点和凌晨一点的建议，不应该是一样的。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

BREAKFAST = "breakfast"
LUNCH = "lunch"
TEA = "tea"
DINNER = "dinner"
LATENIGHT = "latenight"


@dataclass(frozen=True)
class Slot:
    key: str
    label: str
    persona: str                      # 食堂大妈的台词
    start_min: int                    # 含，当日分钟数
    end_min: int                      # 含，可跨零点半夜 wrapping


SLOTS: Tuple[Slot, ...] = (
    Slot(BREAKFAST, "早餐", "Morning call！麦满分和热豆浆在等你", 5 * 60, 10 * 60 + 29),
    Slot(LUNCH, "午餐", "正餐时间，填饱肚子才有力气搬砖", 10 * 60 + 30, 13 * 60 + 59),
    Slot(TEA, "下午茶", "三点几啦，饮茶先啦！", 14 * 60, 16 * 60 + 59),
    Slot(DINNER, "晚餐", "收工前的仪式感，整点好的", 17 * 60, 20 * 60 + 59),
    Slot(LATENIGHT, "夜宵", "加班再晚，也要喂饱自己", 21 * 60, 4 * 60 + 59),
)

_BY_KEY = {s.key: s for s in SLOTS}


def slot_by_key(key: str) -> Slot:
    return _BY_KEY[key]


def all_slots() -> Tuple[Slot, ...]:
    return SLOTS


def _minute_of_day(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def slot_for(dt: datetime) -> Slot:
    """按当前时刻返回所处时段。夜宵档跨午夜（21:00–04:59）。"""
    m = _minute_of_day(dt)
    for s in SLOTS:
        if s.start_min <= s.end_min:
            if s.start_min <= m <= s.end_min:
                return s
        else:  # 跨零点的档（夜宵）
            if m >= s.start_min or m <= s.end_min:
                return s
    # 理论不可达；兜底返回午餐档
    return _BY_KEY[LUNCH]


def slot_for_now(now: Optional[datetime] = None) -> Slot:
    return slot_for(now or datetime.now())
