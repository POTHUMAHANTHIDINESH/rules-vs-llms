"""After filling official_old_tax / official_new_tax in official_calculator_checks.csv from the Income Tax Dept
calculator, run: python -m project_a.tests.verify_official"""
import csv, os
HERE = os.path.dirname(__file__)
ok = bad = todo = 0
for r in csv.DictReader(open(os.path.join(HERE, "official_calculator_checks.csv"))):
    if not r["official_old_tax"] or not r["official_new_tax"]:
        todo += 1; continue
    good = int(float(r["official_old_tax"])) == int(r["our_old_tax"]) and int(float(r["official_new_tax"])) == int(r["our_new_tax"])
    ok += good; bad += not good
    if not good:
        print("MISMATCH", r["case_id"], "ours", r["our_old_tax"], r["our_new_tax"], "official", r["official_old_tax"], r["official_new_tax"])
print(f"verified={ok} mismatched={bad} not_yet_filled={todo}")
