"""Task 5: hybrid pipeline built from the measured winners.
Stage 1 (every row)   : cheap rules / learned-from-baseline statistics, chosen PER PROBLEM from eval results.
Stage 2 (every batch) : batch-level statistical checks already in the plan (null spike, drift).
Stage 3 (rare)        : ONE LLM call per batch on rows already flagged by stages 1-2 for semantically ambiguous
                        problems (p06, p12) plus a small random sample for unknown unknowns. Skipped (cost projected)
                        when no GEMINI_API_KEY."""
import time
import numpy as np
import pandas as pd
from .detectors import RulesDetector, StatsDetector
from .detectors_llm import LLMReviewer, build_prompt
from .injector import inject, PROBLEMS
from project_a.llm import PRICE_IN, PRICE_OUT

LLM_CONFIRM = {"p06", "p12"}


def build_plan(res):
    plan = {}
    for pid, p in res["problems"].items():
        best, bs = None, -9
        for name, m in p["detectors"].items():
            rec = m["row_recall"] if m["row_recall"] is not None else m["detection_rate"]
            sc = rec - 10 * m["false_alarm_row_rate"] - 0.5 * m["false_alarm_batch_rate"] - 1e-9 * (1 if name == "stats" else 0)
            if sc > bs:
                best, bs = name, sc
        plan[pid] = best
    return plan


class Hybrid:
    def __init__(self, base, plan, llm=None, sample_n=20, cap=40):
        self.dets = {"rules": RulesDetector().fit(base), "stats": StatsDetector().fit(base)}
        self.plan, self.llm, self.sample_n, self.cap = plan, llm, sample_n, cap
        self.cheap_s = 0.0
        self.llm_prompt_tokens = 0
        self.llm_calls = 0

    def run(self, df):
        t = time.perf_counter()
        out = {pid: self.dets[d].detect_one(pid, df) for pid, d in self.plan.items()}
        self.cheap_s += time.perf_counter() - t
        flagged = set()
        for pid in LLM_CONFIRM:
            if out[pid].rows is not None:
                flagged |= set(np.flatnonzero(out[pid].rows)[: self.cap].tolist())
        rng = np.random.default_rng(len(df))
        ids = sorted(flagged | set(rng.choice(len(df), self.sample_n, replace=False).tolist()))
        self.llm_calls += 1
        self.llm_prompt_tokens += len(build_prompt(df, ids)) / 4
        if self.llm is not None:
            for pid, a in self.llm.review(df, ids).items():
                if pid not in out or not out[pid].flag:
                    out[pid] = a
        return out


def hybrid_eval(res, llm=None):
    ev, base = res["_ev_all"], res["_base"]
    plan = build_plan(res)
    H = Hybrid(base, plan, llm)
    pids = list(PROBLEMS)
    out = {"plan": plan, "per_problem": {}, "clean_batches": 0}
    nrows = 0
    for i, pid in enumerate(pids):
        from .evaluate import HEAD
        c, truth = inject(ev[i], pid, HEAD.get(pid, HEAD["default"]), 100 + i)
        a = H.run(c)
        nrows += len(c)
        row = {"detected": bool(a[pid].flag)}
        if truth["rows"] is not None and a[pid].rows is not None:
            row["row_recall"] = float((a[pid].rows & truth["rows"]).sum() / max(1, truth["rows"].sum()))
        # other problems flagged on this batch = cross-alerts (confusion)
        row["other_alerts"] = sorted(k for k, v in a.items() if v.flag and k != pid)
        out["per_problem"][pid] = row
    fa = 0
    for b in ev[12:20]:
        a = H.run(b); nrows += len(b)
        fa += sum(v.flag for v in a.values())
    out["clean_batches"] = len(ev[12:20])
    out["false_alerts_on_clean_batches"] = fa
    out["false_alerts_per_clean_batch"] = fa / out["clean_batches"]
    out["cheap_rows_per_sec"] = nrows / H.cheap_s
    out["cheap_usd_per_million_rows"] = (1e6 / out["cheap_rows_per_sec"]) * 0.04 / 3600
    nb = H.llm_calls
    out["llm_calls_per_batch"] = 1
    out["llm_avg_prompt_tokens"] = H.llm_prompt_tokens / nb
    out["llm_usd_per_million_rows_projected"] = (1e6 / len(ev[0])) * (out["llm_avg_prompt_tokens"] * PRICE_IN + 350 * PRICE_OUT) / 1e6
    out["llm_stage"] = "run" if llm else "not_run (cost projected from real prompts; 350 output tokens assumed)"
    return out
