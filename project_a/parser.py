"""Task 3: plain-language -> TaxInput, asking instead of guessing.

Two interchangeable EXTRACTORS (rule-based regex, Gemini) produce the same `Extracted` dict.
One deterministic DECIDER (`decide`) turns it into: ready | needs_clarification | conflict.
The LLM may extract; it never decides whether information is sufficient.
"""
import json
import re

METRO = r"\b(delhi|new delhi|mumbai|bombay|kolkata|calcutta|chennai|madras)\b"
NONMETRO = (r"\b(non[- ]?metro|tier[- ]?2|tier[- ]?3|small town|bangalore|bengaluru|hyderabad|pune|ahmedabad|jaipur|"
            r"lucknow|noida|gurgaon|gurugram|chandigarh|kochi|indore|nagpur|bhopal|patna|surat|coimbatore|vizag|"
            r"visakhapatnam|thane|nashik|ranchi|dehradun|bhubaneswar|mysore|mysuru)\b")
KW = {
    "gross": r"\b(salary|sallary|salry|ctc|package|income|earn\w*|make[s]?|making|kamat\w*|tankh?w?ah|pension|gross|lpa)\b",
    "basic": r"\bbasic\b",
    "hra": r"\bhra\b",
    "rent": r"\brent\b|\bkiraya\w*|\bkiraye\b",
    "c80": r"\bsec80c\b|\bppf\b|\belss\b|\blic\b|\bepf\b|\bnsc\b|tax saver",
    "nps": r"\bsec80ccd\b|\bnps\b",
    "d80": r"\bsec80d\b|mediclaim|health insurance|medical insurance|health premium",
    "loan": r"home ?loan|housing loan|house loan|ghar ka loan|loan interest|\bloan\b",
}
PARENT = r"\b(parents?|mother|father|maa|papa|mummy|in-laws?)\b"
TAKEHOME = r"take[- ]?home|in[- ]?hand|post[- ]?tax|after[- ]?tax|\bnet salary"
NONE_ABS = (r"\bno (tax[- ]saving )?(deductions?|investments?|exemptions?)\b(?! but)|none of the deductions|"
            r"no deductions apply|no tax[- ]saving|\bno deductions\b|\bno investments\b|kuch investment nahi")
NONE_RESID = (r"nothing else|no other|koi (aur |other )?(deduction|investment)( nahi| nahin)|aur (kuch|koi)[a-z ]* (nahi|nahin)|"
              r"kuch (aur )?(nahi|nahin)|koi aur [a-z ]*nahi|baaki (kuch )?nahi")
NORENT = r"\bno rent\b|kiraya nahi|rent nahi|don'?t pay (any )?rent|not paying rent|own house|rent[- ]?free|rent\?\s*no"


def _num(s, unit):
    v = float(s.replace(",", ""))
    u = (unit or "").lower()
    mult = {"crore": 1e7, "cr": 1e7, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "lpa": 1e5, "l": 1e5,
            "k": 1e3, "thousand": 1e3, "": 1}[u]
    return int(round(v * mult)), u


AMT = re.compile(r"(?:₹|rs\.?|inr)?\s*(\d[\d,]*(?:\.\d+)?)\s*(crore|cr|lakhs?|lacs?|lpa|l|k|thousand)?(?![a-z0-9])", re.I)


def _clean(t: str) -> str:
    t = t.lower()
    t = re.sub(r"\b(?:fy|ay)?\s*['’]?20\d\d\s*[-–/]\s*\d{2,4}\b", " ", t)           # FY 2025-26
    t = re.sub(r"\b(?:fy|ay)\s*\d{2}\s*[-–/]\s*\d{2}\b", " ", t)                       # FY 24-25
    t = re.sub(r"\bfy\s*20\d\d\b", " ", t)
    t = re.sub(r"80\s*ccd\s*(?:\(1b\))?", "sec80ccd", t)
    t = re.sub(r"\b80\s*c\b", "sec80c", t)
    t = re.sub(r"\b80\s*d\b", "sec80d", t)
    t = t.replace("house rent allowance", "hra").replace("₹", "rs ")
    t = re.sub(r"\brs\.\s*", "rs ", t)
    return t


