from __future__ import annotations
import asyncio
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.models.report import CompanyReport, DividendInfo, FinancialYear, StockInfo, Consensus
from app.services.dart_service import get_corp_code, get_dividend_info, get_financial_data
from app.services.infographic import generate_report_image
from app.services.stock_service import get_consensus, get_news, get_stock_code, get_stock_info

router = APIRouter()


async def _safe_return_list() -> List[FinancialYear]:
    return []


async def _safe_return_none_div() -> Optional[DividendInfo]:
    return None


# 데이터 소스(시세·재무·배당·컨센서스·뉴스)를 동시에 조회하는 전체 시간 예산(초).
_DATA_BUDGET_SECONDS = 20


async def _gather_with_budget(*coros):
    """여러 소스를 동시에 조회하되, 실패했거나 예산 안에 못 끝낸 소스는 None으로 대체해 돌려준다."""
    tasks = [asyncio.ensure_future(c) for c in coros]
    done, pending = await asyncio.wait(tasks, timeout=_DATA_BUDGET_SECONDS)
    for task in pending:
        task.cancel()
    results = []
    for task in tasks:
        if task in done and not task.cancelled() and task.exception() is None:
            results.append(task.result())
        else:
            results.append(None)
    return tuple(results)


async def _collect_report(company_name: str) -> CompanyReport:
    stock_code = await get_stock_code(company_name)
    if not stock_code:
        raise HTTPException(status_code=400, detail="기업을 찾을 수 없습니다")

    corp_code = await get_corp_code(company_name, stock_code)

    financials_coro = get_financial_data(corp_code) if corp_code else _safe_return_list()
    dividend_coro = get_dividend_info(corp_code) if corp_code else _safe_return_none_div()

    # 데이터 소스 하나가 실패하거나 느려도 나머지로 리포트를 보여준다.
    results = await _gather_with_budget(
        get_stock_info(stock_code),
        financials_coro,
        dividend_coro,
        get_consensus(stock_code),
        get_news(stock_code),
    )
    stock_info, financials, dividend, consensus, news = results
    if stock_info is None and not financials and consensus is None and not news:
        raise HTTPException(status_code=502, detail="데이터 수집 중 오류가 발생했습니다")

    return CompanyReport(
        company_name=company_name,
        stock_code=stock_code,
        corp_code=corp_code,
        stock_info=stock_info,
        financials=financials or [],
        dividend=dividend,
        consensus=consensus,
        news=news or [],
    )


@router.get("/api/data/{company_name}")
async def get_report_data(company_name: str) -> CompanyReport:
    """미니앱용: 리포트 데이터를 JSON으로 반환 (화면에서 HTML 렌더링)."""
    return await _collect_report(company_name)


@router.post("/api/report/{company_name}")
async def create_report(company_name: str) -> Response:
    """웹용: 인포그래픽 PNG 이미지를 직접 반환."""
    report = await _collect_report(company_name)

    try:
        png_bytes = generate_report_image(report)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"인포그래픽 생성 오류: {exc}")

    # HTTP 헤더는 latin-1만 허용 — 한글 파일명은 RFC 5987 filename*로 인코딩
    encoded_name = quote(f"{company_name}_report.png")
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f"inline; filename=\"report.png\"; filename*=UTF-8''{encoded_name}"
        },
    )
