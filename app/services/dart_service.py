from __future__ import annotations
import io
import os
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional

import httpx

from app.models.report import DividendInfo, FinancialYear

DART_BASE = "https://opendart.fss.or.kr/api"
DATA_DIR = Path(__file__).parent.parent.parent / "data"
CORP_XML_PATH = DATA_DIR / "CORPCODE.xml"

# One API call returns three years via thstrm/frmtrm/bfefrmtrm fields
ACCOUNT_IDS = {
    "revenue": "ifrs-full_Revenue",
    "operating_income": "ifrs-full_OperatingIncomeLoss",
    "net_income": "ifrs-full_ProfitLoss",
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
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            # Single call with bsns_year=2024 returns thstrm(2024)/frmtrm(2023)/bfefrmtrm(2022)
            for fs_div in ("CFS", "OFS"):
                params = {
                    "crtfc_key": api_key,
                    "corp_code": corp_code,
                    "bsns_year": "2024",
                    "reprt_code": "11011",
                    "fs_div": fs_div,
                }
                resp = await client.get(f"{DART_BASE}/fnlttSinglAcnt.json", params=params)
                data = resp.json()
                if data.get("status") == "000" and data.get("list"):
                    items = {row["account_id"]: row for row in data["list"]}
                    return _parse_three_years(items)
    except Exception:
        pass
    return []


def _parse_three_years(items: dict) -> List[FinancialYear]:
    def _val(account_id: str, field: str) -> Optional[float]:
        row = items.get(account_id)
        if not row:
            return None
        try:
            raw = row.get(field, "").replace(",", "").strip()
            return float(raw) / 1e8 if raw and raw not in ("-", "") else None
        except Exception:
            return None

    years = [
        FinancialYear(
            year=2024,
            revenue=_val(ACCOUNT_IDS["revenue"], "thstrm_amount"),
            operating_income=_val(ACCOUNT_IDS["operating_income"], "thstrm_amount"),
            net_income=_val(ACCOUNT_IDS["net_income"], "thstrm_amount"),
        ),
        FinancialYear(
            year=2023,
            revenue=_val(ACCOUNT_IDS["revenue"], "frmtrm_amount"),
            operating_income=_val(ACCOUNT_IDS["operating_income"], "frmtrm_amount"),
            net_income=_val(ACCOUNT_IDS["net_income"], "frmtrm_amount"),
        ),
        FinancialYear(
            year=2022,
            revenue=_val(ACCOUNT_IDS["revenue"], "bfefrmtrm_amount"),
            operating_income=_val(ACCOUNT_IDS["operating_income"], "bfefrmtrm_amount"),
            net_income=_val(ACCOUNT_IDS["net_income"], "bfefrmtrm_amount"),
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
            resp = await client.get(
                f"{DART_BASE}/alotMatter.json",
                params={"crtfc_key": api_key, "corp_code": corp_code, "bsns_year": "2024", "reprt_code": "11011"},
            )
        data = resp.json()
        if data.get("status") != "000" or not data.get("list"):
            return None

        rows = {row.get("se", ""): row for row in data["list"] if row.get("stock_knd") == "보통주"}

        def _f(se_key: str, field: str = "thstrm") -> Optional[float]:
            row = rows.get(se_key)
            if not row:
                return None
            try:
                val = row.get(field, "").replace(",", "").replace("%", "").strip()
                return float(val) if val and val not in ("-", "") else None
            except Exception:
                return None

        dps = _f("주당 현금배당금(원)")
        payout = _f("현금배당 성향(%)")
        dyield = _f("현금배당 수익률(%)")

        if all(v is None for v in [dps, payout, dyield]):
            return None
        return DividendInfo(dps=dps, payout_ratio=payout, dividend_yield=dyield)
    except Exception:
        return None
