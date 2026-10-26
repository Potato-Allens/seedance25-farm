# -*- coding: utf-8 -*-
"""Probe every generated mp4 and summarise resolution / duration / suspicious files.

Usage:
    python src/verify_all.py [dir1 dir2 ...]

Env:
    S25_OUT   primary output dir (default: <repo>/out)
"""
import os, sys, glob, json, subprocess, collections, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT = os.environ.get("S25_OUT") or os.path.join(ROOT, "out")
SRC_LIST = sys.argv[1:] or [DEFAULT]

files = []
for s in SRC_LIST:
    files += sorted(glob.glob(os.path.join(s, "*.mp4")))

rows = []
for f in files:
    try:
        j = json.loads(subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,r_frame_rate,nb_frames:format=duration,size",
             "-of", "json", f],
            capture_output=True, text=True, timeout=30).stdout or "{}")
        st = (j.get("streams") or [{}])[0]
        fm = j.get("format") or {}
        w, h, fr = st.get("width"), st.get("height"), st.get("r_frame_rate")
        dur = float(fm.get("duration") or 0)
    except Exception:
        w = h = fr = None
        dur = 0
    rows.append({"f": os.path.basename(f), "w": w, "h": h, "fr": fr,
                 "dur": round(dur, 2), "bytes": os.path.getsize(f)})

c = collections.Counter("%sx%s" % (r["w"], r["h"]) for r in rows)
print("files", len(rows))
for k, v in c.most_common():
    print("  %-12s %d" % (k, v))
bad = [r for r in rows if not r["w"] or r["bytes"] < 50000 or r["dur"] < 3]
print("suspicious", len(bad))
for r in bad[:8]:
    print("  ", r)
print("durations", collections.Counter(r["dur"] for r in rows).most_common(4))

pref = collections.Counter()
for r in rows:
    m = re.search(r"(batch_[0-9a-f]{8})", r["f"])
    if m:
        pref[m.group(1)] += 1
dups = {k: v for k, v in pref.items() if v > 1}
print("dup batch prefixes", len(dups), "extra files", sum(v - 1 for v in dups.values()))
json.dump({"files": len(rows), "res": dict(c), "suspicious": len(bad), "dups": len(dups)},
          open(os.path.join(ROOT, "state", "verify_summary.json"), "w"), ensure_ascii=False, indent=1)