def _fy(t: str):
    m = re.search(r"(?:fy|ay)?\s*['’]?(20\d\d)\s*[-–/]\s*(\d{2,4})", t.lower())
    if m:
        a, b = int(m.group(1)), int(m.group(2)[-2:])
        fy = f"{a}-{b:02d}"
        return fy if not re.search(r"\bay\b", t.lower()[max(0, m.start() - 3):m.start() + 3]) else f"{a - 1}-{a % 100:02d}"
    m = re.search(r"\b(?:fy|ay)\s*(\d{2})\s*[-–/]\s*(\d{2})\b", t.lower())
    if m:
        return f"20{m.group(1)}-{m.group(2)}"
    m = re.search(r"\bfy\s*(20\d\d)\b", t.lower())
    return None if not m else f"{int(m.group(1)) - 1}-{int(m.group(1)) % 100:02d}"


def _period(clause: str):
    if re.search(r"per month|/ ?month|monthly|\bpm\b|p\.m|a month|mahin[ae]|\bmonth\b|/mo\b", clause):
        return "m"
    if re.search(r"per annum|per year|yearly|annual|p\.a|a year|/ ?year|\bsaal\b|\blpa\b|\bpa\b|per yr|\byear\b", clause):
        return "a"
    return None


def extract_rules(text: str) -> dict:
    t = _clean(text)
    ex = {"age": None, "ages_seen": [], "gross": [], "basic": [], "hra": [], "rent": [], "sec_80c": None,
          "sec_80ccd1b": None, "sec_80d_self": None, "sec_80d_parents": None, "parents_senior": None,
          "home_loan_interest": None, "city": None, "fy": _fy(text), "none_declared": False, "none_abs": False,
          "senior_claimed": bool(re.search(r"senior citizen|super senior|retired", t)) and "parents" not in t.split("senior")[0][-25:],
          "takehome": bool(re.search(TAKEHOME, t)), "norent": bool(re.search(NORENT, t)), "mentioned": set(),
          "ambiguous": set(), "contradictions": [], "basic_pct": None}
    # ---- age (user's own; blank spans so they are not read as amounts)
    def take_age(m):
        pre = t[max(0, m.start() - 30):m.start()]
        if re.search(PARENT, pre):
            return m.group(0)
        ex["ages_seen"].append(int(m.group(1)))
        return " "
    t2 = re.sub(r"(?:\bi am|\bi'?m|\bim\b|\bmain\b|\bmeri (?:age|umar)|\bage(?:d)?|\bumar)\s*[:=\-]?\s*(\d{2,3})\b(?!\s*(?:k|l|lakh|%))",
                take_age, t)
    t2 = re.sub(r"\b(\d{2,3})\s*(?:years?[- ]old|years|yrs?|saal|sal ka|yo|y/o)\b", take_age, t2)
    if ex["ages_seen"]:
        ex["age"] = ex["ages_seen"][0]
    pm = re.search(PARENT + r"[^.;\n]*?\b(?:are|is|age[d]?)?\s*\b(\d{2})\b(?!\s*(?:k|l|lakh|,))", t2)
    if pm and 40 <= int(pm.group(2)) <= 110:
        ex["parents_senior"] = int(pm.group(2)) >= 60
    elif re.search(PARENT + r"[^.;\n]*senior", t2):
        ex["parents_senior"] = True
    # ---- city
    if re.search(r"non[- ]?metro|tier[- ]?[23]", t2) and re.search(METRO, t2):
        ex["contradictions"].append("city is described as both a metro and non-metro")
    if re.search(r"non[- ]?metro|tier[- ]?[23]", t2):
        ex["city"] = "nonmetro"
    elif re.search(METRO, t2) or re.search(r"\bmetro\b", t2):
        ex["city"] = "metro"
    elif re.search(NONMETRO, t2):
        ex["city"] = "nonmetro"
    # ---- clauses
    clauses = [c.strip() for c in re.split(r"\.(?=\s|$)|[;\n]|,(?!\d)| and | aur | but | also | & ", t2) if c.strip()]
    prev_kw = None
    for c in clauses:
        if re.match(r"(which is|i\.?e\.?|that is|matlab|yaani|self\b|myself\b)", c) and prev_kw:
            c = prev_kw + " " + c
        hits = [(m.start(), k) for k, rx in KW.items() for m in re.finditer(rx, c)]
        amts = [(m.start(), m.end(), m.group(1), m.group(2)) for m in AMT.finditer(c)]
        amts = [a for a in amts if not (a[3] is None and float(a[2].replace(",", "")) < 100 and "%" in c[a[1]:a[1] + 2])]
        hits.sort()
        if not hits:
            continue
        prev_kw = re.search(KW[hits[0][1]], c).group(0)
        per = _period(c)
        pct = re.search(r"(\d{1,3})\s*%", c)
        for _, k in hits:
            ex["mentioned"].add("d80p" if (k == "d80" and re.search(PARENT, c)) else k)
        if "basic" in c and pct and any(k == "basic" for _, k in hits):
            ex["basic_pct"] = int(pct.group(1))
            continue
        used = set()
        for pos, k in sorted(hits):
            m_kw = re.compile(KW[k]).search(c, pos)
            kw_end = m_kw.end() if m_kw else pos
            negated = bool(re.search(r"\b(no|zero|nil|without|nahi|nahin)\s+(\w+\s+){0,2}$", c[:pos])) or \
                bool(re.match(r"\s*(\w+\s+){0,2}(nahi|nahin)\b", c[kw_end:]))
            if negated and k != "gross":
                if k == "rent":
                    ex["norent"] = True
                else:
                    f = {"c80": "sec_80c", "nps": "sec_80ccd1b", "loan": "home_loan_interest",
                         "d80": "sec_80d_parents" if re.search(PARENT, c) else "sec_80d_self"}.get(k)
                    if f:
                        ex[f] = ex[f] or 0
                continue
            # nearest unused amount: prefer following within 40 chars, else preceding within 30
            cand = [a for a in amts if a[0] >= pos and a[0] - pos <= 40 and a[0] not in used] or \
                   [a for a in amts if a[1] <= pos and pos - a[1] <= 30 and a[0] not in used]
            full = re.search(r"\b(full|maxed|max(?:ed)? out|poora)\b", c)
            if not cand:
                if k == "c80" and full:
                    ex["sec_80c"] = (ex["sec_80c"] or 0) + 150000
                elif k == "nps" and full:
                    ex["sec_80ccd1b"] = (ex["sec_80ccd1b"] or 0) + 50000
                continue
            a = cand[0]
            used.add(a[0])
            val, unit = _num(a[2], a[3])
            known_unit = unit in ("lakh", "lakhs", "lac", "lacs", "lpa", "l", "crore", "cr")
            if per == "m":
                val *= 12
            if k == "gross" and not re.search(TAKEHOME, c):
                ex["gross"].append((val, per or ("a" if known_unit else None), val))
            elif k == "gross":
                ex["takehome"] = True
            elif k in ("basic", "hra", "rent"):
                ex[k].append((val, per or ("a" if known_unit else None), val))
            elif k == "c80":
                ex["sec_80c"] = (ex["sec_80c"] or 0) + val
            elif k == "nps":
                ex["sec_80ccd1b"] = (ex["sec_80ccd1b"] or 0) + val
            elif k == "d80":
                f = "sec_80d_parents" if re.search(PARENT, c) else "sec_80d_self"
                ex[f] = (ex[f] or 0) + val
            elif k == "loan":
                ex["home_loan_interest"] = (ex["home_loan_interest"] or 0) + val
    ex["parents_mentioned_health"] = "d80p" in ex["mentioned"]
    ex["none_abs"] = bool(re.search(NONE_ABS, t2))
    ex["none_declared"] = ex["none_abs"] or bool(re.search(NONE_RESID, t2))
    return ex


