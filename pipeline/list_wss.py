#!/usr/bin/env python3
"""
List RBI Weekly Statistical Supplement XLSX file ids for the tables the dashboard uses, newest first,
as a JS object to paste into pipeline/rbi_extract.js (const WSS = ...).
  PARAM1=2 -> Table 2  Foreign Exchange Reserves        (2T_...)
  PARAM1=3 -> Table 4  SCB - Business in India           (4T_...)
  PARAM1=4 -> Table 5  Ratios and Rates                  (5T_...)
These listing pages on rbi.org.in are plain HTML (no bot challenge). Usage:
  python3 pipeline/list_wss.py [since=YYYY-MM-DD]
"""
import datetime, json, os, re, ssl, sys, urllib.request

since = sys.argv[1] if len(sys.argv) > 1 else (datetime.date.today() - datetime.timedelta(days=150)).isoformat()
ctx = ssl.create_default_context(cafile="/etc/ssl/cert.pem") if os.path.exists("/etc/ssl/cert.pem") else ssl.create_default_context()
out = {}
for key, param in [("fx", 2), ("scb", 3), ("rr", 4)]:
    url = f"https://rbi.org.in/Scripts/WSSViewDetail.aspx?TYPE=Section&PARAM1={param}"
    s = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=120, context=ctx).read().decode("utf-8", "ignore")
    rows, d = [], None
    for a, b in re.findall(r'>(\d{2} \w{3} \d{4})<|href="https://rbidocs\.rbi\.org\.in/rdocs/Wss/DOCs/([^"]+)\.XLSX"', s):
        if a:
            d = datetime.datetime.strptime(a, "%d %b %Y").date().isoformat()
        elif b and d:
            if d >= since:
                rows.append([d, b])
            d = None
    out[key] = rows
print("const WSS = " + json.dumps(out) + ";")
