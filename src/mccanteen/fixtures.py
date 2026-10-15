"""fixtures 加载：离线演示模式的数据底座。

没有 MCP Token 也能完整体验全部能力（除实时数据外），
所有测试也基于 fixtures 运行，零网络依赖。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from .models import Account, Coupon, Meal, Order, OrderItem, Store

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "fixtures"


@dataclass
class Fixtures:
    meals: List[Meal]
    coupons: List[Coupon]
    orders: List[Order]
    account: Account
    stores: List[Store]

    def meal_by_code(self, code: str) -> Optional[Meal]:
        for m in self.meals:
            if m.code == code:
                return m
        return None


def _parse_meal(d: dict) -> Meal:
    return Meal(
        code=d["code"],
        name=d["name"],
        category=d["category"],
        price_fen=int(d["price_fen"]),
        kcal=int(d.get("kcal", 0)),
        protein_g=float(d.get("protein_g", 0)),
        tags=tuple(d.get("tags", ())),
        slots=tuple(d.get("slots", ("breakfast", "lunch", "tea", "dinner", "latenight"))),
        image_url=d.get("image_url", ""),
        is_combo=bool(d.get("is_combo", False)),
    )


def _parse_coupon(d: dict) -> Coupon:
    return Coupon(
        id=d["id"],
        title=d["title"],
        kind=d["kind"],
        value_fen=int(d["value_fen"]),
        min_spend_fen=int(d.get("min_spend_fen", 0)),
        applies_to=tuple(d.get("applies_to", ())),
        slots=tuple(d.get("slots", ())),
        channels=tuple(d.get("channels", ())),
        hours_left=(float(d["hours_left"]) if d.get("hours_left") is not None else None),
    )


def _parse_order(d: dict, meals_by_code: dict, now: datetime) -> Order:
    created = (now - timedelta(days=int(d["days_ago"]))).replace(
        hour=int(d["hour"]), minute=int(d["minute"]), second=0, microsecond=0
    )
    items = []
    for it in d["items"]:
        meal = meals_by_code.get(it["code"])
        items.append(
            OrderItem(
                code=it["code"],
                name=it["name"],
                qty=int(it["qty"]),
                price_fen=int(meal.price_fen) if meal else 0,
                kcal=int(meal.kcal) if meal else 0,
            )
        )
    return Order(
        id=d["id"],
        created_at=created,
        items=tuple(items),
        total_fen=int(d["total_fen"]),
        channel=d.get("channel", "到店"),
    )


def load_fixtures(now: Optional[datetime] = None, fixtures_dir: Optional[Path] = None) -> Fixtures:
    now = now or datetime.now()
    base = Path(fixtures_dir) if fixtures_dir else FIXTURES_DIR

    meals = [_parse_meal(d) for d in json.loads((base / "meals.json").read_text(encoding="utf-8"))["meals"]]
    coupons = [_parse_coupon(d) for d in json.loads((base / "coupons.json").read_text(encoding="utf-8"))["coupons"]]
    orders_raw = json.loads((base / "orders.json").read_text(encoding="utf-8"))["orders"]
    account_raw = json.loads((base / "account.json").read_text(encoding="utf-8"))
    stores = [
        Store(
            id=d["id"],
            name=d["name"],
            address=d["address"],
            distance_m=int(d.get("distance_m", 0)),
            services=tuple(d.get("services", ())),
        )
        for d in json.loads((base / "stores.json").read_text(encoding="utf-8"))["stores"]
    ]

    meals_by_code = {m.code: m for m in meals}
    orders = [_parse_order(d, meals_by_code, now) for d in orders_raw]
    orders.sort(key=lambda o: o.created_at)

    account = Account(
        available_points=int(account_raw["available_points"]),
        expiring_points=int(account_raw.get("expiring_points", 0)),
        expiring_in_hours=account_raw.get("expiring_in_hours"),
    )

    return Fixtures(meals=meals, coupons=coupons, orders=orders, account=account, stores=stores)
