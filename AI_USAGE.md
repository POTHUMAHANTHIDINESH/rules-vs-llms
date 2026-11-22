# AI_USAGE

**Author:** Pothumahanthi Dinesh  
**Repository:** Rules vs LLMs Take-Home Assignment (Fire AI)

## Tools and Methodology
- **Anthropic Claude:** Used for initial architectural scaffolding, test case generation, drafting deterministic rule logic, and developing the 12 corruption injection routines for Project B.
- **Google Gemini 2.5 Flash:** Used for runtime LLM implementations (implementation (b) query-time tax calculation, LLM compiler for rule DSL generation, and natural language extraction experiments).
- **Independent Verification & Review Workflow:**
  - I cross-checked and audited every tax provision against the official statutory texts of the **Finance (No. 2) Act 2024** and **Finance Act 2025**.
  - Generated and validated 319 comprehensive test cases, asserting 10 hand-computed golden baselines against the oracle.
  - Exported and verified 30 distinct edge and fuzz test cases against the **Income Tax Department's official tax portal**, ensuring 0 rupee mismatches (`verified=30, mismatched=0`).
  - Authored a 20-description held-out evaluation set (`tests/heldout.py`) covering complex Hinglish, contradictory numbers, and missing salary components to test parser robustness without overfitting.

## Where the AI was Wrong and How It Was Caught (Real Incidents)

1. **Timestamp Unit Discrepancy (Project B):**
   - *Bug:* The initial near-duplicate detector divided pandas timestamps by $10^9$ assuming nanosecond representation. In pandas 2.2+, timestamps were stored in microseconds, skewing calculated durations by a factor of 1,000.
   - *Symptom:* The rules detector falsely flagged almost every clean batch; the learned repeat-gap median was 12 seconds instead of the expected 5 minutes to 3 days.
   - *Resolution:* Caught by sanity-checking the learned distribution against the dataset generator; fixed explicitly using `.dt.as_unit("s")`.

2. **IsolationForest Score Thresholding on Swapped Coordinates (Project B):**
   - *Bug:* An IsolationForest model initially configured for latitude/longitude swap anomaly detection yielded 0% recall on swaps. The baseline-quantile threshold fell within the swapped points' anomaly score range (score `-0.686` vs threshold `-0.707`).
   - *Symptom:* Injector introduced swapped coordinate pairs, but the model completely missed them.
   - *Resolution:* Identified via the per-problem recall metrics table; replaced with a robust z-score bounding box detector calibrated against NYC geographic extremes.

3. **Parser Tokenization & Clause ID Matching (Project A):**
   - *Bug:* Clause-id validation regex failed on lowercase characters (e.g., rejecting Section 16(ia) as `S16ia`), and the plain-language number extractor split inputs like `"1.5 lakh"` or `"8,50,000"` on punctuation, truncating values to `1` and `8`.
   - *Symptom:* Reconciliations failed and user inputs were parsed with severe rounding errors.
   - *Resolution:* Caught during test suite execution and evaluation against the 50-description benchmark; rewritten with currency-aware regex normalization and strict clause regex matching.

4. **Self-Grading Risk in Tax Oracle (Project A):**
   - *Bug / Risk:* Having the same assistant generate both the rule engine and the verification oracle created an intrinsic self-grading bias.
   - *Resolution:* Enforced 10 independent hand-computed golden cases with full manual arithmetic traces, formulated the oracle using difference-based breakpoint math rather than iterative slab traversal, and verified 30 spot-checks directly against the official Income Tax Department online calculator.
