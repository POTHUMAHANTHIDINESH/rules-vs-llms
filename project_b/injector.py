"""Corruption injector: 12 problem types at a controlled rate, with ground truth.

inject(df, pid, rate, seed) -> (corrupted_df, truth)
truth = {"pid", "rate", "rows": bool array aligned to corrupted_df (None for column-level problems), "detail": str}
"""
import numpy as np
import pandas as pd
from . import schema as S

PROBLEMS = {
    "p01": "Renamed or dropped column", "p02": "Column type change (numbers as strings)",
    "p03": "Date format switch partway", "p04": "Latitude/longitude swapped", "p05": "Exact duplicates",
    "p06": "Near-duplicates", "p07": "Null spike in one agency", "p08": "Closed date before created date",
    "p09": "ZIP inconsistent with borough", "p10": "Complaint Type inconsistent with Descriptor",
    "p11": "Resolution Description contradicts Status", "p12": "Personal data in free text"}
FIRST = ["Maria", "John", "Priya", "Wei", "Aisha", "Robert", "Olga", "Luis", "Fatima", "David", "Keisha", "Tomasz"]
LAST = ["Gonzalez", "Smith", "Nair", "Chen", "Khan", "Johnson", "Petrova", "Rivera", "Ahmed", "Cohen", "Brown", "Nowak"]


def pdt(s):
    return pd.to_datetime(s, format=S.DATE_FMT, errors="coerce")


def fdt(s):
    return s.dt.strftime(S.DATE_FMT)


def _pick(rng, mask, rate, min_n=1):
    idx = np.flatnonzero(mask)
    k = min(len(idx), max(min_n, int(round(rate * len(mask)))))
    return rng.choice(idx, k, replace=False) if k else np.array([], dtype=int)


def _pii(rng):
    f, l = FIRST[rng.integers(len(FIRST))], LAST[rng.integers(len(LAST))]
    kind = rng.integers(3)
    if kind == 0:
        return rng.choice([f"Caller can be reached at ({rng.integers(200, 999)}) 555-{rng.integers(1000, 9999)}.",
                           f"Callback {rng.integers(200, 999)}-555-{rng.integers(1000, 9999)}.",
                           f"Contact number {rng.integers(200, 999)}.555.{rng.integers(1000, 9999)}."])
    if kind == 1:
        return rng.choice([f"Reply to {f.lower()}.{l.lower()}@gmail.com.", f"email: {f.lower()}{rng.integers(10, 99)}@yahoo.com",
                           f"Send update to {l.lower()}_{rng.integers(1, 99)}@outlook.com"])
    return rng.choice([f"Complainant {f} {l} stated the issue persists.", f"Per Mr. {l}.", f"Caller: {f.upper()} {l.upper()}",
                       f"{f} {l} said the problem continues.", f"Ask for {f} {l} at the front desk.",
                       f"Spoke to {f} from apartment {rng.integers(1, 9)}B."])


