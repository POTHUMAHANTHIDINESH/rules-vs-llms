"""Task 6 numbers: 50M rows/day, 120 customers. Reads results/eval.json -> results/scale.json."""
import json, os
from project_a.llm import PRICE_IN, PRICE_OUT
HERE = os.path.dirname(__file__)


def main():
    r = json.load(open(os.path.join(HERE, "results", "eval.json")))
    h, proj = r["hybrid"], r["llm_cost_projection"]
    rows, cust, batch = 50e6, 120, r["batch_rows"]
    cpu_s = rows / h["cheap_rows_per_sec"]
    batches = rows / batch
    out = {"rows_per_day": rows, "customers": cust, "batches_per_day": batches,
           "cheap_cpu_core_hours_per_day": cpu_s / 3600, "cheap_usd_per_day": cpu_s / 3600 * 0.04,
           "hybrid_llm_calls_per_day": batches, "hybrid_llm_usd_per_day": h["llm_usd_per_million_rows_projected"] * rows / 1e6,
           "llm_every_row_usd_per_day": proj["every_row_usd_per_M_rows"] * rows / 1e6,
           "llm_batch_sample_only_usd_per_day": proj["batch_sample_usd_per_M_rows"] * rows / 1e6,
           "baseline_refit_core_hours_per_day_if_daily": sum(r["fit_seconds"].values()) * cust / 3600,
           "schema_onboarding_llm_calls": cust, "peak_calls_per_min_if_8h_window": batches / (8 * 60),
           "free_tier_note": "free-tier Gemini quotas are orders of magnitude below the daily call count: paid tier or self-hosted model required"}
    json.dump(out, open(os.path.join(HERE, "results", "scale.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
