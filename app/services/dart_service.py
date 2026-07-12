from __future__ import annotations
import io
import os
from datetime import date
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional

import httpx

from app.models.report import DividendInfo, FinancialYear

DART_BASE = "https://opendart.fss.or.kr/api"
DATA_DIR = Path(__file__).parent.parent.parent / "data"
CORP_XML_PATH = DATA_DIR / "CORPCODE.xml"

# One API call returns three years via thstrm/frmtrm/bfefrmtrm fields.
# fnlttSinglAcnt 응답에는 account_id가 없고 account_nm(계정명)만 있다
# (account_id는 fnlttSinglAcntAll 전용). 손익계산서(IS/CIS) 계정명으로 매칭한다.
ACCOUNT_NAMES = {
    "revenue": "매출액",
    "operating_income": "영업이익",
    "net_income": "당기순이익",
    "total_assets": "자산총계",
    "total_liabilities": "부채총계",
    "total_equity": "자본총계",
}


def _get_api_key() -> Optional[str]:
    return os.getenv("DART_API_KEY") or None


async def _download_corp_xml(api_key: str) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    url = f"{DART_BASE}/corpCode.xml?crtfc_key={api_key}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        xml_bytes = zf.read(zf.namelist()[0])
    CORP_XML_PATH.write_bytes(xml_bytes)


async def get_corp_code(company_name: str) -> Optional[str]:
    api_key = _get_api_key()
    if not api_key:
        return None
    try:
        if not CORP_XML_PATH.exists():
            await _download_corp_xml(api_key)
        root = ET.parse(CORP_XML_PATH).getroot()
        # Exact match first
        for corp in root.findall("list"):
            name_el = corp.find("corp_name")
            code_el = corp.find("corp_code")
            if name_el is not None and code_el is not None:
                if name_el.text == company_name:
                    return code_el.text
        # Partial match fallback
        for corp in root.findall("list"):
            name_el = corp.find("corp_name")
            code_el = corp.find("corp_code")
            if name_el is not None and code_el is not None:
                if name_el.text and company_name in name_el.text:
                    return code_el.text
    except Exception:
        pass
    return None


async def get_financial_data(corp_code: str) -> List[FinancialYear]:
    api_key = _get_api_key()
    if not api_key or not corp_code:
        return []
    results: List[FinancialYear] = []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            # 사업보고서(11011) 1건이 3개년(thstrm/frmtrm/bfefrmtrm)을 담는다.
            # 최신 연도(작년) 보고서가 아직 미공시면 그 전 연도로 폴백.
            this_year = date.today().year
            for bsns_year in (this_year - 1, this_year - 2):
                for fs_div in ("CFS", "OFS"):
                    params = {
                        "crtfc_key": api_key,
                        "corp_code": corp_code,
                        "bsns_year": str(bsns_year),
                        "reprt_code": "11011",
                        "fs_div": fs_div,
                    }
                    resp = await client.get(f"{DART_BASE}/fnlttSinglAcnt.json", params=params)
                    data = resp.json()
                    if data.get("status") == "000" and data.get("list"):
                        results = _parse_three_years(data["list"], bsns_year)
                        if results:
                            break
                if results:
                    break

            # 당해연도 중간실적: 반기(11012) → 1분기(11013) 순으로 시도
            interim = await _fetch_interim(client, corp_code, api_key, this_year)
            if interim:
                results = results + [interim]
    except Exception:
        pass
    return results


async def _fetch_interim(
    client: httpx.AsyncClient, corp_code: str, api_key: str, year: int,
) -> Optional[FinancialYear]:
    for reprt_code, label in (("11012", f"{year} 상반기"), ("11013", f"{year} 1분기")):
        for fs_div in ("CFS", "OFS"):
            try:
                params = {
                    "crtfc_key": api_key,
                    "corp_code": corp_code,
                    "bsns_year": str(year),
                    "reprt_code": reprt_code,
                    "fs_div": fs_div,
                }
                resp = await client.get(f"{DART_BASE}/fnlttSinglAcnt.json", params=params)
                data = resp.json()
                if data.get("status") != "000" or not data.get("list"):
                    continue
                fy = _parse_interim(data["list"], year, label)
                if fy:
                    return fy
            except Exception:
                continue
    return None


def _parse_interim(rows: list, year: int, label: str) -> Optional[FinancialYear]:
    # 손익 항목은 누적(thstrm_add_amount) 우선 — 반기보고서의 thstrm_amount는
    # 해당 3개월치라 누적치가 "상반기 실적"에 해당한다. BS는 기말 잔액 그대로.
    items: dict = {}
    for row in rows:
        if row.get("sj_div") not in ("IS", "CIS", "BS"):
            continue
        name = (row.get("account_nm") or "").strip()
        if name not in items:
            items[name] = row

    def _val(account_nm: str, prefer_cumulative: bool) -> Optional[float]:
        row = items.get(account_nm)
        if not row:
            return None
        fields = ["thstrm_add_amount", "thstrm_amount"] if prefer_cumulative else ["thstrm_amount"]
        for field in fields:
            try:
                raw = str(row.get(field, "")).replace(",", "").strip()
                if raw and raw not in ("-", ""):
                    return float(raw) / 1e8
            except Exception:
                continue
        return None

    fy = FinancialYear(
        year=year,
        label=label,
        revenue=_val(ACCOUNT_NAMES["revenue"], True),
        operating_income=_val(ACCOUNT_NAMES["operating_income"], True),
        net_income=_val(ACCOUNT_NAMES["net_income"], True),
        total_assets=_val(ACCOUNT_NAMES["total_assets"], False),
        total_liabilities=_val(ACCOUNT_NAMES["total_liabilities"], False),
        total_equity=_val(ACCOUNT_NAMES["total_equity"], False),
    )
    if any(v is not None for v in [fy.revenue, fy.operating_income, fy.net_income]):
        return fy
    return None