def inject(df: pd.DataFrame, pid: str, rate: float, seed: int = 0):
    rng = np.random.default_rng(seed)
    d = df.copy()
    n = len(d)
    rows = None
    detail = ""
    if pid == "p01":
        col = rng.choice([c for c in S.COLS if c not in ("Unique Key", "Created Date")])
        if rng.random() < 0.5:
            d = d.rename(columns={col: {"Incident Zip": "Zip Code", "Latitude": "lat"}.get(col, col + " v2")})
            detail = f"renamed {col}"
        else:
            d = d.drop(columns=[col])
            detail = f"dropped {col}"
    elif pid == "p02":
        col = rng.choice(S.NUMERIC)
        idx = _pick(rng, d[col].notna().values, rate)
        d[col] = d[col].astype(object)
        d.loc[d.index[idx], col] = d.loc[d.index[idx], col].map(lambda v: str(v))
        rows = np.zeros(n, bool); rows[idx] = True
        detail = f"{col} as string in {len(idx)} rows"
    elif pid == "p03":
        k = int(n * (1 - rate))
        for c in S.DATE_COLS:
            t = pdt(d[c])
            iso = t.dt.strftime("%Y-%m-%d %H:%M:%S")
            d.loc[d.index[k:], c] = iso.iloc[k:].where(t.iloc[k:].notna(), None)
        rows = np.zeros(n, bool); rows[k:] = True
        detail = f"ISO date format from row {k}"
    elif pid == "p04":
        idx = _pick(rng, d["Latitude"].notna().values, rate)
        a = d.loc[d.index[idx], "Latitude"].values.copy()
        d.loc[d.index[idx], "Latitude"] = d.loc[d.index[idx], "Longitude"].values
        d.loc[d.index[idx], "Longitude"] = a
        rows = np.zeros(n, bool); rows[idx] = True
    elif pid in ("p05", "p06"):
        idx = _pick(rng, np.ones(n, bool), rate)
        cp = d.iloc[idx].copy()
        if pid == "p06":
            sh = rng.integers(1, 121, len(cp)).astype("timedelta64[s]")
            for c in S.DATE_COLS:
                t = pdt(cp[c])
                cp[c] = fdt(t + sh).where(t.notna(), None)
            cp["Unique Key"] = d["Unique Key"].max() + 1 + np.arange(len(cp))
            alt = rng.random(len(cp)) < 0.5
            cp.loc[alt, "Resolution Description"] = cp.loc[alt, "Resolution Description"].str.rstrip(".") + " ."
        cp.index = idx + 0.5
        d = pd.concat([d, cp]).sort_index(kind="stable")
        rows = (d.index.values % 1) == 0.5
        d = d.reset_index(drop=True)
    elif pid == "p07":
        vc = d["Agency"].value_counts()
        ag = rng.choice(vc[vc >= 0.05 * n].index)
        m = (d["Agency"] == ag).values
        idx = np.flatnonzero(m & (rng.random(n) < rate))
        d.loc[d.index[idx], ["Incident Zip", "Latitude", "Longitude"]] = np.nan
        rows = np.zeros(n, bool); rows[idx] = True
        detail = f"agency {ag}"
    elif pid == "p08":
        idx = _pick(rng, d["Closed Date"].notna().values, rate)
        cr = pdt(d["Created Date"].iloc[idx])
        d.loc[d.index[idx], "Closed Date"] = fdt(cr - rng.integers(3600, 30 * 86400, len(idx)).astype("timedelta64[s]")).values
        rows = np.zeros(n, bool); rows[idx] = True
    elif pid == "p09":
        idx = _pick(rng, d["Incident Zip"].notna().values & d["Borough"].isin(S.BOROUGH_ZIPS).values, rate)
        for i in idx:
            other = [b for b in S.BOROUGH_ZIPS if b != d.at[d.index[i], "Borough"]]
            d.at[d.index[i], "Incident Zip"] = rng.choice(S.BOROUGH_ZIPS[rng.choice(other)])
        rows = np.zeros(n, bool); rows[idx] = True
    elif pid == "p10":
        idx = _pick(rng, np.ones(n, bool), rate)
        for i in idx:
            own = d.at[d.index[i], "Complaint Type"]
            other = rng.choice([c for c in S.COMPLAINTS if c != own])
            ds = [x for x in S.COMPLAINTS[other][1] if x not in S.COMPLAINTS[own][1]] or S.COMPLAINTS[other][1]
            d.at[d.index[i], "Descriptor"] = rng.choice(ds)
        rows = np.zeros(n, bool); rows[idx] = True
    elif pid == "p11":
        idx = _pick(rng, np.ones(n, bool), rate)
        for i in idx:
            a = S.AGENCY_SHORT[d.at[d.index[i], "Agency"]]
            tpl = S.OPEN_TPL if d.at[d.index[i], "Status"] == "Closed" else S.CLOSED_TPL
            d.at[d.index[i], "Resolution Description"] = tpl[rng.integers(len(tpl))].format(a=a)
        rows = np.zeros(n, bool); rows[idx] = True
    elif pid == "p12":
        idx = _pick(rng, np.ones(n, bool), rate)
        for i in idx:
            d.at[d.index[i], "Resolution Description"] = d.at[d.index[i], "Resolution Description"] + " " + _pii(rng)
        rows = np.zeros(n, bool); rows[idx] = True
    else:
        raise ValueError(pid)
    return d, {"pid": pid, "rate": rate, "rows": rows, "detail": detail}
