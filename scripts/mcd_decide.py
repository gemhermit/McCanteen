#!/usr/bin/env python3
"""今天吃什么 —— 麦门食堂决断引擎 CLI。

示例：
  python scripts/mcd_decide.py --context "加班到九点好累"
  python scripts/mcd_decide.py --budget 25 --slot tea --card out.png
  python scripts/mcd_decide.py --live            # 真实 MCP 数据（需 MCD_MCP_TOKEN）
  python scripts/mcd_decide.py --live --store 3330086
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mccanteen.cardgen import render_decide_card
from mccanteen.decide import Context, decide
from mccanteen.fixtures import load_fixtures
from mccanteen.models import fmt_yuan

MEDALS = ["①", "②", "③"]


def _print_decision(decision) -> None:
    print(f"🍱 {decision.slot.label} · {decision.slot.persona}")
    print(decision.verdict)
    print()
    for i, o in enumerate(decision.options[:3]):
        print(f"{MEDALS[i]} {o.meal.name}  {fmt_yuan(o.meal.price)}")
        if o.coupon is not None:
            print(f"   可用「{o.coupon.title}」→ 用券后 {fmt_yuan(o.net_price)}")
        for r in o.reasons:
            print(f"   · {r}")
        print()


def main() -> int:
    ap = argparse.ArgumentParser(description="麦门食堂 · 今天吃什么")
    ap.add_argument("--context", default="", help="处境描述，如「加班好累」「健完身」")
    ap.add_argument("--budget", type=float, default=None, help="预算（元）")
    ap.add_argument("--slot", default=None, choices=["breakfast", "lunch", "tea", "dinner", "latenight"])
    ap.add_argument("--allow-repeat", action="store_true", help="关闭反重复，允许推荐最近吃过的")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--card", default=None, help="生成今日饭卡 PNG 路径")
    ap.add_argument("--live", action="store_true", help="真实 MCP 数据（需 MCD_MCP_TOKEN）")
    ap.add_argument("--store", default=None, help="指定门店 storeCode（live 模式，缺省取附近首家）")
    args = ap.parse_args()

    ctx = Context(text=args.context, budget=args.budget, slot=args.slot, avoid_repeat=not args.allow_repeat)

    if args.live:
        from mccanteen.live import fetch_live
        from mccanteen.mcp_client import McdonaldsMCP

        try:
            data = fetch_live(McdonaldsMCP(), store_code=args.store)
        except Exception as e:  # noqa: BLE001
            print(f"[live] 拉取失败：{e}", file=sys.stderr)
            return 1
        print(f"[live] {data.store.name} · 菜单 {len(data.meals)} 项 · 券 {len(data.coupons)} 张 · 订单 {len(data.orders)} 笔 · MCP 调用 {data.calls} 次")
        for w in data.warnings:
            print(f"[live][warn] {w}")
        decision = decide(data.meals, data.coupons, data.orders, ctx=ctx, now=data.now)
    else:
        fx = load_fixtures()
        decision = decide(fx.meals, fx.coupons, fx.orders, ctx=ctx)

    if args.json:
        payload = {
            "slot": decision.slot.key,
            "verdict": decision.verdict,
            "shake": decision.shake,
            "silent_cost_yuan": decision.silent_cost_yuan,
            "options": [
                {
                    "name": o.meal.name,
                    "price": o.meal.price,
                    "net_price": o.net_price,
                    "coupon": o.coupon.title if o.coupon else None,
                    "score": o.score,
                    "reasons": o.reasons,
                }
                for o in decision.options
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    _print_decision(decision)

    if args.card:
        render_decide_card(decision, args.card)
        print(f"饭卡已生成：{args.card}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
