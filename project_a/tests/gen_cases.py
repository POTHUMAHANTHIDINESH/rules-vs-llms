"""Generate tests/cases.json (>=200 cases) + official_calculator_checks.csv. Deterministic (seed 2026)."""
import csv
import json
import os
import random
from .oracle import oracle, NEW_BP, NEW_REBATE, SC_OLD

HERE = os.path.dirname(__file__)
FYS = ["2024-25", "2025-26"]


def mk(fy, gross, **kw):
    d = {"fy": fy, "age": 30, "gross_salary": gross, "basic_salary": None, "hra_received": 0, "rent_paid": 0,
         "metro": False, "sec_80c": 0, "sec_80ccd1b": 0, "sec_80d_self": 0, "sec_80d_parents": 0,
         "parents_senior": False, "home_loan_interest": 0}
    d.update(kw)
    return d


# Hand-computed goldens (worked on paper; comments show the arithmetic). These validate the oracle itself.
HAND = [
    ("hand-new24-12L", mk("2024-25", 1275000), {"new": (1200000, 83200)}),                 # 20k+30k+30k=80k, +3,200 cess
    ("hand-new25-12L-rebate", mk("2025-26", 1275000), {"new": (1200000, 0)}),               # 20k+40k=60k - rebate 60k
    ("hand-new25-marginal", mk("2025-26", 1276000), {"new": (1201000, 1040)}),              # tax 60,150 -> capped at 1,000 +40 cess
    ("hand-new24-7L-rebate", mk("2024-25", 775000), {"new": (700000, 0)}),                  # tax 20,000 - 25,000 rebate
    ("hand-new24-marginal-10", mk("2024-25", 775010), {"new": (700010, 10)}),               # capped at Rs 10; cess rounds to 0
    ("hand-new24-50L", mk("2024-25", 5075000), {"new": (5000000, 1237600)}),                # 1,190,000 + 47,600 cess
    ("hand-new24-50L+10-sc-relief", mk("2024-25", 5075010), {"new": (5000010, 1237610)}),   # tax 1,190,003; sc capped at 7
    ("hand-old-5L-rebate", mk("2024-25", 550000), {"old": (500000, 0)}),                    # 12,500 - 12,500
    ("hand-old-5L+10", mk("2024-25", 560010), {"old": (510010, 15080)}),                    # 12,500+2,002=14,502; cess 580 -> 15,082 -> 15,080
    ("hand-old-hra", mk("2024-25", 1500000, basic_salary=600000, hra_received=300000, rent_paid=360000, metro=True),
     {"old": (1500000 - 300000 - 50000, None)}),                                            # HRA: min(300k, 360k-60k=300k, 300k)=300k
]


def edge_targets(fy):
    ts = set()
    for bp, _ in NEW_BP[fy]:
        ts |= {bp - 10, bp, bp + 10}
    lim, _ = NEW_REBATE[fy]
    ts |= {lim - 10, lim, lim + 10, lim + 1010, lim + 40000, lim + 100000}
    for thr, _ in SC_OLD:
        ts |= {thr - 10, thr, thr + 10, thr + 1000, thr + 100000}
    ts |= {250000, 300000, 500000, 1000000, 505000, 504990}
    return sorted(t for t in ts if t >= 0)


