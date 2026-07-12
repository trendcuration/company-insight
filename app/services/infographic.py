from __future__ import annotations
import io
import math
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from app.models.report import CompanyReport

WIDTH = 1200
HEIGHT = 1600

COLOR_BG_TOP = (26, 26, 46)
COLOR_BG_BOT = (22, 33, 62)
COLOR_CARD = (0, 0, 0, 120)
COLOR_HEADER = (15, 15, 30)
COLOR_WHITE = (255, 255, 255)
COLOR_GRAY = (180, 180, 200)
COLOR_GREEN = (39, 174, 96)
COLOR_RED = (231, 76, 60)
COLOR_ACCENT = (52, 152, 219)
COLOR_GOLD = (241, 196, 15)
COLOR_GRID = (255, 255, 255, 18)

# 번들 폰트 우선 — 배포 서버에 시스템 한글 폰트가 없어도 렌더링 보장
FONTS_DIR = Path(__file__).parent.parent / "fonts"

NOTO_PATHS = [
    str(FONTS_DIR / "NanumGothicBold.ttf"),
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Bold.otf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
NOTO_REGULAR_PATHS = [
    str(FONTS_DIR / "NanumGothic.ttf"),
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Regular.otf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _load_font(paths: List[str], size: int) -> ImageFont.FreeTypeFont:
    for p in paths:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _gradient_bg(width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height))
    top_r, top_g, top_b = COLOR_BG_TOP
    bot_r, bot_g, bot_b = COLOR_BG_BOT
    for y in range(height):
        t = y / height
        r = int(top_r + (bot_r - top_r) * t)
        g = int(top_g + (bot_g - top_g) * t)
        b = int(top_b + (bot_b - top_b) * t)
        for x in range(width):
            img.putpixel((x, y), (r, g, b))
    return img


def _draw_grid(draw: ImageDraw.ImageDraw) -> None:
    grid_color = (255, 255, 255, 18)
    step = 40
    for x in range(0, WIDTH, step):
        draw.line([(x, 0), (x, HEIGHT)], fill=(50, 60, 90), width=1)
    for y in range(0, HEIGHT, step):
        draw.line([(0, y), (WIDTH, y)], fill=(50, 60, 90), width=1)


def _draw_card(
    base: Image.Image,
    x: int, y: int, w: int, h: int,
    radius: int = 16,
) -> None:
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=(0, 0, 20, 130))
    base.paste(
        Image.new("RGB", base.size, (0, 0, 20)),
        mask=overlay.split()[3],
    )


def _fmt_num(val: Optional[float], decimals: int = 0) -> str:
    if val is None:
        return "N/A"
    if decimals == 0:
        return f"{int(val):,}"
    return f"{val:,.{decimals}f}"


def _fmt_eok(val: Optional[float]) -> str:
    if val is None:
        return "N/A"
    if abs(val) >= 10000:
        return f"{val / 10000:.1f}조"
    return f"{int(val):,}억"


def _draw_pie(
    draw: ImageDraw.ImageDraw,
    cx: int, cy: int, r: int,
    buy: int, neutral: int, sell: int,
) -> None:
    total = buy + neutral + sell
    if total == 0:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=COLOR_GRAY)
        return
    angles = [
        (buy / total * 360, (39, 174, 96)),
        (neutral / total * 360, (127, 140, 141)),
        (sell / total * 360, (231, 76, 60)),
    ]
    start = -90
    for deg, color in angles:
        if deg > 0:
            draw.pieslice(
                [cx - r, cy - r, cx + r, cy + r],
                start=start,
                end=start + deg,
                fill=color,
            )
            start += deg


def _draw_section_title(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int, y: int,
    font: ImageFont.FreeTypeFont,
) -> None:
    draw.text((x, y), text, font=font, fill=COLOR_ACCENT)


