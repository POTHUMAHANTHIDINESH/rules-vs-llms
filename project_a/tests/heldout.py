"""20 held-out descriptions written AFTER the parser was tuned (never used for tuning)."""
from project_a.parser import parse
R, N, C = "ready", "needs_clarification", "conflict"
H = [
 ("I'm 33 and earn 14 lakh a year. No investments, no rent. FY 2025-26", R, dict(age=33, gross_salary=1400000)),
 ("Bhai 27 saal ka hoon, salary 9 lakh, koi deduction nahi", R, dict(age=27, gross_salary=900000)),
 ("age 45, gross 30L, 80C 1.5L, NPS 50k, no other deductions", R, dict(age=45, gross_salary=3000000, sec_80c=150000, sec_80ccd1b=50000)),
 ("Salary 60,000 per month, I am 31, nothing else", R, dict(age=31, gross_salary=720000)),
 ("I am 62, pension 11 lakh annually, mediclaim 45k, no other deductions", R, dict(age=62, gross_salary=1100000, sec_80d_self=45000)),
 ("I make 16 lakh", N, {}),
 ("age 29, salary 12 lakh", N, {}),
 ("mera salary 10 lakh hai", N, {}),
 ("Salary 25 lakh, age 40, I pay rent in Delhi", N, {}),
 ("take home 70000 monthly, age 30", N, {}),
 ("I have PPF and NPS investments, salary 18 lakh, age 35", N, {}),
 ("Salary 100000", N, {}),
 ("I am 25 and a senior citizen, salary 8 lakh, no deductions", C, {}),
 ("Salary 6 lakh yearly i.e. 1 lakh per month, age 28, no deductions", C, {}),
 ("No rent paid, but rent is 30k per month, salary 15 lakh, age 34", C, {}),
 ("Age 30, age 50, salary 10 lakh, nothing else", C, {}),
 ("basic 15 lakh, gross 10 lakh, age 38, no deductions", C, {}),
 ("I'm 15 years old, salary 4 lakh, no deductions", C, {}),
 ("no deductions at all but 80C 1 lakh, salary 9 lakh, age 30", C, {}),
 ("Mumbai is non-metro, rent 2L yearly, basic 5L, HRA 2L, salary 10L, age 30", C, {}),
]
ok = inp_ok = silent = 0
for t, st, exp in H:
    o = parse(t)
    good = o["status"] == st
    ok += good
    inp_ok += all(o["inputs"].get(k) == v for k, v in exp.items())
    silent += st != R and o["status"] == R
    if not good or not all(o["inputs"].get(k) == v for k, v in exp.items()):
        print("FAIL", t, "->", o["status"], o["missing"], o["conflicts"], {k: o["inputs"].get(k) for k in exp})
print(f"held-out: status {ok}/{len(H)}, inputs exact on ready {inp_ok}/{len(H)}, silent 'ready' on should-ask {silent}")
