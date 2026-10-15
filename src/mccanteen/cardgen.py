"""卡片排版引擎 v2：麦门人生角色卡 & 今日饭卡。

设计系统：渐变 + 投影 + 圆角药丸 + 会笑的汉堡吉祥物。
全程程序化绘制（Pillow），不依赖任何图像生成 API：
风格永远一致、永远不会失败、中文价格编号准确不溢出。
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .decide import Decision
from .life import LifeProfile
from .models import fmt_yuan

# —— 麦当劳品牌色（仅作视觉致敬，非官方授权素材）——
RED = (218, 41, 28)
DARK_RED = (168, 28, 20)
RED_TOP = (229, 64, 50)
RED_BOTTOM = (186, 31, 23)
YELLOW = (255, 199, 44)
YELLOW_DARK = (214, 148, 12)
YELLOW_TOP = (255, 216, 96)
YELLOW_BOTTOM = (246, 178, 22)
CREAM_TOP = (255, 251, 242)
CREAM_BOTTOM = (255, 241, 219)
WHITE = (255, 255, 255)
DARK = (51, 40, 36)
GRAY = (122, 112, 106)
LIGHT_LINE = (240, 232, 220)
BAR_BG = (245, 240, 231)
GREEN = (46, 125, 50)
GREEN_TOP = (72, 152, 60)
GREEN_BOTTOM = (34, 108, 40)
BLUE = (25, 118, 210)
ORANGE_TOP = (238, 142, 52)
ORANGE_BOTTOM = (219, 110, 22)
SILVER_TOP = (214, 216, 220)
SILVER_BOTTOM = (160, 163, 170)
BRONZE_TOP = (222, 160, 108)
BRONZE_BOTTOM = (176, 112, 62)
GOLD_TOP = (252, 214, 106)
GOLD_BOTTOM = (235, 170, 30)

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


# ————————————————— 设计系统基元 —————————————————


def _lerp(a: Tuple[int, int, int], b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


def _gradient(size: Tuple[int, int], top: Tuple[int, int, int], bottom: Tuple[int, int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=_lerp(top, bottom, y / max(1, h - 1)))
    return img


def _shadow(img: Image.Image, box: Tuple[int, int, int, int], radius: int = 24, blur: int = 16, alpha: int = 60, offset: int = 6) -> None:
    """在 RGBA 画布上为圆角矩形投射柔和投影。"""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    x0, y0, x1, y1 = box
    od.rounded_rectangle([x0, y0 + offset, x1, y1 + offset], radius=radius, fill=(70, 45, 30, alpha))
    overlay = overlay.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(overlay)  # type: ignore[union-attr]


def _grad_rect(img: Image.Image, box: Tuple[int, int, int, int], radius: int, top: Tuple[int, int, int], bottom: Tuple[int, int, int]) -> None:
    """把渐变填充进圆角矩形（带 mask 粘贴）。"""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return
    grad = _gradient((w, h), top, bottom)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    img.paste(grad, (x0, y0), mask)


def _dots(img: Image.Image, spacing: int = 72, r: int = 2, alpha: int = 12) -> None:
    """背景细点阵纹理（克制，只做质感）。"""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    w, h = img.size
    for x in range(spacing // 2, w, spacing):
        for y in range(spacing // 2, h, spacing):
            od.ellipse([x - r, y - r, x + r, y + r], fill=(190, 130, 60, alpha))
    img.alpha_composite(overlay)  # type: ignore[union-attr]


def _pill(img: Image.Image, center_x: int, y: int, text: str, font: ImageFont.FreeTypeFont, top, bottom, text_color, height: int = 52, pad: int = 30) -> Tuple[int, int]:
    """居中渐变药丸徽章，返回 (x0, x1)。"""
    d = ImageDraw.Draw(img)
    tw = text_w(d, text, font)
    w = tw + pad * 2
    x0, x1 = center_x - w // 2, center_x + w // 2
    _shadow(img, (x0, y, x1, y + height), radius=height // 2, blur=10, alpha=40, offset=3)
    _grad_rect(img, (x0, y, x1, y + height), height // 2, top, bottom)
    d.text((center_x - tw / 2, y + (height - font.size) / 2 - 2), text, font=font, fill=text_color)
    return x0, x1


def _chip(img: Image.Image, x: int, y: int, text: str, font: ImageFont.FreeTypeFont) -> int:
    """金色渐变成就 chip，返回占用宽度。"""
    d = ImageDraw.Draw(img)
    tw = text_w(d, text, font)
    w = tw + 44
    _grad_rect(img, (x, y, x + w, y + 48), 24, GOLD_TOP, GOLD_BOTTOM)
    d.rounded_rectangle([x, y, x + w, y + 48], radius=24, outline=YELLOW_DARK, width=2)
    d.text((x + 22, y + 10), text, font=font, fill=(90, 55, 10))
    return w


# ————————————————— 汉堡吉祥物（分层渐变合成，会笑的那位） —————————————————


def _sesame(canvas: Image.Image, x: float, y: float, w: int, h: int, angle: float) -> None:
    """粘贴一粒旋转的杏仁形芝麻。"""
    s = Image.new("RGBA", (w * 3, h * 3), (0, 0, 0, 0))
    sd = ImageDraw.Draw(s)
    sd.ellipse([w, h, w * 2, h * 2], fill=(252, 231, 178), outline=(226, 196, 140), width=1)
    s = s.rotate(angle, expand=True, resample=Image.BICUBIC)
    canvas.alpha_composite(s, (int(x - s.size[0] / 2), int(y - s.size[1] / 2)))


def _soft_highlight(canvas: Image.Image, box: Tuple[int, int, int, int], alpha: int = 80, blur: int = 10) -> None:
    """柔和白色高光（模糊椭圆）。"""
    x0, y0, x1, y1 = box
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    hl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hl)
    hd.ellipse([0, 0, w - 1, h - 1], fill=(255, 255, 255, alpha))
    hl = hl.filter(ImageFilter.GaussianBlur(blur))
    canvas.alpha_composite(hl, (x0, y0))


def draw_burger(img: Image.Image, cx: int, cy: int, r: int) -> None:
    """在 img 上分层合成汉堡吉祥物。

    自底向上：下层面包 → 肉饼 → 芝士 → 生菜 → 上层面包，
    每层独立渐变 + 卡通描边；随后点缀芝麻、烤痕、高光，最后画表情。
    """
    R = float(r)
    size = int(R * 2.8)
    X = Y = size / 2.0
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    OUT = (112, 68, 44, 255)  # 卡通描边色

    def _layer(shape, top: Tuple[int, int, int], bottom: Tuple[int, int, int], outline: bool = True) -> None:
        if outline:
            dark = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            shape(ImageDraw.Draw(dark), 3.0, OUT)
            canvas.alpha_composite(dark)
        grad = _gradient((size, size), top, bottom)
        mask = Image.new("L", (size, size), 0)
        shape(ImageDraw.Draw(mask), 0.0, 255)
        canvas.paste(grad, (0, 0), mask)

    # —— 下层面包 ——
    def s_bottom_bun(d, g, fill):
        d.pieslice(
            [X - 0.84 * R - g, Y + 0.40 * R, X + 0.84 * R + g, Y + 1.04 * R + g],
            0, 180, fill=fill,
        )

    _layer(s_bottom_bun, (243, 190, 122), (213, 148, 88))

    # —— 肉饼（带烤痕） ——
    def s_patty(d, g, fill):
        d.rounded_rectangle(
            [X - 0.88 * R - g, Y + 0.27 * R - g, X + 0.88 * R + g, Y + 0.47 * R + g],
            radius=0.10 * R + g, fill=fill,
        )

    _layer(s_patty, (154, 100, 66), (114, 70, 46))

    # —— 芝士（带三处垂滴） ——
    cheese_pts = [(-0.82, 0.10), (0.82, 0.10), (0.82, 0.24), (0.46, 0.17),
                  (0.30, 0.35), (0.10, 0.17), (-0.14, 0.33), (-0.34, 0.17),
                  (-0.56, 0.31), (-0.82, 0.22)]

    def s_cheese(d, g, fill):
        k = 1.0 + g / R
        d.polygon([(X + px * R * k, Y + py * R * k) for px, py in cheese_pts], fill=fill)
        for px, py in [(0.30, 0.35), (-0.14, 0.33), (-0.56, 0.31)]:
            rr = 0.075 * R + g
            d.ellipse([X + px * R - rr, Y + py * R - rr, X + px * R + rr, Y + py * R + rr], fill=fill)

    _layer(s_cheese, (255, 216, 102), (243, 176, 42))

    # —— 生菜（波浪垂边） ——
    def s_lettuce(d, g, fill):
        d.rectangle([X - 0.88 * R - g, Y - 0.02 * R - g, X + 0.88 * R + g, Y + 0.12 * R + g], fill=fill)
        for i in range(-4, 5):
            fx = X + i * 0.215 * R
            rr = 0.115 * R + g
            d.ellipse([fx - rr, Y + 0.02 * R - rr, fx + rr, Y + 0.02 * R + rr], fill=fill)

    _layer(s_lettuce, (148, 202, 86), (108, 158, 56))

    # —— 上层面包 ——
    def s_top_bun(d, g, fill):
        d.pieslice(
            [X - 0.86 * R - g, Y - 1.02 * R - g, X + 0.86 * R + g, Y + 0.06 * R],
            180, 360, fill=fill,
        )

    _layer(s_top_bun, (251, 208, 150), (231, 170, 104))

    d = ImageDraw.Draw(canvas)

    # 上层面包弧线光泽（沿面包左上曲线，替代糊状高光）
    shine = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shine)
    sd.arc(
        [X - 0.78 * R, Y - 0.95 * R, X + 0.30 * R, Y - 0.05 * R],
        182, 252, fill=(255, 255, 255, 120), width=max(3, int(R * 0.07)),
    )
    sd.arc(
        [X - 0.70 * R, Y - 0.86 * R, X + 0.22 * R, Y - 0.08 * R],
        186, 246, fill=(255, 255, 255, 90), width=max(2, int(R * 0.035)),
    )
    shine = shine.filter(ImageFilter.GaussianBlur(3))
    canvas.alpha_composite(shine)

    # 芝麻（避开面部区域：X±0.25R、Y-0.5R~Y-0.1R）
    for px, py, ang in [(-0.48, -0.60, 25), (-0.12, -0.80, -15), (0.30, -0.68, 70),
                        (-0.38, -0.36, -50), (0.46, -0.34, 40)]:
        _sesame(canvas, X + px * R, Y + py * R, max(3, int(R * 0.055)), max(2, int(R * 0.032)), ang)

    # 肉饼烤痕
    for px in (-0.32, 0.0, 0.32):
        x0 = X + px * R - 0.16 * R
        x1 = X + px * R + 0.16 * R
        d.line([(x0, Y + 0.365 * R), (x1, Y + 0.345 * R)], fill=(74, 44, 30, 110), width=max(2, int(R * 0.028)))

    # 芝士顶部反光
    d.line([(X - 0.6 * R, Y + 0.13 * R), (X + 0.6 * R, Y + 0.13 * R)], fill=(255, 246, 214, 120), width=max(2, int(R * 0.022)))

    # 下层面包底部暗影
    d.arc([X - 0.84 * R, Y + 0.82 * R, X + 0.84 * R, Y + 1.04 * R], 20, 160, fill=(150, 96, 54, 90), width=max(2, int(R * 0.03)))

    # —— 表情（吉祥物的灵魂） ——
    eye_y = Y - 0.34 * R
    eye_dx = 0.21 * R
    eye_r = 0.078 * R
    # 眉毛（俏皮地上挑）
    for ex in (X - eye_dx, X + eye_dx):
        d.arc([ex - 0.10 * R, eye_y - 0.17 * R, ex + 0.10 * R, eye_y - 0.01 * R], 200, 340, fill=(88, 54, 40, 230), width=max(2, int(R * 0.024)))
    # 眼睛 + 高光
    for ex in (X - eye_dx, X + eye_dx):
        d.ellipse([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r], fill=(62, 40, 30))
        d.ellipse([ex - eye_r * 0.45, eye_y - eye_r * 0.5, ex + eye_r * 0.1, eye_y + eye_r * 0.05], fill=(255, 255, 255))
    # 腮红
    for bx in (X - 0.40 * R, X + 0.40 * R):
        d.ellipse([bx - 0.085 * R, eye_y + 0.10 * R, bx + 0.085 * R, eye_y + 0.20 * R], fill=(244, 148, 122, 150))
    # 微笑
    d.arc([X - 0.11 * R, eye_y - 0.02 * R, X + 0.11 * R, eye_y + 0.16 * R], 25, 155, fill=(62, 40, 30), width=max(2, int(R * 0.03)))

    img.alpha_composite(canvas, (int(cx - size / 2), int(cy - size / 2)))


def _base_canvas() -> Image.Image:
    img = Image.new("RGBA", (CARD_W, CARD_H))
    bg = _gradient((CARD_W, CARD_H), CREAM_TOP, CREAM_BOTTOM)
    img.paste(bg, (0, 0))
    _dots(img)
    return img


def _header(img: Image.Image, title: str, subtitle: str, right: str = "") -> None:
    """渐变红头 + 黄色收口条 + 标题投影。"""
    _grad_rect(img, (0, 0, CARD_W, 208), 0, RED_TOP, RED_BOTTOM)
    _grad_rect(img, (0, 208, CARD_W, 216), 0, YELLOW_TOP, YELLOW_BOTTOM)
    d = ImageDraw.Draw(img)
    # 标题（深色投影制造立体感）
    d.text((74, 52), title, font=load_font(66, bold=True), fill=(120, 18, 12))
    d.text((70, 48), title, font=load_font(66, bold=True), fill=WHITE)
    d.text((72, 140), subtitle, font=load_font(27), fill=(255, 226, 206))
    if right:
        f = load_font(24)
        d.text((CARD_W - 70 - text_w(d, right, f), 66), right, font=f, fill=(255, 214, 190))


def _footer(d: ImageDraw.ImageDraw, text: str) -> None:
    f = load_font(22)
    tw = text_w(d, text, f)
    d.text(((CARD_W - tw) / 2, 1452), text, font=f, fill=GRAY)


# ————————————————— 麦门人生角色卡 —————————————————


def render_life_card(profile: LifeProfile, out_path: str) -> str:
    img = _base_canvas()
    d = ImageDraw.Draw(img)
    _header(img, "麦门人生", "McLIFE CARD · 麦门食堂")

    # 头像圈 + 会笑的汉堡
    cx, cy, r = CARD_W // 2, 382, 118
    _shadow(img, (cx - r - 12, cy - r - 6, cx + r + 12, cy + r + 14), radius=r + 12, blur=22, alpha=55, offset=10)
    d.ellipse([cx - r - 12, cy - r - 12, cx + r + 12, cy + r + 12], fill=YELLOW)
    d.ellipse([cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4], fill=(255, 252, 244))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 250, 240))
    draw_burger(img, cx, cy, r)

    # 编号 + 等级药丸
    serial_f = load_font(28)
    st = f"编号 #{profile.serial}"
    d.text(((CARD_W - text_w(d, st, serial_f)) / 2, 528), st, font=serial_f, fill=GRAY)
    _pill(img, CARD_W // 2, 572, f"Lv.{profile.level_no} · {profile.level_name}", load_font(42, bold=True), RED_TOP, RED_BOTTOM, WHITE, height=68, pad=36)

    # 属性面板
    _shadow(img, (70, 668, 1130, 966), radius=28, blur=20, alpha=50)
    d.rounded_rectangle([70, 668, 1130, 966], radius=28, fill=WHITE, outline=LIGHT_LINE, width=2)
    attrs = [("食力", profile.attrs.食力, ORANGE_TOP, ORANGE_BOTTOM), ("财力", profile.attrs.财力, RED_TOP, RED_BOTTOM),
             ("广度", profile.attrs.广度, GREEN_TOP, GREEN_BOTTOM), ("信仰", profile.attrs.信仰, BLUE, (21, 101, 192))]
    label_f = load_font(26, bold=True)
    value_f = load_font(30, bold=True)
    for i, (name, value, top, bottom) in enumerate(attrs):
        y = 700 + i * 64
        _grad_rect(img, (104, y, 190, y + 44), 22, (250, 246, 239), (243, 238, 229))
        d.rounded_rectangle([104, y, 190, y + 44], radius=22, outline=LIGHT_LINE, width=1)
        d.text((147 - text_w(d, name, label_f) / 2, y + 8), name, font=label_f, fill=DARK)
        d.rounded_rectangle([218, y + 11, 950, y + 33], radius=11, fill=BAR_BG)
        if value > 0:
            _grad_rect(img, (218, y + 11, int(218 + (950 - 218) * value / 100), y + 33), 11, top, bottom)
        d.text((975, y + 4), str(value), font=value_f, fill=top if value > 0 else GRAY)

    # 成就徽章
    d.text((70, 996), "成就徽章", font=load_font(26, bold=True), fill=GRAY)
    chip_f = load_font(24)
    x, y = 70, 1038
    for a in profile.achievements:
        w = text_w(d, a, chip_f) + 44
        if x + w > 1130:
            x = 70
            y += 62
        used = _chip(img, x, y, a, chip_f)
        x += used + 18
    if not profile.achievements:
        d.text((70, 1038), "暂无——去点几单解锁第一枚", font=chip_f, fill=GRAY)

    # 常驻单品
    if profile.top_items:
        fav = "、".join(f"{name}×{n}" for name, n in profile.top_items)
        line = f"常驻{profile.dominant_slot_label} · 常点：{fav}"
        _pill(img, CARD_W // 2, 1200, line, load_font(24), (252, 248, 240), (246, 240, 230), GRAY, height=48, pad=26)

    # 底部信息条
    _shadow(img, (70, 1286, 1130, 1392), radius=24, blur=18, alpha=50)
    _grad_rect(img, (70, 1286, 1130, 1392), 24, YELLOW_TOP, YELLOW_BOTTOM)
    info = f"麦龄 {profile.maling_days} 天 · {profile.total_orders} 单 · 总消费 {fmt_yuan(profile.total_yuan)} · 客单价 {fmt_yuan(profile.avg_order_yuan)}"
    info_font = fit_font(d, info, 30, 1000, bold=True)
    tw = text_w(d, info, info_font)
    d.text(((CARD_W - tw) / 2, 1286 + (106 - info_font.size) / 2 - 4), info, font=info_font, fill=DARK)

    _footer(d, "数据来自你的麦当劳订单 · 非麦当劳官方作品 · 麦门食堂 McCanteen")

    img.convert("RGB").save(out_path, "PNG")
    return out_path


# ————————————————— 今日饭卡 —————————————————


def _medal(img: Image.Image, cx: int, cy: int, r: int, top, bottom, number: str) -> None:
    d = ImageDraw.Draw(img)
    _grad_rect(img, (cx - r, cy - r, cx + r, cy + r), r, top, bottom)
    d.ellipse([cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4], outline=(255, 255, 255, 180), width=3)
    f = load_font(int(r * 1.1), bold=True)
    nw = text_w(d, number, f)
    d.text((cx - nw / 2, cy - r * 0.62), number, font=f, fill=WHITE)


def render_decide_card(decision: Decision, out_path: str) -> str:
    img = _base_canvas()
    d = ImageDraw.Draw(img)

    date_str = datetime.now().strftime("%Y-%m-%d %A")
    _header(img, "今日饭卡", f"{decision.slot.label} · {decision.persona}", right=date_str)

    # 结论卡（带巨大装饰引号）
    _shadow(img, (70, 288, 1130, 428), radius=26, blur=20, alpha=50)
    d.rounded_rectangle([70, 288, 1130, 428], radius=26, fill=WHITE, outline=LIGHT_LINE, width=2)
    quote_f = load_font(110, bold=True)
    d.text((98, 292), "\u201c", font=quote_f, fill=(247, 224, 170))
    verdict_font = fit_font(d, decision.verdict, 33, 900, bold=True)
    y = 312
    for line in wrap_text(d, decision.verdict, verdict_font, 900)[:2]:
        d.text((150, y), line, font=verdict_font, fill=DARK)
        y += 50

    # 摇一摇印章
    if decision.shake:
        stamp = Image.new("RGBA", (380, 96), (0, 0, 0, 0))
        sd = ImageDraw.Draw(stamp)
        sd.rounded_rectangle([4, 4, 376, 92], radius=18, outline=DARK_RED, width=6)
        sf = load_font(40, bold=True)
        sw = text_w(sd, "让食堂替你决定", sf)
        sd.text(((380 - sw) / 2, 24), "让食堂替你决定", font=sf, fill=DARK_RED)
        stamp = stamp.rotate(-10, expand=True, resample=Image.BICUBIC)
        img.paste(stamp, (CARD_W - 450, 296), stamp)

    # 三个候选
    medals = [(GOLD_TOP, GOLD_BOTTOM), (SILVER_TOP, SILVER_BOTTOM), (BRONZE_TOP, BRONZE_BOTTOM)]
    y = 462
    for i, opt in enumerate(decision.options[:3]):
        _shadow(img, (70, y, 1130, y + 246), radius=26, blur=18, alpha=45)
        d.rounded_rectangle([70, y, 1130, y + 246], radius=26, fill=WHITE, outline=LIGHT_LINE, width=2)
        _medal(img, 142, y + 68, 40, medals[i][0], medals[i][1], str(i + 1))

        name_font = fit_font(d, opt.meal.name, 38, 640, bold=True)
        d.text((208, y + 30), opt.meal.name, font=name_font, fill=DARK)

        pf = load_font(38, bold=True)
        d.text((208, y + 96), fmt_yuan(opt.meal.price), font=pf, fill=RED)
        if opt.coupon is not None:
            net_txt = f"用券后 {fmt_yuan(opt.net_price)}"
            nf = load_font(24, bold=True)
            tw = text_w(d, net_txt, nf)
            _grad_rect(img, (208, y + 152, 208 + tw + 40, y + 196), 22, GREEN_TOP, GREEN_BOTTOM)
            d.text((228, y + 162), net_txt, font=nf, fill=WHITE)

        reason = "；".join(opt.reasons[:2]) or "食堂今日推荐"
        rf = load_font(24)
        ry = y + 158 if opt.coupon is None else y + 206
        for line in wrap_text(d, reason, rf, 830)[:1]:
            d.text((208, ry), line, font=rf, fill=GRAY)
        y += 270

    # 沉默成本条
    parts = [f"你还有 {decision.urgent_coupon_count} 张券 48 小时内过期"]
    if decision.silent_cost_yuan > 0:
        parts.append(f"已核实面值 {fmt_yuan(decision.silent_cost_yuan)}")
    if getattr(decision, "unknown_face_count", 0):
        parts.append(f"{decision.unknown_face_count} 张面值待核实")
    if decision.urgent_coupon_count > 0:
        line = "，".join(parts) + "——别让它蒸发了"
        top, bottom, color = YELLOW_TOP, YELLOW_BOTTOM, DARK
    else:
        line = "暂无即将过期的券，安心吃"
        top, bottom, color = (226, 242, 228), (206, 232, 210), (27, 94, 32)
    _shadow(img, (70, 1296, 1130, 1402), radius=24, blur=18, alpha=50)
    _grad_rect(img, (70, 1296, 1130, 1402), 24, top, bottom)
    lf = fit_font(d, line, 30, 1000, bold=True)
    tw = text_w(d, line, lf)
    d.text(((CARD_W - tw) / 2, 1296 + (106 - lf.size) / 2 - 4), line, font=lf, fill=color)

    _footer(d, "真实菜单与价格来自麦当劳 MCP · 演示数据仅供参考 · 麦门食堂 McCanteen")

    img.convert("RGB").save(out_path, "PNG")
    return out_path