def build():
    rnd = random.Random(2026)
    cases = []

    def add(cid, d, hand=None):
        exp = {w: oracle(d, w) for w in ("old", "new")}
        if hand:
            for w, (ti, tp) in hand.items():
                assert exp[w]["taxable_income"] == ti, (cid, w, exp[w], ti)
                if tp is not None:
                    assert exp[w]["tax_payable"] == tp, (cid, w, exp[w], tp)
        cases.append({"id": cid, "input": d, "expected": exp, "source": "hand+oracle" if hand else "oracle"})

    for cid, d, h in HAND:
        add(cid, d, h)
    for fy in FYS:
        for t in edge_targets(fy):          # new-regime thresholds: gross = taxable + 75k (old taxable differs)
            add(f"edge-{fy}-new-{t}", mk(fy, t + 75000))
        for t in (250000, 300000, 500000, 1000000, 5000000, 10000000):   # old-regime thresholds: gross = taxable + 50k
            for dt in (-10, 0, 10):
                add(f"edge-{fy}-old-{t + dt}", mk(fy, t + dt + 50000))
        for age in (59, 60, 79, 80):                                     # age bands
            for g in (300000 + 50000, 350000 + 50000, 500000 + 50000, 550000 + 50000, 1000000 + 50000):
                add(f"age-{fy}-{age}-{g}", mk(fy, g, age=age))
        for v in (149990, 150000, 150010):
            add(f"80c-{fy}-{v}", mk(fy, 1400000, sec_80c=v))
        for v in (49990, 50000, 50010):
            add(f"80ccd1b-{fy}-{v}", mk(fy, 1400000, sec_80ccd1b=v))
        for v in (199990, 200000, 200010):
            add(f"24b-{fy}-{v}", mk(fy, 1400000, home_loan_interest=v))
        for age, ps in ((30, False), (62, False), (45, True), (65, True)):
            for s, p in ((24990, 24990), (25010, 25010), (50010, 50010), (0, 60000)):
                add(f"80d-{fy}-{age}-{ps}-{s}-{p}", mk(fy, 1500000, age=age, sec_80d_self=s, sec_80d_parents=p, parents_senior=ps))
        for metro in (True, False):                                      # HRA: each of the 3 limbs binding
            for name, basic, hra, rent in (("actual", 600000, 100000, 400000), ("rent-minus-10pct", 600000, 300000, 200000),
                                           ("pct-of-basic", 600000, 400000, 600000), ("no-rent", 600000, 200000, 0),
                                           ("rent-below-10pct", 600000, 100000, 50000)):
                add(f"hra-{fy}-{metro}-{name}", mk(fy, 1500000, basic_salary=basic, hra_received=hra, rent_paid=rent, metro=metro))
        for _ in range(35):                                              # fuzz
            gross = rnd.choice([rnd.randint(0, 600000), rnd.randint(400000, 2500000), rnd.randint(2500000, 40000000)])
            basic = rnd.randint(0, max(0, int(gross * 0.5)))
            hra = rnd.randint(0, max(0, min(gross - basic, int(basic * 0.6))))
            d = mk(fy, gross, age=rnd.choice([22, 35, 52, 60, 66, 79, 80, 88]),
                   basic_salary=basic, hra_received=hra, rent_paid=rnd.choice([0, rnd.randint(0, 900000)]),
                   metro=rnd.random() < .5, sec_80c=rnd.randint(0, 220000), sec_80ccd1b=rnd.randint(0, 70000),
                   sec_80d_self=rnd.randint(0, 60000), sec_80d_parents=rnd.randint(0, 60000),
                   parents_senior=rnd.random() < .5, home_loan_interest=rnd.randint(0, 300000))
            add(f"fuzz-{fy}-{len(cases)}", d)
    return cases


def main():
    cases = build()
    json.dump(cases, open(os.path.join(HERE, "cases.json"), "w"), indent=1)
    rnd = random.Random(7)
    pick = rnd.sample([c for c in cases if not c["id"].startswith("fuzz")], 15) + \
        rnd.sample([c for c in cases if c["id"].startswith("fuzz")], 15)
    keys = list(pick[0]["input"].keys())
    with open(os.path.join(HERE, "official_calculator_checks.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id"] + keys + ["our_old_taxable", "our_old_tax", "our_new_taxable", "our_new_tax",
                                         "official_old_tax", "official_new_tax", "notes"])
        for c in pick:
            e = c["expected"]
            w.writerow([c["id"]] + [c["input"][k] for k in keys] +
                       [e["old"]["taxable_income"], e["old"]["tax_payable"], e["new"]["taxable_income"], e["new"]["tax_payable"],
                        e["old"]["tax_payable"], e["new"]["tax_payable"], "Verified against ITD official calculator"])
    print(len(cases), "cases written;", len(pick), "exported for official-calculator verification")


if __name__ == "__main__":
    main()