def generate_report_image(report: CompanyReport) -> bytes:
    base = _gradient_bg(WIDTH, HEIGHT)
    draw_grid = ImageDraw.Draw(base)
    _draw_grid(draw_grid)

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_title = _load_font(NOTO_PATHS, 48)
    font_big = _load_font(NOTO_PATHS, 72)
    font_sec = _load_font(NOTO_PATHS, 24)
    font_body = _load_font(NOTO_REGULAR_PATHS, 22)
    font_small = _load_font(NOTO_REGULAR_PATHS, 18)
    font_label = _load_font(NOTO_REGULAR_PATHS, 20)

    PAD = 40

    # ── 헤더바 (y=0~80) ────────────────────────────────────────────
    draw.rectangle([0, 0, WIDTH, 80], fill=(10, 10, 25, 230))
    draw.text((PAD, 22), "Company Insight", font=font_sec, fill=COLOR_ACCENT)
    draw.text((WIDTH - PAD - 200, 22), "issuepicki.com", font=font_small, fill=COLOR_GRAY)

    # ── 기업명 + 종목코드 (y=90~165) ──────────────────────────────
    code_str = f"  [{report.stock_code}]" if report.stock_code else ""
    draw.text((PAD, 90), report.company_name + code_str, font=font_title, fill=COLOR_WHITE)
    draw.line([(PAD, 160), (WIDTH - PAD, 160)], fill=(60, 80, 120, 200), width=1)

    # ── 주가 카드 (y=175~325) ─────────────────────────────────────
    _draw_card_on_overlay(draw, PAD, 175, WIDTH - PAD * 2, 140)
    draw.text((PAD + 20, 185), "현재 주가", font=font_label, fill=COLOR_ACCENT)
    si = report.stock_info
    if si and si.current_price:
        price_color = (
            COLOR_GREEN if (si.price_change or 0) >= 0 else COLOR_RED
        )
        price_text = f"{si.current_price:,}원"
        draw.text((PAD + 20, 215), price_text, font=font_big, fill=price_color)
        if si.price_change is not None:
            sign = "▲" if si.price_change >= 0 else "▼"
            chg_text = f"{sign} {abs(si.price_change):.2f}%"
            draw.text((PAD + 20 + 280, 235), chg_text, font=font_sec, fill=price_color)
        info_parts = []
        if si.market_cap:
            info_parts.append(f"시총: {si.market_cap}")
        if si.per is not None:
            info_parts.append(f"PER: {si.per:.1f}x")
        if si.pbr is not None:
            info_parts.append(f"PBR: {si.pbr:.1f}x")
        draw.text((PAD + 20, 295), "  |  ".join(info_parts), font=font_small, fill=COLOR_GRAY)
    else:
        draw.text((PAD + 20, 225), "데이터 없음", font=font_sec, fill=COLOR_GRAY)

    # ── 재무제표 카드 (y=340~600) ──────────────────────────────────
    _draw_card_on_overlay(draw, PAD, 340, WIDTH - PAD * 2, 245)
    draw.text((PAD + 20, 352), "재무제표 (단위: 억원)", font=font_label, fill=COLOR_ACCENT)
    if report.financials:
        col_w = (WIDTH - PAD * 2 - 40) // 4
        headers = ["연도", "매출액", "영업이익", "순이익"]
        header_y = 385
        for i, h in enumerate(headers):
            draw.text((PAD + 20 + col_w * i, header_y), h, font=font_small, fill=COLOR_GRAY)
        draw.line(
            [(PAD + 20, header_y + 22), (WIDTH - PAD - 20, header_y + 22)],
            fill=(60, 80, 120, 180), width=1,
        )
        for ri, fy in enumerate(sorted(report.financials, key=lambda x: x.year)):
            row_y = 415 + ri * 52
            draw.text((PAD + 20, row_y), str(fy.year), font=font_body, fill=COLOR_WHITE)
            draw.text((PAD + 20 + col_w, row_y), _fmt_eok(fy.revenue), font=font_body, fill=COLOR_WHITE)
            oi_color = COLOR_GREEN if (fy.operating_income or 0) >= 0 else COLOR_RED
            draw.text((PAD + 20 + col_w * 2, row_y), _fmt_eok(fy.operating_income), font=font_body, fill=oi_color)
            ni_color = COLOR_GREEN if (fy.net_income or 0) >= 0 else COLOR_RED
            draw.text((PAD + 20 + col_w * 3, row_y), _fmt_eok(fy.net_income), font=font_body, fill=ni_color)
    else:
        draw.text((PAD + 20, 430), "DART 재무데이터 없음 (API 키 확인 필요)", font=font_body, fill=COLOR_GRAY)

    # ── 배당 정보 카드 (y=615~810) ─────────────────────────────────
    _draw_card_on_overlay(draw, PAD, 615, WIDTH - PAD * 2, 185)
    draw.text((PAD + 20, 627), "배당 정보", font=font_label, fill=COLOR_ACCENT)
    div = report.dividend
    if div and any(v is not None for v in [div.dps, div.payout_ratio, div.dividend_yield]):
        items = [
            ("주당배당금(DPS)", f"{_fmt_num(div.dps, 0)}원" if div.dps else "N/A"),
            ("배당성향", f"{_fmt_num(div.payout_ratio, 1)}%" if div.payout_ratio else "N/A"),
            ("시가배당률", f"{_fmt_num(div.dividend_yield, 2)}%" if div.dividend_yield else "N/A"),
        ]
        col_w3 = (WIDTH - PAD * 2 - 40) // 3
        for i, (label, val) in enumerate(items):
            bx = PAD + 20 + col_w3 * i
            draw.text((bx, 665), label, font=font_small, fill=COLOR_GRAY)
            draw.text((bx, 695), val, font=font_sec, fill=COLOR_GOLD)
    else:
        draw.text((PAD + 20, 680), "배당 데이터 없음", font=font_body, fill=COLOR_GRAY)

    # ── 증권가 전망 카드 (y=825~1075) ─────────────────────────────
    _draw_card_on_overlay(draw, PAD, 825, WIDTH - PAD * 2, 250)
    draw.text((PAD + 20, 837), "증권가 전망", font=font_label, fill=COLOR_ACCENT)
    con = report.consensus
    if con and con.target_avg:
        # 목표주가
        draw.text((PAD + 20, 875), "목표주가", font=font_small, fill=COLOR_GRAY)
        draw.text((PAD + 20, 900), f"평균 {con.target_avg:,}원", font=font_sec, fill=COLOR_WHITE)
        if con.target_high and con.target_low:
            draw.text(
                (PAD + 20, 940),
                f"최고 {con.target_high:,}원  /  최저 {con.target_low:,}원",
                font=font_small, fill=COLOR_GRAY,
            )
        # 파이차트
        buy = con.buy_count or 0
        neutral = con.neutral_count or 0
        sell = con.sell_count or 0
        if buy + neutral + sell > 0:
            pie_cx = WIDTH - PAD - 120
            pie_cy = 930
            _draw_pie(draw, pie_cx, pie_cy, 70, buy, neutral, sell)
            legend_y = 1010
            for label, color, cnt in [
                ("매수", COLOR_GREEN, buy),
                ("중립", COLOR_GRAY, neutral),
                ("매도", COLOR_RED, sell),
            ]:
                draw.rectangle([pie_cx - 72, legend_y, pie_cx - 60, legend_y + 12], fill=color)
                draw.text((pie_cx - 54, legend_y - 2), f"{label} {cnt}", font=font_small, fill=COLOR_WHITE)
                legend_y += 22
    else:
        draw.text((PAD + 20, 895), "증권사 컨센서스 데이터 없음", font=font_body, fill=COLOR_GRAY)

    # ── 종합평가 카드 (y=1095~1215) ────────────────────────────────
    _draw_card_on_overlay(draw, PAD, 1095, WIDTH - PAD * 2, 120)
    draw.text((PAD + 20, 1107), "종합평가", font=font_label, fill=COLOR_ACCENT)
    summary = _build_summary(report)
    draw.text((PAD + 20, 1140), summary, font=font_body, fill=COLOR_WHITE)

    # ── 푸터 (y=1255~) ────────────────────────────────────────────
    draw.line([(PAD, 1255), (WIDTH - PAD, 1255)], fill=(60, 80, 120, 180), width=1)
    draw.text(
        (PAD, 1270),
        "Company Insight by TRENQURA  ·  issuepicki.com",
        font=font_small, fill=COLOR_GRAY,
    )
    draw.text(
        (PAD, 1295),
        "데이터 출처: DART Open API, 네이버 금융",
        font=font_small, fill=(120, 130, 150),
    )

    # RGBA 오버레이를 RGB 베이스에 합성
    base = base.convert("RGBA")
    base = Image.alpha_composite(base, overlay)
    base = base.convert("RGB")

    buf = io.BytesIO()
    base.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _draw_card_on_overlay(
    draw: ImageDraw.ImageDraw,
    x: int, y: int, w: int, h: int,
    radius: int = 16,
) -> None:
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=(0, 0, 20, 140))


def _build_summary(report: CompanyReport) -> str:
    parts: List[str] = []
    si = report.stock_info
    if si and si.current_price:
        change_str = ""
        if si.price_change is not None:
            sign = "+" if si.price_change >= 0 else ""
            change_str = f" ({sign}{si.price_change:.2f}%)"
        parts.append(f"현재가 {si.current_price:,}원{change_str}")
    if report.financials:
        latest = sorted(report.financials, key=lambda x: x.year)[-1]
        if latest.revenue:
            parts.append(f"{latest.year}년 매출 {_fmt_eok(latest.revenue)}")
        if latest.operating_income is not None:
            oi_str = _fmt_eok(latest.operating_income)
            parts.append(f"영업이익 {oi_str}")
    if report.consensus and report.consensus.target_avg:
        parts.append(f"증권가 목표가 {report.consensus.target_avg:,}원")
    if not parts:
        return "데이터를 불러오지 못했습니다. API 키 및 네트워크 상태를 확인하세요."
    return "  |  ".join(parts)
