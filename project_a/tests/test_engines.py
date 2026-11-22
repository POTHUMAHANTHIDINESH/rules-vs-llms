import json
import os
import re
import pytest
from project_a.tax_common import TaxInput
from project_a.tax_a_rules import HandCodedEngine
from project_a.tax_c_compiled import CompiledEngine, validate_dsl, load_rules
from project_a.tax_b_llm import LLMEngine, clause_ids
from project_a.llm import FakeLLM

HERE = os.path.dirname(__file__)
CASES = json.load(open(os.path.join(HERE, "cases.json")))
ENGINES = [HandCodedEngine(), CompiledEngine()]


def test_at_least_200_cases():
    assert len(CASES) >= 200


@pytest.mark.parametrize("engine", ENGINES, ids=lambda e: e.name)
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_rupee_exact(engine, case):
    r = engine.compute(TaxInput.from_dict(case["input"]))
    for w in ("old", "new"):
        assert r[w]["taxable_income"] == case["expected"][w]["taxable_income"], w
        assert r[w]["tax_payable"] == case["expected"][w]["tax_payable"], w


@pytest.mark.parametrize("engine", ENGINES, ids=lambda e: e.name)
def test_every_rupee_traces_to_a_clause_and_reconciles(engine):
    for case in CASES:
        r = engine.compute(TaxInput.from_dict(case["input"]))
        ids = clause_ids(case["input"]["fy"])
        for w in ("old", "new"):
            reg = r[w]
            assert sum(l["amount"] for l in reg["income_lines"]) == reg["taxable_income"], case["id"]
            assert sum(l["amount"] for l in reg["tax_lines"]) == reg["tax_payable"], case["id"]
            assert all(l["clause"] in ids for l in reg["income_lines"] + reg["tax_lines"]), case["id"]


def test_unknown_fy_fails_loudly():
    with pytest.raises(KeyError):
        HandCodedEngine().compute(TaxInput(fy="2026-27", gross_salary=1000000))
    with pytest.raises(KeyError):
        CompiledEngine().compute(TaxInput(fy="2026-27", gross_salary=1000000))


def test_dsl_validation_rejects_bad_rules():
    d = load_rules("2024-25")
    d["regimes"]["new"]["slab_tables"]["general"][-1]["upto"] = 5
    with pytest.raises(ValueError):
        validate_dsl(d)


def test_input_validation():
    with pytest.raises(ValueError):
        TaxInput(gross_salary=-1).validate()
    with pytest.raises(ValueError):
        TaxInput(gross_salary=500000, hra_received=1000, rent_paid=5000).validate()   # basic missing


def test_llm_engine_plumbing_with_fake_llm():
    """Plumbing only: a FakeLLM that returns the hand-coded answer. Says nothing about real LLM accuracy."""
    hand = HandCodedEngine()

    def responder(prompt):
        d = json.loads(re.search(r"TAXPAYER INPUT[^\n]*\n(\{[^\n]*\})", prompt, re.S).group(1))
        r = hand.compute(TaxInput.from_dict(d))
        return json.dumps({w: {k: r[w][k] for k in ("taxable_income", "tax_payable", "income_lines", "tax_lines")}
                           for w in ("old", "new")})
    e = LLMEngine(FakeLLM(responder))
    out = e.compute(TaxInput(gross_salary=1275000))
    assert out["new"]["tax_payable"] == 83200 and out["recommendation"]["choice"] in ("old", "new")
