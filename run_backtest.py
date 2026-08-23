#!/usr/bin/env python3
"""
0本金回測系統 - 一鍵執行範例
使用方式：
  cd zero-capital-backtest
  python3 run_backtest.py
"""

from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import (
    PrincipalSource, MortgageSource, PolicyLoanSource, RevolvingRepledgeSource,
    FundHolding, BacktestConfig, DCAConfig, TriggerConfig,
    run_backtest, export_excel,
    fetch_price_history, fetch_dividend_history, fetch_fx_yearly_avg, fetch_index,
)


def main():
    print("=" * 60)
    print("0本金回測系統 - 完整流程範示")
    print("=" * 60)

    funding_sources = {
        "principal": PrincipalSource(amount=300, start_date="2017-01-01"),
        "mortgage": MortgageSource(amount=500, annual_rate=1.85, months=84, grace_months=0),
        "policy": PolicyLoanSource(policy_value=200, loan_ratio=0.60, annual_rate=3.80),
        "revolving": RevolvingRepledgeSource(
            draw_amount=200, revolving_rate=2.60, repledge_ratio=0.60, policy_rate=3.80
        ),
    }

    holdings = [
        FundHolding(name="群益台灣精選高息", ticker="00919.TW", weight=0.20, currency="TWD", expense_ratio=0.008),
        FundHolding(name="元大高股息", ticker="0056.TW", weight=0.15, currency="TWD", expense_ratio=0.007),
        FundHolding(name="S&P500 ETF", ticker="SPY", weight=0.25, currency="USD", expense_ratio=0.0009),
        FundHolding(name="全球高收益債代理", ticker="HYG", weight=0.25, currency="USD", expense_ratio=0.004),
        FundHolding(name="投資級債代理", ticker="LQD", weight=0.15, currency="USD", expense_ratio=0.0014),
    ]

    config = BacktestConfig(
        start="2018-01-01",
        end="2025-12-31",
        holdings=holdings,
        dca=DCAConfig(
            frequency="month",
            amount=50000,
            mode="conditional",
            drawdown_pct=3.0,
            max_times_per_month=2,
            max_amount_per_month=150000,
        ),
        trigger=TriggerConfig(
            market="BOTH",
            condition="drop",
            drop_period="month",
            drop_pct=5.0,
            ma_days=144,
            extra_amount=100000,
        ),
        rebalance="quarter",
    )

    print("\n[1/4] 抓取價格與配息資料...")
    price_data = {}
    div_data = {}
    for h in holdings:
        print(f"  - {h.name} ({h.ticker})")
        try:
            px = fetch_price_history(h.ticker, start=config.start, end=config.end)
            price_data[h.ticker] = px
            div = fetch_dividend_history(h.ticker, start=config.start, end=config.end)
            div_data[h.ticker] = div
            print(f"    價格列數: {len(px)}, 配息筆數: {len(div)}")
        except Exception as e:
            print(f"    失敗: {e}")

    print("\n[2/4] 抓取匯率與大盤...")
    fx_yearly = {
        "USD": fetch_fx_yearly_avg("USDTWD=X", start_year=2017),
        "TWD": {y: 1.0 for y in range(2017, 2027)},
    }
    index_data = {
        "TWII": fetch_index("^TWII", start=config.start),
        "GSPC": fetch_index("^GSPC", start=config.start),
    }
    print(f"  USD/TWD 年度匯率筆數: {len(fx_yearly.get('USD', {}))}")
    print(f"  台股資料列數: {len(index_data['TWII'])}")
    print(f"  美股資料列數: {len(index_data['GSPC'])}")

    print("\n[3/4] 執行回測引擎...")
    result = run_backtest(
        funding_sources=funding_sources,
        config=config,
        price_data=price_data,
        div_data=div_data,
        fx_yearly=fx_yearly,
        index_data=index_data,
    )

    print("\n" + "=" * 60)
    print("【資金匯總】")
    print(f"  總可用資金     : {result.funding.total_capital:,.1f} 萬")
    print(f"  每月成本       : {result.funding.monthly_cost:,.0f} 元")
    print(f"  每年成本       : {result.funding.yearly_cost:,.0f} 元")
    print(f"  加權資金成本   : {result.funding.weighted_cost_pct:.2f}%")

    print("\n【績效】")
    print(f"  含息總報酬     : {result.total_return_pct:.2f}%")
    print(f"  年化報酬 CAGR  : {result.cagr_pct:.2f}%")
    print(f"  最大回撤       : {result.max_drawdown_pct:.2f}%")
    print(f"  夏普值         : {result.sharpe:.2f}")
    print(f"  平均月淨現金流 : {result.avg_monthly_net_cashflow:,.0f} 元")

    if result.dividend:
        print("\n【配息實算】")
        print(f"  年化配息率     : {result.dividend.annualized_yield*100:.2f}%")
        print(f"  平均月配息     : {result.dividend.avg_monthly_dividend:,.0f} 元")
        print(f"  平均年配息     : {result.dividend.avg_yearly_dividend:,.0f} 元")
        print(f"  淨總配息       : {result.dividend.total_net_dividend_twd:,.0f} 元")

    if result.stress_results:
        print("\n【壓力情境】")
        for name, d in result.stress_results.items():
            print(f"  {name}: 報酬 {d['return_pct']}% / 最大回撤 {d['max_drawdown_pct']}%")

    out_dir = Path(__file__).resolve().parent / "output"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    xlsx_path = out_dir / f"backtest_result_{ts}.xlsx"
    print(f"\n[4/4] 匯出 Excel → {xlsx_path}")
    try:
        export_excel(result, xlsx_path)
        print("  完成")
    except Exception as e:
        print(f"  Excel 匯出失敗: {e}")

    print("\n" + "=" * 60)
    print("回測完成")
    return result


if __name__ == "__main__":
    main()
