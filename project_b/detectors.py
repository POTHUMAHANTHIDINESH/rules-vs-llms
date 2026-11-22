"""Detector families (a) rules/schema and (b) statistical/ML. Both: fit(baseline) then detect_one(pid, df) -> Alert."""
import re
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from . import schema as S
from .injector import pdt


@dataclass
class Alert:
    pid: str
    detector: str
    flag: bool = False
    rows: Optional[np.ndarray] = None
    reason: str = ""
    fields: dict = field(default_factory=dict)       # column / examples / expected / observed -> explanation score

    def explain_score(self) -> int:
        return sum(k in self.fields and self.fields[k] not in (None, "", []) for k in ("column", "examples", "expected", "observed"))


def _num(s):
    return pd.to_numeric(s, errors="coerce")


def _has(df, *cols):
    return all(c in df.columns for c in cols)


def _alert(pid, det, rows, col, expected, df=None, observed=None, reason=""):
    flag = bool(rows.any()) if rows is not None else bool(reason)
    ex = []
    if rows is not None and flag:
        ex = [int(i) for i in np.flatnonzero(rows)[:3]]
    obs = observed if observed is not None else (f"{int(rows.sum())} rows" if rows is not None and flag else None)
    return Alert(pid, det, flag, rows, reason or (f"{col}: {obs}; expected {expected}" if flag else ""),
                 {"column": col, "examples": ex, "expected": expected, "observed": obs} if flag else {})


