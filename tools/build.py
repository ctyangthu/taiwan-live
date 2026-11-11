"""Build the two pages of the site into dist/.

    python3 tools/build.py

dist/index.html     ground transport and airport access: 高鐵, 臺鐵, 機場捷運, 高雄捷運, departing flights
dist/air.html       the flight map of air-live, with links back to the ground page
dist/artifact.html  index.html's body only, for hosts that add their own document skeleton
"""
import collections, json, pathlib
import air_schedule

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
load = lambda p: json.loads(p.read_text(encoding="utf-8"))
compact = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
TW = ("TPE", "TSA", "RMQ", "KHH")


def page(body, description):
    """title, fonts and styles come before the app markup; they belong in <head>"""
    split = body.index('<div class="app">')
    return ('<!doctype html>\n<html lang="zh-Hant">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f'<meta name="description" content="{description}">\n'
            + body[:split] + "</head>\n<body>\n" + body[split:] + "\n</body>\n</html>\n")


def fill(src, marks):
    for mark, value in marks.items():
        assert mark in src, mark
        src = src.replace(mark, compact(value))
    return src


def patch(src, old, new):
    assert src.count(old) == 1, f"air page changed, cannot find {old[:60]!r}"
    return src.replace(old, new)


# ── flights ──
segs = air_schedule.parse()
airports = load(DATA / "air" / "airports.json"); airports.pop("_fields", None)
audit = load(DATA / "air" / "audit-notes.json")
missing = {c for s in segs for c in (s["o"], s["d"])} - set(airports["airports"])
assert not missing, f"airports missing from data/air/airports.json: {sorted(missing)}"

# ── ground page: the two railways, the two metros, and the flights leaving Taiwan ──
regular = sorted(DATA.glob("thsr-timetable-*.json"))[-1]
reg_from = regular.stem.removeprefix("thsr-timetable-")
hsr = {"regular": {"name": f"{int(reg_from[:4])}/{int(reg_from[5:7])}/{int(reg_from[8:])} 起適用時刻表", "from": reg_from, "trains": load(regular)},
       "special": [load(p) for p in sorted(DATA.glob("thsr-special-*.json"))]}
tra = load(DATA / "tra-trains.json")
metro = load(DATA / "metro.json")
keep = ("no", "o", "d", "dep", "arr", "plus", "ac", "air", "days", "kind", "op", "from", "to", "skip", "only")
out = [{k: s[k] for k in keep if k in s} for s in segs if s["o"] in TW]
air = {"season": "NW26", "valid": list(air_schedule.SEASON), "updated": audit["checked"],
       "airports": {c: airports["airports"][c][:5] for c in sorted({s["d"] for s in out})}, "segs": out}
body = fill((ROOT / "src" / "app.html").read_text(encoding="utf-8"),
            {"__HSR_JSON__": hsr, "__TRA_JSON__": tra, "__MAP_JSON__": load(DATA / "map.json"), "__METRO_JSON__": metro, "__AIR_JSON__": air})

# ── flight map: air-live's page plus the way back ──
NAV_CSS = """
.sitenav{display:flex;gap:2px;padding:3px;border:1px solid var(--rule);border-radius:10px;background:var(--surface-2);align-self:center}
.sitenav a{padding:4px 11px;border-radius:7px;font-size:13px;font-weight:500;color:var(--muted);text-decoration:none;white-space:nowrap}
.sitenav a:hover{color:var(--ink)}
.sitenav a[aria-current]{background:var(--ink);color:var(--surface);font-weight:700}
a.btn{text-decoration:none;color:inherit}
</style>"""
a = (ROOT / "src" / "air.html").read_text(encoding="utf-8")
a = patch(a, "</style>", NAV_CSS)
a = patch(a, '    <div class="clock">\n      <time id="clock"',
          '    <nav class="sitenav" aria-label="系統切換"><a href="./">地面交通・到機場</a><a href="air.html" aria-current="page">航班世界地圖</a></nav>\n'
          '    <div class="clock">\n      <time id="clock"')
a = patch(a, "<title>台灣航空動態</title>", "<title>航班世界地圖 · 台灣交通動態系統</title>")
# a flight leaving Taiwan gets a link to the ground page, which finds the trains that reach the airport in time
a = patch(a, '`<button class="btn icon" data-act="locate"',
          '(TW.has(s.o) ? `<a class="btn" href="./#fly=${s.no}&ap=${s.o}${x ? \'&date=\' + dkey(x.D) : \'\'}" title="查詢到機場的高鐵、臺鐵與捷運">到機場交通</a>` : \'\') + `<button class="btn icon" data-act="locate"')
# air.html#flight=BR6 opens that flight (the link the ground page uses)
a = patch(a, "styleRoutes(); syncControls(); syncDate(); drawNight();\nrequestAnimationFrame(frame);",
          "styleRoutes(); syncControls(); syncDate(); drawNight();\n"
          "{ const no = new URLSearchParams(location.hash.slice(1)).get('flight'), s = no && (SEGS.find(s => s.no === no && TW.has(s.o)) || SEGS.find(s => s.no === no)); if (s) selectSeg(s); }\n"
          "requestAnimationFrame(frame);")
air_body = fill(a, {"__FLIGHTS_JSON__": {"season": "NW26", "valid": list(air_schedule.SEASON), "updated": audit["checked"], "segs": segs},
                    "__AIRPORTS_JSON__": airports, "__MAP_JSON__": load(DATA / "air" / "map.json"), "__AUDIT_JSON__": audit})

dist = ROOT / "dist"
dist.mkdir(exist_ok=True)
(dist / "index.html").write_text(page(body, "台灣交通動態系統：長榮、華航、星宇的航班，加上高鐵、臺鐵、桃園機場捷運與高雄捷運。選一個航班，依「起飛前 2 小時到機場」找出來得及的車次；同一張台灣地圖上推算各列車的位置。非官方展示。"), encoding="utf-8")
(dist / "artifact.html").write_text(body, encoding="utf-8")
(dist / "air.html").write_text(page(air_body, "長榮、華航、星宇三家航空的國際線航班動態：依 2026/27 冬季班表在世界地圖上推算各航班位置。台灣交通動態系統的航班地圖。非官方展示。"), encoding="utf-8")
kb = lambda t: f"{len(t.encode('utf-8')) / 1024:.0f} KB"
print(f"dist/index.html {kb(body)} · 高鐵 {len(hsr['regular']['trains'])} · 臺鐵 {len(tra['trains'])} schedules {tra['dates'][0]}–{tra['dates'][1]} · "
      f"捷運 {len(metro['trips'])} runs · 出發航班 {len(out)} lines", dict(collections.Counter(s['o'] for s in out)))
print(f"dist/air.html {kb(air_body)} · {len(segs)} lines")
