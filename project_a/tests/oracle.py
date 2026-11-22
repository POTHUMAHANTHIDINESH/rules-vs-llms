"""Independent oracle used ONLY to generate/verify expected values.

Deliberately different formulation from engines a and c:
  * slab tax = sum of (rate change at breakpoint) x (income above breakpoint)   [difference form]
  * surcharge marginal relief = min over all lower thresholds                    [min form]
  * exact Fractions, rounded only where the rules say so (half-up).
It is still written by the same author as the engines, so it is NOT a substitute for the official
calculator: 30 cases are exported for manual verification (see official_calculator_checks.csv).
"""
from fractions import Fraction as F
from math import floor

NEW_BP = {
    "2024-25": [(0, 0), (300000, 5), (700000, 10), (1000000, 15), (1200000, 20), (1500000, 30)],
    "2025-26": [(0, 0), (400000, 5), (800000, 10), (1200000, 15), (1600000, 20), (2000000, 25), (2400000, 30)],
}
NEW_REBATE = {"2024-25": (700000, 25000), "2025-26": (1200000, 60000)}
OLD_BP = {"general": [(0, 0), (250000, 5), (500000, 20), (1000000, 30)],
          "senior": [(0, 0), (300000, 5), (500000, 20), (1000000, 30)],
          "super": [(0, 0), (500000, 20), (1000000, 30)]}
SC_NEW = [(5000000, 10), (10000000, 15), (20000000, 25)]
SC_OLD = SC_NEW + [(50000000, 37)]


def hu(x) -> int:
    return int(floor(F(x) + F(1, 2)))


def tax_bp(bps, inc):
    t, prev = F(0), 0
    for bp, rate in bps:
        if inc > bp:
            t += F(rate - prev, 100) * (inc - bp)
        prev = rate
    return hu(t)


def oracle(d: dict, which: str) -> dict:
    fy, age = d["fy"], d["age"]
    gross = d["gross_salary"]
    hra = 0
    if which == "old" and d.get("hra_received", 0) > 0 and d.get("rent_paid", 0) > 0:
        b = d["basic_salary"]
        pct_city = F(1, 2) if d.get("metro") else F(2, 5)
        hra = max(0, min([d["hra_received"], d["rent_paid"] - floor(F(b, 10)), floor(b * pct_city)]))
    std = min(gross - hra, 50000 if which == "old" else 75000)
    ded = 0
    if which == "old":
        ded += min(d.get("sec_80c", 0), 150000) + min(d.get("sec_80ccd1b", 0), 50000)
        ded += min(d.get("sec_80d_self", 0), 50000 if age >= 60 else 25000)
        ded += min(d.get("sec_80d_parents", 0), 50000 if d.get("parents_senior") else 25000)
        ded += min(d.get("home_loan_interest", 0), 200000)
    ti = hu(F(max(0, gross - hra - std - ded), 10)) * 10
    if which == "old":
        bps = OLD_BP["super" if age >= 80 else "senior" if age >= 60 else "general"]
        lim, mx, sc_t = 500000, 12500, SC_OLD
    else:
        bps = NEW_BP[fy]
        lim, mx = NEW_REBATE[fy]
        sc_t = SC_NEW
    T = tax_bp(bps, ti)
    if ti <= lim:
        T = max(0, T - mx)
    elif which == "new":
        T = min(T, ti - lim)
    # surcharge (only incomes > 50L, where rebate is nil so plain slab tax applies)
    total = T
    cur = [(t, r) for t, r in sc_t if ti > t]
    if cur:
        rates = [0] + [r for _, r in sc_t]
        j_cur = len(cur)
        total = T + hu(F(T * rates[j_cur], 100))
        for j in range(1, j_cur + 1):
            thr = sc_t[j - 1][0]
            Tt = tax_bp(bps, thr)
            total = min(total, Tt + hu(F(Tt * rates[j - 1], 100)) + (ti - thr))
    total += hu(F(total * 4, 100))
    return {"taxable_income": ti, "tax_payable": hu(F(total, 10)) * 10}
