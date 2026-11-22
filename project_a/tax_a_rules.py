"""Implementation (a): hand-coded rules (plain Python constants + logic).

Every rupee in the output is a line item carrying a clause id from rule_text/*.md.
"""
from .tax_common import TaxInput, pct, round10, line, compare

# ---- parameters per financial year -------------------------------------------------
NEW = {
    "2024-25": dict(std=75_000, rebate_limit=700_000, rebate_max=25_000, act="FA2024",
                    slabs=[(300_000, 0), (700_000, 5), (1_000_000, 10), (1_200_000, 15),
                           (1_500_000, 20), (None, 30)]),
    "2025-26": dict(std=75_000, rebate_limit=1_200_000, rebate_max=60_000, act="FA2025",
                    slabs=[(400_000, 0), (800_000, 5), (1_200_000, 10), (1_600_000, 15),
                           (2_000_000, 20), (2_400_000, 25), (None, 30)]),
}
_OLD = dict(std=50_000, rebate_limit=500_000, rebate_max=12_500,
            slabs={"general": [(250_000, 0), (500_000, 5), (1_000_000, 20), (None, 30)],
                   "senior": [(300_000, 0), (500_000, 5), (1_000_000, 20), (None, 30)],
                   "super_senior": [(500_000, 0), (1_000_000, 20), (None, 30)]})
OLD = {"2024-25": _OLD, "2025-26": _OLD}
SURCHARGE_NEW = [(5_000_000, 10), (10_000_000, 15), (20_000_000, 25)]
SURCHARGE_OLD = [(5_000_000, 10), (10_000_000, 15), (20_000_000, 25), (50_000_000, 37)]


def slab_tax(slabs, income: int) -> int:
    total, lo = 0, 0
    for hi, rate in slabs:
        top = income if hi is None else min(income, hi)
        if top > lo:
            total += (top - lo) * rate
        if hi is None or income <= hi:
            break
        lo = hi
    return (total + 50) // 100


def _surcharge(slabs, tiers, income: int):
    tax = slab_tax(slabs, income)
    rate = prev = 0
    thr = None
    for t, r in tiers:
        if income > t:
            prev, rate, thr = rate, r, t
    sc = pct(tax, rate)
    if thr is not None:                       # marginal relief
        t_thr = slab_tax(slabs, thr)
        cap = t_thr + pct(t_thr, prev) + (income - thr)
        if tax + sc > cap:
            sc = max(0, cap - tax)
    return sc, rate


def regime(inp: TaxInput, which: str) -> dict:
    if inp.fy not in NEW:
        raise KeyError(f"No rules for FY {inp.fy}")          # loud failure, not silent
    lines = []
    gross = inp.gross_salary
    lines.append(line("Gross salary", gross, "SALARY"))
    hra_ex = std = 0
    ded = {}
    if which == "old":
        p = OLD[inp.fy]
        if inp.hra_received > 0 and inp.rent_paid > 0:
            basic = inp.basic_salary
            hra_ex = max(0, min(inp.hra_received, inp.rent_paid - basic * 10 // 100,
                                basic * (50 if inp.metro else 40) // 100))
        std = min(p["std"], gross - hra_ex)
        ded["S80C"] = min(inp.sec_80c, 150_000)
        ded["S80CCD1B"] = min(inp.sec_80ccd1b, 50_000)
        ded["S80D"] = (min(inp.sec_80d_self, 50_000 if inp.age >= 60 else 25_000)
                       + min(inp.sec_80d_parents, 50_000 if inp.parents_senior else 25_000))
        ded["S24b"] = min(inp.home_loan_interest, 200_000)
        if inp.age >= 80:
            slabs = p["slabs"]["super_senior"]
        elif inp.age >= 60:
            slabs = p["slabs"]["senior"]
        else:
            slabs = p["slabs"]["general"]
        tiers, slab_clause = SURCHARGE_OLD, "SLAB_OLD"
        rebate_limit, rebate_max, marginal = p["rebate_limit"], p["rebate_max"], False
    else:
        p = NEW[inp.fy]
        std = min(p["std"], gross)
        slabs, tiers, slab_clause = p["slabs"], SURCHARGE_NEW, "SLAB_NEW"
        rebate_limit, rebate_max, marginal = p["rebate_limit"], p["rebate_max"], True
    if hra_ex:
        lines.append(line("HRA exemption", -hra_ex, "S10_13A"))
    if std:
        lines.append(line("Standard deduction", -std, "S16ia"))
    for k, v in ded.items():
        if v:
            lines.append(line(f"Deduction {k}", -v, k))
    raw = max(0, gross - hra_ex - std - sum(ded.values()))
    taxable = round10(raw)
    unclamped = gross - hra_ex - std - sum(ded.values())
    lines.append(line("Rounding of taxable income (incl. floor at zero)", taxable - unclamped, "R288A"))
    # ---- tax phase (separate line group; sums to tax_payable)
    tax_lines = []
    tax = slab_tax(slabs, taxable)
    tax_lines.append(line("Tax on slabs", tax, slab_clause))
    rebate = 0
    if taxable <= rebate_limit:
        rebate = min(tax, rebate_max)
        if rebate:
            tax_lines.append(line("Rebate u/s 87A", -rebate, "S87A"))
    elif marginal and tax > taxable - rebate_limit:
        rebate = tax - (taxable - rebate_limit)
        tax_lines.append(line("Marginal relief on rebate", -rebate, "S87A_MR"))
    net = tax - rebate
    sc, _ = _surcharge(slabs, tiers, taxable) if taxable > tiers[0][0] else (0, 0)
    if sc:
        tax_lines.append(line("Surcharge (after marginal relief)", sc, "SURCH"))
    cess = pct(net + sc, 4)
    if cess:
        tax_lines.append(line("Health & education cess 4%", cess, "CESS"))
    pre = net + sc + cess
    payable = round10(pre)
    if payable != pre:
        tax_lines.append(line("Rounding of tax payable", payable - pre, "R288B"))
    return {"regime": which, "fy": inp.fy, "taxable_income": taxable, "tax_payable": payable,
            "total_exemptions_and_deductions": hra_ex + std + sum(ded.values()),
            "income_lines": lines, "tax_lines": tax_lines}


class HandCodedEngine:
    name = "a_hand_coded"

    def compute(self, inp: TaxInput) -> dict:
        return compare(regime, inp)
