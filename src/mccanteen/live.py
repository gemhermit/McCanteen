"""live 模式：把麦当劳 MCP 的真实返回适配为内部模型。

实测结论（2026-10-15，mcd-mcp v1.0.0）：
1. 服务器**不返回** Mcp-Session-Id（无会话机制），initialize 后直接调用即可；
2. 响应有两种包装：①「API Response Information」Markdown + 内嵌 JSON；
   ② 纯 Markdown（query-my-coupons 优惠券列表）；
3. **金额单位是分**：calculate-price 的 subtotal / originalSubtotal；
4. query-meals 只给 code+tags；**名称与价格来自 calculate-price 批量计价**（一次调用可传多个商品）；
5. query-my-coupons 返回 Markdown 文本，有效期字段含星期与时段窗口；
6. query-store-coupons 返回干净 JSON，products[].productCode 可直接关联菜单。

设计：8 次调用拿全一个完整 live 数据集（见 LiveData.fetch）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from . import timeslots
from .mcp_client import McdonaldsMCP
from .models import Account, Coupon, Meal, Order, OrderItem, Store, fen_to_yuan

# ————————————————— 通用解析 —————————————————


def extract_embedded_json(text: str) -> Optional[dict]:
    """从「Markdown 描述 + 内嵌 JSON」响应中提取 JSON。找不到返回 None。"""
    i = text.find('{"success"')
    if i < 0:
        return None
    j = text.rfind("}")
    if j <= i:
        return None
    try:
        import json

        return json.loads(text[i : j + 1])
    except ValueError:
        return None


def _parse_dt(s: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


def _yuan_str_to_fen(s: str) -> int:
    try:
        return int(round(float(s) * 100))
    except (TypeError, ValueError):
        return 0


def _hours_between(later: datetime, now: datetime) -> float:
    return (later - now).total_seconds() / 3600.0


# ————————————————— 营养库 —————————————————


def parse_nutrition(text: str) -> Dict[str, Tuple[int, float]]:
    """解析 list-nutrition-foods 响应（Markdown 包装 + 内嵌 JSON 的 data 字符串）。

    data 行格式：`名称,null,能量kJ,能量kcal,蛋白质,脂肪,碳水,钠,钙`
    """
    data = extract_embedded_json(text)
    body = data.get("data") if data else None
    if not isinstance(body, str):
        return {}
    result: Dict[str, Tuple[int, float]] = {}
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5 or parts[1] not in ("null", ""):
            continue
        name = parts[0]
        try:
            kcal = int(float(parts[3]))
            protein = float(parts[4])
        except ValueError:
            continue
        if name:
            result[name] = (kcal, protein)
    return result


def match_nutrition(meal_name: str, nutrition: Dict[str, Tuple[int, float]]) -> Tuple[int, float]:
    """菜单名 → 营养数据。先精确，再前缀（板烧鸡腿堡三件套 → 板烧鸡腿堡）。"""
    if meal_name in nutrition:
        return nutrition[meal_name]
    for nname, value in nutrition.items():
        if meal_name.startswith(nname) or nname in meal_name:
            return value
    return 0, 0.0


# ————————————————— 门店 / 菜单 —————————————————


def parse_stores(text: str) -> List[Store]:
    data = extract_embedded_json(text)
    if not data or not isinstance(data.get("data"), list):
        return []
    return [
        Store(
            id=str(s.get("storeCode", "")),
            name=s.get("storeName", ""),
            address=s.get("address", ""),
            distance_m=int(s.get("distance", 0) or 0),
        )
        for s in data["data"]
    ]


def parse_menu_codes(text: str) -> List[Tuple[str, str]]:
    """query-meals → [(code, category)]，保序去重。"""
    data = extract_embedded_json(text)
    if not data or not isinstance(data.get("data"), dict):
        return []
    out: List[Tuple[str, str]] = []
    seen = set()
    for cat in data["data"].get("categories", []):
        cat_name = re.sub(r"\s*\n\s*", "", cat.get("name", ""))
        for m in cat.get("meals", []):
            code = str(m.get("code", ""))
            if code and code not in seen:
                seen.add(code)
                out.append((code, cat_name))
    return out


def parse_price_list(text: str) -> Dict[str, dict]:
    """calculate-price → {code: {name, original_fen, subtotal_fen}}。"""
    data = extract_embedded_json(text)
    if not data or not isinstance(data.get("data"), dict):
        return {}
    out: Dict[str, dict] = {}
    for p in data["data"].get("productList", []):
        code = str(p.get("productCode", ""))
        if code:
            out[code] = {
                "name": p.get("productName", ""),
                "original_fen": int(p.get("originalSubtotal", 0) or 0),
                "subtotal_fen": int(p.get("subtotal", 0) or 0),
            }
    return out


# ————————————————— 优惠券 —————————————————


def _parse_validity_window(validity: str) -> Tuple[Optional[datetime], Optional[datetime], Tuple[str, ...], Tuple[Tuple[int, int], ...]]:
    """解析「2026-10-12 10:30-2026-10-16 23:59 周一、二、三、四、五 10:30-23:59」。

    返回 (开始, 结束, 限制星期, 限制时段窗)。字段缺失时为 None/空。
    """
    m = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})-(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", validity)
    if not m:
        return None, None, (), ()
    start, end = _parse_dt(m.group(1)), _parse_dt(m.group(2))
    rest = validity[m.end():].strip()
    weekdays = tuple(re.findall(r"[一二三四五六日天]", rest.split(" ")[0])) if rest else ()
    windows: List[Tuple[int, int]] = []
    for wm in re.finditer(r"(\d{2}:\d{2})-(\d{2}:\d{2})", rest):
        h1, m1 = map(int, wm.group(1).split(":"))
        h2, m2 = map(int, wm.group(2).split(":"))
        windows.append((h1 * 60 + m1, h2 * 60 + m2))
    return start, end, weekdays, tuple(windows)


def _minutes(start: int, end: int) -> set:
    """[start, end] 闭区间分钟集合，支持跨零点。"""
    if start <= end:
        return set(range(start, end + 1))
    return set(range(start, 1440)) | set(range(0, end + 1))


def _slot_from_window(windows: Tuple[Tuple[int, int], ...]) -> Tuple[str, ...]:
    """时段窗 → 麦当劳时段键。05:00-10:29 → 仅早餐；21:00-04:59 → 仅夜宵。"""
    if not windows:
        return ()
    keys = set()
    for start_min, end_min in windows:
        w = _minutes(start_min, end_min)
        for s in timeslots.all_slots():
            if w & _minutes(s.start_min, s.end_min):
                keys.add(s.key)
    return tuple(sorted(keys))


def parse_my_coupons(text: str, now: datetime, price_map: Dict[str, dict]) -> List[Coupon]:
    """解析 query-my-coupons 的 Markdown 券列表。

    面值口径：
    - 买一送一：面值 ≈ 用券价格（获赠商品与付款商品同价的近似，已在报告注明）；
    - 套餐/固定价：标题能匹配到菜单商品时，面值 = 菜单原价 − 用券价格；
      匹配不到 → 面值未知（value_fen=0，报告中单独计数，不静默按 0 蒸发）。
    """
    coupons: List[Coupon] = []
    sections = re.split(r"\n##\s+", text)
    for sec in sections[1:]:
        lines = sec.strip().splitlines()
        if not lines:
            continue
        title = lines[0].strip()
        body = "\n".join(lines[1:])

        price_m = re.search(r"\*\*优惠\*\*:\s*¥([\d.]+)", body)
        use_price_fen = int(round(float(price_m.group(1)) * 100)) if price_m else 0

        val_m = re.search(r"\*\*有效期\*\*:\s*(.+)", body)
        validity = val_m.group(1).strip() if val_m else ""
        _, end, _, windows = _parse_validity_window(validity)
        hours_left = _hours_between(end, now) if end else None

        tag_m = re.search(r"\*\*标签\*\*:\s*(.+)", body)
        channels = tuple(t.strip() for t in tag_m.group(1).split("、")) if tag_m else ()

        # 券型与适用商品（标题 ↔ 菜单名模糊匹配）
        applies_to: Tuple[str, ...] = ()
        for code, info in price_map.items():
            iname = info["name"]
            if iname and (iname in title or title in iname):
                applies_to = applies_to + (code,)
                break

        if "买一送一" in title:
            kind = "买一送一"
            face_fen = use_price_fen  # 近似：获赠品单价 ≈ 付款价
            face_known = True
        else:
            kind = "固定价"
            face_fen = 0
            face_known = False
            if applies_to:
                original = price_map[applies_to[0]]["original_fen"]
                if original > use_price_fen:
                    face_fen = original - use_price_fen
                    face_known = True

        coupons.append(
            Coupon(
                id=f"mycoupon-{len(coupons) + 1:02d}",
                title=title,
                kind=kind,
                value_fen=face_fen,
                min_spend_fen=0,
                applies_to=applies_to,
                slots=_slot_from_window(windows),
                channels=channels,
                hours_left=hours_left,
                face_known=face_known,
            )
        )
    return coupons


def parse_store_coupons(text: str, now: datetime, price_map: Dict[str, dict]) -> List[Coupon]:
    """解析 query-store-coupons 的 JSON 券列表（含 productCode，可精确关联菜单）。"""
    data = extract_embedded_json(text)
    if not data or not isinstance(data.get("data"), list):
        return []
    coupons: List[Coupon] = []
    for c in data["data"]:
        trade = c.get("tradeDateTime", "")
        m = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})-(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", trade)
        end = _parse_dt(m.group(2)) if m else None
        hours_left = _hours_between(end, now) if end else None
        products = c.get("products", []) or []
        applies_to = tuple(str(p.get("productCode", "")) for p in products if p.get("productCode"))
        title = c.get("title", "")
        face_fen = 0
        face_known = False
        if "买一送一" in title and applies_to:
            # 获赠品单价：找去掉「买一送一」后缀的常规菜单项
            base = title.replace("买一送一", "")
            for code, info in price_map.items():
                if info["name"] and (info["name"] == base or info["name"].startswith(base)):
                    face_fen = info["subtotal_fen"]
                    face_known = True
                    break
        coupons.append(
            Coupon(
                id=str(c.get("couponId", f"storecoupon-{len(coupons) + 1}")),
                title=title,
                kind="买一送一" if "买一送一" in title else "固定价",
                value_fen=face_fen,
                min_spend_fen=0,
                applies_to=applies_to,
                slots=(),
                channels=(),
                hours_left=hours_left,
                face_known=face_known,
            )
        )
    return coupons


# ————————————————— 账户 / 订单 —————————————————


def parse_account(text: str) -> Account:
    data = extract_embedded_json(text)
    if not data or not isinstance(data.get("data"), dict):
        return Account(available_points=0)
    d = data["data"]

    def _int(v) -> int:
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return 0

    return Account(
        available_points=_int(d.get("availablePoint")),
        expiring_points=_int(d.get("currentMouthExpirePoint")),
        expiring_in_hours=None,  # 官方未返回具体过期时刻，不编造
    )


def parse_orders(text: str, nutrition: Dict[str, Tuple[int, float]]) -> List[Order]:
    data = extract_embedded_json(text)
    if not data or not isinstance(data.get("data"), dict):
        return []
    orders: List[Order] = []
    for o in data["data"].get("list", []):
        created = _parse_dt(o.get("createTime", ""))
        if created is None:
            continue
        items = []
        for p in o.get("orderProductList", []):
            name = p.get("productName", "")
            kcal, _ = match_nutrition(name, nutrition)
            items.append(
                OrderItem(
                    code=str(p.get("productCode", "")),
                    name=name,
                    qty=int(p.get("quantity", 1) or 1),
                    price_fen=0,
                    kcal=kcal,
                )
            )
        orders.append(
            Order(
                id=str(o.get("orderId", "")),
                created_at=created,
                items=tuple(items),
                total_fen=_yuan_str_to_fen(o.get("realTotalAmount", "0")),
                channel="外送" if str(o.get("orderType")) == "2" else "到店",
            )
        )
    orders.sort(key=lambda x: x.created_at)
    return orders


# ————————————————— live 数据集 —————————————————


@dataclass
class LiveData:
    now: datetime
    store: Optional[Store]
    meals: List[Meal]
    my_coupons: List[Coupon]
    store_coupons: List[Coupon]
    account: Account
    orders: List[Order]
    calls: int = 0
    warnings: List[str] = field(default_factory=list)

    @property
    def coupons(self) -> List[Coupon]:
        """账户券 + 门店券，按标题去重并合并信息：

        - 同一张券两个接口都会返回；
        - applies_to 取有精确商品关联的一侧（门店券带 productCode）；
        - 面值取两侧中更可靠的估计（max），不重复计入沉默成本。
        """
        merged: Dict[str, Coupon] = {}
        for c in self.my_coupons + self.store_coupons:
            existing = merged.get(c.title)
            if existing is None:
                merged[c.title] = c
                continue
            applies = existing.applies_to or c.applies_to
            face = max(existing.value_fen, c.value_fen)
            face_known = existing.face_known or c.face_known
            merged[c.title] = Coupon(
                id=existing.id,
                title=existing.title,
                kind=existing.kind,
                value_fen=face if face_known else 0,
                min_spend_fen=existing.min_spend_fen,
                applies_to=applies,
                slots=existing.slots or c.slots,
                channels=existing.channels or c.channels,
                hours_left=existing.hours_left if existing.hours_left is not None else c.hours_left,
                face_known=face_known,
            )
        return list(merged.values())


def fetch_live(
    client: McdonaldsMCP,
    search_type: int = 1,
    order_type: int = 1,
    be_type: int = 1,
    store_code: Optional[str] = None,
    chunk: int = 20,
) -> LiveData:
    """8 次调用拉取完整 live 数据集。任何一步失败都记录 warning 并降级，不中断。"""
    warnings: List[str] = []
    calls = 0

    def call(name: str, args: dict):
        nonlocal calls
        calls += 1
        return client.text_of(client.call_tool(name, args))

    # 1. 服务端时间
    now_text = call("now-time-info", {})
    now_data = extract_embedded_json(now_text)
    now = _parse_dt(now_data["data"]["datetime"]) if now_data and now_data.get("data") else datetime.now()
    if not (now_data and now_data.get("data")):
        warnings.append("now-time-info 解析失败，使用本机时间")

    # 2. 门店
    store: Optional[Store] = None
    if store_code:
        store = Store(id=store_code, name="(指定门店)", address="")
    else:
        try:
            stores = parse_stores(call("query-nearby-stores", {"beType": be_type, "searchType": search_type}))
            store = stores[0] if stores else None
        except Exception as e:  # noqa: BLE001
            warnings.append(f"query-nearby-stores 失败：{e}")
    if store is None:
        raise RuntimeError("未获取到门店（searchType=1 附近门店为空？可用 --store 指定 storeCode）")
    store_args = {"storeCode": store.id, "orderType": order_type, "beType": be_type}

    # 3. 菜单 code 列表
    menu_codes: List[Tuple[str, str]] = []
    try:
        menu_codes = parse_menu_codes(call("query-meals", store_args))
    except Exception as e:  # noqa: BLE001
        warnings.append(f"query-meals 失败：{e}")
    if not menu_codes:
        raise RuntimeError("菜单为空，无法决断")

    # 4. 批量计价（分块 + 失败重试：实测单块 60 个商品会被服务器断连，20 个以内稳定）
    price_map: Dict[str, dict] = {}
    codes = [c for c, _ in menu_codes]

    def _price_batch(batch: List[str]) -> None:
        text = call(
            "calculate-price",
            {**store_args, "items": [{"productCode": c, "quantity": 1} for c in batch]},
        )
        price_map.update(parse_price_list(text))

    i = 0
    while i < len(codes):
        batch = codes[i : i + chunk]
        try:
            _price_batch(batch)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"calculate-price 块 {i // chunk + 1}（{len(batch)} 项）失败：{e}，拆细重试")
            ok = True
            for j in range(0, len(batch), 8):
                mini = batch[j : j + 8]
                try:
                    _price_batch(mini)
                except Exception as e2:  # noqa: BLE001
                    ok = False
                    warnings.append(f"calculate-price 小块（{len(mini)} 项）仍失败：{e2}，跳过")
            if not ok:
                pass
        i += chunk

    # 5. 营养库
    nutrition: Dict[str, Tuple[int, float]] = {}
    try:
        nutrition = parse_nutrition(call("list-nutrition-foods", {}))
    except Exception as e:  # noqa: BLE001
        warnings.append(f"list-nutrition-foods 失败：{e}")

    meals: List[Meal] = []
    for code, category in menu_codes:
        info = price_map.get(code)
        if not info or not info["name"]:
            continue  # 计价失败的商品不进候选池（没有名字和价格无法决断）
        price_fen = info["subtotal_fen"] or info["original_fen"]
        if price_fen < 500:
            continue  # 低于 ¥5 视为加购/配料项（酱料、饼干、特调件），不进候选池
        kcal, protein = match_nutrition(info["name"], nutrition)
        meals.append(
            Meal(
                code=code,
                name=info["name"],
                category=category,
                price_fen=info["subtotal_fen"] or info["original_fen"],
                kcal=kcal,
                protein_g=protein,
                tags=(),
                slots=("breakfast", "lunch", "tea", "dinner", "latenight"),
                image_url="",
                is_combo=("套餐" in info["name"] or "件套" in info["name"] or "随心配" in info["name"]),
            )
        )

    # 6. 券（账户券 + 门店券）
    my_coupons: List[Coupon] = []
    store_coupons: List[Coupon] = []
    try:
        my_coupons = parse_my_coupons(call("query-my-coupons", {}), now, price_map)
    except Exception as e:  # noqa: BLE001
        warnings.append(f"query-my-coupons 失败：{e}")
    try:
        store_coupons = parse_store_coupons(
            call("query-store-coupons", store_args), now, price_map
        )
    except Exception as e:  # noqa: BLE001
        warnings.append(f"query-store-coupons 失败：{e}")

    # 7. 积分 + 8. 历史订单
    try:
        account = parse_account(call("query-my-account", {}))
    except Exception as e:  # noqa: BLE001
        warnings.append(f"query-my-account 失败：{e}")
        account = Account(available_points=0)
    try:
        orders = parse_orders(call("order-list", {}), nutrition)
    except Exception as e:  # noqa: BLE001
        warnings.append(f"order-list 失败：{e}")
        orders = []

    return LiveData(
        now=now,
        store=store,
        meals=meals,
        my_coupons=my_coupons,
        store_coupons=store_coupons,
        account=account,
        orders=orders,
        calls=calls,
        warnings=warnings,
    )
