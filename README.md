# Rules vs LLMs - Fire AI take-home
`pip install -r requirements.txt && python run_all.py` regenerates every number in RESULTS_A.md, RESULTS_B.md, DECISION_MATRIX.md.
Add `GEMINI_API_KEY` (free tier) to also measure the LLM variants. Project A: `project_a/` (engines `tax_a_rules.py`, `tax_b_llm.py`, `tax_c_compiled.py`, parser `parser.py`, tests `tests/`). Project B: `project_b/`.

## Before you submit - things only you can do
1. Run the 30 cases in `project_a/tests/official_calculator_checks.csv` through the official Income Tax Dept calculator, fill the two `official_*` columns, run `python -m project_a.tests.verify_official`. Verify the rule text against official sources (Finance Act 2024/2025) - I encoded from memory.
2. `export GEMINI_API_KEY=...; python run_all.py` to fill the NOT RUN cells ((b) engine, LLM parser, LLM review). Optionally `python -m project_a.compile_rules --fy 2025-26` and review the diff.
3. `python -m project_b.fetch_311` then `RUN_CSV=project_b/data/nyc311_2023.csv python run_all.py` for real-data findings (Task 1) - current B numbers are SYNTHETIC.
4. Time yourself applying the FY2025-26 change to each implementation and fill the log in RESULTS_A.md (report.py will overwrite - copy it into a separate section/file).
5. Edit AI_USAGE.md. Read every file: you must change any line live in the interview.
