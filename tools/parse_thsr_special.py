"""Parse a THSR special-period timetable PDF (疏運期間時刻表) into JSON.

    python3 tools/parse_thsr_special.py 疏運時刻表.pdf data/thsr-special-2026-11-27.json "2026選舉疏運"

Special timetables replace the regular one for a few dates. Every page holds one table; the
適用期間 line gives the dates, and the 行駛日 column lists the dates a train runs on
("11/28, 11/30", "11/27~11/28"); a blank column means every date of the period. Output:

    name, from, to   period (ISO dates, inclusive)
    trains           no, dir (S/N), dates (ISO dates, or null for the whole period),
                     t (12 times north → south: "HH:MM", "─" passes, null not served)

Needs pdfplumber.
"""
import datetime, json, re, sys
import pdfplumber

EN = ["Nangang", "Taipei", "Banqiao", "Taoyuan", "Hsinchu", "Miaoli", "Taichung", "Changhua", "Yunlin", "Chiayi", "Tainan", "Zuoying"]


def main(src, dst, name):
    pdf = pdfplumber.open(src)
    text = pdf.pages[0].extract_text()
    m = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})\s*~\s*(\d{4})/(\d{1,2})/(\d{1,2})", text)
    if not m:
        raise SystemExit("no 適用期間 (YYYY/M/D~YYYY/M/D) on the first page")
    y = int(m[1])
    d0 = datetime.date(y, int(m[2]), int(m[3]))
    d1 = datetime.date(int(m[4]), int(m[5]), int(m[6]))

    def md(s):  # "11/28" → date within the period's year
        mo, d = (int(v) for v in s.split("/"))
        return datetime.date(y + (mo < d0.month), mo, d)

    def dates_of(s):
        out = set()
        for part in filter(None, (p.strip() for p in s.split(","))):
            a, _, b = part.partition("~")
            a, b = md(a), md(b or a)
            while a <= b:
                out.add(a.isoformat())
                a += datetime.timedelta(days=1)
        return sorted(out)

    trains = []
    for pi, pg in enumerate(pdf.pages):
        ws = pg.extract_words()
        head = sorted((w for w in ws if w["text"] in EN), key=lambda w: w["x0"])
        if len(head) != 12:
            raise SystemExit(f"page {pi + 1}: found {len(head)} station columns")
        # column x → station index; northbound pages list 左營 first, so map by name
        cols = [((w["x0"] + w["x1"]) / 2, EN.index(w["text"])) for w in head]
        direction = "N" if "北上" in pg.extract_text() else "S"
        hy, left = head[0]["top"], cols[0][0]
        nos = [w for w in ws if re.fullmatch(r"\d{3,4}", w["text"]) and w["x0"] < left - 120 and w["top"] > hy + 8]
        for t in nos:
            row = sorted((w for w in ws if abs(w["top"] - t["top"]) < 3 and w is not t), key=lambda w: w["x0"])
            times, day = [None] * 12, []
            for w in row:
                cx = (w["x0"] + w["x1"]) / 2
                if re.fullmatch(r"\d\d:\d\d|-", w["text"]) and cx > left - 30:
                    x, i = min(cols, key=lambda c: abs(c[0] - cx))
                    if abs(x - cx) > 20:
                        print("WARN far", pi, t["text"], w["text"], file=sys.stderr)
                    times[i] = "─" if w["text"] == "-" else w["text"]
                elif re.fullmatch(r"[\d/~,]+", w["text"]):
                    day.append(w["text"])
                else:
                    print("WARN other", pi, t["text"], repr(w["text"]), file=sys.stderr)
            trains.append({"no": t["text"], "dir": direction, "dates": dates_of("".join(day)) if day else None, "t": times})

    out = {"name": name, "from": d0.isoformat(), "to": d1.isoformat(), "trains": trains}
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
    by = {}
    for t in trains:
        by[t["dir"]] = by.get(t["dir"], 0) + 1
    print(f"{name} {d0}–{d1}: {len(trains)} trains {by}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "疏運期間")
