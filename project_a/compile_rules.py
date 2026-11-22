"""Implementation (c) step 1: LLM converts rule text -> JSON DSL ONCE. A human reviews the diff, then the suite runs.
    python -m project_a.compile_rules --fy 2025-26   (needs GEMINI_API_KEY)
Writes project_a/rules/compiled/dsl_fy<fy>.json (NOT used at runtime until you copy it over rules/ after review)."""
import argparse, difflib, json, os, re
from .llm import GeminiClient
from .tax_b_llm import rule_text
from .tax_c_compiled import validate_dsl, RULES_DIR

PROMPT = """Convert the tax rules below into the JSON DSL shown by the example. Output JSON only, same keys and structure,
amounts in rupees, rates in percent, last slab upto=null, surcharge tiers use 'above'. Do not invent rules.
EXAMPLE (financial year {ex_fy}) - structure reference only, values may differ:
{example}
RULES TO COMPILE (financial year {fy}):
{rules}"""


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--fy", required=True); ap.add_argument("--example-fy", default="2024-25")
    a = ap.parse_args()
    ex = open(os.path.join(RULES_DIR, f"dsl_fy{a.example_fy.replace('-', '_')}.json")).read()
    res = GeminiClient().generate(PROMPT.format(ex_fy=a.example_fy, example=ex, fy=a.fy, rules=rule_text(a.fy)))
    d = json.loads(re.sub(r"^```(?:json)?|```$", "", res.text.strip(), flags=re.M))
    validate_dsl(d)
    os.makedirs(os.path.join(RULES_DIR, "compiled"), exist_ok=True)
    out = os.path.join(RULES_DIR, "compiled", f"dsl_fy{a.fy.replace('-', '_')}.json")
    json.dump(d, open(out, "w"), indent=1)
    seed = os.path.join(RULES_DIR, f"dsl_fy{a.fy.replace('-', '_')}.json")
    if os.path.exists(seed):
        print("".join(difflib.unified_diff(open(seed).read().splitlines(1), open(out).read().splitlines(1), "seed", "llm_compiled")) or "IDENTICAL to seed")
    print(f"wrote {out}; cost ${res.cost_usd:.4f}. Review, copy to rules/, run pytest.")


if __name__ == "__main__":
    main()
