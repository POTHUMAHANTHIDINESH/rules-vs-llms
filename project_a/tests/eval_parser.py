import json, os, sys
from project_a.parser import parse

HERE = os.path.dirname(__file__)


def evaluate(client=None, verbose=False):
    cases = json.load(open(os.path.join(HERE, "user_descriptions.json")))
    res = {"n": len(cases), "status_ok": 0, "inputs_ok": 0, "missing_ok": 0, "silent_guess": 0, "fails": []}
    n_ready_exp = n_clar_exp = 0
    for c in cases:
        out = parse(c["text"], client)
        st_ok = out["status"] == c["expected_status"]
        res["status_ok"] += st_ok
        in_ok = all(out["inputs"].get(k) == v for k, v in c["expected_inputs"].items())
        miss_ok = True
        if c["expected_status"] == "needs_clarification":
            n_clar_exp += 1
            miss_ok = set(out["missing"]) == set(c["expected_missing"])
            res["missing_ok"] += miss_ok
        if c["expected_status"] == "ready":
            n_ready_exp += 1
            res["inputs_ok"] += in_ok
        if c["expected_status"] != "ready" and out["status"] == "ready":
            res["silent_guess"] += 1          # said "ready" when it should have asked / flagged
        if not (st_ok and in_ok and miss_ok):
            res["fails"].append({"id": c["id"], "text": c["text"], "expected": c["expected_status"], "got": out["status"],
                                 "missing": out["missing"], "exp_missing": c["expected_missing"],
                                 "bad_inputs": {k: (out["inputs"].get(k), v) for k, v in c["expected_inputs"].items() if out["inputs"].get(k) != v},
                                 "conflicts": out["conflicts"]})
    res.update(n_ready_expected=n_ready_exp, n_clarify_expected=n_clar_exp)
    return res


if __name__ == "__main__":
    r = evaluate()
    print({k: v for k, v in r.items() if k != "fails"})
    for f in r["fails"]:
        print(json.dumps(f, ensure_ascii=False))