def _parse_three_years(rows: list, base_year: int) -> List[FinancialYear]:
    # 손익계산서 행만, 계정명 기준 매칭. 같은 계정명이 연결/포괄 등으로
    # 중복될 수 있어 첫 번째(정렬 우선) 행을 사용한다.
    # 손익계산서(IS/CIS)와 재무상태표(BS) 계정을 모두 수집한다.
    items: dict = {}
    for row in rows:
        if row.get("sj_div") not in ("IS", "CIS", "BS"):
            continue
        name = (row.get("account_nm") or "").strip()
        if name not in items:
            items[name] = row

    def _val(account_nm: str, field: str) -> Optional[float]:
        row = items.get(account_nm)
        if not row:
            return None
        try:
            raw = str(row.get(field, "")).replace(",", "").strip()
            return float(raw) / 1e8 if raw and raw not in ("-", "") else None
        except Exception:
            return None

    years = [
        FinancialYear(
            year=base_year,
            revenue=_val(ACCOUNT_NAMES["revenue"], "thstrm_amount"),
            operating_income=_val(ACCOUNT_NAMES["operating_income"], "thstrm_amount"),
            net_income=_val(ACCOUNT_NAMES["net_income"], "thstrm_amount"),
            total_assets=_val(ACCOUNT_NAMES["total_assets"], "thstrm_amount"),
            total_liabilities=_val(ACCOUNT_NAMES["total_liabilities"], "thstrm_amount"),
            total_equity=_val(ACCOUNT_NAMES["total_equity"], "thstrm_amount"),
        ),
        FinancialYear(
            year=base_year - 1,
            revenue=_val(ACCOUNT_NAMES["revenue"], "frmtrm_amount"),
            operating_income=_val(ACCOUNT_NAMES["operating_income"], "frmtrm_amount"),
            net_income=_val(ACCOUNT_NAMES["net_income"], "frmtrm_amount"),
            total_assets=_val(ACCOUNT_NAMES["total_assets"], "frmtrm_amount"),
            total_liabilities=_val(ACCOUNT_NAMES["total_liabilities"], "frmtrm_amount"),
            total_equity=_val(ACCOUNT_NAMES["total_equity"], "frmtrm_amount"),
        ),
        FinancialYear(
            year=base_year - 2,
            revenue=_val(ACCOUNT_NAMES["revenue"], "bfefrmtrm_amount"),
            operating_income=_val(ACCOUNT_NAMES["operating_income"], "bfefrmtrm_amount"),
            net_income=_val(ACCOUNT_NAMES["net_income"], "bfefrmtrm_amount"),
            total_assets=_val(ACCOUNT_NAMES["total_assets"], "bfefrmtrm_amount"),
            total_liabilities=_val(ACCOUNT_NAMES["total_liabilities"], "bfefrmtrm_amount"),
            total_equity=_val(ACCOUNT_NAMES["total_equity"], "bfefrmtrm_amount"),
        ),
    ]
    # Return only years with at least one non-None value
    return [fy for fy in years if any(v is not None for v in [fy.revenue, fy.operating_income, fy.net_income])]


async def get_dividend_info(corp_code: str) -> Optional[DividendInfo]:
    api_key = _get_api_key()
    if not api_key or not corp_code:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            this_year = date.today().year
            data = None
            for bsns_year in (this_year - 1, this_year - 2):
                resp = await client.get(
                    f"{DART_BASE}/alotMatter.json",
                    params={"crtfc_key": api_key, "corp_code": corp_code, "bsns_year": str(bsns_year), "reprt_code": "11011"},
                )
                data = resp.json()
                if data.get("status") == "000" and data.get("list"):
                    break
        if not data or data.get("status") != "000" or not data.get("list"):
            return None

        # se 표기는 연도별로 공백·"(연결)" 접두어가 달라 정규화해 매칭한다.
        # 종류(stock_knd)가 있는 항목은 보통주 우선, 없는 항목(배당성향 등)은 그대로 수용.
        rows: dict = {}
        for row in data["list"]:
            se = row.get("se", "").replace(" ", "").replace("(연결)", "")
            knd = (row.get("stock_knd") or "").strip()
            if se not in rows or "보통" in knd:
                rows[se] = row

        def _f(se_key: str, field: str = "thstrm") -> Optional[float]:
            row = rows.get(se_key)
            if not row:
                return None
            try:
                val = row.get(field, "").replace(",", "").replace("%", "").strip()
                return float(val) if val and val not in ("-", "") else None
            except Exception:
                return None

        dps = _f("주당현금배당금(원)")
        payout = _f("현금배당성향(%)")
        dyield = _f("현금배당수익률(%)")

        if all(v is None for v in [dps, payout, dyield]):
            return None
        return DividendInfo(dps=dps, payout_ratio=payout, dividend_yield=dyield)
    except Exception:
        return None
