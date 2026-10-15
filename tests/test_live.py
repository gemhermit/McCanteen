#!/usr/bin/env python3
"""live 解析器测试：全部基于 tests/fixtures/live 合成样本，零网络。"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _util import check, finish, section  # noqa: E402

from mccanteen.live import (  # noqa: E402
    extract_embedded_json,
    match_nutrition,
    parse_account,
    parse_menu_codes,
    parse_my_coupons,
    parse_nutrition,
    parse_orders,
    parse_price_list,
    parse_stores,
    parse_store_coupons,
)

LIVE = Path(__file__).resolve().parent / "fixtures" / "live"
NOW = datetime(2026, 10, 15, 16, 0)  # 周四下午茶

section("通用 JSON 提取")
text = (LIVE / "account.md").read_text(encoding="utf-8")
data = extract_embedded_json(text)
check(data is not None and data["code"] == 200, "从 Markdown 包装中提取内嵌 JSON")
check(extract_embedded_json("没有 JSON 的文本") is None, "无 JSON 返回 None")

section("门店解析")
stores = parse_stores((LIVE / "stores.md").read_text(encoding="utf-8"))
check(len(stores) == 1 and stores[0].id == "3330086", "解析出门店与 storeCode")
check(stores[0].distance_m == 380, "解析出门店距离")

section("菜单与计价解析")
menu = parse_menu_codes((LIVE / "meals.md").read_text(encoding="utf-8"))
check(len(menu) == 3, "菜单 3 个 code（保序去重）")
check(menu[0][1] == "人气热卖", "code 带分类")
price_map = parse_price_list((LIVE / "calc-price.md").read_text(encoding="utf-8"))
check(price_map["9900005462"]["name"] == "板烧鸡腿堡三件套", "计价返回商品名")
check(price_map["9900005462"]["subtotal_fen"] == 3450, "价格单位为分（3450 = ¥34.50）")

section("营养库解析")
nutrition = parse_nutrition((LIVE / "nutrition.md").read_text(encoding="utf-8"))
check(nutrition["板烧鸡腿堡"] == (391, 23.0), "解析 kcal 与蛋白质")
check(match_nutrition("板烧鸡腿堡三件套", nutrition) == (391, 23.0), "前缀匹配：三件套→单堡营养")
check(match_nutrition("不存在的餐品", nutrition) == (0, 0.0), "无匹配返回 0 不编造")

section("账户券解析（Markdown）")
coupons = parse_my_coupons((LIVE / "my-coupons.md").read_text(encoding="utf-8"), NOW, price_map)
check(len(coupons) == 3, "解析出 3 张券")
bogo = next(c for c in coupons if "买一送一" in c.title)
check(bogo.kind == "买一送一", "识别买一送一券型")
check(bogo.hours_left is not None and 30 < bogo.hours_left < 32, "48h 内到期（约 31.9 小时）")
check(bogo.face_known and bogo.value_fen == 1350, "买一送一面值 ≈ 用券价格 ¥13.5")
breakfast = next(c for c in coupons if "早餐" in c.title)
check(breakfast.slots == ("breakfast",), "有效期窗口 05:00-10:29 → 仅早餐档")
long_term = next(c for c in coupons if "满50减12" in c.title)
check(long_term.hours_left is not None and long_term.hours_left > 1000, "长期券 hours_left 很大")
check(not long_term.face_known, "无法对照原价的券标记面值待核实")

section("门店券解析（JSON）")
store_coupons = parse_store_coupons((LIVE / "store-coupons.md").read_text(encoding="utf-8"), NOW, price_map)
check(len(store_coupons) == 2, "解析出 2 张门店券")
bogo2 = store_coupons[0]
check(bogo2.applies_to == ("9900012387",), "门店券带精确商品关联")
check(bogo2.face_known and bogo2.value_fen == 1350, "买一送一面值取常规菜单项中薯条价格")
check(store_coupons[1].hours_left > 1000, "11 月底到期的券 hours_left 大")

section("账户与订单解析")
account = parse_account((LIVE / "account.md").read_text(encoding="utf-8"))
check(account.available_points == 8560, "可用积分")
check(account.expiring_points == 1200, "本月将过期积分")
orders = parse_orders((LIVE / "orders.md").read_text(encoding="utf-8"), nutrition)
check(len(orders) == 2, "2 笔订单")
check(orders[0].total_fen == 2050, "订单金额字符串 → 分")
check(orders[0].kcal == 391, "订单 kcal 由营养库关联")
check(orders[1].channel == "外送", "orderType=2 → 外送")
check(orders[0].created_at < orders[1].created_at, "订单按时间排序")

finish()
