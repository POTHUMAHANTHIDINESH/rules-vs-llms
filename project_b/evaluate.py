"""Task 3-4: run every detector on clean and corrupted batches. `python -m project_b.evaluate [--csv real.csv] [--llm]`"""
import argparse, json, os, time, warnings
import numpy as np
import pandas as pd
from . import schema as S
from .synth_311 import generate, batches
from .injector import inject, PROBLEMS
from .detectors import RulesDetector, StatsDetector
from .detectors_llm import LLMReviewer, project_cost

warnings.filterwarnings("ignore")
HERE = os.path.dirname(__file__)
RATES = {"default": [0.01, 0.05, 0.20], "p03": [0.1, 0.3, 0.6], "p07": [0.1, 0.3, 0.6]}
HEAD = {"default": 0.05, "p03": 0.3, "p07": 0.3}
CPU_USD_PER_SEC = float(os.environ.get("CPU_USD_PER_HOUR", "0.04")) / 3600   # ASSUMPTION: $0.04 per vCPU-hour


def load(csv=None, rows=200_000):
    if csv:
        df = pd.read_csv(csv, low_memory=False)
        df = df[[c for c in S.COLS if c in df.columns]]
        df["Incident Zip"] = df["Incident Zip"].astype("string").str.slice(0, 5).astype(object)
        return df, "REAL NYC 311 2023 (user-supplied CSV)"
    return generate(rows), "SYNTHETIC (generator in project_b/synth_311.py)"


def run(csv=None, n_batches=10, seed=0, use_llm=False):
    df, source = load(csv)
    base = df.iloc[:100_000].reset_index(drop=True)
    ev_all = [b for b, _ in zip(batches(df.iloc[100_000:].reset_index(drop=True)), range(20))]
    ev = ev_all[:n_batches]
    dets, fit_s = [], {}
    for D in (RulesDetector, StatsDetector):
        t = time.time(); d = D().fit(base); fit_s[d.name] = time.time() - t; dets.append(d)
    res = {"source": source, "baseline_rows": len(base), "batch_rows": len(ev[0]), "n_batches": len(ev), "fit_seconds": fit_s, "problems": {}}
    for pid, title in PROBLEMS.items():
        rates = RATES.get(pid, RATES["default"])
        head = HEAD.get(pid, HEAD["default"])
        pr = {"title": title, "headline_rate": head, "detectors": {}}
        for d in dets:
            m = {"by_rate": {}, "fa_batches": 0, "fa_rows": 0, "t_clean": 0.0}
            for b in ev:                                             # clean batches -> false alarms
                t = time.perf_counter(); a = d.detect_one(pid, b); m["t_clean"] += time.perf_counter() - t
                m["fa_batches"] += a.flag
                m["fa_rows"] += int(a.rows.sum()) if a.rows is not None else 0
            for r in rates:
                det_n, rec, prec, expl, tt = 0, [], [], [], 0.0
                for i, b in enumerate(ev):
                    c, truth = inject(b, pid, r, seed + i)
                    t = time.perf_counter(); a = d.detect_one(pid, c); tt += time.perf_counter() - t
                    det_n += a.flag
                    if a.flag:
                        expl.append(a.explain_score())
                    if truth["rows"] is not None and a.rows is not None:
                        tp = (a.rows & truth["rows"]).sum()
                        rec.append(tp / max(1, truth["rows"].sum()))
                        prec.append(tp / a.rows.sum() if a.rows.sum() else 1.0)
                m["by_rate"][str(r)] = {"detection_rate": det_n / len(ev), "row_recall": float(np.mean(rec)) if rec else None,
                                        "row_precision": float(np.mean(prec)) if prec else None, "explain_score_0_4": float(np.mean(expl)) if expl else None,
                                        "seconds_per_batch": tt / len(ev)}
            h = m["by_rate"][str(head)]
            m.update(detection_rate=h["detection_rate"], row_recall=h["row_recall"], row_precision=h["row_precision"],
                     explain_score_0_4=h["explain_score_0_4"], false_alarm_batch_rate=m.pop("fa_batches") / len(ev),
                     false_alarm_row_rate=m.pop("fa_rows") / (len(ev) * len(ev[0])))
            spb = max(h["seconds_per_batch"], 1e-6)
            m["rows_per_sec"] = len(ev[0]) / spb
            m["usd_per_million_rows"] = (1e6 / m["rows_per_sec"]) * CPU_USD_PER_SEC
            m.pop("t_clean")
            pr["detectors"][d.name] = m
        res["problems"][pid] = pr
    res["llm_cost_projection"] = project_cost(ev[0])
    res["llm_eval"] = {"status": "not_run", "reason": "GEMINI_API_KEY not set or --llm not passed"}
    if use_llm:
        from project_a.llm import get_client_or_none
        client = get_client_or_none()
        if client is not None:
            res["llm_eval"] = run_llm(client, ev, seed)
    res["_ev_all"] = ev_all
    res["_base"] = base
    return res, ev


def run_llm(client, ev, seed, n_batches=3):
    rv = LLMReviewer(client)
    out = {"status": "run", "model": client.model, "sample_rows": rv.sample_n, "problems": {}}
    fa = 0
    for i in range(n_batches):
        fa += len(rv.review(ev[i], seed=seed + i)) > 0
    out["clean_batches_with_any_alert"] = fa / n_batches
    for pid in PROBLEMS:
        r = HEAD.get(pid, HEAD["default"])
        hit, rec = 0, []
        for i in range(n_batches):
            c, truth = inject(ev[i], pid, r, seed + i)
            al = rv.review(c, seed=seed + i)
            hit += pid in al
            if truth["rows"] is not None and pid in al and al[pid].rows is not None:
                ids = np.flatnonzero(al[pid].rows)
                out.setdefault("precision_of_ids", {}).setdefault(pid, []).append(float(truth["rows"][ids].mean()) if len(ids) else None)
        out["problems"][pid] = {"detection_rate": hit / n_batches}
    out["usd_total"] = sum(u.cost_usd for u in rv.usage)
    out["usd_per_million_rows_measured"] = out["usd_total"] / (len(rv.usage) * len(ev[0]) * 1.0) * 1e6 * (len(ev[0]) / rv.sample_n) / (len(ev[0]) / 1) if False else \
        sum(u.cost_usd for u in rv.usage) / len(rv.usage) * (1e6 / len(ev[0]))
    out["latency_s_mean"] = float(np.mean([u.latency_s for u in rv.usage]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--batches", type=int, default=10)
    a = ap.parse_args()
    res, _ = run(a.csv, a.batches, use_llm=a.llm)
    from .hybrid import hybrid_eval
    res["hybrid"] = hybrid_eval(res)
    res.pop("_ev_all"); res.pop("_base")
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    json.dump(res, open(os.path.join(HERE, "results", "eval.json"), "w"), indent=1)
    print(res["source"])
    for pid, p in res["problems"].items():
        print(pid, p["title"][:28].ljust(28), *[f"{n}: det={m['detection_rate']:.2f} rec={m['row_recall'] if m['row_recall'] is None else round(m['row_recall'],2)} faB={m['false_alarm_batch_rate']:.1f} faR={m['false_alarm_row_rate']:.4f} {m['rows_per_sec']:.0f}r/s |"
                                           for n, m in p["detectors"].items()])


if __name__ == "__main__":
    main()
