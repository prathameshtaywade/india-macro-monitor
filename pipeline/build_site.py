#!/usr/bin/env python3
"""
Assemble the static website in site/ from the shared dashboard page and the exported data.
  web/template.html + dashboard/page/index.html  -> site/index.html
  dashboard/page/app.js, web/dash-shim.js        -> site/
  dashboard/{observations,catalog,snapshot}.json -> site/data/
Preview locally:  python3 -m http.server -d site 8000
"""
import os, re, shutil

ROOT = os.path.join(os.path.dirname(__file__), "..")
SITE = os.path.join(ROOT, "site")
shutil.rmtree(SITE, ignore_errors=True)
os.makedirs(os.path.join(SITE, "data"))

page = open(os.path.join(ROOT, "dashboard", "page", "index.html"), encoding="utf-8").read()
page = re.sub(r'<meta name="dash-[^"]*"[^>]*>\s*', "", page)          # Claude-dashboard-only markers
page = re.sub(r'<script src="app\.js"></script>\s*', "", page)        # the template loads scripts itself
tpl = open(os.path.join(ROOT, "web", "template.html"), encoding="utf-8").read()
open(os.path.join(SITE, "index.html"), "w", encoding="utf-8").write(tpl.replace("<!-- PAGE -->", page))

shutil.copy(os.path.join(ROOT, "dashboard", "page", "app.js"), SITE)
shutil.copy(os.path.join(ROOT, "web", "dash-shim.js"), SITE)
for f in ("observations.json", "catalog.json", "snapshot.json", "regions.json"):
    shutil.copy(os.path.join(ROOT, "dashboard", f), os.path.join(SITE, "data", f))
open(os.path.join(SITE, ".nojekyll"), "w").close()
print("site/ built:", sorted(os.listdir(SITE)))
