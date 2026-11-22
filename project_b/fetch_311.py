"""Download NYC 311 requests created in calendar 2023 from NYC Open Data (Socrata dataset erm2-nwe9).
    python -m project_b.fetch_311 --out project_b/data/nyc311_2023.csv [--limit 1000000]
Needs internet (not available in the sandbox that authored this repo, so this script is UNTESTED there).
Optional: SOCRATA_APP_TOKEN env var raises rate limits."""
import argparse, json, os, time, urllib.parse, urllib.request
import pandas as pd
from . import schema as S

URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
MAP = {"unique_key": "Unique Key", "created_date": "Created Date", "closed_date": "Closed Date", "agency": "Agency",
       "complaint_type": "Complaint Type", "descriptor": "Descriptor", "location_type": "Location Type",
       "incident_zip": "Incident Zip", "city": "City", "borough": "Borough", "latitude": "Latitude", "longitude": "Longitude",
       "status": "Status", "resolution_description": "Resolution Description", "open_data_channel_type": "Open Data Channel Type"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="project_b/data/nyc311_2023.csv")
    ap.add_argument("--limit", type=int, default=1_000_000)
    ap.add_argument("--page", type=int, default=50_000)
    a = ap.parse_args()
    rows, off = [], 0
    hdr = {"X-App-Token": os.environ["SOCRATA_APP_TOKEN"]} if os.environ.get("SOCRATA_APP_TOKEN") else {}
    while off < a.limit:
        q = urllib.parse.urlencode({"$where": "created_date between '2023-01-01T00:00:00' and '2023-12-31T23:59:59'",
                                    "$select": ",".join(MAP), "$order": "created_date,unique_key", "$limit": a.page, "$offset": off})
        with urllib.request.urlopen(urllib.request.Request(f"{URL}?{q}", headers=hdr), timeout=120) as r:
            chunk = json.load(r)
        if not chunk:
            break
        rows += chunk
        off += len(chunk)
        print(off, "rows", flush=True)
        time.sleep(0.5)
    df = pd.DataFrame(rows).rename(columns=MAP)
    for c in S.DATE_COLS:                         # Socrata ISO -> CSV-export format used by the detectors
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.strftime(S.DATE_FMT)
    df.reindex(columns=S.COLS).to_csv(a.out, index=False)
    print("wrote", a.out, len(df))


if __name__ == "__main__":
    main()
