"""Parse the three airlines' timetable files in data/ into one list of flight segments."""
import pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = ("schedule-eva.txt", "schedule-ci.txt", "schedule-jx.txt")
SEASON = ("2026-10-25", "2027-03-27")
LINE = re.compile(r"^((?:BR|B7|CI|AE|JX)\d+)\s+([A-Z]{3})\s+(\d\d:\d\d)\s+([A-Z]{3})\s+(\d\d:\d\d)([+-]\d)?\s+(D|[1-7]+)\s+(\S+)((?:\s+\w+=\S+)*)\s*$")
OPTIONS = ("from", "to", "skip", "only", "op", "alt", "ex")
AIR = {"BR": "BR", "B7": "BR", "CI": "CI", "AE": "CI", "JX": "JX"}
JX_PARTNER = {"JX7300", "JX7301"}    # Etihad EY898/899 under a JX number


def kind(no, op=None):
    """Who flies it: BR, B7, CI, AE, JX, or CS for a partner flying under one of those numbers."""
    pre, n = no[:2], int(no[2:])
    if op: return "CS"
    if pre == "BR" and n >= 1000: return "CS"
    if pre == "B7" and n >= 1000: return "CS"
    if pre == "CI" and n >= 8000: return "CS"
    if pre == "AE" and 5000 <= n < 6000: return "CS"
    if no in JX_PARTNER: return "CS"
    return pre


def parse():
    segs = []
    for f in FILES:
        path = ROOT / "data" / "air" / f
        for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = raw.split("#", 1)[0].strip()
            if not line: continue
            m = LINE.match(line)
            if not m: raise ValueError(f"{f}:{n}: cannot parse {raw!r}")
            no, o, dep, d, arr, plus, days, ac, opts = m.groups()
            seg = {"no": no, "o": o, "d": d, "dep": dep, "arr": arr, "plus": int(plus or 0), "ac": ac, "air": AIR[no[:2]],
                   "days": "1234567" if days == "D" else "".join(sorted(set(days)))}
            for kv in opts.split():
                k, v = kv.split("=", 1)
                if k not in OPTIONS: raise ValueError(f"{f}:{n}: unknown option {k}")
                seg[k] = v
            seg["kind"] = kind(no, seg.get("op"))
            segs.append(seg)
    return segs


def operates(s, day):
    k = day.isoformat()
    if not SEASON[0] <= k <= SEASON[1]: return False
    if "only" in s: return k in s["only"].split(",")
    return str(day.isoweekday()) in s["days"] and not ("from" in s and k < s["from"]) and not ("to" in s and k > s["to"]) \
        and k not in s.get("skip", "").split(",")
