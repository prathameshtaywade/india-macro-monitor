"""
Parsers and listing for two RBI press releases (plain HTML on rbi.org.in, no browser step):

  Money Market Operations as on <date>          (daily)   -> parse_mmo()
  Lending and Deposit Rates of SCBs – <Month>   (monthly) -> parse_lending()

Listing: the press-release archive is a month-by-month form post on BS_PressReleaseDisplay.aspx
(the page's own "year/month" links set hdnYear/hdnMonth and resubmit the form); list_month() does the same.
Pure parsing functions take HTML text, so they can be tested against saved fixtures without the network.
"""
import html as _html
import datetime as dt
import os
import re
import ssl
import time
import urllib.parse
import urllib.request

BASE = "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx"
UA = "Mozilla/5.0 (india-macro-monitor; open-data refresh)"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
MON_IDX = {m: i for i, m in enumerate(MONTHS, 1)}


class ParseError(Exception):
    """The release did not have the expected structure; nothing from it should be stored."""


# ---------------------------------------------------------------- network (thin, retried, polite)
def _ctx():
    for p in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(p):
            return ssl.create_default_context(cafile=p)
    return ssl.create_default_context()


def http(url, data=None, tries=4, pause=1.0):
    body = urllib.parse.urlencode(data).encode() if data else None
    headers = {"User-Agent": UA}
    if body:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    for attempt in range(tries):
        try:
            time.sleep(pause)                                  # be gentle with rbi.org.in
            deadline = time.monotonic() + 120               # total time per request, not just per read
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers),
                                        timeout=30, context=_ctx()) as r:
                chunks = []
                while True:
                    if time.monotonic() > deadline:
                        raise TimeoutError(f"{url}: no complete answer within 120 s")
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
                return b"".join(chunks).decode("utf-8", "ignore")
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(3 * (attempt + 1))


def list_month(year, month, getter=http):
    """[(prid, title), ...] for every press release in a month of the archive."""
    page = getter(BASE)
    form = {}
    for name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        m = re.search(r'name="%s"[^>]*value="([^"]*)"' % name, page) or re.search(r'id="%s" value="([^"]*)"' % name, page)
        form[name] = m.group(1) if m else ""
    form.update({"__EVENTTARGET": "", "__EVENTARGUMENT": "", "hdnYear": str(year), "hdnMonth": str(month)})
    return list_from_html(getter(BASE, form))


def list_from_html(page):
    return [(int(p), _html.unescape(t).strip()) for p, t in re.findall(r"prid=(\d+)>([^<]+)</a>", page)]


def release(prid, getter=http):
    return getter(f"{BASE}?prid={prid}")


# ---------------------------------------------------------------- helpers
def text_of(page):
    page = re.sub(r"(?s)<script.*?</script>|<style.*?</style>", "", page)
    t = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " | ", page)))
    return re.sub(r"(\|\s*)+", "| ", t)


def num(s):
    """Indian-format number ('1,45,486.00', '-65,248.00') -> float; '-' or blank -> None."""
    s = (s or "").strip()
    if s in ("", "-", "–", "--"):
        return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def iso(month_name, day, year):
    return f"{int(year)}-{MON_IDX[month_name]:02d}-{int(day):02d}"


# ---------------------------------------------------------------- Money Market Operations
NUM = r"(-?[\d,]+\.\d+|-)"


def parse_mmo(page, prid=None):
    """
    Return {date, prid, call_rate, call_volume, overnight_rate, net_liq_today, net_liq_outstanding}.
      call_rate          A.I  Call Money, weighted average rate (%); None when no call trades (shown as '-')
      overnight_rate     A    Overnight segment (I+II+III+IV) weighted average rate (%)
      net_liq_today      C.I.5 Net liquidity injected from today's operations (₹ crore; + injection, - absorption)
      net_liq_outstanding F    Net liquidity injected, outstanding including today's operations (₹ crore)
    Raises ParseError unless the date and row F parse.
    """
    t = text_of(page)
    m = re.search(r"Money Market Operations as on ([A-Z][a-z]+) (\d{1,2}), (\d{4})", t)
    if not m or m.group(1) not in MON_IDX:
        raise ParseError("release date not found")
    out = {"date": iso(*m.groups()), "prid": prid}

    a = re.search(r"A\. Overnight Segment \(I\+II\+III\+IV\) \| " + NUM + r" \| " + NUM, t)
    c = re.search(r"I\. Call Money \| " + NUM + r" \| " + NUM, t)
    today = re.search(r"Net liquidity injected from today's operations \[injection \(\+\)/absorption \(-\)\]\*? \| " + NUM, t)
    f = re.search(r"F\. Net liquidity injected \(outstanding including today's \|? ?operations\) "
                  r"\[injection \(\+\)/absorption \(-\)\]\*? \| " + NUM, t)
    if not f or num(f.group(1)) is None:
        raise ParseError("row F (net liquidity outstanding including today's operations) not found")
    if not c:
        raise ParseError("call money row not found")
    out.update({
        "overnight_rate": num(a.group(2)) if a else None,
        "call_volume": num(c.group(1)),
        "call_rate": num(c.group(2)),
        "net_liq_today": num(today.group(1)) if today else None,
        "net_liq_outstanding": num(f.group(1)),
    })
    if out["call_volume"] in (None, 0.0):
        out["call_rate"] = None                               # no trades: no rate, even if a dash parsed oddly
    return out


