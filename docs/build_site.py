#!/usr/bin/env python3
"""
Parses the awesome-ai-ml-pharmacometrics README.md and generates
an interactive index.html for GitHub Pages deployment.

Usage:
    python build_site.py --readme README.md --output index.html
"""

import argparse
import json
import re


def parse_readme(readme_path: str) -> dict:
    """Parse README.md into structured paper data."""
    with open(readme_path, "r") as f:
        content = f.read()

    sections = re.split(r"\n## ", content)
    papers = []
    paper_id = 0
    seen_urls = {}

    for section in sections[1:]:
        lines = section.strip().split("\n")
        category = lines[0].strip()

        if category == "Table of Contents":
            continue

        current_paper = None
        for line in lines[1:]:
            title_match = re.match(r"- \*\*\[(.+?)\]\((.+?)\)\*\*", line)
            if title_match:
                if current_paper:
                    url = current_paper["url"]
                    if url in seen_urls:
                        existing = papers[seen_urls[url]]
                        if category not in existing["applications"]:
                            existing["applications"].append(category)
                    else:
                        seen_urls[url] = len(papers)
                        papers.append(current_paper)
                        paper_id += 1

                current_paper = {
                    "id": paper_id,
                    "title": title_match.group(1),
                    "url": title_match.group(2),
                    "methodologies": [],
                    "applications": [category],
                    "published": "",
                    "summary": "",
                }
            elif current_paper:
                meth_match = re.match(r"\s*- Methodology:\s*(.+)", line)
                pub_match = re.match(r"\s*- Published:\s*(.+)", line)
                sum_match = re.match(r"\s*- Summary:\s*(.+)", line)

                if meth_match:
                    current_paper["methodologies"] = [
                        m.strip() for m in meth_match.group(1).split(",")
                    ]
                elif pub_match:
                    current_paper["published"] = pub_match.group(1).strip()
                elif sum_match:
                    current_paper["summary"] = sum_match.group(1).strip()

        if current_paper:
            url = current_paper["url"]
            if url in seen_urls:
                existing = papers[seen_urls[url]]
                if category not in existing["applications"]:
                    existing["applications"].append(category)
            else:
                seen_urls[url] = len(papers)
                papers.append(current_paper)
                paper_id += 1

    # Normalize methodology tags
    meth_remap = {"Machine Learning": "Machine learning", "Artificial Intelligence": None}
    for paper in papers:
        cleaned = []
        for m in paper["methodologies"]:
            if m in meth_remap:
                if meth_remap[m] is not None:
                    cleaned.append(meth_remap[m])
            else:
                cleaned.append(m)
        paper["methodologies"] = list(set(cleaned))

    # Tag reviews
    for p in papers:
        p["is_review"] = "Reviews / Tutorials / Perspectives" in p["applications"]
        p["applications"] = [
            a for a in p["applications"] if a != "Reviews / Tutorials / Perspectives"
        ]

    # Build metadata
    all_apps = sorted(set(a for p in papers for a in p["applications"]))
    all_meths = sorted(set(m for p in papers for m in p["methodologies"] if m))

    # Build matrix
    matrix = {}
    for app in all_apps:
        matrix[app] = {}
        for meth in all_meths:
            count = len(
                [
                    p
                    for p in papers
                    if app in p["applications"] and meth in p["methodologies"]
                ]
            )
            matrix[app][meth] = count

    from datetime import datetime

    return {
        "papers": papers,
        "applications": all_apps,
        "methodologies": all_meths,
        "matrix": matrix,
        "lastUpdated": datetime.now().strftime("%Y-%m-%d"),
    }


