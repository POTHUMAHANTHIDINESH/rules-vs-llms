"""Implementation (c): generic interpreter for LLM-compiled, human-reviewed rule files (JSON DSL).

No LLM runs here. Rules are data (rules/dsl_<fy>.json); this file is the fixed, reviewed interpreter.
validate_dsl() refuses malformed rule files so a bad compile fails loudly instead of silently.
"""
import json
import os
from .tax_common import TaxInput, pct, round10, line, compare

RULES_DIR = os.path.join(os.path.dirname(__file__), "rules")
REQUIRED_REGIME_KEYS = {"standard_deduction", "slab_tables", "slab_selection", "slab_clause",
                        "rebate", "surcharge", "deductions"}


def validate_dsl(d: dict) -> None:
    for k in ("fy", "cess_pct", "round_taxable_to", "round_tax_to", "regimes"):
        if k not in d:
            raise ValueError(f"DSL missing '{k}'")
    for r in ("old", "new"):
        reg = d["regimes"].get(r)
        if reg is None or not REQUIRED_REGIME_KEYS <= set(reg):
            raise ValueError(f"DSL regime '{r}' incomplete: need {sorted(REQUIRED_REGIME_KEYS)}")
        for name, tbl in reg["slab_tables"].items():
            if tbl[-1]["upto"] is not None:
                raise ValueError(f"{r}/{name}: last slab must be open-ended")
            ups = [s["upto"] for s in tbl[:-1]]
            if ups != sorted(ups):
                raise ValueError(f"{r}/{name}: slab limits not ascending")
        ab = [s["above"] for s in reg["surcharge"]]
        if ab != sorted(ab):
            raise ValueError(f"{r}: surcharge tiers not ascending")


def load_rules(fy: str, directory: str = None) -> dict:
    path = os.path.join(directory or RULES_DIR, f"dsl_fy{fy.replace('-', '_')}.json")
    if not os.path.exists(path):
        raise KeyError(f"No compiled rules for FY {fy}")
    d = json.load(open(path))
    validate_dsl(d)
    return d


def _slab_tax(table, income):
    total, lo = 0, 0
    for s in table:
        hi, rate = s["upto"], s["rate"]
        top = income if hi is None else min(income, hi)
        if top > lo:
            total += (top - lo) * rate
        if hi is None or income <= hi:
            break
        lo = hi
    return (total + 50) // 100


def _regime(inp: TaxInput, which: str, rules: dict) -> dict:
    R = rules["regimes"][which]
    gross = inp.gross_salary
    income_lines = [line("Gross salary", gross, "SALARY")]
    hra_ex = 0
    h = R.get("hra")
    if h and inp.hra_received > 0 and inp.rent_paid > 0:
        basic = inp.basic_salary
        hra_ex = max(0, min(inp.hra_received, inp.rent_paid - basic * h["rent_over_basic_pct"] // 100,
                            basic * (h["metro_pct"] if inp.metro else h["nonmetro_pct"]) // 100))
        if hra_ex:
            income_lines.append(line("HRA exemption", -hra_ex, h["clause"]))
    std = min(R["standard_deduction"], gross - hra_ex)
    if std:
        income_lines.append(line("Standard deduction", -std, "S16ia"))
    ded_total = 0
    for d in R["deductions"]:
        if d["type"] == "capped":
            v = min(getattr(inp, d["field"]), d["cap"])
        elif d["type"] == "health":
            sc = d["self_cap_senior"] if inp.age >= d["senior_age"] else d["self_cap"]
            pc = d["parents_cap_senior"] if inp.parents_senior else d["parents_cap"]
            v = min(getattr(inp, d["self_field"]), sc) + min(getattr(inp, d["parents_field"]), pc)
        else:
            raise ValueError(f"unknown deduction type {d['type']}")
        if v:
            income_lines.append(line(f"Deduction {d['id']}", -v, d["clause"]))
        ded_total += v
    unclamped = gross - hra_ex - std - ded_total
    rt = rules["round_taxable_to"]
    taxable = max(0, unclamped)
    taxable = ((taxable + rt // 2) // rt) * rt
    income_lines.append(line("Rounding of taxable income (incl. floor at zero)", taxable - unclamped, "R288A"))
    table = None
    for sel in R["slab_selection"]:
        if inp.age >= sel["min_age"]:
            table = R["slab_tables"][sel["table"]]
            break
    tax = _slab_tax(table, taxable)
    tl = [line("Tax on slabs", tax, R["slab_clause"])]
    rb = R["rebate"]
    rebate = 0
    if taxable <= rb["income_limit"]:
        rebate = min(tax, rb["max"])
        if rebate:
            tl.append(line("Rebate u/s 87A", -rebate, rb["clause"]))
    elif rb["marginal_relief"] and tax > taxable - rb["income_limit"]:
        rebate = tax - (taxable - rb["income_limit"])
        tl.append(line("Marginal relief on rebate", -rebate, "S87A_MR"))
    net = tax - rebate
    sc = 0
    rate = prev = 0
    thr = None
    for t in R["surcharge"]:
        if taxable > t["above"]:
            prev, rate, thr = rate, t["rate"], t["above"]
    if thr is not None:
        sc = pct(tax, rate)
        t_thr = _slab_tax(table, thr)
        cap = t_thr + pct(t_thr, prev) + (taxable - thr)
        if tax + sc > cap:
            sc = max(0, cap - tax)
        tl.append(line("Surcharge (after marginal relief)", sc, "SURCH"))
    cess = pct(net + sc, rules["cess_pct"])
    if cess:
        tl.append(line("Health & education cess 4%", cess, "CESS"))
    pre = net + sc + cess
    rr = rules["round_tax_to"]
    payable = ((pre + rr // 2) // rr) * rr
    if payable != pre:
        tl.append(line("Rounding of tax payable", payable - pre, "R288B"))
    return {"regime": which, "fy": inp.fy, "taxable_income": taxable, "tax_payable": payable,
            "total_exemptions_and_deductions": hra_ex + std + ded_total,
            "income_lines": income_lines, "tax_lines": tl}


class CompiledEngine:
    name = "c_llm_compiled"

    def __init__(self, rules_dir: str = None):
        self.rules_dir = rules_dir
        self._cache = {}

    def _rules(self, fy):
        if fy not in self._cache:
            self._cache[fy] = load_rules(fy, self.rules_dir)
        return self._cache[fy]

    def compute(self, inp: TaxInput) -> dict:
        rules = self._rules(inp.fy)
        return compare(lambda i, w: _regime(i, w, rules), inp)
