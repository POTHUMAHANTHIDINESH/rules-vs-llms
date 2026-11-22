"""Implementation (b): LLM at query time. The model reads the rule text and does all arithmetic."""
import json
import os
import re
from .tax_common import TaxInput, recommend

HERE = os.path.dirname(__file__)
SYSTEM = ("You are an Indian income-tax calculator for salaried residents. Use ONLY the rules provided. "
          "Do the arithmetic exactly (integers, rupees). Return JSON only.")

PROMPT = """RULES:
{rules}

TAXPAYER INPUT (annual, rupees):
{inp}

Compute tax under BOTH regimes (old and new) following the rules exactly, including rounding clauses.
Return JSON with this exact shape:
{{"old": {{"taxable_income": int, "tax_payable": int,
          "income_lines": [{{"label": str, "amount": int, "clause": str}}],
          "tax_lines": [{{"label": str, "amount": int, "clause": str}}]}},
  "new": {{ same shape }}}}
income_lines: signed amounts from gross salary down to taxable income (deductions negative), ending with the
R288A rounding line so they sum to taxable_income. tax_lines: signed amounts summing to tax_payable
(slab tax, rebate, surcharge, cess, R288B rounding). Every line must cite a clause id from the rules in `clause`."""


def rule_text(fy: str) -> str:
    return open(os.path.join(HERE, "rule_text", f"fy{fy.replace('-', '_')}.md")).read()


def clause_ids(fy: str) -> set:
    return set(re.findall(r"\[([A-Za-z0-9_]+)\]", rule_text(fy)))


def _clean(reg: dict) -> dict:
    return {"taxable_income": int(reg["taxable_income"]), "tax_payable": int(reg["tax_payable"]),
            "income_lines": reg.get("income_lines", []), "tax_lines": reg.get("tax_lines", []),
            "total_exemptions_and_deductions": -sum(l["amount"] for l in reg.get("income_lines", [])
                                                    if l["amount"] < 0 and l.get("clause") != "R288A")}


class LLMEngine:
    name = "b_llm_query_time"

    def __init__(self, client):
        self.client = client
        self.last = None       # last LLMResult, for cost/latency accounting

    def compute(self, inp: TaxInput) -> dict:
        inp.validate()
        prompt = PROMPT.format(rules=rule_text(inp.fy), inp=json.dumps(inp.to_dict()))
        res = self.client.generate(prompt, system=SYSTEM, json_mode=True, temperature=0.0)
        self.last = res
        txt = re.sub(r"^```(?:json)?|```$", "", res.text.strip(), flags=re.M).strip()
        d = json.loads(txt)
        old, new = _clean(d["old"]), _clean(d["new"])
        old["regime"], new["regime"] = "old", "new"
        return {"old": old, "new": new, "recommendation": recommend(old, new)}
