"""Shared types, rounding and recommendation logic used by all three engines."""
from dataclasses import dataclass, asdict, fields
from typing import Optional


def pct(x: int, p: int) -> int:
    """x * p% rounded half-up to the rupee (integer arithmetic only)."""
    return (x * p + 50) // 100


def round10(x: int) -> int:
    """Section 288A / 288B: round to nearest ten rupees (half-up)."""
    return ((x + 5) // 10) * 10


@dataclass
class TaxInput:
    fy: str = "2024-25"                 # "2024-25" or "2025-26"
    age: int = 30
    gross_salary: int = 0               # annual taxable salary before exemptions/deductions
    basic_salary: Optional[int] = None  # basic + DA, annual (needed only for HRA)
    hra_received: int = 0
    rent_paid: int = 0                  # annual
    metro: bool = False                 # Delhi / Mumbai / Kolkata / Chennai
    sec_80c: int = 0
    sec_80ccd1b: int = 0
    sec_80d_self: int = 0               # premium paid for self/spouse/children
    sec_80d_parents: int = 0
    parents_senior: bool = False
    home_loan_interest: int = 0         # self-occupied house, annual

    @classmethod
    def from_dict(cls, d: dict) -> "TaxInput":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})

    def to_dict(self) -> dict:
        return asdict(self)

    def validate(self) -> None:
        errs = []
        for f in ("gross_salary", "hra_received", "rent_paid", "sec_80c", "sec_80ccd1b",
                  "sec_80d_self", "sec_80d_parents", "home_loan_interest"):
            if getattr(self, f) < 0:
                errs.append(f"{f} cannot be negative")
        if self.basic_salary is not None and self.basic_salary < 0:
            errs.append("basic_salary cannot be negative")
        if not (18 <= self.age <= 120):
            errs.append("age must be between 18 and 120")
        if self.hra_received > 0 and self.rent_paid > 0 and self.basic_salary is None:
            errs.append("basic_salary is required to compute HRA exemption")
        if self.basic_salary is not None and self.basic_salary + self.hra_received > self.gross_salary:
            errs.append("basic_salary + hra_received exceeds gross_salary")
        if errs:
            raise ValueError("; ".join(errs))


def line(label: str, amount: int, clause: str) -> dict:
    return {"label": label, "amount": int(amount), "clause": clause}


def recommend(old: dict, new: dict) -> dict:
    o, n = old["tax_payable"], new["tax_payable"]
    if n <= o:
        choice, saving = "new", o - n
    else:
        choice, saving = "old", n - o
    if o == n:
        reason = (f"Both regimes cost Rs {o:,}; choose new (no proof of investments/rent needed).")
    else:
        cheaper = "new" if choice == "new" else "old"
        reason = (f"{cheaper.capitalize()} regime is cheaper by Rs {saving:,} "
                  f"(old Rs {o:,} vs new Rs {n:,}). Old-regime exemptions+deductions claimed: "
                  f"Rs {old['total_exemptions_and_deductions']:,}; new-regime: "
                  f"Rs {new['total_exemptions_and_deductions']:,}.")
    return {"choice": choice, "saving": saving, "reason": reason}


def compare(engine_regime_fn, inp: TaxInput) -> dict:
    inp.validate()
    old = engine_regime_fn(inp, "old")
    new = engine_regime_fn(inp, "new")
    return {"old": old, "new": new, "recommendation": recommend(old, new)}
