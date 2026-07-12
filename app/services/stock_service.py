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


async def _get(url: str) -> Optional[BeautifulSoup]:
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=10, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
    except Exception:
        return None


def _clean_num(text: str) -> Optional[float]:
    try:
        val = re.sub(r"[^\d.\-]", "", text.strip())
        return float(val) if val not in ("", "-", ".") else None
    except Exception:
        return None


async def get_stock_code(company_name: str) -> Optional[str]:
    """Search stock code via Naver autocomplete API (replaces broken searchList.naver)."""
    try:
        encoded = quote(company_name)
        url = f"https://ac.stock.naver.com/ac?q={encoded}&target=stock,index,marketindicator"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://finance.naver.com/",
        }
        async with httpx.AsyncClient(headers=headers, timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("items", []):
                code = item.get("code", "")
                if item.get("category") == "stock" and len(code) == 6 and code.isdigit():
                    return code
        return None
    except Exception:
        return None


async def _get_json(url: str) -> Optional[dict]:
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=10, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


async def _stock_info_from_api(stock_code: str) -> Optional[StockInfo]:
    """네이버 공개 JSON API — HTML 스크래핑보다 구조 변경에 강하다."""
    price: Optional[int] = None
    price_change: Optional[float] = None
    market_cap: Optional[str] = None
    per: Optional[float] = None
    pbr: Optional[float] = None

    # 실시간 시세 (현재가/등락률)
    data = await _get_json(
        f"https://polling.finance.naver.com/api/realtime/domestic/stock/{stock_code}"
    )
    if data:
        try:
            item = (data.get("datas") or [{}])[0]
            close = str(item.get("closePrice", "")).replace(",", "")
            if close:
                price = int(float(close))
            ratio = str(item.get("fluctuationsRatio", "")).replace(",", "")
            if ratio:
                price_change = float(ratio)
                # 하락 방향인데 부호가 없는 경우 보정
                direction = (item.get("compareToPreviousPrice") or {}).get("code")
                if direction in ("4", "5") and price_change > 0:
                    price_change = -price_change
        except Exception:
            pass

    eps: Optional[float] = None
    bps: Optional[float] = None
    high_52w: Optional[int] = None
    low_52w: Optional[int] = None
    volume: Optional[str] = None
    foreign_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None

    # 종목 개요 (시총/PER/PBR/52주/거래량 등) — code와 한글 key 라벨 병행 매칭
    data = await _get_json(
        f"https://m.stock.naver.com/api/stock/{stock_code}/integration"
    )
    if data:
        try:
            for info in data.get("totalInfos", []):
                code = info.get("code", "")
                key = str(info.get("key", ""))
                value = str(info.get("value", ""))
                if (code == "marketValue" or "시가총액" in key) and not market_cap:
                    market_cap = value.replace("억원", "억").strip() or None
                elif (code == "per" or key.upper().startswith("PER")) and per is None:
                    per = _clean_num(value)
                elif (code == "pbr" or key.upper().startswith("PBR")) and pbr is None:
                    pbr = _clean_num(value)
                elif (code == "eps" or key.upper().startswith("EPS")) and eps is None:
                    eps = _clean_num(value)
                elif (code == "bps" or key.upper().startswith("BPS")) and bps is None:
                    bps = _clean_num(value)
                elif "52주 최고" in key and high_52w is None:
                    v = _clean_num(value)
                    high_52w = int(v) if v else None
                elif "52주 최저" in key and low_52w is None:
                    v = _clean_num(value)
                    low_52w = int(v) if v else None
                elif key == "거래량" and volume is None:
                    volume = value.strip() or None
                elif "외국인" in key and foreign_ratio is None:
                    foreign_ratio = _clean_num(value)
                elif "배당수익률" in key and dividend_yield is None:
                    dividend_yield = _clean_num(value)
        except Exception:
            pass

    if price is None and market_cap is None and per is None:
        return None
    return StockInfo(
        current_price=price,
        price_change=price_change,
        market_cap=market_cap,
        per=per,
        pbr=pbr,
        eps=eps,
        bps=bps,
        high_52w=high_52w,
        low_52w=low_52w,
        volume=volume,
        foreign_ratio=foreign_ratio,
        dividend_yield=dividend_yield,
    )


async def get_stock_info(stock_code: str) -> Optional[StockInfo]:
    # 1차: JSON API, 2차: 데스크톱 페이지 스크래핑
    info = await _stock_info_from_api(stock_code)
    if info and info.current_price is not None:
        return info
    try:
        soup = await _get(
            f"https://finance.naver.com/item/main.naver?code={stock_code}"
        )
        if not soup:
            return info

        price: Optional[int] = None
        price_change: Optional[float] = None
        market_cap: Optional[str] = None
        per: Optional[float] = None
        pbr: Optional[float] = None

        # 현재가: <dl class="no_today"> 첫 blind span
        today_dl = soup.select_one("dl.no_today")
        if today_dl:
            span = today_dl.select_one("span.blind")
            if span:
                v = _clean_num(span.get_text())
                if v is not None:
                    price = int(v)

        # 등락률: <dl class="no_exday"> — blind span 2개(전일대비 금액, 등락률)
        exday_dl = soup.select_one("dl.no_exday")
        if exday_dl:
            spans = exday_dl.select("span.blind")
            if len(spans) >= 2:
                pct = _clean_num(spans[1].get_text())
                if pct is not None:
                    # 하락 여부는 클래스로 판별 (no_down / ico down)
                    is_down = bool(
                        exday_dl.select_one("em.no_down")
                        or exday_dl.select_one("span.ico.down")
                    )
                    price_change = -abs(pct) if is_down else abs(pct)

        # 시가총액: <em id="_market_sum"> (단위: 억원, "429조 5,394" 형태)
        mc_el = soup.select_one("em#_market_sum")
        if mc_el:
            raw = re.sub(r"\s+", " ", mc_el.get_text(strip=True)).strip()
            if raw:
                market_cap = raw if "조" in raw else f"{raw}억원"
        if not market_cap:
            sise_total = soup.select_one("dl.sise_total span.blind")
            if sise_total:
                market_cap = sise_total.get_text(strip=True)

        per_el = soup.select_one("em#_per")
        pbr_el = soup.select_one("em#_pbr")
        if per_el:
            per = _clean_num(per_el.get_text())
        if pbr_el:
            pbr = _clean_num(pbr_el.get_text())

        if price is None and market_cap is None and per is None:
            return info

        # API에서 얻은 부분 데이터로 빈 값을 보충
        if info:
            price_change = price_change if price_change is not None else info.price_change
            market_cap = market_cap or info.market_cap
            per = per if per is not None else info.per
            pbr = pbr if pbr is not None else info.pbr

        return StockInfo(
            current_price=price,
            price_change=price_change,
            market_cap=market_cap,
            per=per,
            pbr=pbr,
        )
    except Exception:
        return info


def _parse_consensus_soup(soup) -> Optional[Consensus]:
    """페이지에서 '목표주가'/'투자의견' 라벨 기반으로 컨센서스를 추출한다."""
    try:

        target_avg: Optional[int] = None
        target_high: Optional[int] = None
        target_low: Optional[int] = None
        buy_count: Optional[int] = None
        neutral_count: Optional[int] = None
        sell_count: Optional[int] = None

        # "목표주가" 라벨이 붙은 셀의 인접 값만 신뢰한다
        for label_el in soup.find_all(string=re.compile("목표주가")):
            cell = label_el.find_parent(["th", "td", "dt", "strong"])
            if not cell:
                continue
            sibling = cell.find_next_sibling(["td", "dd", "em"])
            if sibling:
                v = _clean_num(sibling.get_text())
                if v and v > 100:
                    target_avg = int(v)
                    break

        # 투자의견 분포 (있는 경우에만)
        for text in [el.get_text(" ", strip=True) for el in soup.select("dl.opinion_grade, div.opinion")]:
            m = re.search(r"매수[^\d]*(\d+)", text)
            if m:
                buy_count = int(m.group(1))
            m = re.search(r"중립[^\d]*(\d+)", text)
            if m:
                neutral_count = int(m.group(1))
            m = re.search(r"매도[^\d]*(\d+)", text)
            if m:
                sell_count = int(m.group(1))

        if target_avg is None and buy_count is None:
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


async def get_consensus(stock_code: str) -> Optional[Consensus]:
    # 1차: 모바일 통합 API에 컨센서스 필드가 있으면 사용
    try:
        data = await _get_json(
            f"https://m.stock.naver.com/api/stock/{stock_code}/integration"
        )
        if data:
            ci = data.get("consensusInfo") or {}
            target = _clean_num(str(ci.get("priceTargetMean", "")))
            if target and target > 100:
                return Consensus(target_avg=int(target))
    except Exception:
        pass

    # 2차: 네이버 종목 코인포 페이지의 실제 데이터 소스(WISEfn) 직접 조회
    for url in (
        f"https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={stock_code}",
        f"https://finance.naver.com/item/coinfo.naver?code={stock_code}",
    ):
        soup = await _get(url)
        if not soup:
            continue
        con = _parse_consensus_soup(soup)
        if con:
            return con
    return None
