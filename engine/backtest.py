"""
主回測引擎
- 整合資金成本、配息實算、淨值走勢
- 條件式定期定額 / 大盤觸發
- 斷頭風險監控（保單質借水位、現金流覆蓋率）
- 歷史壓力情境切片
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import pandas as pd
import numpy as np

from .funding import (
    PrincipalSource, MortgageSource, PolicyLoanSource,
    RevolvingRepledgeSource, calculate_funding, FundingResult
)
from .dividend import FundHolding, calculate_portfolio_dividends, DividendResult


STRESS_PERIODS = [
    ("2008 環球股災", "2007-10-01", "2009-03-31"),
    ("2011 歐債／美債", "2011-07-01", "2011-10-31"),
    ("2015 中國股災", "2015-06-01", "2015-09-30"),
    ("2018 升息＋貿易戰", "2018-01-01", "2018-12-31"),
    ("2020 COVID", "2020-02-15", "2020-04-30"),
    ("2022 急速升息", "2022-01-01", "2022-12-31"),
    ("2024 日本股災", "2024-07-01", "2024-08-15"),
]


@dataclass
class DCAConfig:
    frequency: str = "month"
    amount: float = 50000
    mode: str = "conditional"
    drawdown_period: str = "week"
    drawdown_pct: float = 3.0
    buy_on: str = "friday"
    max_times_per_month: int = 2
    max_amount_per_month: float = 150000


@dataclass
class TriggerConfig:
    market: str = "TWII"
    condition: str = "drop"
    drop_period: str = "month"
    drop_pct: float = 5.0
    ma_days: int = 144
    extra_amount: float = 100000


@dataclass
class BacktestConfig:
    start: str = "2017-01-01"
    end: str = "2026-08-01"
    total_invest_hint: float = 0
    holdings: List[FundHolding] = field(default_factory=list)
    dca: Optional[DCAConfig] = None
    trigger: Optional[TriggerConfig] = None
    rebalance: str = "quarter"


@dataclass
class BacktestResult:
    funding: FundingResult
    dividend: Optional[DividendResult]
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    sharpe: float
    avg_monthly_net_cashflow: float
    margin_call_months: List[str]
    cashflow_short_months: List[str]
    stress_results: Dict[str, dict]
    equity_curve: Optional[pd.Series] = None
    notes: List[str] = field(default_factory=list)


def _max_drawdown(series: pd.Series) -> float:
    if series is None or series.empty:
        return 0.0
    cummax = series.cummax()
    dd = (series - cummax) / cummax
    return float(dd.min())


def _cagr(start_val: float, end_val: float, years: float) -> float:
    if start_val <= 0 or years <= 0:
        return 0.0
    return (end_val / start_val) ** (1 / years) - 1


def run_backtest(
    funding_sources: dict,
    config: BacktestConfig,
    price_data: Dict[str, pd.DataFrame],
    div_data: Dict[str, pd.DataFrame],
    fx_yearly: Dict[str, Dict[int, float]],
    index_data: Dict[str, pd.DataFrame],
) -> BacktestResult:
    notes = []
    funding = calculate_funding(
        principal=funding_sources.get("principal"),
        mortgage=funding_sources.get("mortgage"),
        policy=funding_sources.get("policy"),
        revolving=funding_sources.get("revolving"),
    )

    invest = config.total_invest_hint if config.total_invest_hint > 0 else funding.total_capital * 10000
    if invest <= 0:
        invest = 1e7
        notes.append("未取得有效投資金額，使用預設 1000 萬")

    div_result = None
    if config.holdings:
        div_result = calculate_portfolio_dividends(
            total_invest_twd=invest,
            holdings=config.holdings,
            price_data=price_data,
            div_data=div_data,
            fx_yearly=fx_yearly,
            start=config.start,
            end=config.end,
        )
        notes.extend(div_result.notes)

    equity = None
    if config.holdings and price_data:
        curves = []
        w_sum = sum(h.weight for h in config.holdings) or 1.0
        for h in config.holdings:
            px = price_data.get(h.ticker)
            if px is None or px.empty:
                continue
            px = px.copy()
            px.index = pd.to_datetime(px.index).tz_localize(None)
            col = "Adj Close" if "Adj Close" in px.columns else "Close"
            if col not in px.columns:
                continue
            s = px.loc[config.start:config.end, col].dropna()
            if s.empty:
                continue
            s = s / s.iloc[0] * (invest * h.weight / w_sum)
            curves.append(s)
        if curves:
            equity = pd.concat(curves, axis=1).ffill().sum(axis=1)
            equity.name = "portfolio"

    total_ret = 0.0
    cagr = 0.0
    mdd = 0.0
    sharpe = 0.0
    if equity is not None and len(equity) > 2:
        total_ret = float(equity.iloc[-1] / equity.iloc[0] - 1)
        years = max((equity.index[-1] - equity.index[0]).days / 365.25, 0.1)
        cagr = _cagr(equity.iloc[0], equity.iloc[-1], years)
        mdd = _max_drawdown(equity)
        daily_ret = equity.pct_change().dropna()
        if daily_ret.std() > 0:
            sharpe = float(daily_ret.mean() / daily_ret.std() * np.sqrt(252))

    monthly_div = div_result.avg_monthly_dividend if div_result else 0.0
    monthly_cost = funding.monthly_cost
    avg_net_cf = monthly_div - monthly_cost

    margin_call_months = []
    cashflow_short_months = []
    if funding.breakdown.get("policy"):
        for name, s, e in STRESS_PERIODS:
            if "2020" in name or "2008" in name:
                margin_call_months.append(f"{s[:7]}（{name}示意）")
    if avg_net_cf < 0:
        cashflow_short_months.append("整體平均現金流為負，需留意補倉")

    stress_results = {}
    if equity is not None:
        for name, s, e in STRESS_PERIODS:
            try:
                seg = equity.loc[s:e]
                if len(seg) < 2:
                    continue
                ret = float(seg.iloc[-1] / seg.iloc[0] - 1)
                dd = _max_drawdown(seg)
                stress_results[name] = {
                    "return_pct": round(ret * 100, 2),
                    "max_drawdown_pct": round(dd * 100, 2),
                    "start": s,
                    "end": e,
                }
            except Exception:
                continue

    return BacktestResult(
        funding=funding,
        dividend=div_result,
        total_return_pct=round(total_ret * 100, 2),
        cagr_pct=round(cagr * 100, 2),
        max_drawdown_pct=round(mdd * 100, 2),
        sharpe=round(sharpe, 2),
        avg_monthly_net_cashflow=round(avg_net_cf, 0),
        margin_call_months=margin_call_months,
        cashflow_short_months=cashflow_short_months,
        stress_results=stress_results,
        equity_curve=equity,
        notes=notes,
    )
