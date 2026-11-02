#!/usr/bin/env python3
"""Generates GitHub stats SVG cards (no external services).
Run by GitHub Actions; output goes to assets/."""
import json, os, urllib.request, datetime, html

USER = os.environ.get("GH_USER", "Bread11YT")
TOKEN = os.environ["GH_TOKEN"]
OUT = os.environ.get("OUT_DIR", "assets")

def gql(query, variables=None):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": "stats-gen"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(data["errors"])
    return data["data"]

# ---------- main data ----------
main = gql("""
query($u:String!){ user(login:$u){
  name followers{totalCount}
  contributionsCollection{ contributionYears totalCommitContributions
    totalPullRequestContributions totalIssueContributions }
  repositories(ownerAffiliations:OWNER, isFork:false, first:100){
    totalCount
    nodes{ stargazerCount
      languages(first:10, orderBy:{field:SIZE, direction:DESC}){ edges{ size node{ name color } } } }
  }
}}""", {"u": USER})["user"]

repos = main["repositories"]["nodes"]
stars = sum(r["stargazerCount"] for r in repos)

langs = {}
for r in repos:
    for e in r["languages"]["edges"]:
        n = e["node"]["name"]
        langs.setdefault(n, [0, e["node"]["color"] or "#8b949e"])
        langs[n][0] += e["size"]
top = sorted(langs.items(), key=lambda kv: -kv[1][0])[:6]
total_size = sum(v[0] for _, v in top) or 1

# ---------- streak across all years ----------
days = {}
for y in main["contributionsCollection"]["contributionYears"]:
    d = gql("""query($u:String!,$f:DateTime!,$t:DateTime!){ user(login:$u){
      contributionsCollection(from:$f,to:$t){ contributionCalendar{ totalContributions
        weeks{ contributionDays{ date contributionCount } } } } } }""",
        {"u": USER, "f": f"{y}-01-01T00:00:00Z", "t": f"{y}-12-31T23:59:59Z"})
    cal = d["user"]["contributionsCollection"]["contributionCalendar"]
    for w in cal["weeks"]:
        for c in w["contributionDays"]:
            days[c["date"]] = c["contributionCount"]

total_contrib = sum(days.values())
today = datetime.date.today()
longest = cur = 0
longest_end = None
d0 = min(map(datetime.date.fromisoformat, days)) if days else today
d = d0
while d <= today:
    if days.get(d.isoformat(), 0) > 0:
        cur += 1
        if cur > longest:
            longest, longest_end = cur, d
    else:
        cur = 0
    d += datetime.timedelta(days=1)
# current streak (today may still be 0 - not a break)
cur = 0
d = today
if days.get(d.isoformat(), 0) == 0:
    d -= datetime.timedelta(days=1)
while days.get(d.isoformat(), 0) > 0:
    cur += 1
    d -= datetime.timedelta(days=1)

# ---------- SVG ----------
BG, BORDER, GREEN, TXT, MUTED = "#0d1117", "#1f3a2b", "#3ddc84", "#c9d1d9", "#7d8f86"
FONT = "font-family:'Segoe UI',Arial,sans-serif"

def card(w, h, title, body):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<style>.t{{{FONT};font-size:18px;font-weight:700;fill:{GREEN}}}.l{{{FONT};font-size:14px;fill:{TXT}}}
.v{{{FONT};font-size:14px;font-weight:700;fill:{GREEN}}}.m{{{FONT};font-size:12px;fill:{MUTED}}}
.big{{{FONT};font-size:34px;font-weight:700;fill:{GREEN}}}
.f{{animation:fade .8s ease-out both}}@keyframes fade{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}</style>
<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="10" fill="{BG}" stroke="{BORDER}"/>
<text class="t" x="20" y="32">{html.escape(title)}</text>
{body}
</svg>'''

# stats
rows = [
    ("⭐ Total Stars", stars),
    ("📦 Repositories", main["repositories"]["totalCount"]),
    ("🔨 Commits (last year)", main["contributionsCollection"]["totalCommitContributions"]),
    ("🔀 Pull Requests", main["contributionsCollection"]["totalPullRequestContributions"]),
    ("🐞 Issues", main["contributionsCollection"]["totalIssueContributions"]),
    ("👥 Followers", main["followers"]["totalCount"]),
]
body = ""
for i, (k, v) in enumerate(rows):
    y = 62 + i * 26
    body += f'<g class="f" style="animation-delay:{i*.1}s"><text class="l" x="20" y="{y}">{k}</text><text class="v" x="370" y="{y}" text-anchor="end">{v}</text></g>'
open(f"{OUT}/stats.svg", "w", encoding="utf-8").write(card(390, 225, f"{USER}'s Stats", body))

# langs
body = ""
x = 20
bar = ""
for name, (size, color) in top:
    wd = 350 * size / total_size
    bar += f'<rect x="{x:.1f}" y="48" width="{wd:.1f}" height="10" fill="{color}"/>'
    x += wd
body += f'<clipPath id="r"><rect x="20" y="48" width="350" height="10" rx="5"/></clipPath><g clip-path="url(#r)">{bar}</g>'
for i, (name, (size, color)) in enumerate(top):
    col, row = i % 2, i // 2
    cx, cy = 20 + col * 180, 90 + row * 30
    body += f'<circle cx="{cx+5}" cy="{cy-5}" r="5" fill="{color}"/><text class="l" x="{cx+16}" y="{cy}">{html.escape(name)}</text><text class="m" x="{cx+165}" y="{cy}" text-anchor="end">{100*size/total_size:.1f}%</text>'
open(f"{OUT}/langs.svg", "w", encoding="utf-8").write(card(390, 225, "Top Languages", body))

# streak
def col(x, num, label, sub):
    return (f'<text class="big" x="{x}" y="85" text-anchor="middle">{num}</text>'
            f'<text class="l" x="{x}" y="112" text-anchor="middle">{label}</text>'
            f'<text class="m" x="{x}" y="132" text-anchor="middle">{sub}</text>')
le = longest_end.strftime("%b %d, %Y") if longest_end else "—"
body = (col(130, total_contrib, "Total Contributions", "all time")
        + col(400, cur, "Current Streak", "days in a row")
        + col(670, longest, "Longest Streak", f"until {le}")
        + f'<line x1="265" y1="55" x2="265" y2="140" stroke="{BORDER}"/><line x1="535" y1="55" x2="535" y2="140" stroke="{BORDER}"/>')
open(f"{OUT}/streak.svg", "w", encoding="utf-8").write(card(800, 160, "🔥 Contribution Streak", body))
print("ok", stars, total_contrib, cur, longest)
