import gzip, io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.chdir(r"C:\Users\Administrator\Documents\dsh-workplace\fund-PETrace")

files = [
    "web/index.html",
    "web/app.js",
    "web/style.css",
    "web/vendor/echarts.min.js",
    "web/data/manifest.json",
    "web/data/summary.json",
    "web/data/index/SH000300.json",
]
raw = gz = 0
print("%-38s %10s %10s %7s" % ("file", "raw", "gzip", "ratio"))
for f in files:
    b = open(f, "rb").read()
    g = len(gzip.compress(b, 9))
    raw += len(b)
    gz += g
    print("%-38s %10s %10s %6.0f%%" % (f, format(len(b), ","), format(g, ","), g / len(b) * 100))
print("-" * 70)
print("%-38s %10s %10s %6.0f%%" % ("TOTAL critical path", format(raw, ","), format(gz, ","), gz / raw * 100))
print()
# measured throughputs from this session (B/s)
for name, bps in (("GitHub Pages (gzip)", 76 * 1024), ("EdgeOne (mainland node)", 2150 * 1024)):
    print("%-28s %8.1f KB/s  ->  %.1f s for the gzipped critical path" % (name, bps / 1024, gz / bps))
