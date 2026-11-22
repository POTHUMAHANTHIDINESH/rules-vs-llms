# Rules vs LLMs - Fire AI Take-Home Submission

**Author:** Pothumahanthi Dinesh  
**Repository:** https://github.com/POTHUMAHANTHIDINESH/rules-vs-llms

A comprehensive comparative study evaluating deterministic rules, statistical/ML models, and Large Language Models (LLMs) across two mission-critical enterprise systems:
1. **Project A:** Indian Income-Tax Engine (Old vs. New Regimes, FY 2024-25 & FY 2025-26).
2. **Project B:** Multi-Stage Data Quality & Anomaly Detection Pipeline (NYC 311 Service Requests).

---

## Quickstart: Reproducing All Results

In accordance with the submission guidelines, **a single command executes the entire test suite, benchmarks, mutation analyses, and regenerates every report and decision matrix**:

```bash
pip install -r requirements.txt
python run_all.py
```

### Optional Live LLM & Real-Data Evaluation
- **Live Gemini API:** Set `GEMINI_API_KEY` (free tier) to execute query-time LLM calculations, dynamic rule compilation, and LLM review passes:
  ```bash
  export GEMINI_API_KEY="your-api-key"
  python run_all.py
  ```
- **Real NYC 311 Dataset:** To execute on live NYC Open Data (requires network connection):
  ```bash
  python -m project_b.fetch_311 --out project_b/data/nyc311_2023.csv --limit 200000
  RUN_CSV=project_b/data/nyc311_2023.csv python run_all.py
  ```

---

## Deliverables Index

| Deliverable | Location | Description |
| :--- | :--- | :--- |
| **Project A Code** | `project_a/` | Hand-coded (`tax_a_rules.py`), LLM query-time (`tax_b_llm.py`), LLM-compiled (`tax_c_compiled.py`), NLP parser (`parser.py`), and test suite (`tests/`). |
| **Project A Results** | `RESULTS_A.md` | Rupee-exact accuracy tables, latency/cost benchmarks, mutation test log, and production architecture defense. |
| **Project B Code** | `project_b/` | 12-problem injector (`injector.py`), rule & stats detectors (`detectors.py`), LLM reviewer (`detectors_llm.py`), and hybrid pipeline (`hybrid.py`). |
| **Project B Results** | `RESULTS_B.md` | Per-problem detection rate, false-alarm rates, throughput, cost/M rows, and 50M rows/day scale architecture. |
| **Decision Matrix** | `DECISION_MATRIX.md` | Component-by-component classification (Rule, Statistical, LLM, or Hybrid) strictly justified by empirical metrics. |
| **AI Usage Note** | `AI_USAGE.md` | Tools used, verification methodology, and 4 concrete failure incidents caught during development. |

---

## Summary of Findings

### Project A (Tax Engine)
- **Deterministic Rules & Compiled DSL are Superior for Tax Arithmetic:** 100.0% accuracy across 319 edge/fuzz cases, sub-0.02 ms latency, $0 runtime cost, and 100% line-item clause auditability.
- **Official ITD Calculator Verification:** 30 spot-check cases exported and verified against the Income Tax Department's official tax portal (`python -m project_a.tests.verify_official` reports 30/30 verified, 0 mismatches).
- **Silent Failure Risk:** When the law changed in Budget 2025, partial updates failed completely silently (wrong tax numbers with 0 runtime errors) in 13–86 cases. Exhaustive threshold testing is strictly mandatory before release.
- **Hybrid Parser for Plain Language:** Rule-based regex extractor + deterministic state validator scored 50/50 on dev cases and 20/20 on held-out Hinglish descriptions, with **0 silent guesses** on ambiguous or incomplete inputs.

### Project B (Data Quality Layer)
- **High-Throughput Rules for Structural Anomalies:** Schema changes, null spikes, and format mutations are caught at >1,000,000 rows/second with $0.0000/M cost and 0% false alarms.
- **Statistical Detectors for Semantic & Distribution Drift:** Unsupervised z-score and temporal gap modeling efficiently catch near-duplicates and coordinate swaps.
- **Selective LLM Gating:** Reviewing every row with an LLM costs ~$39.00 / million rows (~$1,972/day at 50M rows). A hybrid pipeline—where cheap rules and statistical filters triage data and invoke an LLM only on flagged anomalies or micro-batches—cuts daily cost to ~$14.80/day (a 99.2% cost reduction).
