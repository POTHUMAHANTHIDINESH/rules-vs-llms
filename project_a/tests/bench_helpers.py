import json, os
HERE = os.path.dirname(__file__)


def load_cases():
    return json.load(open(os.path.join(HERE, "cases.json")))


def exact(res, exp):
    return all(res[w]["taxable_income"] == exp[w]["taxable_income"] and res[w]["tax_payable"] == exp[w]["tax_payable"]
               for w in ("old", "new"))