def generate_html(data: dict) -> str:
    """Generate the full interactive HTML page."""
    compact_json = json.dumps(data, separators=(",", ":"))

    # The HTML template (CSS + JS inline for single-file deployment)
    return (
        """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI/ML in Pharmacometrics — Interactive Explorer</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,300;1,9..40,400&family=JetBrains+Mono:wght@400;500&family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,600;0,9..144,800;1,9..144,300&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #0c0f14;
  --bg-card: #141820;
  --bg-card-hover: #1a2030;
  --bg-surface: #111520;
  --border: #1e2738;
  --border-active: #3a7bfd;
  --text: #e2e8f0;
  --text-dim: #7a8ba8;
  --text-muted: #4a5568;
  --accent: #3a7bfd;
  --accent-glow: rgba(58,123,253,0.15);
  --heat-0: #141820;
  --heat-1: #0d2847;
  --heat-2: #134080;
  --heat-3: #1a5ab8;
  --heat-4: #2474e8;
  --heat-5: #3a8fff;
  --green: #34d399;
  --amber: #fbbf24;
  --rose: #f87171;
  --radius: 8px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; min-height: 100vh; }
::selection { background: var(--accent); color: white; }
.container { max-width: 1400px; margin: 0 auto; padding: 0 24px; }
header { padding: 48px 0 32px; border-bottom: 1px solid var(--border); }
header .eyebrow { font-family: 'JetBrains Mono', monospace; font-size: 11px; letter-spacing: 2px; text-transform: uppercase; color: var(--accent); margin-bottom: 12px; }
header h1 { font-family: 'Fraunces', serif; font-size: clamp(28px, 4vw, 42px); font-weight: 800; line-height: 1.15; color: var(--text); margin-bottom: 12px; }
header h1 span { color: var(--accent); }
header .subtitle { color: var(--text-dim); font-size: 15px; max-width: 600px; margin-bottom: 24px; }
.stats-row { display: flex; gap: 32px; flex-wrap: wrap; }
.stat { display: flex; flex-direction: column; }
.stat-value { font-family: 'JetBrains Mono', monospace; font-size: 28px; font-weight: 500; color: var(--text); }
.stat-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; }
.links-row { display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap; }
.link-btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; color: var(--text-dim); text-decoration: none; font-size: 13px; font-family: 'JetBrains Mono', monospace; transition: all 0.2s; }
.link-btn:hover { border-color: var(--accent); color: var(--accent); }
.link-btn svg { width: 16px; height: 16px; }
.section-title { font-family: 'Fraunces', serif; font-size: 22px; font-weight: 600; margin: 48px 0 8px; color: var(--text); }
.section-desc { color: var(--text-dim); font-size: 14px; margin-bottom: 24px; }
.active-filter { display: none; align-items: center; gap: 12px; padding: 12px 16px; background: var(--accent-glow); border: 1px solid var(--border-active); border-radius: var(--radius); margin-bottom: 20px; flex-wrap: wrap; }
.active-filter.visible { display: flex; }
.filter-tag { display: inline-flex; align-items: center; gap: 6px; background: var(--bg-card); border: 1px solid var(--border-active); padding: 4px 12px; border-radius: 20px; font-size: 13px; color: var(--accent); font-family: 'JetBrains Mono', monospace; }
.filter-tag .type-label { font-size: 10px; text-transform: uppercase; letter-spacing: 1px; color: var(--text-muted); margin-right: 4px; }
.clear-btn { margin-left: auto; background: none; border: 1px solid var(--border); color: var(--text-dim); padding: 4px 12px; border-radius: 20px; font-size: 12px; cursor: pointer; font-family: 'DM Sans', sans-serif; transition: all 0.2s; }
.clear-btn:hover { border-color: var(--rose); color: var(--rose); }
.heatmap-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: var(--radius); background: var(--bg-surface); padding: 2px; }
.heatmap-wrap::-webkit-scrollbar { height: 8px; }
.heatmap-wrap::-webkit-scrollbar-track { background: var(--bg-card); }
.heatmap-wrap::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
table.heatmap { border-collapse: separate; border-spacing: 2px; width: max-content; min-width: 100%; }
table.heatmap th { font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 500; color: var(--text-dim); padding: 8px 6px; white-space: nowrap; position: sticky; background: var(--bg-surface); z-index: 2; cursor: pointer; transition: color 0.2s; user-select: none; }
table.heatmap th:hover { color: var(--accent); }
table.heatmap th.col-header { top: 0; writing-mode: vertical-lr; transform: rotate(180deg); text-align: left; height: 160px; vertical-align: bottom; }
table.heatmap th.row-header { left: 0; text-align: right; padding-right: 12px; max-width: 220px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
table.heatmap th.corner { top: 0; left: 0; z-index: 3; }
table.heatmap th.active { color: var(--accent); font-weight: 700; }
table.heatmap td { width: 44px; height: 38px; text-align: center; font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 500; border-radius: 4px; cursor: pointer; transition: all 0.15s; position: relative; user-select: none; }
table.heatmap td:hover { outline: 2px solid var(--accent); outline-offset: -1px; z-index: 1; }
table.heatmap td.active { outline: 2px solid #fff; outline-offset: -1px; z-index: 1; }
table.heatmap td.zero { color: var(--text-muted); opacity: 0.4; }
table.heatmap td.row-total, table.heatmap th.total-header { font-weight: 600; border-left: 2px solid var(--border); color: var(--text-dim); background: var(--bg-surface) !important; cursor: default; }
table.heatmap td.row-total:hover { outline: none; }
.paper-count { font-family: 'JetBrains Mono', monospace; font-size: 13px; color: var(--text-muted); margin-bottom: 16px; }
.paper-count strong { color: var(--accent); }
.search-box { width: 100%; max-width: 400px; padding: 10px 16px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); color: var(--text); font-family: 'DM Sans', sans-serif; font-size: 14px; margin-bottom: 20px; transition: border-color 0.2s; }
.search-box:focus { outline: none; border-color: var(--accent); }
.search-box::placeholder { color: var(--text-muted); }
.toggle-row { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.toggle-btn { padding: 6px 14px; font-size: 12px; font-family: 'JetBrains Mono', monospace; background: var(--bg-card); border: 1px solid var(--border); border-radius: 20px; color: var(--text-dim); cursor: pointer; transition: all 0.2s; }
.toggle-btn:hover { border-color: var(--text-dim); }
.toggle-btn.active { border-color: var(--accent); color: var(--accent); background: var(--accent-glow); }
.papers-grid { display: flex; flex-direction: column; gap: 8px; margin-bottom: 80px; }
.paper-card { padding: 16px 20px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); transition: all 0.2s; animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.paper-card:hover { border-color: #2a3a55; background: var(--bg-card-hover); }
.paper-title { font-size: 14px; font-weight: 500; line-height: 1.45; margin-bottom: 8px; }
.paper-title a { color: var(--text); text-decoration: none; transition: color 0.2s; }
.paper-title a:hover { color: var(--accent); }
.paper-meta { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.tag { font-family: 'JetBrains Mono', monospace; font-size: 10px; padding: 3px 8px; border-radius: 4px; letter-spacing: 0.3px; }
.tag-app { background: rgba(52,211,153,0.12); color: var(--green); border: 1px solid rgba(52,211,153,0.2); }
.tag-meth { background: rgba(59,130,246,0.12); color: #60a5fa; border: 1px solid rgba(59,130,246,0.2); }
.tag-date { background: rgba(251,191,36,0.08); color: var(--amber); border: 1px solid rgba(251,191,36,0.15); }
.tag-review { background: rgba(248,113,113,0.1); color: var(--rose); border: 1px solid rgba(248,113,113,0.2); }
.paper-summary { font-size: 13px; color: var(--text-dim); line-height: 1.55; }
.no-results { text-align: center; padding: 48px 20px; color: var(--text-muted); font-size: 14px; }
footer { padding: 32px 0; border-top: 1px solid var(--border); color: var(--text-muted); font-size: 12px; text-align: center; }
footer a { color: var(--text-dim); text-decoration: none; }
footer a:hover { color: var(--accent); }
@media (max-width: 768px) { .container { padding: 0 12px; } header { padding: 32px 0 24px; } .stats-row { gap: 20px; } .stat-value { font-size: 22px; } }
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="eyebrow">Open Research Compendium</div>
    <h1>AI/ML in <span>Pharmacometrics</span></h1>
    <p class="subtitle">An interactive explorer of research papers on artificial intelligence and machine learning applications in pharmacometrics and clinical pharmacology.</p>
    <div class="stats-row" id="stats"></div>
    <div class="links-row">
      <a href="https://github.com/aiml-sig/awesome-ai-ml-pharmacometrics/" class="link-btn" target="_blank">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
        GitHub
      </a>
      <a href="https://www.zotero.org/groups/6377183/ai-ml-pharmacometrics/library" class="link-btn" target="_blank">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 3h18v2H6.5L18 17.5V18H3v-2h13L4 4.5V3z"/></svg>
        Zotero Library
      </a>
    </div>
  </header>
  <h2 class="section-title">Research Landscape</h2>
  <p class="section-desc">Click any cell to filter papers by application × methodology. Click row/column headers to filter by a single dimension.</p>
  <div class="active-filter" id="activeFilter">
    <span style="font-size:12px; color:var(--text-dim);">Filtering:</span>
    <div id="filterTags"></div>
    <button class="clear-btn" onclick="clearFilters()">Clear all</button>
  </div>
  <div class="heatmap-wrap"><table class="heatmap" id="heatmap"></table></div>
  <h2 class="section-title" id="papersSection">Papers</h2>
  <input type="text" class="search-box" id="searchBox" placeholder="Search titles, summaries...">
  <div class="toggle-row" id="toggleRow">
    <button class="toggle-btn active" onclick="toggleReview('all')">All papers</button>
    <button class="toggle-btn" onclick="toggleReview('original')">Original research</button>
    <button class="toggle-btn" onclick="toggleReview('review')">Reviews & perspectives</button>
  </div>
  <div class="paper-count" id="paperCount"></div>
  <div class="papers-grid" id="papersGrid"></div>
</div>
<footer><div class="container">Built for <a href="https://github.com/aiml-sig/awesome-ai-ml-pharmacometrics/" target="_blank">awesome-ai-ml-pharmacometrics</a> · Data curated via PubMed + Claude classification · Last updated <span id="lastUpdated"></span></div></footer>
<script>
const DATA = """
        + compact_json
        + """;
let state = { selectedApp: null, selectedMeth: null, searchQuery: '', reviewFilter: 'all' };
function init() {
  document.getElementById('lastUpdated').textContent = DATA.lastUpdated;
  const nonReview = DATA.papers.filter(p => !p.is_review);
  const reviews = DATA.papers.filter(p => p.is_review);
  document.getElementById('stats').innerHTML = `
    <div class="stat"><span class="stat-value">${DATA.papers.length}</span><span class="stat-label">Total papers</span></div>
    <div class="stat"><span class="stat-value">${nonReview.length}</span><span class="stat-label">Original research</span></div>
    <div class="stat"><span class="stat-value">${reviews.length}</span><span class="stat-label">Reviews & perspectives</span></div>
    <div class="stat"><span class="stat-value">${DATA.applications.length}</span><span class="stat-label">Application areas</span></div>
    <div class="stat"><span class="stat-value">${DATA.methodologies.length}</span><span class="stat-label">Methodology types</span></div>`;
  renderHeatmap(); renderPapers();
  document.getElementById('searchBox').addEventListener('input', (e) => { state.searchQuery = e.target.value.toLowerCase(); renderPapers(); });
}
function getHeatColor(value, maxVal) {
  if (value === 0) return 'var(--heat-0)';
  const ratio = Math.log(value + 1) / Math.log(maxVal + 1);
  if (ratio < 0.15) return 'var(--heat-1)';
  if (ratio < 0.3) return 'var(--heat-2)';
  if (ratio < 0.5) return 'var(--heat-3)';
  if (ratio < 0.75) return 'var(--heat-4)';
  return 'var(--heat-5)';
}
function escAttr(s) { return s.replace(/'/g, "\\\\'").replace(/"/g, '&quot;'); }
function renderHeatmap() {
  const apps = DATA.applications, meths = DATA.methodologies, matrix = DATA.matrix;
  let maxVal = 0;
  apps.forEach(app => meths.forEach(meth => { maxVal = Math.max(maxVal, matrix[app]?.[meth] || 0); }));
  let html = '<thead><tr><th class="corner"></th>';
  meths.forEach(meth => { html += `<th class="col-header ${state.selectedMeth === meth ? 'active' : ''}" onclick="clickMeth('${escAttr(meth)}')" title="${meth}">${meth}</th>`; });
  html += '<th class="col-header total-header">Total</th></tr></thead><tbody>';
  apps.forEach(app => {
    html += `<tr><th class="row-header ${state.selectedApp === app ? 'active' : ''}" onclick="clickApp('${escAttr(app)}')" title="${app}">${app}</th>`;
    let rowTotal = 0;
    meths.forEach(meth => {
      const val = matrix[app]?.[meth] || 0; rowTotal += val;
      const isActive = state.selectedApp === app && state.selectedMeth === meth;
      html += `<td class="${val === 0 ? 'zero' : ''} ${isActive ? 'active' : ''}" style="background:${getHeatColor(val, maxVal)};color:${val === 0 ? 'var(--text-muted)' : '#fff'}" onclick="clickCell('${escAttr(app)}','${escAttr(meth)}')" title="${app} × ${meth}: ${val} papers">${val}</td>`;
    });
    html += `<td class="row-total">${rowTotal}</td></tr>`;
  });
  html += '</tbody>';
  document.getElementById('heatmap').innerHTML = html;
}
function clickCell(app, meth) { if (state.selectedApp === app && state.selectedMeth === meth) { clearFilters(); return; } state.selectedApp = app; state.selectedMeth = meth; update(); }
function clickApp(app) { if (state.selectedApp === app && !state.selectedMeth) { clearFilters(); return; } state.selectedApp = app; state.selectedMeth = null; update(); }
function clickMeth(meth) { if (state.selectedMeth === meth && !state.selectedApp) { clearFilters(); return; } state.selectedApp = null; state.selectedMeth = meth; update(); }
function clearFilters() { state.selectedApp = null; state.selectedMeth = null; update(); }
function update() { renderHeatmap(); renderFilterBar(); renderPapers(); }
function renderFilterBar() {
  const el = document.getElementById('activeFilter'), tags = document.getElementById('filterTags');
  if (!state.selectedApp && !state.selectedMeth) { el.classList.remove('visible'); return; }
  el.classList.add('visible');
  let html = '';
  if (state.selectedApp) html += `<span class="filter-tag"><span class="type-label">App</span>${state.selectedApp}</span>`;
  if (state.selectedMeth) html += `<span class="filter-tag"><span class="type-label">Method</span>${state.selectedMeth}</span>`;
  tags.innerHTML = html;
}
function toggleReview(mode) { state.reviewFilter = mode; document.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active')); event.target.classList.add('active'); renderPapers(); }
function parsePubDate(d) {
  if (!d) return 0;
  const months = {Jan:0,Feb:1,Mar:2,Apr:3,May:4,Jun:5,Jul:6,Aug:7,Sep:8,Oct:9,Nov:10,Dec:11};
  const m = d.match(/(\\d{4})(\\w{3})?(\\d{1,2})?/);
  if (!m) return 0;
  return new Date(parseInt(m[1]), m[2] ? (months[m[2]] || 0) : 0, m[3] ? parseInt(m[3]) : 1).getTime();
}
function getFilteredPapers() {
  let papers = DATA.papers;
  if (state.selectedApp) papers = papers.filter(p => p.applications.includes(state.selectedApp));
  if (state.selectedMeth) papers = papers.filter(p => p.methodologies.includes(state.selectedMeth));
  if (state.reviewFilter === 'original') papers = papers.filter(p => !p.is_review);
  else if (state.reviewFilter === 'review') papers = papers.filter(p => p.is_review);
  if (state.searchQuery) papers = papers.filter(p => p.title.toLowerCase().includes(state.searchQuery) || p.summary.toLowerCase().includes(state.searchQuery));
  papers.sort((a, b) => parsePubDate(b.published) - parsePubDate(a.published));
  return papers;
}
function renderPapers() {
  const papers = getFilteredPapers();
  document.getElementById('paperCount').innerHTML = `Showing <strong>${papers.length}</strong> of ${DATA.papers.length} papers`;
  const grid = document.getElementById('papersGrid');
  if (papers.length === 0) { grid.innerHTML = '<div class="no-results">No papers match the current filters.</div>'; return; }
  const shown = papers.slice(0, 100);
  grid.innerHTML = shown.map(p => `<div class="paper-card"><div class="paper-title"><a href="${p.url}" target="_blank">${p.title}</a></div><div class="paper-meta">${p.published ? `<span class="tag tag-date">${p.published}</span>` : ''}${p.is_review ? '<span class="tag tag-review">Review</span>' : ''}${p.applications.map(a => `<span class="tag tag-app">${a}</span>`).join('')}${p.methodologies.map(m => `<span class="tag tag-meth">${m}</span>`).join('')}</div>${p.summary ? `<div class="paper-summary">${p.summary}</div>` : ''}</div>`).join('') + (papers.length > 100 ? `<div class="no-results">Showing first 100 of ${papers.length} results. Use search to narrow down.</div>` : '');
}
init();
</script>
</body>
</html>"""
    )


def main():
    parser = argparse.ArgumentParser(description="Build interactive AI/ML Pharmacometrics explorer")
    parser.add_argument("--readme", default="README.md", help="Path to source README.md")
    parser.add_argument("--output", default="index.html", help="Output HTML file path")
    args = parser.parse_args()

    print(f"📖 Parsing {args.readme}...")
    data = parse_readme(args.readme)

    print(
        f"   Found {len(data['papers'])} papers, "
        f"{len(data['applications'])} applications, "
        f"{len(data['methodologies'])} methodologies"
    )

    print(f"🔨 Generating {args.output}...")
    html = generate_html(data)

    with open(args.output, "w") as f:
        f.write(html)

    print(f"✅ Done! {len(html):,} bytes written to {args.output}")


if __name__ == "__main__":
    main()
