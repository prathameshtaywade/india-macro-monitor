#!/usr/bin/env python3
"""
Scrape the "Current Rates" box on https://www.rbi.org.in/ (plain HTML, no bot challenge).
Gives the latest policy rates, reserve ratios, FBIL reference rates and benchmark G-Sec yields
with their 'as on' dates. Writes data/raw/rbi_home.json. Standard library only.
"""
import html, json, os, re, ssl, time, urllib.request

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "rbi_home.json")
URL = "https://www.rbi.org.in/"


def ctx():
    for p in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(p):
            return ssl.create_default_context(cafile=p)
    return ssl.create_default_context()


def main():
    raw = urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"}),
                                 timeout=60, context=ctx()).read().decode("utf-8", "ignore")
    raw = re.sub(r"(?s)<script.*?</script>|<style.*?</style>", "", raw)
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " | ", raw)))
    t = re.sub(r"(\|\s*)+", "| ", t)
    i = t.find("Policy Repo Rate")
    box = t[i - 50: i + 2200]

    def grab(label, pat=r"([\d.]+)"):
        m = re.search(re.escape(label) + r"\s*\|\s*:\s*" + pat, box)
        return float(m.group(1)) if m else None

    snap = {
        "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
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
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(snap, open(OUT, "w"), indent=1)
    print(json.dumps(snap, indent=1))


if __name__ == "__main__":
    main()
