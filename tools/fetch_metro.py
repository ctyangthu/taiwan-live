"""Download the 桃園機場捷運 (TYMC) and 高雄捷運 (KRTC) open data from TDX into raw/metro/.

    python3 tools/fetch_metro.py

Six requests in all. Without a key TDX allows only a few requests a day per address, so do not
run this in a loop; set TDX_TOKEN to an access token from your own TDX account to lift the limit.
"""
import os, pathlib, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "raw" / "metro"
BASE = "https://tdx.transportdata.tw/api/basic/v2/Rail/Metro"

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    if os.environ.get("TDX_TOKEN"): headers["Authorization"] = "Bearer " + os.environ["TDX_TOKEN"]
    for op in ("TYMC", "KRTC"):
        for ep in ("Station", "StationTimeTable", "S2STravelTime"):
            req = urllib.request.Request(f"{BASE}/{ep}/{op}?%24format=JSON", headers=headers)
            with urllib.request.urlopen(req, timeout=90) as r: body = r.read()
            if not body.lstrip().startswith(b"["): sys.exit(f"{ep}/{op}: unexpected reply {body[:200]!r}")
            (OUT / f"{ep}-{op}.json").write_bytes(body)
            print(f"{ep}-{op}.json {len(body) / 1024:.0f} KB")
            time.sleep(1)

if __name__ == "__main__":
    main()
