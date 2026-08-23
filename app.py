#!/usr/bin/env python3
"""
0本金回測系統 - Streamlit 手機友善 App
執行：streamlit run app.py --server.port 8501 --server.address 0.0.0.0
"""

from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Optional

import streamlit as st
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from engine import (
    PrincipalSource, MortgageSource, PolicyLoanSource, RevolvingRepledgeSource,
    FundHolding, BacktestConfig, DCAConfig, TriggerConfig,
    calculate_funding, run_backtest, export_excel,
    fetch_price_history, fetch_dividend_history, fetch_fx_yearly_avg, fetch_index,
)

st.set_page_config(page_title="0本金回測系統", page_icon="\U0001F4CA", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; max-width: 430px; }
    div[data-testid="stMetric"] { background: #f8fafc; padding: 10px; border-radius: 10px; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

if "page" not in st.session_state:
    st.session_state.page = "home"
if "funding_result" not in st.session_state:
    st.session_state.funding_result = None
if "backtest_result" not in st.session_state:
    st.session_state.backtest_result = None
if "holdings" not in st.session_state:
    st.session_state.holdings = [
        {"name": "\u5143\u5927\u9ad8\u80a1\u606f", "ticker": "0056.TW", "weight": 20, "currency": "TWD", "expense": 0.7},
        {"name": "SPY", "ticker": "SPY", "weight": 25, "currency": "USD", "expense": 0.09},
        {"name": "HYG", "ticker": "HYG", "weight": 25, "currency": "USD", "expense": 0.4},
        {"name": "LQD", "ticker": "LQD", "weight": 15, "currency": "USD", "expense": 0.14},
        {"name": "0050", "ticker": "0050.TW", "weight": 15, "currency": "TWD", "expense": 0.3},
    ]

def go(page: str):
    st.session_state.page = page
    st.rerun()

def nav():
    cols = st.columns(4)
    labels = [("\U0001F3E0", "home"), ("\U0001F4B0", "funding"), ("\U0001F4C8", "portfolio"), ("\U0001F4CB", "result")]
    for i, (icon, p) in enumerate(labels):
        with cols[i]:
            if st.button(icon, key=f"nav_{p}", use_container_width=True):
                go(p)

def page_home():
    st.title("\U0001F4CA 0\u672c\u91d1\u56de\u6e2c\u7cfb\u7d71")
    st.caption("\u672c\u91d1\uff0f\u623f\u8cb8\uff0f\u4fdd\u55ae\u8cea\u62bc \u00d7 \u914d\u606f\u7d44\u5408\u56de\u6e2c")
    st.markdown("---")
    st.markdown("**\u4f7f\u7528\u6d41\u7a0b**\n1. \u8cc7\u91d1\u4f86\u6e90\n2. \u6295\u8cc7\u7d44\u5408\n3. \u57f7\u884c\u56de\u6e2c\n4. \u4e0b\u8f09 Excel")
    if st.button("\u958b\u59cb\u8a2d\u5b9a\u8cc7\u91d1\u4f86\u6e90", type="primary"):
        go("funding")

def page_funding():
    st.subheader("\u8cc7\u91d1\u4f86\u6e90\u8a2d\u5b9a")
    use_principal = st.checkbox("\u81ea\u6709\u672c\u91d1", value=True)
    p_amt = st.number_input("\u672c\u91d1\uff08\u842c\u5143\uff09", value=300.0, step=10.0) if use_principal else 0.0

    use_mort = st.checkbox("\u4e00\u822c\u623f\u8cb8\uff0f\u4fe1\u8cb8", value=True)
    if use_mort:
        c1, c2 = st.columns(2)
        m_amt = c1.number_input("\u8cb8\u6b3e\u91d1\u984d\uff08\u842c\uff09", value=500.0, step=10.0)
        m_rate = c2.number_input("\u5e74\u5229\u7387 %", value=1.85, step=0.05)
        c3, c4 = st.columns(2)
        m_months = c3.number_input("\u671f\u6578\uff08\u6708\uff09", value=84, step=12)
        m_grace = c4.number_input("\u5bec\u9650\u671f\uff08\u6708\uff09", value=0, step=1)
    else:
        m_amt = m_rate = m_months = m_grace = 0

    use_pol = st.checkbox("\u4fdd\u55ae\u8cea\u62bc", value=True)
    if use_pol:
        pol_val = st.number_input("\u4fdd\u50f9\u91d1\uff08\u842c\uff09", value=200.0, step=10.0)
        c1, c2 = st.columns(2)
        pol_ratio = c1.number_input("\u53ef\u8cb8\u6210\u6578 %", value=60.0, step=5.0) / 100
        pol_rate = c2.number_input("\u8cea\u501f\u5e74\u5229\u7387 %", value=3.80, step=0.1)
    else:
        pol_val = pol_ratio = pol_rate = 0

    use_rev = st.checkbox("\u5faa\u74b0\u578b\u623f\u8cb8\u2192\u518d\u8cea\u62bc", value=True)
    if use_rev:
        rev_draw = st.number_input("\u5be6\u969b\u52d5\u7528\uff08\u842c\uff09", value=200.0, step=10.0)
        c1, c2 = st.columns(2)
        rev_rate = c1.number_input("\u5faa\u74b0\u5229\u7387 %", value=2.60, step=0.1)
        rev_ratio = c2.number_input("\u518d\u8cea\u62bc\u6210\u6578 %", value=60.0, step=5.0) / 100
        rev_pol_rate = st.number_input("\u518d\u8cea\u62bc\u5229\u7387 %", value=3.80, step=0.1)
    else:
        rev_draw = rev_rate = rev_ratio = rev_pol_rate = 0

    if st.button("\u8a08\u7b97\u8cc7\u91d1", type="primary"):
        sources = {}
        if use_principal and p_amt > 0:
            sources["principal"] = PrincipalSource(amount=p_amt)
        if use_mort and m_amt > 0:
            sources["mortgage"] = MortgageSource(amount=m_amt, annual_rate=m_rate, months=int(m_months), grace_months=int(m_grace))
        if use_pol and pol_val > 0:
            sources["policy"] = PolicyLoanSource(policy_value=pol_val, loan_ratio=pol_ratio, annual_rate=pol_rate)
        if use_rev and rev_draw > 0:
            sources["revolving"] = RevolvingRepledgeSource(draw_amount=rev_draw, revolving_rate=rev_rate, repledge_ratio=rev_ratio, policy_rate=rev_pol_rate)
        res = calculate_funding(
            principal=sources.get("principal"),
            mortgage=sources.get("mortgage"),
            policy=sources.get("policy"),
            revolving=sources.get("revolving"),
        )
        st.session_state.funding_result = res
        st.session_state.funding_sources = sources

    if st.session_state.funding_result:
        r = st.session_state.funding_result
        st.success("\u8a08\u7b97\u5b8c\u6210")
        c1, c2 = st.columns(2)
        c1.metric("\u7e3d\u53ef\u7528\u8cc7\u91d1\uff08\u842c\uff09", f"{r.total_capital:,.1f}")
        c2.metric("\u52a0\u6b0a\u8cc7\u91d1\u6210\u672c", f"{r.weighted_cost_pct:.2f}%")
        c3, c4 = st.columns(2)
        c3.metric("\u6bcf\u6708\u6210\u672c", f"{r.monthly_cost:,.0f}")
        c4.metric("\u6bcf\u5e74\u6210\u672c", f"{r.yearly_cost:,.0f}")

    if st.button("\u4e0b\u4e00\u6b65\uff1a\u6295\u8cc7\u7d44\u5408"):
        go("portfolio")

def page_portfolio():
    st.subheader("\u6295\u8cc7\u7d44\u5408")
    holdings = st.session_state.holdings
    new_holdings = []
    total_w = 0.0
    for i, h in enumerate(holdings):
        with st.expander(f"{h['name']} ({h['ticker']}) \u2014 {h['weight']}%", expanded=(i==0)):
            name = st.text_input("\u540d\u7a31", h["name"], key=f"n_{i}")
            ticker = st.text_input("\u4ee3\u78bc", h["ticker"], key=f"t_{i}")
            c1, c2, c3 = st.columns(3)
            w = c1.number_input("\u6b0a\u91cd %", value=float(h["weight"]), key=f"w_{i}", step=1.0)
            cur = c2.selectbox("\u5e63\u5225", ["TWD", "USD", "ZAR", "AUD"],
                               index=["TWD", "USD", "ZAR", "AUD"].index(h.get("currency", "TWD")), key=f"c_{i}")
            exp = c3.number_input("\u7ba1\u7406\u8cbb %", value=float(h.get("expense", 0.5)), key=f"e_{i}", step=0.1)
            new_holdings.append({"name": name, "ticker": ticker, "weight": w, "currency": cur, "expense": exp})
            total_w += w
    st.session_state.holdings = new_holdings
    st.info(f"\u6b0a\u91cd\u5408\u8a08\uff1a{total_w:.1f}%")

    c1, c2 = st.columns(2)
    start = c1.date_input("\u8d77\u59cb", value=date(2018, 1, 1))
    end = c2.date_input("\u7d50\u675f", value=date(2025, 12, 31))
    st.session_state.bt_start = str(start)
    st.session_state.bt_end = str(end)

    if st.button("\U0001F680 \u958b\u59cb\u56de\u6e2c", type="primary"):
        with st.spinner("\u8a08\u7b97\u4e2d..."):
            run_full_backtest()
        go("result")

def run_full_backtest():
    holdings_raw = st.session_state.holdings
    w_sum = sum(h["weight"] for h in holdings_raw) or 100
    holdings = [
        FundHolding(name=h["name"], ticker=h["ticker"], weight=h["weight"]/w_sum,
                    currency=h["currency"], expense_ratio=h["expense"]/100)
        for h in holdings_raw if h["weight"] > 0
    ]
    sources = st.session_state.get("funding_sources") or {
        "principal": PrincipalSource(amount=300),
        "mortgage": MortgageSource(amount=500, annual_rate=1.85, months=84),
        "policy": PolicyLoanSource(policy_value=200, loan_ratio=0.6, annual_rate=3.8),
        "revolving": RevolvingRepledgeSource(draw_amount=200, revolving_rate=2.6, repledge_ratio=0.6, policy_rate=3.8),
    }
    start = st.session_state.get("bt_start", "2018-01-01")
    end = st.session_state.get("bt_end", "2025-12-31")

    price_data, div_data = {}, {}
    for h in holdings:
        try:
            price_data[h.ticker] = fetch_price_history(h.ticker, start=start, end=end)
            div_data[h.ticker] = fetch_dividend_history(h.ticker, start=start, end=end)
        except Exception:
            pass

    fx_yearly = {
        "USD": fetch_fx_yearly_avg("USDTWD=X", start_year=2017),
        "TWD": {y: 1.0 for y in range(2015, 2027)},
        "ZAR": {y: 1.7 for y in range(2015, 2027)},
        "AUD": {y: 20.5 for y in range(2015, 2027)},
    }
    index_data = {"TWII": fetch_index("^TWII", start=start), "GSPC": fetch_index("^GSPC", start=start)}

    config = BacktestConfig(start=start, end=end, holdings=holdings,
                            trigger=TriggerConfig(market="BOTH", condition="drop", drop_pct=5.0),
                            rebalance="quarter")
    result = run_backtest(funding_sources=sources, config=config, price_data=price_data,
                          div_data=div_data, fx_yearly=fx_yearly, index_data=index_data)
    st.session_state.backtest_result = result

    out = ROOT / "output"
    out.mkdir(exist_ok=True)
    path = out / f"backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    try:
        export_excel(result, path)
        st.session_state.excel_path = str(path)
    except Exception:
        st.session_state.excel_path = None

def page_result():
    st.subheader("\u56de\u6e2c\u7d50\u679c")
    r = st.session_state.backtest_result
    if r is None:
        st.warning("\u5c1a\u672a\u57f7\u884c\u56de\u6e2c")
        if st.button("\u524d\u5f80\u7d44\u5408"):
            go("portfolio")
        return

    c1, c2 = st.columns(2)
    c1.metric("\u542b\u606f\u7e3d\u5831\u916c", f"{r.total_return_pct:.1f}%")
    c2.metric("CAGR", f"{r.cagr_pct:.1f}%")
    c3, c4 = st.columns(2)
    c3.metric("\u6700\u5927\u56de\u64a4", f"{r.max_drawdown_pct:.1f}%")
    c4.metric("\u590f\u666e", f"{r.sharpe:.2f}")

    c1, c2 = st.columns(2)
    c1.metric("\u7e3d\u8cc7\u91d1\uff08\u842c\uff09", f"{r.funding.total_capital:,.1f}")
    c2.metric("\u52a0\u6b0a\u6210\u672c", f"{r.funding.weighted_cost_pct:.2f}%")

    if r.dividend:
        c1, c2, c3 = st.columns(3)
        c1.metric("\u5e74\u5316\u914d\u606f", f"{r.dividend.annualized_yield*100:.2f}%")
        c2.metric("\u6708\u914d\u606f", f"{r.dividend.avg_monthly_dividend:,.0f}")
        c3.metric("\u5e74\u914d\u606f", f"{r.dividend.avg_yearly_dividend:,.0f}")

    if r.equity_curve is not None and len(r.equity_curve) > 5:
        st.line_chart(r.equity_curve)

    if r.stress_results:
        for name, d in r.stress_results.items():
            st.write(f"**{name}** \u5831\u916c {d['return_pct']}% / DD {d['max_drawdown_pct']}%")

    if st.session_state.get("excel_path"):
        path = Path(st.session_state.excel_path)
        if path.exists():
            with open(path, "rb") as f:
                st.download_button("\U0001F4E5 \u4e0b\u8f09 Excel", f, file_name=path.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

nav()
st.markdown("---")
page = st.session_state.page
if page == "home":
    page_home()
elif page == "funding":
    page_funding()
elif page == "portfolio":
    page_portfolio()
elif page == "result":
    page_result()
else:
    page_home()
