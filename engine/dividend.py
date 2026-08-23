"""
配息歷史實算引擎
依確認公式：
1. 總投資額依組合權重分配到各基金
2. 各基金：分配金額 × 該月實際配息率，加總該基金所有月份配息
3. 依配息幣別，以「當年平均匯率」換算成台幣
4. 扣除管理費與相關成本
5. 再加總所有基金的淨配息
年化配息率 = 淨總配息 / 投入本金 / 年數
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd
import numpy as np


@dataclass
class FundHolding:
    name: str
    ticker: str
    weight: float
    currency: str = "TWD"
    expense_ratio: float = 0.015


@dataclass
class DividendResult:
    total_net_dividend_twd: float
    annualized_yield: float
    avg_monthly_dividend: float
    avg_yearly_dividend: float
    years: float
    by_fund: Dict[str, dict] = field(default_factory=dict)
    monthly_series: Optional[pd.Series] = None
    notes: List[str] = field(default_factory=list)


def _year_frac(start: pd.Timestamp, end: pd.Timestamp) -> float:
    return max((end - start).days / 365.25, 1/12)


def calculate_portfolio_dividends(
    total_invest_twd: float,
    holdings: List[FundHolding],
    price_data: Dict[str, pd.DataFrame],
    div_data: Dict[str, pd.DataFrame],
    fx_yearly: Dict[str, Dict[int, float]],
    start: str,
    end: str,
    default_fx: Optional[Dict[str, float]] = None,
) -> DividendResult:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    years = _year_frac(start_ts, end_ts)
    default_fx = default_fx or {"USD": 31.0, "ZAR": 1.7, "AUD": 20.5, "TWD": 1.0}

    w_sum = sum(h.weight for h in holdings) or 1.0
    notes = []
    by_fund = {}
    monthly_net = pd.Series(dtype=float)

    for h in holdings:
        alloc = total_invest_twd * (h.weight / w_sum)
        ticker = h.ticker
        px = price_data.get(ticker)
        div = div_data.get(ticker)

        if px is None or px.empty:
            notes.append(f"{h.name}({ticker}) 無價格資料，跳過")
            continue

        px = px.copy()
        px.index = pd.to_datetime(px.index).tz_localize(None)
        px = px.loc[start_ts:end_ts]
        if px.empty:
            notes.append(f"{h.name} 在區間內無價格")
            continue

        if div is not None and not div.empty:
            d = div.copy()
            d.index = pd.to_datetime(d.index).tz_localize(None)
            d = d.loc[start_ts:end_ts]
        else:
            d = pd.DataFrame()

        close_col = "Adj Close" if "Adj Close" in px.columns else "Close"
        if close_col not in px.columns:
            notes.append(f"{h.name} 缺少收盤價欄位")
            continue

        fund_monthly_div_twd = []
        total_div_twd = 0.0

        if not d.empty and "Dividends" in d.columns:
            try:
                init_nav = float(px[close_col].iloc[0])
            except Exception:
                init_nav = 0.0
            if init_nav <= 0:
                notes.append(f"{h.name} 期初淨值異常")
                continue
            start_year = int(px.index[0].year) if len(px) else start_ts.year
            init_fx = fx_yearly.get(h.currency, {}).get(start_year, default_fx.get(h.currency, 1.0))
            if h.currency == "TWD":
                alloc_ccy = alloc
            else:
                alloc_ccy = alloc / init_fx if init_fx > 0 else alloc
            units = alloc_ccy / init_nav
            for dt, row in d.iterrows():
                raw_div = float(row["Dividends"])
                if raw_div <= 0:
                    continue
                div_amount_ccy = units * raw_div
                year = int(pd.Timestamp(dt).year)
                rate = fx_yearly.get(h.currency, {}).get(year, default_fx.get(h.currency, 1.0))
                div_twd = div_amount_ccy * rate
                total_div_twd += div_twd
                fund_monthly_div_twd.append((pd.Timestamp(dt), div_twd))
        else:
            notes.append(f"{h.name} 無真實配息紀錄，該檔配息以 0 計算（請補資料）")
            total_div_twd = 0.0

        mgmt_fee = alloc * h.expense_ratio * years
        net_div = max(total_div_twd - mgmt_fee, 0.0)

        by_fund[h.name] = {
            "alloc_twd": round(alloc, 0),
            "gross_div_twd": round(total_div_twd, 0),
            "mgmt_fee_twd": round(mgmt_fee, 0),
            "net_div_twd": round(net_div, 0),
            "weight": h.weight,
            "currency": h.currency,
            "expense_ratio": h.expense_ratio,
        }

        if fund_monthly_div_twd:
            s = pd.Series({dt: v for dt, v in fund_monthly_div_twd})
            monthly_net = monthly_net.add(s, fill_value=0)

    total_net = sum(v["net_div_twd"] for v in by_fund.values())
    ann_yield = (total_net / total_invest_twd / years) if total_invest_twd > 0 and years > 0 else 0.0
    avg_monthly = total_net / (years * 12) if years > 0 else 0.0
    avg_yearly = total_net / years if years > 0 else 0.0

    return DividendResult(
        total_net_dividend_twd=round(total_net, 0),
        annualized_yield=round(ann_yield, 4),
        avg_monthly_dividend=round(avg_monthly, 0),
        avg_yearly_dividend=round(avg_yearly, 0),
        years=round(years, 2),
        by_fund=by_fund,
        monthly_series=monthly_net.sort_index() if not monthly_net.empty else None,
        notes=notes,
    )