# ---------------------------------------------------------------- Lending and Deposit Rates
# Highlight sentences name the metric, then one or two "X per cent in <Month YYYY>" pairs.
LENDING_METRICS = [
    ("walr_out", r"WALR\)? on outstanding rupee loans"),
    ("walr_fresh", r"WALR\)? on fresh rupee loans"),
    ("mclr_1y_median", r"1-Year median Marginal Cost of Funds?[- ]based Lending Rate"),
    ("wadtdr_out", r"WADTDR\)? on outstanding rupee term deposits"),
    ("wadtdr_fresh", r"WADTDR\)? on fresh rupee term deposits"),
]
# Wordings seen 2023-2026: "9.40 per cent as at end-November 2024", "(9.54 per cent in October 2024)",
# "from 9.84 in August 2023" (no "per cent"), "6.33 per August 2023" (typo in the release).
PAIR = re.compile(r"(\d+\.\d+)(?: per cent)?(?: (?:in|at|as at|per))? (?:end-)?([A-Z][a-z]+) (\d{4})")
UNCHANGED_AFTER_DATE = re.compile(
    r"unchanged in ([A-Z][a-z]+) (\d{4}) at (\d+\.\d+) per cent"
    r"(?: from that of ([A-Z][a-z]+)(?: (\d{4}))?)?"
)


def parse_lending(page, prid=None):
    """
    Return {release_month, prid, obs: {metric: [(YYYY-MM, value), ...]}} from the release highlights.
    Each metric is dated by the month its own sentence names (MCLR is usually a month later than WALR).
    Raises ParseError unless all five metrics parse.
    """
    t = text_of(page)
    m = re.search(r"Lending and Deposit Rates of Scheduled Commercial Banks\s*[–-]\s*([A-Z][a-z]+) (\d{4})", t)
    if not m or m.group(1) not in MON_IDX:
        raise ParseError("release month not found")
    rel = f"{m.group(2)}-{MON_IDX[m.group(1)]:02d}"
    hi = t[t.find("Highlights"):] if "Highlights" in t else t
    sentences = re.split(r"\|", hi)
    obs = {}
    for key, pat in LENDING_METRICS:
        sent = next((s for s in sentences if re.search(pat, s, re.I)), None)
        if not sent:
            raise ParseError(f"{key}: highlight sentence not found")
        pairs = [(f"{y}-{MON_IDX[mo]:02d}", float(v)) for v, mo, y in PAIR.findall(sent) if mo in MON_IDX]
        reversed_pair = UNCHANGED_AFTER_DATE.search(sent)
        if reversed_pair:
            month, year, value, earlier_month, earlier_year = reversed_pair.groups()
            if month not in MON_IDX:
                raise ParseError(f"{key}: unrecognized observation month")
            current = dt.date(int(year), MON_IDX[month], 1)
            pairs.append((current.isoformat()[:7], float(value)))
            if earlier_month in MON_IDX:
                prior_year = int(earlier_year) if earlier_year else current.year - (MON_IDX[earlier_month] > current.month)
                earlier = dt.date(prior_year, MON_IDX[earlier_month], 1)
                if earlier >= current:
                    raise ParseError(f"{key}: invalid comparison month")
                pairs.append((earlier.isoformat()[:7], float(value)))
        if not pairs:
            raise ParseError(f"{key}: no 'per cent in <month>' value")
        # "remained unchanged at X per cent in Sep compared to Aug": the earlier month has the same value.
        unchanged = re.search(r"unchanged at ([\d.]+) per cent in ([A-Z][a-z]+) (\d{4}) compared to ([A-Z][a-z]+) (\d{4})", sent)
        if unchanged:
            v, mo1, y1, mo2, y2 = unchanged.groups()
            pairs.append((f"{y2}-{MON_IDX[mo2]:02d}", float(v)))
        obs[key] = sorted(set(pairs))
    return {"release_month": rel, "prid": prid, "obs": obs}