def decide(ex: dict, default_fy: str = "2025-26") -> dict:
    inputs, missing, conflicts, assumptions, warnings = {}, [], [], [], []
    conflicts += ex.get("contradictions", [])
    ages = set(ex.get("ages_seen", []))
    if len(ages) > 1:
        conflicts.append(f"two different ages given: {sorted(ages)}")
    age = ex.get("age")
    if age is not None and not (18 <= age <= 110):
        conflicts.append(f"age {age} is outside the supported range 18-110")
    if age is not None and age < 60 and ex.get("senior_claimed"):
        conflicts.append(f"described as a senior citizen but age is {age}")
    if age is None:
        missing.append("age")
    else:
        inputs["age"] = age

    def annual(cands, name):
        ok = []
        for val, per, _ in cands:
            if per is None and val < 200000:
                ex.setdefault("ambiguous", set()).add(name)
            else:
                ok.append(val)
        return ok
    g = annual(ex.get("gross", []), "salary_period")
    if g and (max(g) - min(g)) > 0.02 * max(g):
        conflicts.append(f"different salary figures given: {sorted(set(g))}")
    if g:
        inputs["gross_salary"] = g[0]
    elif "salary_period" in ex["ambiguous"]:
        missing.append("salary_period")
    elif ex.get("takehome"):
        missing.append("gross_salary")
        warnings.append("take-home pay is not taxable salary; need gross salary")
    else:
        missing.append("gross_salary")
    rent = annual(ex.get("rent", []), "rent_period")
    hra = annual(ex.get("hra", []), "hra_period")
    basic = annual(ex.get("basic", []), "basic_period")
    if ex.get("norent") and rent and max(rent) > 0:
        conflicts.append("says no rent is paid but also gives a rent amount")
    if ex.get("none_abs") and any(ex.get(k) for k in ("sec_80c", "sec_80ccd1b", "sec_80d_self", "sec_80d_parents", "home_loan_interest")):
        conflicts.append("says there are no deductions but also gives deduction amounts")
    for nm in ("rent_period", "hra_period", "basic_period"):
        if nm in ex["ambiguous"]:
            missing.append(nm)
    if ex.get("basic_pct") and "gross_salary" in inputs and not basic:
        basic = [inputs["gross_salary"] * ex["basic_pct"] // 100]
    if basic:
        inputs["basic_salary"] = basic[0]
    if hra:
        inputs["hra_received"] = hra[0]
    if rent:
        inputs["rent_paid"] = rent[0]
    if "gross_salary" in inputs and inputs.get("basic_salary", 0) > inputs["gross_salary"]:
        conflicts.append("basic salary is higher than gross salary")
    if ("gross_salary" in inputs and inputs.get("basic_salary", 0) + inputs.get("hra_received", 0) > inputs["gross_salary"]
            and inputs.get("basic_salary", 0) <= inputs["gross_salary"]):
        conflicts.append("basic + HRA is higher than gross salary")
    mentioned = ex["mentioned"]
    rent_involved = (inputs.get("rent_paid", 0) > 0) or (inputs.get("hra_received", 0) > 0) or "rent" in mentioned or "hra" in mentioned
    if ex.get("norent"):
        inputs["rent_paid"] = 0
        rent_involved = False
        mentioned = mentioned | {"rent"}
    if rent_involved and not ex.get("norent"):
        if "rent" in mentioned and "rent_paid" not in inputs and "rent_period" not in missing:
            missing.append("rent_paid")
        if "rent_paid" not in inputs and "hra" in mentioned and "rent_paid" not in missing and "rent_period" not in missing:
            missing.append("rent_paid")
        if "hra_received" not in inputs and "hra_period" not in missing:
            missing.append("hra_received")
        if "basic_salary" not in inputs and "basic_period" not in missing:
            missing.append("basic_salary")
        if ex.get("city") is None:
            missing.append("city")
    if ex.get("city"):
        inputs["metro"] = ex["city"] == "metro"
    # deductions
    for key, kw in (("sec_80c", "c80"), ("sec_80ccd1b", "nps"), ("sec_80d_self", "d80"), ("home_loan_interest", "loan")):
        if ex.get(key) is not None:
            inputs[key] = ex[key]
        elif kw in mentioned:
            missing.append(key + "_amount" if key != "sec_80d_self" else "sec_80d_self")
    if ex.get("sec_80d_parents") is not None:
        inputs["sec_80d_parents"] = ex["sec_80d_parents"]
    elif ex.get("parents_mentioned_health"):
        missing.append("sec_80d_parents")
    if ex.get("sec_80d_parents") is not None or ex.get("parents_mentioned_health"):
        if ex.get("parents_senior") is None:
            missing.append("parents_senior")
        else:
            inputs["parents_senior"] = ex["parents_senior"]
    any_deduction_info = bool(mentioned & {"c80", "nps", "d80", "d80p", "loan", "rent", "hra"}) or any(ex.get(k) is not None for k in ("sec_80c", "sec_80ccd1b", "sec_80d_self", "sec_80d_parents", "home_loan_interest")) or ex.get("none_declared") or ex.get("norent")
    if not any_deduction_info:
        missing.append("deductions")
    elif not ex.get("none_declared"):
        zeros = [f for f in ("sec_80c", "sec_80ccd1b", "sec_80d_self", "sec_80d_parents", "home_loan_interest")
                 if f not in inputs and (f + "_amount") not in missing and f not in missing]
        if zeros:
            assumptions.append("treated as 0 because not mentioned: " + ", ".join(zeros))
    if "sec_80c" in inputs and inputs["sec_80c"] > 150000:
        warnings.append("80C above Rs 1,50,000 will be capped")
    if ex.get("fy"):
        inputs["fy"] = ex["fy"]
    else:
        inputs["fy"] = default_fy
        assumptions.append(f"financial year not stated; using default FY {default_fy}")
    if re.search(r"ctc|package|lpa", " ".join(map(str, ex.get("mentioned", [])))):
        pass
    if conflicts:
        status = "conflict"
    elif missing:
        status = "needs_clarification"
    else:
        status = "ready"
    full = {"age": 30, "gross_salary": 0, "basic_salary": None, "hra_received": 0, "rent_paid": 0, "metro": False,
            "sec_80c": 0, "sec_80ccd1b": 0, "sec_80d_self": 0, "sec_80d_parents": 0, "parents_senior": False,
            "home_loan_interest": 0}
    return {"status": status, "inputs": inputs if status != "ready" else {**full, **inputs}, "missing": sorted(set(missing)),
            "conflicts": conflicts, "assumptions": assumptions, "warnings": warnings,
            "questions": [QUESTIONS[m] for m in sorted(set(missing))] + [f"Please clarify: {c}." for c in conflicts]}


QUESTIONS = {
    "age": "What is your age (needed for old-regime slabs and the 80D limit)?",
    "gross_salary": "What is your annual gross salary (before tax; not take-home)?",
    "salary_period": "Is that salary figure per month or per year?",
    "rent_period": "Is the rent per month or per year?", "hra_period": "Is the HRA per month or per year?",
    "basic_period": "Is the basic salary per month or per year?",
    "deductions": "Do you have any rent/HRA, 80C investments, NPS, health insurance (80D) or home-loan interest? Say 'none' if not.",
    "basic_salary": "What is your annual basic salary (including DA)?",
    "hra_received": "How much HRA do you receive annually (0 if none)?",
    "rent_paid": "How much rent do you pay annually?",
    "city": "Which city do you live in (Delhi/Mumbai/Kolkata/Chennai count as metro for HRA)?",
    "sec_80c_amount": "How much did you invest under 80C (PPF/ELSS/LIC/EPF etc.) this year?",
    "sec_80ccd1b_amount": "How much did you put in NPS (80CCD(1B))?",
    "sec_80d_self": "What health-insurance premium do you pay for yourself/family?",
    "home_loan_interest_amount": "How much home-loan interest did you pay this year?",
    "sec_80d_parents": "What health-insurance premium do you pay for your parents?",
    "parents_senior": "Are your parents 60 or older?",
}


EXTRACT_PROMPT = """Extract tax facts from the user's message. Do NOT guess: use null when not stated.
Return JSON: {{"age": int|null, "gross": [{{"amount_rupees": int, "period": "m"|"a"|null}}],
"basic": [same], "hra": [same], "rent": [same], "sec_80c": int|null, "sec_80ccd1b": int|null,
"sec_80d_self": int|null, "sec_80d_parents": int|null, "parents_senior": bool|null, "home_loan_interest": int|null,
"city": "metro"|"nonmetro"|null, "fy": "2024-25"|"2025-26"|null, "none_declared": bool, "norent": bool,
"senior_claimed": bool, "takehome": bool, "mentioned": [subset of "c80","nps","d80","loan","rent","hra","basic"],
"contradictions": [str]}}
amount_rupees is the figure as stated (period "m" = monthly, "a" = annual, null = not stated). 1 lakh = 100000.
"metro" only for Delhi/Mumbai/Kolkata/Chennai. Message: {text}"""


def extract_llm(text: str, client) -> dict:
    res = client.generate(EXTRACT_PROMPT.format(text=json.dumps(text)), json_mode=True)
    d = json.loads(re.sub(r"^```(?:json)?|```$", "", res.text.strip(), flags=re.M))
    ex = extract_rules("")
    for k in ("age", "sec_80c", "sec_80ccd1b", "sec_80d_self", "sec_80d_parents", "parents_senior", "home_loan_interest",
              "city", "fy", "none_declared", "norent", "senior_claimed", "takehome", "contradictions"):
        if k in d and d[k] is not None:
            ex[k] = d[k]
    if ex["age"] is not None:
        ex["ages_seen"] = [ex["age"]]
    for k in ("gross", "basic", "hra", "rent"):
        for item in d.get(k) or []:
            v, p = int(item["amount_rupees"]), item.get("period")
            ex[k].append((v * 12 if p == "m" else v, p, v))
    ex["mentioned"] = set(d.get("mentioned") or [])
    if ex["gross"]:
        ex["mentioned"].add("gross")
    ex["parents_mentioned_health"] = ex["sec_80d_parents"] is not None or (d.get("parents_health_mentioned") is True)
    return ex


def parse(text: str, client=None, default_fy: str = "2025-26") -> dict:
    ex = extract_llm(text, client) if client is not None else extract_rules(text)
    return decide(ex, default_fy)
