"""Deterministic synthetic NYC-311-like generator (offline development + CI).

IMPORTANT: this is SYNTHETIC. It exists because the sandbox that built this repo cannot reach NYC Open Data.
Findings about 'real quality problems' come from `python -m project_b.profile_raw --csv <real 2023 file>`
after running `python -m project_b.fetch_311`. Everything measured on synthetic data is labelled so.
Natural nulls (lat/lon/zip, closed-date on open requests) and legit repeat complaints are modelled so false
alarms are measurable, but those rates are MY assumptions, not NYC's.
"""
import numpy as np
import pandas as pd
from . import schema as S

SYN_NULL_LATLON = 0.03
SYN_NULL_ZIP = 0.01
SYN_REPEAT_RATE = 0.015


def generate(n: int = 200_000, seed: int = 2023) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ctypes = list(S.COMPLAINTS)
    cw = rng.dirichlet(np.ones(len(ctypes)) * 3)
    ct = rng.choice(len(ctypes), n, p=cw)
    comp = np.array(ctypes)[ct]
    agency = np.array([S.COMPLAINTS[c][0] for c in comp])
    desc = np.array([S.COMPLAINTS[c][1][rng.integers(len(S.COMPLAINTS[c][1]))] for c in comp])
    bor_names = list(S.BOROUGH_W)
    bor = rng.choice(bor_names, n, p=list(S.BOROUGH_W.values()))
    zips = np.empty(n, dtype=object)
    lat = np.empty(n)
    lon = np.empty(n)
    for b in bor_names:
        m = bor == b
        k = m.sum()
        zips[m] = rng.choice(S.BOROUGH_ZIPS[b], k)
        a, bb, c, d = S.BOROUGH_BOX[b]
        lat[m] = rng.uniform(a, bb, k)
        lon[m] = rng.uniform(c, d, k)
    start = np.datetime64("2023-01-01T00:00:00")
    created = start + (rng.uniform(0, 365 * 86400, n)).astype("timedelta64[s]")
    order = np.argsort(created)
    created = created[order]
    # legit repeat complaints: same place+type again shortly after an earlier request
    rep = np.where(rng.random(n) < SYN_REPEAT_RATE)[0]
    rep = rep[rep > 50]
    src = np.maximum(rep - rng.integers(1, 300, len(rep)), 0)      # legit repeat of a RECENT request (same batch)
    for i, j in zip(rep, src):
        comp[i], agency[i], desc[i], bor[i], zips[i], lat[i], lon[i] = comp[j], agency[j], desc[j], bor[j], zips[j], lat[j], lon[j]
        created[i] = created[j] + np.timedelta64(int(np.exp(rng.uniform(np.log(300), np.log(3 * 86400)))), "s")
    created = np.sort(created) if False else created
    status = rng.choice(["Closed", "Open", "Pending", "In Progress", "Assigned"], n, p=[.86, .04, .04, .03, .03])
    dur = np.exp(rng.normal(np.log(8 * 3600), 1.4, n)).astype("int64")
    closed = created + dur.astype("timedelta64[s]")
    res = np.empty(n, dtype=object)
    for i in range(n):
        a = S.AGENCY_SHORT[agency[i]]
        tpls = S.CLOSED_TPL if status[i] == "Closed" else S.OPEN_TPL
        res[i] = tpls[rng.integers(len(tpls))].format(a=a)
    df = pd.DataFrame({
        "Unique Key": np.arange(56_000_000, 56_000_000 + n),
        "Created Date": pd.Series(created).dt.strftime(S.DATE_FMT),
        "Closed Date": pd.Series(closed).dt.strftime(S.DATE_FMT),
        "Agency": agency, "Complaint Type": comp, "Descriptor": desc,
        "Location Type": rng.choice(["RESIDENTIAL BUILDING", "Street/Sidewalk", "Store/Commercial", "Club/Bar/Restaurant"], n),
        "Incident Zip": zips, "City": np.array([b.title() if b != "QUEENS" else "NEW YORK" for b in bor]), "Borough": bor,
        "Latitude": lat.round(6), "Longitude": lon.round(6), "Status": status, "Resolution Description": res,
        "Open Data Channel Type": rng.choice(["PHONE", "ONLINE", "MOBILE", "UNKNOWN"], n, p=[.45, .3, .2, .05])})
    df.loc[status != "Closed", "Closed Date"] = None
    nl = rng.random(n) < SYN_NULL_LATLON
    df.loc[nl, ["Latitude", "Longitude"]] = np.nan
    df.loc[rng.random(n) < SYN_NULL_ZIP, "Incident Zip"] = None
    df["Unique Key"] = df["Unique Key"].astype("int64")
    return df[S.COLS].reset_index(drop=True)


def batches(df: pd.DataFrame, size: int = 5000):
    for i in range(0, len(df) - size + 1, size):
        yield df.iloc[i:i + size].reset_index(drop=True)


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "project_b/data/synthetic_2023.csv"
    d = generate()
    d.to_csv(out, index=False)
    print(d.shape, "->", out)
