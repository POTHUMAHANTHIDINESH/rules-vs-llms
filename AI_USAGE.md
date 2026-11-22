# AI_USAGE
**Tools:** Claude (chat) wrote the first version of all code in this repo; Gemini is called at runtime only for implementation (b), the LLM parser/compiler and LLM review (not run in the authoring sandbox). **You (Dinesh) must edit this file to say what YOU used and reviewed.**

**Where the AI was wrong and how it was caught (real incidents from the build):**
1. *Timestamp unit bug (Project B).* Near-duplicate detectors divided pandas timestamps by 10**9 assuming nanoseconds; pandas 3 stores microseconds, so "seconds" were 1000x off. Symptoms: rules detector flagged every clean batch; learned repeat-gap median was 12 s although the generator draws 5 min-3 days. Caught by sanity-checking the learned distribution against the generator. Fixed with `.dt.as_unit("s")`.
2. *IsolationForest for swapped lat/lon (Project B).* First stats detector had 0% recall on swaps because a baseline-quantile threshold sat inside the swapped points' score range (score -0.686 vs threshold -0.707). Caught by the per-problem recall table; replaced by robust z-score with a baseline-max threshold.
3. *Test-harness bugs (Project A).* Clause-id regex missed lowercase ids (`S16ia`); parser split "1.5 lakh" and "8,50,000" on punctuation, turning amounts into 1 and 8. Caught by failing tests / the 50-case evaluation.
4. *Self-grading risk.* Expected tax values come from an oracle written by the same AI. Mitigation: 10 hand-worked goldens asserted against the oracle, and 30 cases exported for the official calculator.
