#!/usr/bin/env python3
"""Генерирует SVG-карточки статистики GitHub (без внешних сервисов).
Запускается GitHub Actions, результат кладётся в assets/."""
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

# ---------- основные данные ----------
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

# ---------- стрик по всем годам ----------
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
# текущий стрик (сегодня ещё может быть 0 — не считаем это разрывом)
cur = 0
d = today
if days.get(d.isoformat(), 0) == 0:
    d -= datetime.timedelta(days=1)
while days.get(d.isoformat(), 0) > 0:
    cur += 1
    d -= datetime.timedelta(days=1)

# ---------- SVG ----------
BG, BORDER, ORANGE, TXT, MUTED = "#0d1117", "#30363d", "#ff8c00", "#c9d1d9", "#8b949e"
FONT = "font-family:'Segoe UI',Arial,sans-serif"

def card(w, h, title, body):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<style>.t{{{FONT};font-size:18px;font-weight:700;fill:{ORANGE}}}.l{{{FONT};font-size:14px;fill:{TXT}}}
.v{{{FONT};font-size:14px;font-weight:700;fill:{ORANGE}}}.m{{{FONT};font-size:12px;fill:{MUTED}}}
.big{{{FONT};font-size:34px;font-weight:700;fill:{ORANGE}}}
.f{{animation:fade .8s ease-out both}}@keyframes fade{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}</style>
<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="10" fill="{BG}" stroke="{BORDER}"/>
<text class="t" x="20" y="32">{html.escape(title)}</text>
{body}
</svg>'''

# stats
rows = [
    ("⭐ Звёзд", stars),
    ("📦 Репозиториев", main["repositories"]["totalCount"]),
    ("🔨 Коммитов (за год)", main["contributionsCollection"]["totalCommitContributions"]),
    ("🔀 Pull Request’ов", main["contributionsCollection"]["totalPullRequestContributions"]),
    ("🐞 Issues", main["contributionsCollection"]["totalIssueContributions"]),
    ("👥 Подписчиков", main["followers"]["totalCount"]),
]
body = ""
for i, (k, v) in enumerate(rows):
    y = 62 + i * 26
    body += f'<g class="f" style="animation-delay:{i*.1}s"><text class="l" x="20" y="{y}">{k}</text><text class="v" x="370" y="{y}" text-anchor="end">{v}</text></g>'
open(f"{OUT}/stats.svg", "w", encoding="utf-8").write(card(390, 225, f"Статистика {USER}", body))

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
open(f"{OUT}/langs.svg", "w", encoding="utf-8").write(card(390, 225, "Топ языков", body))

# streak
def col(x, num, label, sub):
    return (f'<text class="big" x="{x}" y="85" text-anchor="middle">{num}</text>'
            f'<text class="l" x="{x}" y="112" text-anchor="middle">{label}</text>'
            f'<text class="m" x="{x}" y="132" text-anchor="middle">{sub}</text>')
le = longest_end.strftime("%d.%m.%Y") if longest_end else "—"
body = (col(130, total_contrib, "Всего вкладов", "за всё время")
        + col(400, cur, "Текущий стрик", "дней подряд")
        + col(670, longest, "Лучший стрик", f"до {le}")
        + f'<line x1="265" y1="55" x2="265" y2="140" stroke="{BORDER}"/><line x1="535" y1="55" x2="535" y2="140" stroke="{BORDER}"/>')
open(f"{OUT}/streak.svg", "w", encoding="utf-8").write(card(800, 160, "🔥 Стрик", body))
print("ok", stars, total_contrib, cur, longest)
