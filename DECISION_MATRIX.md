# DECISION_MATRIX (generated)

Trade-offs stated honestly: rules = auditable, deterministic, cheap, but need maintenance on every change; statistics = adapt to data but give weak explanations and false alarms; LLM = flexible on language but costly, slower, non-deterministic and (per this repo) unmeasured here without an API key.

| Component / check | Type | Measurement that justifies it |
|---|---|---|
| B p01 Renamed or dropped column | rule | rules: detect 100.0%, row recall n/a, batch FA 0.0%, 176,242,515 rows/s; alternative stats: detect 100.0%, recall n/a, batch FA 0.0% (real NYC 311 2023 data) |
| B p02 Column type change (numbers as strings) | rule | rules: detect 100.0%, row recall 100.0%, batch FA 0.0%, 1,531,150 rows/s; alternative stats: detect 100.0%, recall 100.0%, batch FA 0.0% (real NYC 311 2023 data) |
| B p03 Date format switch partway | rule | rules: detect 100.0%, row recall 100.0%, batch FA 0.0%, 722,057 rows/s; alternative stats: detect 100.0%, recall 100.0%, batch FA 0.0% (real NYC 311 2023 data) |
| B p04 Latitude/longitude swapped | rule | rules: detect 100.0%, row recall 100.0%, batch FA 0.0%, 6,269,671 rows/s; alternative stats: detect 100.0%, recall 100.0%, batch FA 0.0% (real NYC 311 2023 data) |
| B p05 Exact duplicates | rule | rules: detect 100.0%, row recall 100.0%, batch FA 0.0%, 200,224 rows/s; alternative stats: detect 100.0%, recall 100.0%, batch FA 0.0% (real NYC 311 2023 data) |
| B p06 Near-duplicates | statistical + LLM confirm on flagged rows (semantic residue) | stats: detect 100.0%, row recall 41.2%, batch FA 100.0%, 136,400 rows/s; alternative rules: detect 100.0%, recall 96.8%, batch FA 100.0% (real NYC 311 2023 data) |
| B p07 Null spike in one agency | statistical | stats: detect 100.0%, row recall 100.0%, batch FA 10.0%, 651,352 rows/s; alternative rules: detect 100.0%, recall 100.0%, batch FA 100.0% (real NYC 311 2023 data) |
| B p08 Closed date before created date | rule | rules: detect 100.0%, row recall 100.0%, batch FA 50.0%, 171,079 rows/s; alternative stats: detect 10.0%, recall 0.0%, batch FA 10.0% (real NYC 311 2023 data) |
| B p09 ZIP inconsistent with borough | rule | rules: detect 100.0%, row recall 100.0%, batch FA 90.0%, 1,474,961 rows/s; alternative stats: detect 100.0%, recall 100.0%, batch FA 100.0% (real NYC 311 2023 data) |
| B p10 Complaint Type inconsistent with Descriptor | statistical | stats: detect 100.0%, row recall 99.7%, batch FA 100.0%, 1,190,096 rows/s; alternative rules: detect 100.0%, recall 100.0%, batch FA 100.0% (real NYC 311 2023 data) |
| B p11 Resolution Description contradicts Status | rule | rules: detect 100.0%, row recall 100.0%, batch FA 50.0%, 35,650 rows/s; alternative stats: detect 100.0%, recall 0.8%, batch FA 100.0% (real NYC 311 2023 data) |
| B p12 Personal data in free text | rule + LLM confirm on flagged rows (semantic residue) | rules: detect 100.0%, row recall 83.9%, batch FA 100.0%, 35,431 rows/s; alternative stats: detect 100.0%, recall 1.4%, batch FA 30.0% (real NYC 311 2023 data) |
| B LLM batch sample (unknown unknowns) | LLM | projected $0.40/M rows vs $45/M for every row; detection NOT MEASURED (no key) |
| A tax arithmetic | rule | (a) 100.0% and (c) 100.0% exact on 319 cases, deterministic, $0.0/1k req, 100% clause trace; (b) LLM: NOT RUN - treat as unproven until `python -m project_a.bench` is run with a key |
| A rule authoring per Budget | hybrid (LLM drafts, human reviews, suite gates) | mutation table: partial updates give 13-86 silently wrong cases of 159, caught only by the suite |
| A free-text extraction | hybrid (LLM or regex extracts; code decides) | regex extractor 50/50 status correct (dev set, tuned); LLM extractor NOT RUN |
| A clarify-vs-compute decision | rule | 0 'ready' answers on incomplete/contradictory descriptions in the 50-case set (dev set) |
| A regime recommendation | rule | pure function of two audited results |
| A explanation prose | LLM (optional) | presentation only; numbers injected from rule output |
