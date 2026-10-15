#!/usr/bin/env python3
"""麦门人生 —— 从真实订单生成的 RPG 档案。

示例：python scripts/mcd_life.py [--card out.png] [--json] [--live]
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mccanteen.cardgen import render_life_card
from mccanteen.fixtures import load_fixtures
from mccanteen.life import life_profile
from mccanteen.models import fmt_yuan


def main() -> int:
    ap = argparse.ArgumentParser(description="麦门食堂 · 麦门人生")
    ap.add_argument("--card", default=None, help="生成角色卡 PNG 路径")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--live", action="store_true", help="连通性冒烟（需 MCD_MCP_TOKEN）")
    args = ap.parse_args()

    if args.live:
        from mccanteen.mcp_client import McdonaldsMCP

        try:
            print(json.dumps(McdonaldsMCP().smoke_test(), ensure_ascii=False, indent=2))
            return 0
        except Exception as e:  # noqa: BLE001
            print(f"[live] MCP 冒烟失败：{e}", file=sys.stderr)
            return 1

    fx = load_fixtures()
    p = life_profile(fx.orders)

    if args.json:
        payload = {
            "serial": p.serial,
            "level": [p.level_no, p.level_name],
            "maling_days": p.maling_days,
            "total_orders": p.total_orders,
            "total_yuan": p.total_yuan,
            "avg_order_yuan": p.avg_order_yuan,
            "unique_items": p.unique_items,
            "top_items": p.top_items,
            "dominant_slot": p.dominant_slot_label,
            "attrs": {"食力": p.attrs.食力, "财力": p.attrs.财力, "广度": p.attrs.广度, "信仰": p.attrs.信仰},
            "achievements": p.achievements,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"🎴 麦门人生档案 #{p.serial}")
    print(f"Lv.{p.level_no} {p.level_name} · 麦龄 {p.maling_days} 天 · {p.total_orders} 单 · 总消费 {fmt_yuan(p.total_yuan)}")
    print(f"常驻时段：{p.dominant_slot_label} · 客单价 {fmt_yuan(p.avg_order_yuan)}")
    print(f"TOP3 单品：" + "、".join(f"{name}×{n}" for name, n in p.top_items))
    print(f"属性：食力 {p.attrs.食力} / 财力 {p.attrs.财力} / 广度 {p.attrs.广度} / 信仰 {p.attrs.信仰}")
    print(f"成就：{'、'.join(p.achievements) if p.achievements else '暂无'}")
    if args.card:
        render_life_card(p, args.card)
        print(f"\n角色卡已生成：{args.card}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
