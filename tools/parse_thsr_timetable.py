import sys, re, json, pdfplumber
EN = ["Nangang","Taipei","Banqiao","Taoyuan","Hsinchu","Miaoli","Taichung","Changhua","Yunlin","Chiayi","Tainan","Zuoying"]
DAYS = "一二三四五六日"
p = pdfplumber.open(sys.argv[1])
out = []
for pi, pg in enumerate(p.pages):
    ws = pg.extract_words(extra_attrs=["size"])
    anchors = [w for w in ws if w['text']=="Train" and w['top']<80]
    for a in anchors:
        hy = a['top']
        st = [w for w in ws if w['text'] in EN and abs(w['top']-hy)<4 and a['x0'] < w['x0'] < a['x0']+620]
        st.sort(key=lambda w: w['x0'])
        names = [w['text'] for w in st]
        cols = [((w['x0']+w['x1'])/2) for w in st]
        dcols = [w for w in ws if w['text'] in DAYS and len(w['text'])==1 and abs(w['top']-(hy-7))<4 and a['x0'] < w['x0'] < a['x0']+90]
        dcols.sort(key=lambda w: w['x0'])
        dx = [((w['x0']+w['x1'])/2) for w in dcols]
        direction = "N" if names and names[0]=="Zuoying" else "S"
        xL, xR = a['x0']-12, cols[-1]+25
        print(f"page{pi} table@{a['x0']:.0f} dir={direction} stations={len(names)} days={len(dx)} {names[:2]}...", file=sys.stderr)
        body = [w for w in ws if xL < w['x0'] < xR and w['top'] > hy+5]
        trains = [w for w in body if re.fullmatch(r"\d{3,4}", w['text']) and a['x0']-8 < w['x0'] < a['x0']+25]
        for t in trains:
            ty = t['top']
            row = [w for w in body if abs(w['top']-ty) < 3.5 and w is not t]
            days = [False]*7
            anyday = False
            times = [None]*12
            for w in row:
                cx = (w['x0']+w['x1'])/2
                if set(w['text'])=={"●"}:
                    n = len(w['text']); step = (w['x1']-w['x0'])/n
                    for j in range(n):
                        c = w['x0'] + step*(j+0.5)
                        i = min(range(7), key=lambda k: abs(dx[k]-c)); days[i]=True; anyday=True
                elif re.fullmatch(r"\d\d:\d\d", w['text']) or w['text']=="─":
                    i = min(range(12), key=lambda k: abs(cols[k]-cx))
                    if abs(cols[i]-cx) > 18: print("WARN far", t['text'], w['text'], file=sys.stderr)
                    times[i] = w['text']
                else:
                    print("WARN other", pi, t['text'], repr(w['text']), file=sys.stderr)
            if not anyday: days=[True]*7
            # order stations north->south always
            if direction=="N": times = times[::-1]
            out.append({"no": t['text'], "dir": direction, "days": [int(d) for d in days], "t": times})
json.dump(out, open(sys.argv[2],"w"), ensure_ascii=False)
from collections import Counter
print(Counter(o['dir'] for o in out), file=sys.stderr)
