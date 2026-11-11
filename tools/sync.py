"""Copy the data of the two source systems, air-live and rail-live, into this project.

    python3 tools/sync.py

Run this after either of them changes (both must sit next to this project). It copies
  air-live   the three timetables, airports, world map, audit notes → data/air/
             its page → src/air.html, its timetable parser → tools/air_schedule.py
  rail-live  the 高鐵 timetables, 臺鐵 stations and trains, the Taiwan map → data/
src/app.html is this project's own page: it started from rail-live's and is not overwritten,
so a change to rail-live's page has to be ported by hand.
"""
import pathlib, shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
AIR, RAIL = ROOT.parent / "air-live", ROOT.parent / "rail-live"

(ROOT / "data" / "air").mkdir(parents=True, exist_ok=True)
for p in sorted((AIR / "data").glob("*.*")):
    shutil.copy(p, ROOT / "data" / "air" / p.name)
shutil.copy(AIR / "src" / "app.html", ROOT / "src" / "air.html")
parser = (AIR / "tools" / "schedule.py").read_text(encoding="utf-8")
assert 'ROOT / "data" / f' in parser
(ROOT / "tools" / "air_schedule.py").write_text(parser.replace('ROOT / "data" / f', 'ROOT / "data" / "air" / f'), encoding="utf-8")
print("air-live copied")

for old in list((ROOT / "data").glob("thsr-*.json")): old.unlink()
for p in sorted((RAIL / "data").glob("*.json")):
    shutil.copy(p, ROOT / "data" / p.name)
print("rail-live copied")