# ------------------------------------------------------------------ (a) rules
PHONE = re.compile(r"(?:\(?\b\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
NAME = re.compile(r"\b(?:Mr|Ms|Mrs|Dr)\.?\s+[A-Z][a-z]+|(?:Caller|Complainant|Reported by|reported by|Contact|contact|Spoke with|spoke with)\s*:?\s*[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?")
CLOSED_WORDS = re.compile(r"closed|resolved|completed the|took action|investigated and|no violation", re.I)
OPEN_WORDS = re.compile(r"awaiting|not yet|still pending|is reviewing|will be updated|assigned to an inspector", re.I)
MAX_NULL = {"Incident Zip": 0.05, "Latitude": 0.10, "Longitude": 0.10}      # hand-set config, generous


class RulesDetector:
    name = "rules"

    def fit(self, baseline):
        return self

    def detect_one(self, pid, df):
        return getattr(self, pid)(df)

    def p01(self, df):
        miss, extra = sorted(set(S.COLS) - set(df.columns)), sorted(set(df.columns) - set(S.COLS))
        if not (miss or extra):
            return Alert("p01", self.name)
        return _alert("p01", self.name, None, ",".join(miss + extra), f"columns {len(S.COLS)}", observed=f"missing={miss} unexpected={extra}",
                      reason=f"schema mismatch: missing={miss} unexpected={extra}")

    def p02(self, df):
        bad = np.zeros(len(df), bool); cols = []
        for c in S.NUMERIC:
            if c in df:
                m = df[c].map(lambda v: isinstance(v, str)).values
                if m.any():
                    bad |= m; cols.append(c)
        return _alert("p02", self.name, bad, ",".join(cols), "numeric dtype")

    def p03(self, df):
        bad = np.zeros(len(df), bool)
        for c in S.DATE_COLS:
            if c in df:
                s = df[c].astype(object)
                bad |= (s.notna() & ~s.astype(str).str.match(S.DATE_RE)).values
        return _alert("p03", self.name, bad, "Created/Closed Date", f"format {S.DATE_FMT}")

    def p04(self, df):
        if not _has(df, "Latitude", "Longitude"):
            return Alert("p04", self.name)
        la, lo = _num(df["Latitude"]), _num(df["Longitude"])
        bad = (la.notna() & lo.notna() & ((la < S.NYC_LAT[0]) | (la > S.NYC_LAT[1]) | (lo < S.NYC_LON[0]) | (lo > S.NYC_LON[1]))).values
        return _alert("p04", self.name, bad, "Latitude/Longitude", "inside NYC bbox lat 40.4-41.0, lon -74.3..-73.6")

    def p05(self, df):
        return _alert("p05", self.name, df.astype(str).duplicated(keep="first").values, "all columns", "unique rows")

    def p06(self, df):
        if not _has(df, "Complaint Type", "Incident Zip", "Latitude", "Longitude", "Created Date", "Unique Key"):
            return Alert("p06", self.name)
        t = pdt(df["Created Date"]).dt.as_unit("s").astype("int64")
        key = df["Complaint Type"].astype(str) + "|" + df["Incident Zip"].astype(str) + "|" + df["Latitude"].astype(str) + "|" + df["Longitude"].astype(str)
        o = pd.DataFrame({"k": key.values, "t": t.values, "u": _num(df["Unique Key"]).values}).sort_values(["k", "t"], kind="stable")
        same = (o["k"] == o["k"].shift()) & ((o["t"] - o["t"].shift()) <= 600) & (o["u"] != o["u"].shift()) & (~o["k"].str.contains("nan"))
        bad = np.zeros(len(df), bool); bad[o.index[same.values]] = True
        return _alert("p06", self.name, bad, "Complaint Type+location", "no same-place same-type request within 10 min")

    def p07(self, df):
        if not _has(df, "Agency"):
            return Alert("p07", self.name)
        bad = np.zeros(len(df), bool); hits = []
        for ag, g in df.groupby("Agency"):
            for c, thr in MAX_NULL.items():
                if c in df and g[c].isna().mean() > thr:
                    bad[g.index.values] |= g[c].isna().values; hits.append(f"{ag}.{c}={g[c].isna().mean():.0%}")
        return _alert("p07", self.name, bad, "Agency x null rate", f"null rate <= {MAX_NULL}", observed="; ".join(hits[:3]))

    def p08(self, df):
        if not _has(df, "Created Date", "Closed Date"):
            return Alert("p08", self.name)
        bad = (pdt(df["Closed Date"]) < pdt(df["Created Date"])).fillna(False).values
        return _alert("p08", self.name, bad, "Closed Date", "Closed Date >= Created Date")

    def p09(self, df):
        if not _has(df, "Incident Zip", "Borough"):
            return Alert("p09", self.name)
        exp = df["Incident Zip"].astype(str).str[:3].map(S.ZIP_PREFIX_BOROUGH)
        bad = (df["Incident Zip"].notna() & df["Borough"].isin(S.BOROUGH_ZIPS) & (exp != df["Borough"])).values
        return _alert("p09", self.name, bad, "Incident Zip vs Borough", "zip prefix maps to Borough")

    def p10(self, df):
        if not _has(df, "Complaint Type", "Descriptor"):
            return Alert("p10", self.name)
        ok = {(c, d) for c, (_, ds) in S.COMPLAINTS.items() for d in ds}
        bad = np.array([(c, d) not in ok for c, d in zip(df["Complaint Type"], df["Descriptor"])])
        return _alert("p10", self.name, bad, "Descriptor", "descriptor valid for Complaint Type (reference table)")

    def p11(self, df):
        if not _has(df, "Status", "Resolution Description"):
            return Alert("p11", self.name)
        r = df["Resolution Description"].fillna("")
        closed = df["Status"] == "Closed"
        bad = ((~closed & r.str.contains(CLOSED_WORDS)) | (closed & r.str.contains(OPEN_WORDS))).values
        return _alert("p11", self.name, bad, "Resolution Description vs Status", "resolution wording consistent with Status")

    def p12(self, df):
        if not _has(df, "Resolution Description"):
            return Alert("p12", self.name)
        r = df["Resolution Description"].fillna("").astype(str)
        bad = (r.str.contains(PHONE) | r.str.contains(EMAIL) | r.str.contains(NAME)).values
        return _alert("p12", self.name, bad, "Resolution Description", "no phone/email/person name")


# ------------------------------------------------------------------ (b) statistical / ML
def _sig(s):
    return s.astype(str).str.replace(r"\d", "9", regex=True).str.replace(r"[A-Za-z]", "a", regex=True)


def _charfeats(r):
    r = r.fillna("").astype(str)
    L = r.str.len().clip(lower=1)
    return np.c_[r.str.count(r"\d") / L, r.str.count(r"[A-Z]") / L, r.str.count("@"), L, r.str.count(r"\b[A-Z][a-z]+\b"), r.str.count(r"\d{7,}|\d{3}[\s.)-]+\d{3}[\s.-]+\d{4}")]


class StatsDetector:
    name = "stats"

    def fit(self, base):
        self.cols = set(base.columns)
        self.n_base = len(base)
        self.sigs = {c: _sig(base[c].dropna()).value_counts(normalize=True) for c in S.DATE_COLS}
        ll = base[["Latitude", "Longitude"]].dropna()
        self.if_ll = IsolationForest(n_estimators=60, random_state=0).fit(ll.sample(min(20000, len(ll)), random_state=0).values)
        self.thr_ll = np.quantile(self.if_ll.score_samples(ll.sample(min(20000, len(ll)), random_state=1).values), 0.0002)
        self.ll_med = ll.median(); self.ll_mad = 1.4826 * (ll - ll.median()).abs().median()
        self.ll_zmax = float(((ll - self.ll_med).abs() / self.ll_mad).max(axis=1).max()) * 1.25
        self.null_rate = base.groupby("Agency")[["Incident Zip", "Latitude", "Longitude"]].apply(lambda g: g.isna().mean())
        self.agency_n = base["Agency"].value_counts()
        dur = ((pdt(base["Closed Date"]) - pdt(base["Created Date"])).dt.total_seconds() / 3600).dropna()
        self.dur_lo = float(np.arcsinh(dur).min())
        near = self._near_gaps(base)
        self.gap_lo = float(near.quantile(0.02)) if len(near) else 0.0
        zb = base.dropna(subset=["Incident Zip"]).groupby("Incident Zip")["Borough"].agg(lambda s: s.value_counts().index[0])
        self.zip_b = zb.to_dict()
        self.pairs = base.groupby(["Complaint Type", "Descriptor"]).size()
        self.pair_ok = set(self.pairs[self.pairs >= 3].index)
        self.tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=2)
        samp = base.sample(min(20000, len(base)), random_state=0)
        X = self.tfidf.fit_transform(samp["Resolution Description"].fillna(""))
        self.clf = LogisticRegression(max_iter=300).fit(X, (samp["Status"] == "Closed").astype(int))
        F = _charfeats(samp["Resolution Description"])
        self.if_txt = IsolationForest(n_estimators=60, random_state=0).fit(F)
        self.thr_txt = np.quantile(self.if_txt.score_samples(F), 0.0002)
        return self

    def _near_gaps(self, df):
        t = pdt(df["Created Date"]).dt.as_unit("s").astype("int64")
        key = df["Complaint Type"].astype(str) + "|" + df["Incident Zip"].astype(str) + "|" + df["Latitude"].astype(str) + "|" + df["Longitude"].astype(str)
        o = pd.DataFrame({"k": key.values, "t": t.values}).sort_values(["k", "t"], kind="stable")
        g = (o["t"] - o["t"].shift())[(o["k"] == o["k"].shift()) & (~o["k"].str.contains("nan"))]
        return g[g > 0]

    def detect_one(self, pid, df):
        return getattr(self, pid)(df)

    def p01(self, df):
        import difflib
        miss, extra = sorted(self.cols - set(df.columns)), sorted(set(df.columns) - self.cols)
        if not (miss or extra):
            return Alert("p01", self.name)
        pairs = [(e, difflib.get_close_matches(e, miss, n=1, cutoff=0.5)) for e in extra]
        return _alert("p01", self.name, None, ",".join(miss + extra), "baseline column set", observed=f"fuzzy renames={pairs} missing={miss}",
                      reason=f"column set drift vs baseline: missing={miss} new={extra} (likely renames: {pairs})")

    def p02(self, df):
        bad = np.zeros(len(df), bool); cols = []
        for c in S.NUMERIC:
            if c in df:
                m = df[c].map(lambda v: isinstance(v, str)).values
                z = (m.sum() - len(df) / self.n_base) / np.sqrt(max(len(df) / self.n_base, 1e-9))
                if z > 4:
                    bad |= m; cols.append(c)
        return _alert("p02", self.name, bad, ",".join(cols), "baseline: 0% string cells")

    def p03(self, df):
        bad = np.zeros(len(df), bool)
        for c in S.DATE_COLS:
            if c in df:
                s = df[c].dropna()
                f = _sig(s).map(self.sigs[c]).fillna(0)
                bad[df.index.get_indexer(s.index)] |= (f < 1e-4).values
        return _alert("p03", self.name, bad, "Created/Closed Date", "date character-pattern seen in baseline")

    def p04(self, df):
        if not _has(df, "Latitude", "Longitude"):
            return Alert("p04", self.name)
        ll = pd.DataFrame({"Latitude": _num(df["Latitude"]), "Longitude": _num(df["Longitude"])})
        med, mad = self.ll_med, self.ll_mad
        z = ((ll - med).abs() / mad).max(axis=1)
        bad = (z > self.ll_zmax).fillna(False).values
        return _alert("p04", self.name, bad, "Latitude/Longitude", f"robust |z| <= {self.ll_zmax:.1f} (baseline max)")

    def p05(self, df):
        dup = df.astype(str).duplicated(keep="first").values
        z = (dup.sum() - 1e-5 * len(df)) / np.sqrt(1e-5 * len(df))
        return _alert("p05", self.name, dup if z > 4 else np.zeros(len(df), bool), "all columns", "baseline duplicate rate ~0")

    def p06(self, df):
        if not _has(df, "Complaint Type", "Incident Zip", "Latitude", "Longitude", "Created Date"):
            return Alert("p06", self.name)
        t = pdt(df["Created Date"]).dt.as_unit("s").astype("int64")
        key = df["Complaint Type"].astype(str) + "|" + df["Incident Zip"].astype(str) + "|" + df["Latitude"].astype(str) + "|" + df["Longitude"].astype(str)
        o = pd.DataFrame({"k": key.values, "t": t.values}).sort_values(["k", "t"], kind="stable")
        gap = o["t"] - o["t"].shift()
        same = (o["k"] == o["k"].shift()) & (gap < self.gap_lo) & (gap > 0) & (~o["k"].str.contains("nan"))
        bad = np.zeros(len(df), bool); bad[o.index[same.values]] = True
        return _alert("p06", self.name, bad, "Complaint Type+location+time", f"learned min legit repeat gap {self.gap_lo:.0f}s")

    def p07(self, df):
        if not _has(df, "Agency"):
            return Alert("p07", self.name)
        bad = np.zeros(len(df), bool); hits = []
        for ag, g in df.groupby("Agency"):
            if ag not in self.null_rate.index:
                continue
            for c in ("Incident Zip", "Latitude", "Longitude"):
                if c not in df:
                    continue
                p0, p1, n = self.null_rate.at[ag, c], g[c].isna().mean(), len(g)
                se = np.sqrt(max(p0 * (1 - p0), 1e-4) / n)
                if (p1 - p0) / se > 6 and p1 - p0 > 0.05:
                    bad[g.index.values] |= g[c].isna().values; hits.append(f"{ag}.{c}: {p1:.0%} vs baseline {p0:.1%}")
        return _alert("p07", self.name, bad, "Agency x null rate", "baseline null rate per agency (z>6)", observed="; ".join(hits[:3]))

    def p08(self, df):
        if not _has(df, "Created Date", "Closed Date"):
            return Alert("p08", self.name)
        dur = np.arcsinh((pdt(df["Closed Date"]) - pdt(df["Created Date"])).dt.total_seconds() / 3600)
        bad = (dur < self.dur_lo).fillna(False).values
        return _alert("p08", self.name, bad, "Closed-Created duration", f"asinh(hours) >= baseline minimum {self.dur_lo:.3f}")

    def p09(self, df):
        if not _has(df, "Incident Zip", "Borough"):
            return Alert("p09", self.name)
        exp = df["Incident Zip"].map(self.zip_b)
        bad = (df["Incident Zip"].notna() & df["Borough"].notna() & (exp != df["Borough"])).values
        return _alert("p09", self.name, bad, "Incident Zip vs Borough", "learned zip->borough majority (incl. unseen zips)")

    def p10(self, df):
        if not _has(df, "Complaint Type", "Descriptor"):
            return Alert("p10", self.name)
        bad = np.array([(c, d) not in self.pair_ok for c, d in zip(df["Complaint Type"], df["Descriptor"])])
        return _alert("p10", self.name, bad, "Descriptor", "pair seen >=3 times in baseline")

    def p11(self, df):
        if not _has(df, "Status", "Resolution Description"):
            return Alert("p11", self.name)
        p = self.clf.predict_proba(self.tfidf.transform(df["Resolution Description"].fillna("")))[:, 1]
        y = (df["Status"] == "Closed").values
        return _alert("p11", self.name, np.abs(y - p) > 0.9, "Resolution Description vs Status", "TF-IDF logistic model agrees with Status (|diff|<=0.9)")

    def p12(self, df):
        if not _has(df, "Resolution Description"):
            return Alert("p12", self.name)
        bad = self.if_txt.score_samples(_charfeats(df["Resolution Description"])) < self.thr_txt
        return _alert("p12", self.name, bad, "Resolution Description", "char-feature IsolationForest above baseline 0.05% quantile")
