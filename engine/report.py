"""
Excel 報表輸出
"""

from __future__ import annotations
from pathlib import Path
from datetime import datetime
from typing import Optional
import pandas as pd

from .backtest import BacktestResult


def export_excel(result: BacktestResult, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary = {
            "項目": [
                "總可用資金（萬）",
                "每月資金成本（元）",
                "每年資金成本（元）",
                "加權資金成本 %",
                "含息總報酬 %",
                "年化報酬 CAGR %",
                "最大回撤 %",
                "夏普值",
                "平均每月淨現金流（元）",
                "平均每月領息（元）",
                "平均每年領息（元）",
                "年化配息率 %",
            ],
            "數值": [
                result.funding.total_capital,
                result.funding.monthly_cost,
                result.funding.yearly_cost,
                result.funding.weighted_cost_pct,
                result.total_return_pct,
                result.cagr_pct,
                result.max_drawdown_pct,
                result.sharpe,
                result.avg_monthly_net_cashflow,
                result.dividend.avg_monthly_dividend if result.dividend else None,
                result.dividend.avg_yearly_dividend if result.dividend else None,
                (result.dividend.annualized_yield * 100) if result.dividend else None,
            ]
        }
        pd.DataFrame(summary).to_excel(writer, sheet_name="總覽", index=False)

        rows = []
        for k, v in result.funding.breakdown.items():
            row = {"來源": k}
            row.update(v)
            rows.append(row)
        if rows:
            pd.DataFrame(rows).to_excel(writer, sheet_name="資金明細", index=False)

        if result.dividend and result.dividend.by_fund:
            fund_rows = []
            for name, d in result.dividend.by_fund.items():
                fund_rows.append({"基金": name, **d})
            pd.DataFrame(fund_rows).to_excel(writer, sheet_name="各基金配息", index=False)

        if result.stress_results:
            stress_rows = []
            for name, d in result.stress_results.items():
                stress_rows.append({"情境": name, **d})
            pd.DataFrame(stress_rows).to_excel(writer, sheet_name="壓力情境", index=False)

        warn = []
        for m in result.margin_call_months:
            warn.append({"類型": "斷頭／補倉風險", "說明": m})
        for m in result.cashflow_short_months:
            warn.append({"類型": "現金流不足", "說明": m})
        if result.notes:
            for n in result.notes:
                warn.append({"類型": "備註", "說明": n})
        if warn:
            pd.DataFrame(warn).to_excel(writer, sheet_name="警示與備註", index=False)

        if result.equity_curve is not None and not result.equity_curve.empty:
            eq = result.equity_curve.reset_index()
            eq.columns = ["日期", "組合市值"]
            eq.to_excel(writer, sheet_name="權益曲線", index=False)

    return path
