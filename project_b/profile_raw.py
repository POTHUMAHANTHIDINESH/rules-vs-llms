"""Task 1: profile quality problems already present in the 2023 data (real CSV, or synthetic for a dry run).
    python -m project_b.profile_raw --csv project_b/data/nyc311_2023.csv
Writes project_b/results/profile.json with counts + up to 3 example rows per finding."""
import argparse, json, os
import numpy as np
import pandas as pd
from . import schema as S
from .injector import pdt
from .detectors import PHONE, EMAIL

HERE = os.path.dirname(__file__)


def ex(df, mask, cols):
    return df.loc[mask, [c for c in cols if c in df.columns]].head(3).to_dict("records")


def profile(df):
    n, out = len(df), {}

    def add(name, mask, cols=("Unique Key",)):
        mask = pd.Series(mask, index=df.index).fillna(False)
        out[name] = {"count": int(mask.sum()), "pct": round(100 * mask.mean(), 4), "examples": ex(df, mask, cols)}
    c, cl = pdt(df["Created Date"]), pdt(df["Closed Date"])
    add("created_date_unparseable", c.isna() & df["Created Date"].notna(), ["Unique Key", "Created Date"])
    add("created_outside_2023", (c < "2023-01-01") | (c >= "2024-01-01"), ["Unique Key", "Created Date"])
    add("closed_before_created", cl < c, ["Unique Key", "Created Date", "Closed Date"])
    add("closed_in_future_or_pre_2023", (cl > "2025-01-01") | (cl < "2023-01-01"), ["Unique Key", "Closed Date"])
    add("closed_date_missing_but_status_closed", df["Closed Date"].isna() & (df["Status"] == "Closed"), ["Unique Key", "Status"])
    add("closed_date_present_but_status_open", df["Closed Date"].notna() & df["Status"].isin(S.OPEN_STATUS), ["Unique Key", "Status", "Closed Date"])
    add("exact_duplicate_rows", df.astype(str).duplicated(keep="first"))
    add("duplicate_unique_key", df["Unique Key"].duplicated(keep="first"))
    la, lo = pd.to_numeric(df["Latitude"], errors="coerce"), pd.to_numeric(df["Longitude"], errors="coerce")
    add("latlon_missing", la.isna() | lo.isna(), ["Unique Key", "Borough", "Incident Zip"])
    add("latlon_outside_nyc_bbox", la.notna() & ((la < S.NYC_LAT[0]) | (la > S.NYC_LAT[1]) | (lo < S.NYC_LON[0]) | (lo > S.NYC_LON[1])), ["Unique Key", "Latitude", "Longitude"])
    add("latlon_exactly_zero", (la == 0) | (lo == 0), ["Unique Key", "Latitude", "Longitude"])
    z = df["Incident Zip"].astype("string")
    add("zip_missing", z.isna())
    add("zip_not_5_digits", z.notna() & ~z.str.fullmatch(r"\d{5}"), ["Unique Key", "Incident Zip"])
    exp = z.str[:3].map(S.ZIP_PREFIX_BOROUGH)
    add("zip_borough_mismatch", z.notna() & df["Borough"].isin(S.BOROUGH_ZIPS) & (exp != df["Borough"]), ["Unique Key", "Incident Zip", "Borough"])
    add("borough_unspecified_or_missing", df["Borough"].isna() | (df["Borough"].astype(str).str.upper() == "UNSPECIFIED"))
    add("descriptor_missing", df["Descriptor"].isna(), ["Unique Key", "Complaint Type"])
    pair = df.groupby(["Complaint Type", "Descriptor"]).size()
    rare = pair[pair <= 2].index
    add("rare_complaint_descriptor_pair(<=2 rows)", df.set_index(["Complaint Type", "Descriptor"]).index.isin(rare), ["Unique Key", "Complaint Type", "Descriptor"])
    add("resolution_missing", df["Resolution Description"].isna())
    r = df["Resolution Description"].fillna("").astype(str)
    add("pii_phone_or_email_in_resolution", r.str.contains(PHONE) | r.str.contains(EMAIL), ["Unique Key", "Resolution Description"])
    for col in ("Agency", "Complaint Type", "Borough", "Status"):
        s = df[col].dropna().astype(str)
        norm = s.str.strip().str.lower()
        var = s.groupby(norm).nunique()
        out[f"case_or_whitespace_variants_in_{col}"] = {"count": int((var > 1).sum()), "examples": list(var[var > 1].index[:3])}
    out["null_rate_by_column"] = df.isna().mean().round(4).to_dict()
    out["rows"] = n
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    a = ap.parse_args()
    if a.csv:
        df = pd.read_csv(a.csv, low_memory=False)
        src = "REAL: " + a.csv
    else:
        from .synth_311 import generate
        df, src = generate(200_000), "SYNTHETIC (dry run; these are NOT real NYC findings)"
    res = {"source": src, **profile(df)}
    json.dump(res, open(os.path.join(HERE, "results", "profile.json"), "w"), indent=1, default=str)
    print(src)
    for k, v in res.items():
        if isinstance(v, dict) and "count" in v:
            print(f"{k:50s} {v['count']:>8}")


if __name__ == "__main__":
    main()
