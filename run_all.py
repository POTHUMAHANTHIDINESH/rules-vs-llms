"""Single command: regenerates cases, runs tests, benchmarks, experiments, and writes RESULTS_*.md + DECISION_MATRIX.md.
Optional: export GEMINI_API_KEY to also measure implementation (b), the LLM parser and LLM review (free tier: slow, ~10 RPM).
Optional real data: python -m project_b.fetch_311 first, then RUN_CSV=project_b/data/nyc311_2023.csv python run_all.py"""
import os, subprocess, sys
py = sys.executable
llm = ["--llm"] if os.environ.get("GEMINI_API_KEY") else []
default_csv = "project_b/data/nyc311_2023.csv" if os.path.exists("project_b/data/nyc311_2023.csv") else None
csv_path = os.environ.get("RUN_CSV", default_csv)
csv = ["--csv", csv_path] if csv_path else []
steps = [[py, "-m", "project_a.tests.gen_cases"], [py, "-m", "project_a.tests.verify_official"],
         [py, "-m", "project_a.tests.gen_descriptions"], [py, "-m", "pytest", "-q"],
         [py, "-m", "project_a.tests.heldout"], [py, "-m", "project_a.bench"],
         [py, "-m", "project_a.task5"], [py, "-m", "project_b.profile_raw"] + csv,
         [py, "-m", "project_b.evaluate"] + csv + llm, [py, "-m", "project_b.scale"], [py, "report.py"]]
for s in steps:
    print(">>", " ".join(s), flush=True)
    subprocess.run(s, check=True)
