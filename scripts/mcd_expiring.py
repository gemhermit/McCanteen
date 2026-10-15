#!/usr/bin/env python3
"""止损雷达 —— 券和积分，是另一种有保质期的钱。

示例：python scripts/mcd_expiring.py [--json] [--live]
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mccanteen.expiring import expiring_report
from mccanteen.fixtures import load_fixtures
from mccanteen.models import fmt_yuan


def main() -> int:
    ap = argparse.ArgumentParser(description="麦门食堂 · 止损雷达")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--live", action="store_true", help="真实 MCP 数据（需 MCD_MCP_TOKEN）")
    args = ap.parse_args()

    if args.live:
        from mccanteen.live import fetch_live
        from mccanteen.mcp_client import McdonaldsMCP

        try:
            data = fetch_live(McdonaldsMCP())
        except Exception as e:  # noqa: BLE001
            print(f"[live] 拉取失败：{e}", file=sys.stderr)
            return 1
        print(f"[live] {data.store.name} · 券 {len(data.coupons)} 张 · MCP 调用 {data.calls} 次")
        for w in data.warnings:
            print(f"[live][warn] {w}")
        report = expiring_report(data.coupons, data.account, now=data.now)
    else:
        fx = load_fixtures()
        report = expiring_report(fx.coupons, fx.account)

    if args.json:
        payload = {
            "silent_cost_yuan": report.silent_cost_yuan,
            "expiring_points": report.expiring_points,
            "points_in_hours": report.points_in_hours,
            "buckets": [
                {"label": b.label, "face_value": b.face_value,
                 "coupons": [{"title": c.title, "face_value": c.face_value, "hours_left": c.hours_left} for c in b.coupons]}
                for b in report.buckets
            ],
            "verdict": report.verdict,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("⏳ 止损雷达 —— 正在蒸发的钱，量化给你看")
    for b in report.buckets:
        if b.coupons:
            extra = f" · {b.unknown_count} 张面值待核实" if b.unknown_count else ""
            print(f"\n{b.label}（{len(b.coupons)} 张 · 已核实面值 {fmt_yuan(b.face_value)}{extra}）")
            for c in b.coupons:
                when = f"{int(c.hours_left)} 小时后过期" if c.hours_left is not None else "长期有效"
                face = fmt_yuan(c.face_value) if c.face_known else "面值待核实"
                print(f"  · {c.title}  {face} · {when}")
    print(f"\n长期有效：{report.long_term_count} 张")
    if report.expiring_points:
        when = f"{int(report.points_in_hours)} 小时内" if report.points_in_hours is not None else "不久后"
        print(f"即将过期积分：{report.expiring_points} 分（{when}）")
    print(f"\n{report.verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
