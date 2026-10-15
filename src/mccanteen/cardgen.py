"""卡片排版引擎：麦门人生角色卡 & 今日饭卡。

全程程序化绘制（Pillow），不依赖任何图像生成 API：
风格永远一致、永远不会失败、中文价格编号准确不溢出。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

from .decide import Decision
from .life import LifeProfile
from .models import fmt_yuan

# —— 麦当劳品牌色（仅作视觉致敬，非官方授权素材）——
RED = (218, 41, 28)
DARK_RED = (168, 28, 20)
YELLOW = (255, 199, 44)
CREAM = (255, 248, 235)
WHITE = (255, 255, 255)
DARK = (51, 40, 36)
GRAY = (122, 112, 106)
LIGHT_LINE = (238, 228, 216)
BAR_BG = (243, 237, 227)
GREEN = (46, 125, 50)
BLUE = (25, 118, 210)
ORANGE = (230, 126, 34)
GOLD = (240, 173, 34)

CARD_W, CARD_H = 1200, 1600

_BOLD_CANDIDATES = [
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]
_REGULAR_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]

_font_cache = {}


def _first_existing(paths: Sequence[str]) -> Optional[str]:
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]
    path = _first_existing(_BOLD_CANDIDATES if bold else _REGULAR_CANDIDATES)
    if path is None:
        raise RuntimeError(
            "找不到可用中文字体。请安装微软雅黑 / 黑体 / PingFang / Noto Sans CJK 之一，"
            "或在 cardgen.py 的候选列表中追加本机字体路径。"
        )
    font = ImageFont.truetype(path, size)
    _font_cache[key] = font
    return font


def text_w(draw: ImageDraw.ImageDraw, s: str, font: ImageFont.FreeTypeFont) -> int:
    return int(draw.textlength(s, font=font))


def wrap_text(draw: ImageDraw.ImageDraw, s: str, font: ImageFont.FreeTypeFont, max_w: int) -> List[str]:
    """按字符贪心换行（中英文混排安全）。"""
    lines: List[str] = []
    current = ""
    for ch in s:
        if ch == "\n":
            lines.append(current)
            current = ""
            continue
        trial = current + ch
        if text_w(draw, trial, font) <= max_w or not current:
            current = trial
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def fit_font(draw: ImageDraw.ImageDraw, s: str, start: int, max_w: int, bold: bool = False, min_size: int = 18) -> ImageFont.FreeTypeFont:
    size = start
    while size > min_size:
        font = load_font(size, bold)
        if text_w(draw, s, font) <= max_w:
            return font
        size -= 2
    return load_font(min_size, bold)


def _centered(draw: ImageDraw.ImageDraw, y: int, s: str, font: ImageFont.FreeTypeFont, fill) -> None:
    w = text_w(draw, s, font)
    draw.text(((CARD_W - w) / 2, y), s, font=font, fill=fill)


# ————————————————— 汉堡吉祥物（程序绘制） —————————————————

def draw_burger(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int) -> None:
    bun = (235, 176, 106)
    bun_dark = (219, 155, 88)
    lettuce = (124, 179, 66)
    cheese = (255, 205, 86)
    patty = (122, 78, 55)

    # 上层面包
    draw.pieslice([cx - r * 0.82, cy - r * 0.95, cx + r * 0.82, cy + r * 0.05], 180, 360, fill=bun)
    # 芝麻
    for dx, dy in [(-0.34, -0.52), (0.0, -0.62), (0.34, -0.5), (-0.16, -0.36), (0.18, -0.36)]:
        draw.ellipse([cx + r * dx - r * 0.05, cy + r * dy - r * 0.03, cx + r * dx + r * 0.05, cy + r * dy + r * 0.03], fill=(250, 226, 170))
    # 生菜
    draw.rectangle([cx - r * 0.86, cy + r * 0.02, cx + r * 0.86, cy + r * 0.14], fill=lettuce)
    for i in range(-4, 5):
        x = cx + i * r * 0.21
        draw.ellipse([x - r * 0.12, cy + r * 0.10, x + r * 0.12, cy + r * 0.22], fill=lettuce)
    # 芝士（带流心）
    draw.polygon(
        [
            (cx - r * 0.80, cy + r * 0.14),
            (cx + r * 0.80, cy + r * 0.14),
            (cx + r * 0.80, cy + r * 0.26),
            (cx + r * 0.45, cy + r * 0.20),
            (cx + r * 0.28, cy + r * 0.34),
            (cx + r * 0.10, cy + r * 0.20),
            (cx - r * 0.14, cy + r * 0.32),
            (cx - r * 0.32, cy + r * 0.20),
            (cx - r * 0.55, cy + r * 0.30),
            (cx - r * 0.80, cy + r * 0.22),
        ],
        fill=cheese,
    )
    # 肉饼
    draw.rounded_rectangle([cx - r * 0.84, cy + r * 0.30, cx + r * 0.84, cy + r * 0.48], radius=r * 0.09, fill=patty)
    # 下层面包
    draw.pieslice([cx - r * 0.82, cy + r * 0.44, cx + r * 0.82, cy + r * 0.95], 0, 180, fill=bun)
    draw.rectangle([cx - r * 0.82, cy + r * 0.86, cx + r * 0.82, cy + r * 0.90], fill=bun_dark)


# ————————————————— 麦门人生角色卡 —————————————————

def render_life_card(profile: LifeProfile, out_path: str) -> str:
    img = Image.new("RGB", (CARD_W, CARD_H), CREAM)
    d = ImageDraw.Draw(img)

    # 头部红 band
    d.rectangle([0, 0, CARD_W, 200], fill=RED)
    d.text((60, 52), "麦门人生", font=load_font(64, bold=True), fill=WHITE)
    d.text((62, 138), "McLIFE CARD · 麦门食堂", font=load_font(26), fill=(255, 230, 210))

    # 头像圈 + 汉堡
    cx, cy, r = CARD_W // 2, 372, 118
    d.ellipse([cx - r - 12, cy - r - 12, cx + r + 12, cy + r + 12], outline=YELLOW, width=10)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 251, 242))
    draw_burger(d, cx, cy, r)

    # 编号 + 等级
    _centered(d, 522, f"编号 #{profile.serial}", load_font(28), GRAY)
    _centered(d, 566, f"Lv.{profile.level_no} · {profile.level_name}", load_font(56, bold=True), RED)

    # 属性面板
    d.rounded_rectangle([80, 660, 1120, 950], radius=24, fill=WHITE, outline=LIGHT_LINE, width=2)
    attrs = [("食力", profile.attrs.食力, ORANGE), ("财力", profile.attrs.财力, RED),
             ("广度", profile.attrs.广度, GREEN), ("信仰", profile.attrs.信仰, BLUE)]
    label_font = load_font(30, bold=True)
    value_font = load_font(30, bold=True)
    for i, (name, value, color) in enumerate(attrs):
        y = 692 + i * 66
        d.text((116, y + 6), name, font=label_font, fill=DARK)
        d.rounded_rectangle([240, y + 10, 930, y + 40], radius=15, fill=BAR_BG)
        if value > 0:
            d.rounded_rectangle([240, y + 10, 240 + (930 - 240) * value / 100, y + 40], radius=15, fill=color)
        d.text((960, y + 4), str(value), font=value_font, fill=color)

    # 成就徽章
    d.text((80, 986), "成就徽章", font=load_font(26, bold=True), fill=GRAY)
    chip_font = load_font(24)
    x, y = 80, 1026
    for a in profile.achievements:
        w = text_w(d, a, chip_font) + 44
        if x + w > 1120:
            x = 80
            y += 62
        d.rounded_rectangle([x, y, x + w, y + 46], radius=23, fill=YELLOW)
        d.text((x + 22, y + 9), a, font=chip_font, fill=DARK)
        x += w + 18
    if not profile.achievements:
        d.text((80, 1026), "暂无——去点几单解锁第一枚", font=chip_font, fill=GRAY)

    # 常驻单品（填充中部留白）
    if profile.top_items:
        fav = "、".join(f"{name}×{n}" for name, n in profile.top_items)
        line = f"常驻{profile.dominant_slot_label} · 常点：{fav}"
        fav_font = fit_font(d, line, 26, 1020)
        _centered(d, 1200, line, fav_font, GRAY)

    # 底部信息条
    d.rounded_rectangle([80, 1310, 1120, 1400], radius=20, fill=YELLOW)
    info = f"麦龄 {profile.maling_days} 天 · {profile.total_orders} 单 · 总消费 {fmt_yuan(profile.total_yuan)} · 客单价 {fmt_yuan(profile.avg_order_yuan)}"
    info_font = fit_font(d, info, 30, 1000, bold=True)
    _centered(d, 1338, info, info_font, DARK)

    # 页脚
    _centered(d, 1452, "数据来自你的麦当劳订单 · 非麦当劳官方作品 · 麦门食堂 McCanteen", load_font(22), GRAY)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


# ————————————————— 今日饭卡 —————————————————

def render_decide_card(decision: Decision, out_path: str) -> str:
    img = Image.new("RGB", (CARD_W, CARD_H), CREAM)
    d = ImageDraw.Draw(img)

    # 头部
    d.rectangle([0, 0, CARD_W, 250], fill=RED)
    d.text((60, 48), "今日饭卡", font=load_font(60, bold=True), fill=WHITE)
    d.text((62, 136), f"{decision.slot.label} · {decision.persona}", font=load_font(28), fill=(255, 230, 210))
    tag = "McCanteen"
    tag_font = load_font(24)
    d.text((CARD_W - 60 - text_w(d, tag, tag_font), 60), tag, font=tag_font, fill=(255, 214, 190))

    # 结论（自动缩字号防溢出）
    verdict_font = fit_font(d, decision.verdict, 34, CARD_W - 120, bold=True)
    y = 292
    for line in wrap_text(d, decision.verdict, verdict_font, CARD_W - 120)[:2]:
        d.text((60, y), line, font=verdict_font, fill=DARK)
        y += 52

    # 摇一摇印章
    if decision.shake:
        stamp = Image.new("RGBA", (360, 90), (0, 0, 0, 0))
        sd = ImageDraw.Draw(stamp)
        sd.rounded_rectangle([4, 4, 356, 86], radius=16, outline=DARK_RED, width=6)
        sf = load_font(38, bold=True)
        sw = text_w(sd, "让食堂替你决定", sf)
        sd.text(((360 - sw) / 2, 20), "让食堂替你决定", font=sf, fill=DARK_RED)
        stamp = stamp.rotate(-10, expand=True, resample=Image.BICUBIC)
        img.paste(stamp, (CARD_W - 420, 300), stamp)

    # 三个选项
    medals = [GOLD, (170, 170, 170), (205, 127, 50)]
    y = 430
    for i, opt in enumerate(decision.options[:3]):
        d.rounded_rectangle([60, y, 1140, y + 230], radius=24, fill=WHITE, outline=LIGHT_LINE, width=2)
        badge_x, badge_y = 132, y + 58
        d.ellipse([badge_x - 36, badge_y - 36, badge_x + 36, badge_y + 36], fill=medals[i])
        num = str(i + 1)
        nf = load_font(40, bold=True)
        nw = text_w(d, num, nf)
        d.text((badge_x - nw / 2, badge_y - 26), num, font=nf, fill=WHITE)

        name_font = fit_font(d, opt.meal.name, 38, 700, bold=True)
        d.text((196, y + 28), opt.meal.name, font=name_font, fill=DARK)

        price_txt = fmt_yuan(opt.meal.price)
        pf = load_font(36, bold=True)
        d.text((196, y + 92), price_txt, font=pf, fill=RED)
        pw = text_w(d, price_txt, pf)
        if opt.coupon is not None:
            net_txt = f"  用券后 {fmt_yuan(opt.net_price)}"
            nf2 = load_font(24)
            d.text((196 + pw, y + 102), net_txt, font=nf2, fill=GREEN)

        reason = "；".join(opt.reasons[:2]) or "食堂今日推荐"
        rf = load_font(24)
        ry = y + 148
        for line in wrap_text(d, reason, rf, 880)[:2]:
            d.text((196, ry), line, font=rf, fill=GRAY)
            ry += 34
        y += 260

    # 底部：沉默成本
    band_y = 1240
    d.rounded_rectangle([60, band_y, 1140, band_y + 120], radius=20, fill=YELLOW if decision.silent_cost_yuan > 0 else (232, 245, 233))
    if decision.silent_cost_yuan > 0 or decision.urgent_coupon_count > 0:
        parts = [f"你还有 {decision.urgent_coupon_count} 张券 48 小时内过期"]
        if decision.silent_cost_yuan > 0:
            parts.append(f"已核实面值 {fmt_yuan(decision.silent_cost_yuan)}")
        if getattr(decision, "unknown_face_count", 0):
            parts.append(f"{decision.unknown_face_count} 张面值待核实")
        line = "，".join(parts) + "——别让它蒸发了"
        color = DARK
    else:
        line = "暂无即将过期的券，安心吃"
        color = (27, 94, 32)
    lf = fit_font(d, line, 30, 1020, bold=True)
    _centered(d, band_y + 40, line, lf, color)

    # 页脚
    _centered(d, 1420, "真实菜单与价格来自麦当劳 MCP · 演示数据仅供参考 · 麦门食堂 McCanteen", load_font(22), GRAY)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path
