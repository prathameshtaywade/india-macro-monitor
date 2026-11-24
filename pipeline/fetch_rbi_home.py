#!/usr/bin/env python3
"""
Scrape the "Current Rates" box on https://www.rbi.org.in/ (plain HTML, no bot challenge).
Gives the latest policy rates, reserve ratios, FBIL reference rates and benchmark G-Sec yields
with their 'as on' dates. Writes data/raw/rbi_home.json. Standard library only.

Safety: the new snapshot replaces the saved one only if every required field parsed and is in range
(pipeline/checks.py). Otherwise the last good snapshot is kept and the script exits 1.
"""
import html, json, os, re, ssl, sys, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from checks import snapshot_errors  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "rbi_home.json")
URL = "https://www.rbi.org.in/"


def ctx():
    for p in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(p):
            return ssl.create_default_context(cafile=p)
    return ssl.create_default_context()


def parse(raw, fetched_utc=None):
    """Parse the homepage HTML into a snapshot dict. Fields that are not found are None / empty."""
    raw = re.sub(r"(?s)<script.*?</script>|<style.*?</style>", "", raw)
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " | ", raw)))
    t = re.sub(r"(\|\s*)+", "| ", t)
    i = t.find("Policy Repo Rate")
    box = t[max(0, i - 50): i + 2200] if i >= 0 else ""

    def grab(label, pat=r"([\d.]+)"):
        m = re.search(re.escape(label) + r"\s*\|\s*:\s*" + pat, box)
        try:
            return float(m.group(1)) if m else None
        except ValueError:
            return None

    snap = {
        "fetched_utc": fetched_utc or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_url": URL,
        "policy": {k: grab(k) for k in ["Policy Repo Rate", "Standing Deposit Facility Rate",
                                         "Marginal Standing Facility Rate", "Bank Rate", "Fixed Reverse Repo Rate"]},
        "ratios": {"CRR": grab("CRR"), "SLR": grab("SLR")},
        "fx": {k: grab(k) for k in ["INR / 1 USD", "INR / 1 GBP", "INR / 1 EUR", "INR / 100 JPY", "INR / 1 AED"]},
        "gsec": {m.group(1): float(m.group(2)) for m in re.finditer(r"([\d.]+% GS \d{4})\s*\|\s*:\s*([\d.]+)%", box)},
        "tbill": {m.group(1): float(m.group(2)) for m in re.finditer(r"(\d+ day T-bills)\s*\|\s*:\s*([\d.]+)%", box)},
    }
    m = re.search(r"As at ([^)]*?of [A-Za-z]+ \d+, \d{4})", box)
    snap["fx_as_of"] = m.group(1) if m else None
    m = re.search(r"Government Securities Market.*?as on \|\s*([A-Za-z]+ \d+, \d{4})", box)
    snap["gsec_as_of"] = m.group(1) if m else None
    return snap


def save_if_valid(snap, out=OUT):
    """Write the snapshot only if it passes the checks. Returns the list of errors (empty = saved)."""
    errs = snapshot_errors(snap)
    if errs:
        return errs
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "w") as f:
        json.dump(snap, f, indent=1)
    os.replace(tmp, out)
    return []


def main():
    raw = urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"}),
                                 timeout=60, context=ctx()).read().decode("utf-8", "ignore")
    snap = parse(raw)
    errs = save_if_valid(snap)
    if errs:
        print("rbi.org.in snapshot rejected; keeping the last good file:\n  " + "\n  ".join(errs), file=sys.stderr)
        sys.exit(1)
    print(json.dumps(snap, indent=1))


if __name__ == "__main__":
    main()
