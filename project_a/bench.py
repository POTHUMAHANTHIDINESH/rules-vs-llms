"""Task 4: measure all three implementations. `python -m project_a.bench [--llm-n 30] [--det-n 5]`
Engines a and c always run. Engine b (and the LLM parser) run only if GEMINI_API_KEY is set; otherwise they
are recorded as not_run (never simulated)."""
import argparse, hashlib, json, os, statistics, time
from .tax_common import TaxInput
from .tax_a_rules import HandCodedEngine
from .tax_c_compiled import CompiledEngine
from .tax_b_llm import LLMEngine, clause_ids
from .llm import get_client_or_none, LLMUnavailable
from .tests.eval_parser import evaluate

HERE = os.path.dirname(__file__)
CASES = json.load(open(os.path.join(HERE, "tests", "cases.json")))


def trace_ok(res, fy):
    ids = clause_ids(fy)
    ok = True
    for w in ("old", "new"):
        r = res[w]
        lines = r["income_lines"] + r["tax_lines"]
        ok &= all(l.get("clause") in ids for l in lines)
        ok &= sum(l["amount"] for l in r["income_lines"]) == r["taxable_income"]
        ok &= sum(l["amount"] for l in r["tax_lines"]) == r["tax_payable"]
    return ok


def exact(res, exp):
    return all(res[w]["taxable_income"] == exp[w]["taxable_income"] and res[w]["tax_payable"] == exp[w]["tax_payable"]
               for w in ("old", "new"))


def digest(res):
    core = {w: [res[w]["taxable_income"], res[w]["tax_payable"]] for w in ("old", "new")}
    return hashlib.sha1(json.dumps(core).encode()).hexdigest()[:10]


def run_engine(engine, cases, det_cases, reps=10, llm=False):
    out = {"n_cases": len(cases), "correct": 0, "errors": 0, "traceable": 0, "lat": [], "cost": 0.0, "tokens_in": 0, "tokens_out": 0}
    wrong = []
    for c in cases:
        inp = TaxInput.from_dict(c["input"])
        t0 = time.perf_counter()
        try:
            r = engine.compute(inp)
        except Exception as e:                                   # LLM malformed output etc. = loud failure
            out["errors"] += 1
            out["lat"].append(time.perf_counter() - t0)
            continue
        out["lat"].append(time.perf_counter() - t0)
        if llm and engine.last:
            out["cost"] += engine.last.cost_usd
            out["tokens_in"] += engine.last.in_tokens
            out["tokens_out"] += engine.last.out_tokens
        if exact(r, c["expected"]):
            out["correct"] += 1
        else:
            wrong.append(c["id"])
        out["traceable"] += trace_ok(r, c["input"]["fy"])
    n = len(cases)
    lat = sorted(out.pop("lat"))
    out.update(accuracy=out["correct"] / n, trace_rate=out["traceable"] / n, wrong_ids=wrong[:15],
               silent_wrong=len(wrong), latency_ms_p50=1000 * statistics.median(lat),
               latency_ms_p95=1000 * lat[int(0.95 * (len(lat) - 1))],
               cost_per_1000_usd=(out["cost"] / n * 1000) if llm else 0.0)
    # determinism: same input x reps
    varying = 0
    for c in det_cases:
        inp = TaxInput.from_dict(c["input"])
        seen = set()
        for _ in range(reps):
            try:
                seen.add(digest(engine.compute(inp)))
            except Exception:
                seen.add("ERR")
        varying += len(seen) > 1
    out["determinism"] = {"inputs": len(det_cases), "repeats": reps, "inputs_with_varying_output": varying}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm-n", type=int, default=30)
    ap.add_argument("--det-n", type=int, default=5)
    a = ap.parse_args()
    res = {"suite_size": len(CASES), "engines": {}}
    det = CASES[:a.det_n]
    res["engines"]["a_hand_coded"] = run_engine(HandCodedEngine(), CASES, CASES[:50])
    res["engines"]["c_llm_compiled"] = run_engine(CompiledEngine(), CASES, CASES[:50])
    client = get_client_or_none()
    if client is None:
        res["engines"]["b_llm_query_time"] = {"status": "not_run", "reason": "GEMINI_API_KEY not set"}
        res["parser_llm"] = {"status": "not_run", "reason": "GEMINI_API_KEY not set"}
    else:
        import random
        rnd = random.Random(1)
        sample = CASES[:10] + rnd.sample(CASES[10:], max(0, a.llm_n - 10))
        eng = LLMEngine(client)
        try:
            r = run_engine(eng, sample, sample[:a.det_n], reps=10, llm=True)
            r["model"] = client.model
            r["sampled_cases"] = len(sample)
            res["engines"]["b_llm_query_time"] = r
        except LLMUnavailable as e:
            res["engines"]["b_llm_query_time"] = {"status": "failed", "reason": str(e)}
        try:
            pr = evaluate(client)
            res["parser_llm"] = {k: v for k, v in pr.items() if k != "fails"}
        except Exception as e:
            res["parser_llm"] = {"status": "failed", "reason": str(e)}
    pr = evaluate(None)
    res["parser_rules"] = {k: v for k, v in pr.items() if k != "fails"}
    res["parser_rules"]["failing_ids"] = [f["id"] for f in pr["fails"]]
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    json.dump(res, open(os.path.join(HERE, "results", "bench.json"), "w"), indent=1)
    for k, v in res["engines"].items():
        print(k, {x: v[x] for x in ("accuracy", "trace_rate", "latency_ms_p50", "cost_per_1000_usd") if x in v} or v)


if __name__ == "__main__":
    main()
