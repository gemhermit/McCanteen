#!/usr/bin/env python3
"""摇一摇 —— 让食堂替你决定（secrets 真随机）。

选择困难症发作时专用：不要问十个人，让随机数替你选。
示例：python scripts/mcd_shake.py --context "不知道吃啥"
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mccanteen.cardgen import render_decide_card
from mccanteen.decide import Context
from mccanteen.fixtures import load_fixtures
from mccanteen.models import fmt_yuan
from mccanteen.shake import shake


def main() -> int:
    ap = argparse.ArgumentParser(description="麦门食堂 · 摇一摇")
    ap.add_argument("--context", default="", help="处境描述")
    ap.add_argument("--budget", type=float, default=None, help="预算（元）")
    ap.add_argument("--slot", default=None, choices=["breakfast", "lunch", "tea", "dinner", "latenight"])
    ap.add_argument("--card", default=None, help="生成饭卡 PNG 路径")
    args = ap.parse_args()

    fx = load_fixtures()
    decision = shake(fx.meals, fx.coupons, fx.orders, ctx=Context(text=args.context, budget=args.budget, slot=args.slot))

    print("🎲 摇一摇 —— 让食堂替你决定（secrets 真随机，模型无权插手）")
    print(decision.verdict)
    print()
    for i, o in enumerate(decision.options[:3]):
        mark = "👉" if i == 0 else "  "
        print(f"{mark} {o.meal.name}  {fmt_yuan(o.meal.price)}")
        if o.coupon is not None:
            print(f"     可用「{o.coupon.title}」→ 用券后 {fmt_yuan(o.net_price)}")
        for r in o.reasons:
            print(f"     · {r}")
    if args.card:
        render_decide_card(decision, args.card)
        print(f"\n饭卡已生成：{args.card}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
