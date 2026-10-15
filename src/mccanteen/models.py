"""数据模型与单位换算。

约定：所有来自 MCP / fixtures 的金额一律以「分」（int）在模型层流转，
仅在渲染层换算为「元」。麦当劳 MCP 的计价字段单位为分
（详见 references/mcp-contracts.md，已实测确认）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple


def fen_to_yuan(fen: float) -> float:
    """分 → 元。全项目唯一换算入口，杜绝单位幻觉。"""
    return round(float(fen) / 100.0, 2)


def yuan_to_fen(yuan: float) -> int:
    return int(round(float(yuan) * 100))


def fmt_yuan(yuan: float) -> str:
    """¥20.5 / ¥13 —— 展示层格式化。"""
    if yuan == int(yuan):
        return f"¥{int(yuan)}"
    return f"¥{yuan:.2f}".rstrip("0")


@dataclass(frozen=True)
class Meal:
    code: str
    name: str
    category: str
    price_fen: int
    kcal: int = 0
    protein_g: float = 0.0
    tags: Tuple[str, ...] = ()
    slots: Tuple[str, ...] = ("breakfast", "lunch", "tea", "dinner", "latenight")
    image_url: str = ""
    is_combo: bool = False

    @property
    def price(self) -> float:
        return fen_to_yuan(self.price_fen)


@dataclass(frozen=True)
class Coupon:
    """优惠券。kind ∈ {满减, 免费, 固定价, 买一送一}。

    value_fen 语义随 kind 变化：满减=减免额；免费=商品原价；
    固定价=相比原价省下的金额；买一送一=获赠商品的单价。
    """

    id: str
    title: str
    kind: str
    value_fen: int
    min_spend_fen: int = 0
    applies_to: Tuple[str, ...] = ()   # 空 = 全场通用
    slots: Tuple[str, ...] = ()        # 空 = 全时段可用
    channels: Tuple[str, ...] = ()     # 空 = 全渠道可用
    hours_left: Optional[float] = None  # None = 长期有效
    face_known: bool = True             # False = 面值待核实（live 下菜单无原价对照），不计入沉默成本

    @property
    def face_value(self) -> float:
        """券面价值（元）。过期即损失的金额。"""
        return fen_to_yuan(self.value_fen)

    def applies_to_meal(self, meal: Meal, slot: Optional[str] = None) -> bool:
        if self.applies_to and meal.code not in self.applies_to:
            return False
        if self.slots and slot and slot not in self.slots:
            return False
        return True

    def benefit_fen(self, meal: Meal, slot: Optional[str] = None) -> int:
        """用这张券点这份餐，实际省下多少分。不适用返回 0。"""
        if not self.applies_to_meal(meal, slot):
            return 0
        if self.kind == "满减" and meal.price_fen >= self.min_spend_fen:
            return self.value_fen
        return self.value_fen if self.kind in ("免费", "固定价", "买一送一") else 0


@dataclass(frozen=True)
class OrderItem:
    code: str
    name: str
    qty: int
    price_fen: int
    kcal: int = 0


@dataclass(frozen=True)
class Order:
    id: str
    created_at: datetime
    items: Tuple[OrderItem, ...]
    total_fen: int
    channel: str = "到店"

    @property
    def total(self) -> float:
        return fen_to_yuan(self.total_fen)

    @property
    def kcal(self) -> int:
        return sum(i.kcal * i.qty for i in self.items)

    def codes(self) -> Tuple[str, ...]:
        return tuple(i.code for i in self.items)


@dataclass(frozen=True)
class Account:
    """积分账户。积分是另一种有保质期的钱。"""

    available_points: int
    expiring_points: int = 0
    expiring_in_hours: Optional[float] = None


@dataclass(frozen=True)
class Store:
    id: str
    name: str
    address: str
    distance_m: int = 0
    services: Tuple[str, ...] = ()
