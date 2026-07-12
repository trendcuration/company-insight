from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel


class FinancialYear(BaseModel):
    year: int
    revenue: Optional[float] = None
    operating_income: Optional[float] = None
    net_income: Optional[float] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    total_equity: Optional[float] = None


class DividendInfo(BaseModel):
    dps: Optional[float] = None
    payout_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None


class StockInfo(BaseModel):
    current_price: Optional[int] = None
    price_change: Optional[float] = None
    market_cap: Optional[str] = None
    per: Optional[float] = None
    pbr: Optional[float] = None
    eps: Optional[float] = None
    bps: Optional[float] = None
    high_52w: Optional[int] = None
    low_52w: Optional[int] = None
    volume: Optional[str] = None
    foreign_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None


class Consensus(BaseModel):
    target_avg: Optional[int] = None
    target_high: Optional[int] = None
    target_low: Optional[int] = None
    buy_count: Optional[int] = None
    neutral_count: Optional[int] = None
    sell_count: Optional[int] = None


class NewsItem(BaseModel):
    title: str
    press: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None


class CompanyReport(BaseModel):
    company_name: str
    stock_code: Optional[str] = None
    corp_code: Optional[str] = None
    stock_info: Optional[StockInfo] = None
    financials: List[FinancialYear] = []
    dividend: Optional[DividendInfo] = None
    consensus: Optional[Consensus] = None
    news: List[NewsItem] = []
