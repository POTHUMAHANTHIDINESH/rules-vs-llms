import numpy as np
import pytest
from project_b.synth_311 import generate
from project_b.injector import inject, PROBLEMS
from project_b.detectors import RulesDetector, StatsDetector

DF = generate(30_000)
BASE, B = DF.iloc[:25_000].reset_index(drop=True), DF.iloc[25_000:].reset_index(drop=True)


@pytest.mark.parametrize("pid", list(PROBLEMS))
def test_injector_changes_data_and_truth_aligned(pid):
    c, t = inject(B, pid, 0.05, 1)
    assert c is not B and (t["rows"] is None or len(t["rows"]) == len(c))
    if t["rows"] is not None:
        assert t["rows"].sum() > 0


def test_injector_deterministic():
    a, ta = inject(B, "p10", 0.05, 3)
    b, tb = inject(B, "p10", 0.05, 3)
    assert a.equals(b) and (ta["rows"] == tb["rows"]).all()


@pytest.mark.parametrize("pid", ["p01", "p02", "p03", "p04", "p05", "p08", "p09", "p10", "p11"])
def test_rules_catch_structural_problems_without_false_alarm(pid):
    R = RulesDetector()
    assert not R.detect_one(pid, B).flag
    c, t = inject(B, pid, 0.05, 1)
    assert R.detect_one(pid, c).flag
