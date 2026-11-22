# DECISION_MATRIX (generated)

Trade-offs stated honestly: rules = auditable, deterministic, cheap, but need maintenance on every change; statistics = adapt to data but give weak explanations and false alarms; LLM = flexible on language but costly, slower, non-deterministic and (per this repo) unmeasured here without an API key.

| Component / check | Type | Measurement that justifies it |
|---|---|---|
| B p01 Renamed or dropped column | rule | rules: detect 100.0%, row recall n/a, batch FA 0.0%, 119,351,112 rows/s; alternative stats: detect 100.0%, recall n/a, batch FA 0.0% (synthetic data) |
| B p02 Column type change (numbers as strings) | rule | rules: detect 100.0%, row recall 100.0%, batch FA 0.0%, 2,783,925 rows/s; alternative stats: detect 100.0%, recall 100.0%, batch FA 0.0% (synthetic data) |
| B p03 Date format switch partway | rule | rules: detect 100.0%, row recall 100.0%, batch FA 0.0%, 1,350,678 rows/s; alternative stats: detect 100.0%, recall 100.0%, batch FA 0.0% (synthetic data) |
| B p04 Latitude/longitude swapped | rule | rules: detect 100.0%, row recall 100.0%, batch FA 0.0%, 7,717,766 rows/s; alternative stats: detect 100.0%, recall 100.0%, batch FA 0.0% (synthetic data) |
| B p05 Exact duplicates | rule | rules: detect 100.0%, row recall 100.0%, batch FA 0.0%, 317,395 rows/s; alternative stats: detect 100.0%, recall 100.0%, batch FA 0.0% (synthetic data) |
| B p06 Near-duplicates | statistical + LLM confirm on flagged rows (semantic residue) | stats: detect 100.0%, row recall 95.4%, batch FA 70.0%, 170,538 rows/s; alternative rules: detect 100.0%, recall 95.4%, batch FA 100.0% (synthetic data) |
| B p07 Null spike in one agency | rule | rules: detect 100.0%, row recall 100.0%, batch FA 0.0%, 1,268,748 rows/s; alternative stats: detect 100.0%, recall 100.0%, batch FA 0.0% (synthetic data) |
| B p08 Closed date before created date | rule | rules: detect 100.0%, row recall 100.0%, batch FA 0.0%, 318,278 rows/s; alternative stats: detect 100.0%, recall 100.0%, batch FA 0.0% (synthetic data) |
| B p09 ZIP inconsistent with borough | rule | rules: detect 100.0%, row recall 100.0%, batch FA 0.0%, 1,841,805 rows/s; alternative stats: detect 100.0%, recall 100.0%, batch FA 0.0% (synthetic data) |
| B p10 Complaint Type inconsistent with Descriptor | rule | rules: detect 100.0%, row recall 100.0%, batch FA 0.0%, 2,457,255 rows/s; alternative stats: detect 100.0%, recall 100.0%, batch FA 0.0% (synthetic data) |
| B p11 Resolution Description contradicts Status | rule | rules: detect 100.0%, row recall 100.0%, batch FA 0.0%, 137,420 rows/s; alternative stats: detect 100.0%, recall 100.0%, batch FA 0.0% (synthetic data) |
| B p12 Personal data in free text | rule + LLM confirm on flagged rows (semantic residue) | rules: detect 100.0%, row recall 83.3%, batch FA 0.0%, 83,124 rows/s; alternative stats: detect 100.0%, recall 2.4%, batch FA 0.0% (synthetic data) |
| B LLM batch sample (unknown unknowns) | LLM | projected $0.36/M rows vs $39/M for every row; detection NOT MEASURED (no key) |
| A tax arithmetic | rule | (a) 100.0% and (c) 100.0% exact on 319 cases, deterministic, $0.0/1k req, 100% clause trace; (b) LLM: NOT RUN - treat as unproven until `python -m project_a.bench` is run with a key |
| A rule authoring per Budget | hybrid (LLM drafts, human reviews, suite gates) | mutation table: partial updates give 13-86 silently wrong cases of 159, caught only by the suite |
| A free-text extraction | hybrid (LLM or regex extracts; code decides) | regex extractor 50/50 status correct (dev set, tuned); LLM extractor NOT RUN |
| A clarify-vs-compute decision | rule | 0 'ready' answers on incomplete/contradictory descriptions in the 50-case set (dev set) |
| A regime recommendation | rule | pure function of two audited results |
| A explanation prose | LLM (optional) | presentation only; numbers injected from rule output |
