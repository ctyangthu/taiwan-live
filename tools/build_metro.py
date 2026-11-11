"""Turn the TDX station timetables of 桃園機場捷運 and 高雄捷運 into train-by-train runs: data/metro.json.

    python3 tools/build_metro.py

TDX publishes, for every station, the departure times towards each terminus. A train is rebuilt by
following one departure down the line: at the next stop it is the departure closest to the expected
running time. Trains of one stopping pattern never overtake each other, so the matching keeps order.
The terminus has no departure of its own; its arrival is the last departure plus the running time.
"""
import collections, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "metro"
load = lambda n: json.loads((RAW / n).read_text(encoding="utf-8"))
WEEK = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
TOL = 2          # minutes a departure may differ from the expected running time
# [operator, line, name, station order]
A_ORDER = [f"A{n}" for n in range(1, 14)] + ["A14a"] + [f"A{n}" for n in range(15, 23)]
R_ORDER = ["R3", "R4", "R4A"] + [f"R{n}" for n in range(5, 23)] + ["R22A", "R23", "R24", "RK1"]
O_ORDER = ["O1", "O2"] + [f"O{n}" for n in range(4, 15)] + ["OT1"]
LINES = [("TYMC", "A", "桃園機場捷運", A_ORDER), ("KRTC", "R", "高雄捷運紅線", R_ORDER), ("KRTC", "O", "高雄捷運橘線", O_ORDER)]


def minute(s):
    h, m = map(int, s.split(":"))
    return h * 60 + m + (1440 if h < 4 else 0)     # after midnight belongs to the service day before


def short(name):
    return name if name.endswith("車站") or not name.endswith("站") else name[:-1]


def main():
    stations, lines, index = [], [], {}
    for li, (op, lid, name, order) in enumerate(LINES):
        src = {s["StationID"]: s for s in load(f"Station-{op}.json")}
        ids = []
        for sid in order:
            s = src[sid]
            index[(op, sid)] = len(stations); ids.append(len(stations))
            stations.append([li, sid, short(s["StationName"]["Zh_tw"]), s["StationName"]["En"].replace(" Station", ""),
                             round(s["StationPosition"]["PositionLat"], 5), round(s["StationPosition"]["PositionLon"], 5)])
        lines.append({"id": lid, "op": op, "name": name, "stations": ids})
        missing = set(k for k in src if k.startswith(lid[0]) and k[0] == lid) - set(order)
        assert not missing, f"{lid}: stations not in the line order: {missing}"

    # running time estimates in seconds: every pair for TYMC, neighbours for KRTC
    est = {}
    for op in ("TYMC", "KRTC"):
        for r in load(f"S2STravelTime-{op}.json"):
            tts = r["TravelTimes"]
            for k, t in enumerate(tts):
                dwell = tts[k + 1]["StopTime"] if op == "KRTC" and k + 1 < len(tts) else 0
                est[(op, r["TrainType"], t["FromStationID"], t["ToStationID"])] = (t["RunTime"] + dwell) / 60

    trips = collections.defaultdict(int)     # (line, kind, dir, stops, times) → weekday mask
    stats = collections.Counter()
    for li, (op, lid, name, order) in enumerate(LINES):
        pos = {sid: k for k, sid in enumerate(order)}
        groups = collections.defaultdict(lambda: collections.defaultdict(list))
        for r in load(f"StationTimeTable-{op}.json"):
            if r["LineID"] != lid: continue
            mask = sum(1 << k for k, d in enumerate(WEEK) if r["ServiceDay"][d])
            for t in r["Timetables"]:
                g = (mask, r["Direction"], r["DestinationStaionID"], t.get("TrainType") or 0, t.get("StoppingPatternID"))
                groups[g][r["StationID"]].append(minute(t["DepartureTime"]))
        for (mask, direction, dest, kind, pattern), at in groups.items():
            seq = sorted(at, key=lambda s: pos[s], reverse=bool(direction))
            assert all((pos[s] < pos[dest]) != bool(direction) for s in seq), (lid, dest, seq)

            def expect(a, b):
                e = est.get((op, kind, a, b))
                if e is None and abs(pos[a] - pos[b]) == 1: e = est.get((op, 0, a, b))
                assert e is not None, f"no running time {op} {kind} {a}→{b}"
                return e

            runs, open_ = [], []
            for k, sid in enumerate(seq):
                times = sorted(at[sid])
                if k == 0:
                    open_ = [[(sid, t)] for t in times]; runs += open_; continue
                # near the published running time, the gap that carries the most departures on to this stop.
                # Only near it: with even headways a gap one headway longer fits just as many departures.
                have, about = set(times), round(expect(seq[k - 1], sid))
                e = max(range(max(1, about - 2), about + 3), key=lambda g: (sum(r[-1][1] + g in have for r in open_), -g))
                # first the trains that keep that time to the minute, then the ones held a little longer
                # (機捷 commuter trains wait at A8 for the express to pass); order is kept in both passes
                taken, nxt = set(), []
                for lo, hi in ((-1, 1), (-TOL, 8)):
                    i = 0
                    for r in open_:
                        if r[-1][0] == sid: continue
                        target = r[-1][1] + e
                        while i < len(times) and (times[i] < target + lo or i in taken): i += 1
                        if i < len(times) and times[i] <= target + hi:
                            r.append((sid, times[i])); taken.add(i); nxt.append(r); i += 1
                stats["ends early"] += sum(r[-1][0] != sid for r in open_)
                for i, t in enumerate(times):
                    if i not in taken: nxt.append([(sid, t)]); runs.append(nxt[-1])
                open_ = sorted(nxt, key=lambda r: r[-1][1])
            for r in runs:
                if r[-1][0] == seq[-1]:
                    r.append((dest, r[-1][1] + max(1, round(expect(seq[-1], dest)))))
                if len(r) < 2: stats["single stop"] += 1; continue
                if r[0][0] != seq[0]: stats["starts mid-line"] += 1
                stops = tuple(index[(op, s)] for s, _ in r)
                trips[(li, kind, direction, stops, tuple(t for _, t in r))] |= mask
                stats[f"{lid} runs"] += 1

    patterns, offsets, out = {}, {}, []
    for (li, kind, direction, stops, times), mask in sorted(trips.items(), key=lambda kv: (kv[0][0], kv[0][4][0])):
        p = patterns.setdefault(stops, len(patterns))
        o = offsets.setdefault(tuple(t - times[0] for t in times), len(offsets))
        out.append([li, kind, direction, p, o, times[0], mask])
    src = load("StationTimeTable-TYMC.json") + load("StationTimeTable-KRTC.json")
    data = {"updated": max(r["SrcUpdateTime"] for r in src)[:10], "lines": lines, "stations": stations,
            "patterns": [list(p) for p in patterns], "offsets": [list(o) for o in offsets], "trips": out}
    (ROOT / "data" / "metro.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    per_day = collections.Counter()
    for li, kind, direction, p, o, t0, mask in out:
        for d in range(7):
            if mask >> d & 1: per_day[(lines[li]["id"], "一二三四五六日"[d])] += 1
    print(f"data/metro.json: {len(stations)} stations, {len(out)} runs, {len(patterns)} stop patterns, {len(offsets)} timings")
    print("runs per day:", {f"{l}{d}": n for (l, d), n in sorted(per_day.items())})
    print("checks:", dict(stats))


if __name__ == "__main__":
    main()
