"""
Guard against fixed page text going stale. Text that depends on the data is drawn from the data; the fixed text in
dashboard/page/index.html may mention a specific month or year only if it is a permanent historical fact listed here.
A new dated sentence fails this test until it is made data-driven or deliberately added to ALLOWED.
Run: python3 -m unittest discover -s tests -v
"""
import html, os, re, unittest

PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dashboard", "page", "index.html")
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"

# Permanent facts: base-year changes, the HDFC merger, RBI's reporting-date change, series start dates.
ALLOWED = {
    "February 2026",            # GDP 2022-23 base released
    "January 2026",             # CPI 2024 base: inflation published from
    "December 2025",            # 2012-base CPI ends; RBI reporting-date change
    "November 2025",            # last month on the reporting-Friday basis
    "November 2026",            # end of the Friday-comparator months
    "April 2023", "March 2026",  # IIP new base starts / old base ends
    "July 2023", "June 2024",   # HDFC merger effect on y/y growth
    "January 2022",             # bank aggregates start
    "April 2008", "May 2011",   # policy-rate history start; repo becomes the single policy rate
}
ALLOWED_YEARS_ONLY = {"1990", "1992", "2008",   # forex, exchange-rate and policy-rate history starts
                      "2012", "2024"}           # CPI base-year names


def fixed_text():
    with open(PAGE, encoding="utf-8") as f:
        h = f.read()
    h = h[h.index('<div class="mm">'):]
    h = re.sub(r"(?s)<script.*?</script>|<code>.*?</code>", " ", h)
    h = re.sub(r'(?s)<(\w+)[^>]*data-draw="[^"]*"[^>]*>.*?</\1>', " ", h)   # drawn (data-driven) elements
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h)))


class FixedPageText(unittest.TestCase):
    def test_dated_mentions_are_permanent_facts(self):
        text = fixed_text()
        found = set(re.findall(rf"(?:{MONTHS}) \d{{4}}", text))
        self.assertEqual(sorted(found - ALLOWED), [], "time-bound fixed text: make it data-driven or allow it")
        years = set(re.findall(r"\b(?:19|20)\d\d\b", re.sub(rf"(?:{MONTHS}) \d{{4}}", " ", text)))
        loose = {y for y in years if y not in ALLOWED_YEARS_ONLY and not re.search(rf"{y}-\d\d", text)}
        self.assertEqual(sorted(loose), [], "bare years in fixed text")

    def test_no_reference_to_the_current_event_in_fixed_text(self):
        text = fixed_text()
        for phrase in ("this month", "this week", "currently", "the latest MPC", "Handbook 2025-26", "Handbook 2026-27"):
            self.assertNotIn(phrase, text)

    def test_overview_opens_first_and_topic_links_remain_available(self):
        with open(PAGE, encoding="utf-8") as f:
            h = f.read()
        tabs = re.findall(r'data-tab="([a-z]+)"', h)
        self.assertEqual(tabs, ["overview", "macro", "states", "brief", "explore"])
        overview = h[h.index('data-tab="overview"'):h.index('data-tab="macro"')]
        self.assertNotIn("hidden", overview.split(">", 1)[0])
        self.assertIn('id="headline"', overview)
        economy = h[h.index('data-tab="macro"'):h.index('data-tab="states"')]
        for part in ('id="growth"', 'id="demand"', 'id="jobs"'):
            self.assertIn(part, economy)
        self.assertEqual(re.findall(r'<section class="mm-sec" id="([^"]+)"', economy)[-1], "current-rates")
        brief = h[h.index('data-tab="brief"'):h.index('data-tab="explore"')]
        for part in ('id="brief"', 'id="brief-funding"', 'id="brief-pricing"', 'id="banking"', 'id="funding"'):
            self.assertIn(part, brief)

    def test_catalogue_and_methods_are_not_on_the_page(self):
        with open(PAGE, encoding="utf-8") as f:
            h = f.read()
        self.assertNotIn('id="catalog"', h)
        self.assertNotIn("<details", h)
        self.assertIn("github.com/prathameshtaywade/india-macro-monitor#readme", h)

    def test_no_time_range_control(self):
        with open(PAGE, encoding="utf-8") as f:
            self.assertNotIn("data-range-btn", f.read())


if __name__ == "__main__":
    unittest.main()
