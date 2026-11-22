"""Task 5 evidence: what does a Budget change cost, and which failures are silent?

Measured here (no LLM needed):
 1. size of the change per implementation (changed rule-text lines / DSL lines / constants);
 2. mutation analysis: plausible wrong ways to apply the FY2025-26 change (forgetting a part). For each,
    how many suite cases give a WRONG answer with NO runtime error (= silent) and whether the suite catches it;
 3. unknown-FY behaviour (loud vs silent).
Wall-clock time to implement the change must be recorded by the human doing it (see RESULTS_A.md log).
"""
import copy, difflib, json, os, tempfile
from . import tax_a_rules as A
from .tax_common import TaxInput
from .tax_c_compiled import CompiledEngine, RULES_DIR
from .tests.bench_helpers import load_cases, exact

HERE = os.path.dirname(__file__)


def difflines(a, b):
    return sum(1 for l in difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm="", n=0)
               if l[:1] in "+-" and l[:3] not in ("+++", "---"))


def a_mutations():
    base = copy.deepcopy(A.NEW["2025-26"])
    old24 = A.NEW["2024-25"]
    return {
        "forgot new slabs (kept FY24-25 slabs)": dict(slabs=old24["slabs"]),
        "forgot rebate limit (kept 7L)": dict(rebate_limit=700_000),
        "forgot rebate max (kept 25k)": dict(rebate_max=25_000),
        "slab boundary typo 12L->12.5L": dict(slabs=[(s if s != 1_200_000 else 1_250_000, r) for s, r in base["slabs"]]),
        "forgot 25% slab (20L-24L at 30%)": dict(slabs=[(400_000, 0), (800_000, 5), (1_200_000, 10), (1_600_000, 15), (2_000_000, 20), (None, 30)]),
    }


def run_a(cases, mut):
    saved = copy.deepcopy(A.NEW["2025-26"])
    A.NEW["2025-26"].update(mut)
    eng = A.HandCodedEngine()
    wrong = 0
    for c in cases:
        r = eng.compute(TaxInput.from_dict(c["input"]))      # never raises -> any mismatch is silent at runtime
        wrong += not exact(r, c["expected"])
    A.NEW["2025-26"].clear(); A.NEW["2025-26"].update(saved)
    return wrong


def c_mutations():
    return {
        "forgot new slabs (kept FY24-25 slabs)": lambda d: d["regimes"]["new"].update(slab_tables=copy.deepcopy(json.load(open(os.path.join(RULES_DIR, "dsl_fy2024_25.json")))["regimes"]["new"]["slab_tables"])),
        "forgot rebate limit (kept 7L)": lambda d: d["regimes"]["new"]["rebate"].update(income_limit=700000),
        "forgot rebate max (kept 25k)": lambda d: d["regimes"]["new"]["rebate"].update(max=25000),
        "slab boundary typo 12L->12.5L": lambda d: [s.update(upto=1250000) for s in d["regimes"]["new"]["slab_tables"]["general"] if s["upto"] == 1200000],
        "forgot 25% slab (20L-24L at 30%)": lambda d: d["regimes"]["new"]["slab_tables"].update(general=[s for s in d["regimes"]["new"]["slab_tables"]["general"] if s["rate"] != 25][:-1] + [{"upto": None, "rate": 30}]),
    }


def run_c(cases, fn):
    d = json.load(open(os.path.join(RULES_DIR, "dsl_fy2025_26.json")))
    fn(d)
    with tempfile.TemporaryDirectory() as td:
        json.dump(d, open(os.path.join(td, "dsl_fy2025_26.json"), "w"))
        eng = CompiledEngine(td)
        wrong = 0
        for c in cases:
            wrong += not exact(eng.compute(TaxInput.from_dict(c["input"])), c["expected"])
    return wrong


def main():
    cases = [c for c in load_cases() if c["input"]["fy"] == "2025-26"]
    res = {"n_fy2526_cases": len(cases)}
    rt24 = open(os.path.join(HERE, "rule_text", "fy2024_25.md")).read()
    rt25 = open(os.path.join(HERE, "rule_text", "fy2025_26.md")).read()
    d24 = open(os.path.join(RULES_DIR, "dsl_fy2024_25.json")).read()
    d25 = open(os.path.join(RULES_DIR, "dsl_fy2025_26.json")).read()
    changed_consts = sum(1 for k in A.NEW["2024-25"] if A.NEW["2024-25"][k] != A.NEW["2025-26"][k])
    res["change_size"] = {"b_rule_text_lines_changed": difflines(rt24, rt25), "c_dsl_json_lines_changed": difflines(d24, d25),
                          "a_constants_changed": changed_consts, "a_code_logic_lines_changed": 0}
    res["mutations"] = {}
    cm = c_mutations()
    for name, mut in a_mutations().items():
        res["mutations"][name] = {"a_wrong_cases_silent_at_runtime": run_a(cases, mut), "c_wrong_cases_silent_at_runtime": run_c(cases, cm[name])}
    loud = {}
    for nm, eng in (("a", A.HandCodedEngine()), ("c", CompiledEngine())):
        try:
            eng.compute(TaxInput(fy="2026-27", gross_salary=1_000_000)); loud[nm] = "SILENT (returned a number)"
        except KeyError:
            loud[nm] = "loud (KeyError)"
    res["unknown_fy"] = loud
    json.dump(res, open(os.path.join(HERE, "results", "task5.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
