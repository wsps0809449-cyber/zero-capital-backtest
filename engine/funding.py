"""
資金來源計算引擎
支援：本金、一般房貸（本利攤還＋寬限期）、保單質押、循環型房貸→再質押（利息疊加）
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import math


@dataclass
class PrincipalSource:
    amount: float          # 萬元
    start_date: str = ""   # YYYY-MM-DD


@dataclass
class MortgageSource:
    amount: float          # 萬元
    annual_rate: float     # 例如 1.85 表示 1.85%
    months: int
    grace_months: int = 0  # 寬限期（月），期間只繳利息


@dataclass
class PolicyLoanSource:
    policy_value: float    # 保價金 / 帳戶價值（萬元）
    loan_ratio: float      # 可貸成數，例如 0.60
    annual_rate: float     # 質借年利率 %


@dataclass
class RevolvingRepledgeSource:
    """循環型房貸 → 再質押（雙重樂桿，利息疊加）"""
    draw_amount: float         # 實際動用金額 A（萬元）
    revolving_rate: float      # 循環利率 %
    repledge_ratio: float      # 再質押成數，例如 0.60
    policy_rate: float         # 再質押（保單）利率 %
    limit: float = 0.0         # 循環額度（僅供參考）


@dataclass
class FundingResult:
    total_capital: float           # 總可用資金（萬元）
    monthly_cost: float            # 每月總成本（元）
    yearly_cost: float             # 每年總成本（元）
    weighted_cost_pct: float       # 加權資金成本 %
    breakdown: dict = field(default_factory=dict)
    formulas: dict = field(default_factory=dict)


def mortgage_payment(principal: float, annual_rate_pct: float, months: int, grace_months: int = 0) -> dict:
    """
    本利攤還計算（支援寬限期）
    principal: 元
    回傳 monthly_payment（寬限期後）、grace_interest（寬限期月利息）
    """
    if months <= 0:
        raise ValueError("期數必須 > 0")
    r = (annual_rate_pct / 100) / 12
    grace_interest = principal * r if grace_months > 0 else 0.0

    remaining_months = months - grace_months
    if remaining_months <= 0:
        return {
            "monthly_during_grace": grace_interest,
            "monthly_after_grace": grace_interest,
            "total_interest_estimate": grace_interest * months
        }

    if r == 0:
        monthly = principal / remaining_months
    else:
        monthly = principal * r * (1 + r) ** remaining_months / ((1 + r) ** remaining_months - 1)

    return {
        "monthly_during_grace": round(grace_interest, 2),
        "monthly_after_grace": round(monthly, 2),
        "grace_months": grace_months,
        "formula": f"月付金 = P × r(1+r)^n / [(1+r)^n − 1]，r={r:.6f}, n={remaining_months}"
    }


def calculate_funding(
    principal: Optional[PrincipalSource] = None,
    mortgage: Optional[MortgageSource] = None,
    policy: Optional[PolicyLoanSource] = None,
    revolving: Optional[RevolvingRepledgeSource] = None,
) -> FundingResult:
    """
    匯總所有資金來源，計算總可用資金、每月/每年成本、加權資金成本
    """
    total_capital = 0.0
    monthly_cost = 0.0
    weighted_num = 0.0
    breakdown = {}
    formulas = {}

    if principal and principal.amount > 0:
        total_capital += principal.amount
        breakdown["principal"] = {
            "amount_wan": principal.amount,
            "monthly_cost": 0.0,
            "yearly_cost": 0.0,
            "rate_pct": 0.0
        }
        formulas["principal"] = "本金無利息成本"

    if mortgage and mortgage.amount > 0:
        P = mortgage.amount * 10000
        pay = mortgage_payment(P, mortgage.annual_rate, mortgage.months, mortgage.grace_months)
        m_cost = pay["monthly_after_grace"]
        total_capital += mortgage.amount
        monthly_cost += m_cost
        weighted_num += mortgage.amount * mortgage.annual_rate
        breakdown["mortgage"] = {
            "amount_wan": mortgage.amount,
            "monthly_cost": m_cost,
            "yearly_cost": round(m_cost * 12, 2),
            "rate_pct": mortgage.annual_rate,
            "grace_months": mortgage.grace_months,
            "monthly_during_grace": pay["monthly_during_grace"]
        }
        formulas["mortgage"] = pay["formula"]

    if policy and policy.policy_value > 0:
        loanable = policy.policy_value * policy.loan_ratio
        m_int = loanable * 10000 * (policy.annual_rate / 100) / 12
        y_int = loanable * 10000 * (policy.annual_rate / 100)
        total_capital += loanable
        monthly_cost += m_int
        weighted_num += loanable * policy.annual_rate
        breakdown["policy"] = {
            "policy_value_wan": policy.policy_value,
            "loanable_wan": round(loanable, 4),
            "monthly_cost": round(m_int, 2),
            "yearly_cost": round(y_int, 2),
            "rate_pct": policy.annual_rate,
            "loan_ratio": policy.loan_ratio
        }
        formulas["policy"] = (
            f"可質借 = {policy.policy_value} × {policy.loan_ratio} = {loanable:.2f} 萬\n"
            f"月利息 = 可質借 × {policy.annual_rate}% / 12"
        )

    if revolving and revolving.draw_amount > 0:
        A = revolving.draw_amount
        int1 = A * 10000 * (revolving.revolving_rate / 100) / 12
        B = A * revolving.repledge_ratio
        int2 = B * 10000 * (revolving.policy_rate / 100) / 12
        total_int = int1 + int2
        total_cap = A + B
        total_capital += total_cap
        monthly_cost += total_int
        combined_rate = (total_int * 12 / (total_cap * 10000) * 100) if total_cap > 0 else 0
        weighted_num += total_cap * combined_rate
        breakdown["revolving_repledge"] = {
            "draw_A_wan": A,
            "repledge_B_wan": round(B, 4),
            "total_available_wan": round(total_cap, 4),
            "revolving_monthly_int": round(int1, 2),
            "repledge_monthly_int": round(int2, 2),
            "total_monthly_int": round(total_int, 2),
            "total_yearly_int": round(total_int * 12, 2),
            "combined_rate_pct": round(combined_rate, 4)
        }
        formulas["revolving_repledge"] = (
            f"A = {A} 萬\n"
            f"循環月息 = A × {revolving.revolving_rate}% / 12 = {int1:.0f} 元\n"
            f"B = A × {revolving.repledge_ratio} = {B:.2f} 萬\n"
            f"再質押月息 = B × {revolving.policy_rate}% / 12 = {int2:.0f} 元\n"
            f"總月息 = {total_int:.0f} 元（利息疊加）\n"
            f"最終可用 = A + B = {total_cap:.2f} 萬"
        )

    weighted_pct = (weighted_num / total_capital) if total_capital > 0 else 0.0

    return FundingResult(
        total_capital=round(total_capital, 4),
        monthly_cost=round(monthly_cost, 2),
        yearly_cost=round(monthly_cost * 12, 2),
        weighted_cost_pct=round(weighted_pct, 4),
        breakdown=breakdown,
        formulas=formulas
    )


if __name__ == "__main__":
    res = calculate_funding(
        principal=PrincipalSource(amount=300),
        mortgage=MortgageSource(amount=500, annual_rate=1.85, months=84, grace_months=0),
        policy=PolicyLoanSource(policy_value=200, loan_ratio=0.60, annual_rate=3.80),
        revolving=RevolvingRepledgeSource(
            draw_amount=200, revolving_rate=2.60, repledge_ratio=0.60, policy_rate=3.80
        )
    )
    print("=== 資金匯總 ===")
    print(f"總可用資金: {res.total_capital} 萬")
    print(f"每月成本: {res.monthly_cost:,.0f} 元")
    print(f"每年成本: {res.yearly_cost:,.0f} 元")
    print(f"加權資金成本: {res.weighted_cost_pct:.2f}%")
    print("\n明細:")
    for k, v in res.breakdown.items():
        print(f"  {k}: {v}")
