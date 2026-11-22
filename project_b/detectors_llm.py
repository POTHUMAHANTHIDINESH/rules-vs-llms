"""Detector family (c): LLM review of batch samples or of specific rows (Gemini).

Runs only with GEMINI_API_KEY. Cost projections (`project_cost`) are computed offline from real prompt text
(chars/4 token estimate; replace with usageMetadata numbers from a real run).
"""
import json
import re
import numpy as np
import pandas as pd
from . import schema as S
from .injector import PROBLEMS
from .detectors import Alert
from project_a.llm import LLMResult, PRICE_IN, PRICE_OUT

PROMPT = """You review rows of NYC 311 service requests for data-quality problems.
Expected columns: {cols}. Dates are MM/DD/YYYY hh:mm:ss AM/PM. NYC latitude is 40.4-41.0, longitude -74.3 to -73.6.
Problem taxonomy:
{tax}
Rows (CSV, first column row_id):
{csv}
Report only problems you are confident about. Return JSON:
{{"issues":[{{"problem":"pNN","row_ids":[ints],"column":"name","explanation":"short"}}],
  "batch_level":[{{"problem":"pNN","explanation":"short"}}]}}
Use empty lists when the rows look fine."""


def render(df: pd.DataFrame, ids) -> str:
    return df.loc[ids].to_csv(index_label="row_id")


def build_prompt(df, ids):
    tax = "\n".join(f"{k}: {v}" for k, v in PROBLEMS.items())
    return PROMPT.format(cols=", ".join(S.COLS), tax=tax, csv=render(df, ids))


class LLMReviewer:
    name = "llm"

    def __init__(self, client, sample_n: int = 40):
        self.client, self.sample_n = client, sample_n
        self.usage = []

    def review(self, df: pd.DataFrame, ids=None, seed: int = 0) -> dict:
        rng = np.random.default_rng(seed)
        ids = list(ids) if ids is not None else sorted(rng.choice(len(df), min(self.sample_n, len(df)), replace=False))
        res: LLMResult = self.client.generate(build_prompt(df, ids), json_mode=True)
        self.usage.append(res)
        try:
            d = json.loads(re.sub(r"^```(?:json)?|```$", "", res.text.strip(), flags=re.M))
        except json.JSONDecodeError:
            d = {"issues": [], "batch_level": []}
        out = {}
        for it in d.get("issues", []):
            pid = it.get("problem")
            if pid in PROBLEMS:
                rows = np.zeros(len(df), bool)
                for r in it.get("row_ids", []):
                    if isinstance(r, int) and 0 <= r < len(df):
                        rows[r] = True
                a = out.setdefault(pid, Alert(pid, self.name, True, np.zeros(len(df), bool), it.get("explanation", ""), {}))
                a.rows |= rows
                a.fields = {"column": it.get("column"), "examples": [int(x) for x in np.flatnonzero(a.rows)[:3]],
                            "expected": "per LLM taxonomy", "observed": it.get("explanation")}
        for it in d.get("batch_level", []):
            pid = it.get("problem")
            if pid in PROBLEMS and pid not in out:
                out[pid] = Alert(pid, self.name, True, None, it.get("explanation", ""), {"column": None, "observed": it.get("explanation")})
        return out


def project_cost(df: pd.DataFrame, sample_n: int = 40, per_row_chunk: int = 50, out_tokens: int = 350, batch_rows: int = 5000):
    """USD per million rows for (1) batch-sample review and (2) review of every row, from real prompt text."""
    ids = list(range(min(sample_n, len(df))))
    tok_in_sample = len(build_prompt(df, ids)) / 4
    ids2 = list(range(min(per_row_chunk, len(df))))
    tok_in_chunk = len(build_prompt(df, ids2)) / 4
    sample = (1e6 / batch_rows) * (tok_in_sample * PRICE_IN + out_tokens * PRICE_OUT) / 1e6
    every = (1e6 / per_row_chunk) * (tok_in_chunk * PRICE_IN + out_tokens * PRICE_OUT) / 1e6
    return {"batch_sample_usd_per_M_rows": sample, "every_row_usd_per_M_rows": every, "prompt_tokens_sample": tok_in_sample,
            "prompt_tokens_row_chunk": tok_in_chunk, "assumed_output_tokens": out_tokens,
            "calls_per_M_rows_sample": 1e6 / batch_rows, "calls_per_M_rows_every_row": 1e6 / per_row_chunk}
