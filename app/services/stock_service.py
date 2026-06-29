from __future__ import annotations
import re
from typing import Optional
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from app.models.report import Consensus, StockInfo

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://finance.naver.com/",
}


def _get(url: str) -> Optional[BeautifulSoup]:
    try:
        with httpx.Client(headers=HEADERS, timeout=10, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
    except Exception:
        return None


def _clean_num(text: str) -> Optional[float]:
    try:
        val = re.sub(r"[^\d.\-]", "", text.strip())
        return float(val) if val else None
    except Exception:
        return None


async def get_stock_code(company_name: str) -> Optional[str]:
    try:
        encoded = quote(company_name)
        soup = _get(
            f"https://finance.naver.com/search/searchList.naver?query={encoded}"
        )
        if not soup:
            return None
        link = soup.select_one("dl.name_area dt a")
        if not link:
            link = soup.select_one("table.type_1 td.tit a")
        if not link:
            link = soup.select_one("a[href*='code=']")
        if not link:
            return None
        href = link.get("href", "")
        m = re.search(r"code=(\d{6})", href)
        return m.group(1) if m else None
    except Exception:
        return None


async def get_stock_info(stock_code: str) -> Optional[StockInfo]:
    try:
        soup = _get(
            f"https://finance.naver.com/item/main.naver?code={stock_code}"
        )
        if not soup:
            return None

        price: Optional[int] = None
        price_change: Optional[float] = None
        market_cap: Optional[str] = None
        per: Optional[float] = None
        pbr: Optional[float] = None

        # 현재가
        today_dl = soup.select_one("dl.no_today")
        if today_dl:
            spans = today_dl.select("span.blind")
            if spans:
                price_text = spans[0].get_text(strip=True).replace(",", "")
                try:
                    price = int(price_text)
                except Exception:
                    pass

        # 등락률
        blind_spans = soup.select("dl.no_today span.blind")
        for span in blind_spans:
            t = span.get_text(strip=True)
            if "%" in t:
                try:
                    price_change = float(t.replace("%", "").replace("+", ""))
                except Exception:
                    pass
                break

        # 시가총액
        sise_total = soup.select_one("dl.sise_total")
        if sise_total:
            mc_spans = sise_total.select("span.blind")
            if mc_spans:
                market_cap = mc_spans[0].get_text(strip=True)

        # PER / PBR
        per_el = soup.select_one("em#_per")
        pbr_el = soup.select_one("em#_pbr")
        if per_el:
            per = _clean_num(per_el.get_text())
        if pbr_el:
            pbr = _clean_num(pbr_el.get_text())

        return StockInfo(
            current_price=price,
            price_change=price_change,
            market_cap=market_cap,
            per=per,
            pbr=pbr,
        )
    except Exception:
        return None


async def get_consensus(stock_code: str) -> Optional[Consensus]:
    try:
        soup = _get(
            f"https://finance.naver.com/item/coinfo.naver?code={stock_code}"
        )
        if not soup:
            return None

        target_avg: Optional[int] = None
        target_high: Optional[int] = None
        target_low: Optional[int] = None
        buy_count: Optional[int] = None
        neutral_count: Optional[int] = None
        sell_count: Optional[int] = None

        # 목표주가 영역
        consensus_table = soup.select_one("div.con_tab")
        if not consensus_table:
            consensus_table = soup

        # 목표주가 평균/최고/최저
        target_els = consensus_table.select("em.num_score, td em, span.num")
        price_nums = []
        for el in target_els:
            v = _clean_num(el.get_text())
            if v and v > 1000:
                price_nums.append(int(v))

        if len(price_nums) >= 3:
            target_avg, target_high, target_low = price_nums[0], price_nums[1], price_nums[2]
        elif len(price_nums) == 1:
            target_avg = price_nums[0]

        # 투자의견 분포 파싱
        opinion_area = soup.select("dl.opinion_grade dd")
        opinion_texts = [el.get_text(strip=True) for el in opinion_area]
        for text in opinion_texts:
            m = re.search(r"매수[^\d]*(\d+)", text)
            if m:
                buy_count = int(m.group(1))
            m = re.search(r"중립[^\d]*(\d+)", text)
            if m:
                neutral_count = int(m.group(1))
            m = re.search(r"매도[^\d]*(\d+)", text)
            if m:
                sell_count = int(m.group(1))

        if all(v is None for v in [target_avg, target_high, target_low, buy_count]):
            return None

        return Consensus(
            target_avg=target_avg,
            target_high=target_high,
            target_low=target_low,
            buy_count=buy_count,
            neutral_count=neutral_count,
            sell_count=sell_count,
        )
    except Exception:
        return None
