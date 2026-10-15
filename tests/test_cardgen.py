#!/usr/bin/env python3
"""卡片生成测试：真实渲染 PNG，校验尺寸与像素内容。"""
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _util import check, finish, section  # noqa: E402

from PIL import Image  # noqa: E402

from mccanteen.cardgen import render_decide_card, render_life_card  # noqa: E402
from mccanteen.decide import Context, decide  # noqa: E402
from mccanteen.fixtures import load_fixtures  # noqa: E402
from mccanteen.life import life_profile  # noqa: E402

NOW = datetime(2026, 10, 15, 15, 30)  # 下午茶档
fx = load_fixtures(now=NOW)
tmp = Path(tempfile.mkdtemp(prefix="mccanteen-test-"))

section("麦门人生角色卡")
life_path = tmp / "life.png"
render_life_card(life_profile(fx.orders, now=NOW), str(life_path))
img = Image.open(life_path)
check(img.size == (1200, 1600), "尺寸 1200×1600")
check(img.getpixel((10, 10))[:3] == (218, 41, 28), "头部为麦当劳红")
check(img.getpixel((600, 1520))[:3] != (255, 255, 255), "页脚区域有内容（非纯白）")
check(life_path.stat().st_size > 30_000, "PNG 体积合理（>30KB）")

section("今日饭卡（下午茶 · 长结论）")
dec = decide(fx.meals, fx.coupons, fx.orders, ctx=Context(text="加班好累", budget=30), now=NOW)
dec_path = tmp / "decide.png"
render_decide_card(dec, str(dec_path))
img2 = Image.open(dec_path)
check(img2.size == (1200, 1600), "尺寸 1200×1600")
check(img2.getpixel((10, 10))[:3] == (218, 41, 28), "头部为麦当劳红")

section("摇一摇饭卡（印章路径）")
import random  # noqa: E402

shaken = decide(fx.meals, fx.coupons, fx.orders, now=NOW, rng=random.Random(7), shake=True)
shake_path = tmp / "shake.png"
render_decide_card(shaken, str(shake_path))
check(Image.open(shake_path).size == (1200, 1600), "摇一摇饭卡渲染成功")

section("空档案卡（无成就分支）")
empty_path = tmp / "empty.png"
render_life_card(life_profile([], now=NOW), str(empty_path))
check(Image.open(empty_path).size == (1200, 1600), "空档案卡渲染成功（暂无成就分支）")

print(f"\n测试产物目录：{tmp}")
finish()
