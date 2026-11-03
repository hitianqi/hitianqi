"""Render the profile README's neofetch-style terminal as assets/neofetch.svg."""

import base64
import json
import os
import urllib.request
from collections import Counter
from datetime import date, datetime, timezone
from xml.sax.saxutils import escape

LOGIN = os.environ.get("LOGIN", "hitianqi")
TOKEN = os.environ["GH_TOKEN"]
HERE = os.path.dirname(os.path.abspath(__file__))
# Notebook bytes are mostly cell output, not code.
SKIP_LANGUAGES = {"Jupyter Notebook"}
SHORT = {"JavaScript": "JS", "Jupyter Notebook": "Jupyter"}

COLS, CW, LH, FS = 90, 8.4, 20, 14
PAD, TITLE, TOP = 24, 36, 18
INFO_COL = 38
HEAT_STATS_COL = 57

C = dict(bg="#0b0d10", title="#12151a", ring="#ffffff14", fg="#c8ccd4", dim="#5c6370",
         key="#7aa2f7", user="#ff9e64", ok="#9ece6a", empty="#1a1e24")
HEAT = ["#0e4429", "#006d32", "#26a641", "#39d353"]
LOGO_FROM, LOGO_TO = (0xff, 0x9e, 0x64), (0xbb, 0x9a, 0xf7)
SWATCHES = [["#15161e", "#f7768e", "#9ece6a", "#e0af68", "#7aa2f7", "#bb9af7", "#7dcfff", "#a9b1d6"],
            ["#414868", "#ff7a93", "#b9f27c", "#ff9e64", "#7da6ff", "#c0a8ff", "#0db9d7", "#c0caf5"]]

# "TZ" in JetBrains Mono ExtraBold, rasterised once onto a 35x10 character grid.
LOGO = """\
@@@@@@@@@@@@@@@@#   :@@@@@@@@@@@@@*
%%%%%%@@@@@%%%%%*   :%%%%%%%%@@@@@*
     .@@@@#                 *@@@@*.
      @@@@#               :%@@@@=
      @@@@#              +@@@@#.
      @@@@#            .#@@@@+
      @@@@#           -@@@@%:
      @@@@#          *@@@@*.
      @@@@#         +@@@@@%%%%%%%%%
      @@@@#         +@@@@@@@@@@@@@@""".split("\n")


def graphql(query):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"bearer {TOKEN}"},
    )
    with urllib.request.urlopen(req) as res:
        body = json.load(res)
    if "errors" in body:
        raise SystemExit(f"GraphQL error: {body['errors']}")
    return body["data"]["user"]


def fetch():
    user = graphql(f"""{{ user(login: "{LOGIN}") {{
      createdAt
      pullRequests {{ totalCount }}
      repositories(ownerAffiliations: OWNER, isFork: false, first: 100) {{
        totalCount
        nodes {{ languages(first: 10, orderBy: {{field: SIZE, direction: DESC}}) {{
          edges {{ size node {{ name color }} }} }} }}
      }}
      contributionsCollection {{ contributionCalendar {{
        totalContributions weeks {{ contributionDays {{ date contributionCount }} }} }} }}
    }} }}""")

    created = datetime.fromisoformat(user["createdAt"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    years = "\n".join(
        f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{min(now.isoformat(), f"{y}-12-31T23:59:59+00:00")}")'
        " { totalCommitContributions restrictedContributionsCount }"
        for y in range(created.year, now.year + 1)
    )
    per_year = graphql(f'{{ user(login: "{LOGIN}") {{ {years} }} }}')
    commits = sum(c["totalCommitContributions"] + c["restrictedContributionsCount"] for c in per_year.values())

    sizes, colors = Counter(), {}
    for repo in user["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name not in SKIP_LANGUAGES:
                sizes[name] += edge["size"]
                colors[name] = edge["node"]["color"] or C["fg"]
    total = sum(sizes.values()) or 1

    cal = user["contributionsCollection"]["contributionCalendar"]
    return dict(
        created=created, now=now, commits=commits,
        prs=user["pullRequests"]["totalCount"], repos=user["repositories"]["totalCount"],
        languages=[(n, s / total, colors[n]) for n, s in sizes.most_common(4)],
        contributions=cal["totalContributions"],
        weeks=[[(date.fromisoformat(d["date"]), d["contributionCount"]) for d in w["contributionDays"]] for w in cal["weeks"]],
    )


# --- small helpers -----------------------------------------------------------

def x(col):
    return PAD + col * CW


def y(row):
    return TITLE + TOP + row * LH + 15


def mix(a, b, t):
    return "#" + "".join(f"{round(a[i] + (b[i] - a[i]) * t):02x}" for i in range(3))


def readable(hex_colour):
    """Lighten a language colour until it reads on the dark background."""
    rgb = tuple(int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    t = 0.0
    while t < 1:
        r, g, b = (c + (255 - c) * t for c in rgb)
        if 0.2126 * r + 0.7152 * g + 0.0722 * b >= 110:
            break
        t += 0.1
    return mix(rgb, (255, 255, 255), t)


def span(text, colour=None, bold=False):
    attrs = (f' fill="{colour}"' if colour else "") + (' font-weight="700"' if bold else "")
    return f"<tspan{attrs}>{escape(text)}</tspan>"


def line(row, col, parts, delay):
    return f'<text x="{x(col):.1f}" y="{y(row)}" class="ln" style="animation-delay:{delay:.2f}s">{"".join(parts)}</text>'


def prompt(cmd=""):
    return [span("tianqi", C["user"], True), span("@github", C["user"]), span(":", C["dim"]),
            span("~", C["key"]), span("$ ", C["dim"]), span(cmd)]


def typed(row, cmd, start, n):
    """A prompt whose command types out once, one character every 45 ms."""
    col = len("tianqi@github:~$ ")
    step = 0.045
    widths = ";".join(f"{i * CW:.1f}" for i in range(len(cmd) + 1))
    return (line(row, 0, prompt(), start)
            + f'<clipPath id="c{n}"><rect x="{x(col):.1f}" y="{y(row) - 15}" height="{LH}" width="0">'
            f'<animate attributeName="width" values="{widths}" begin="{start:.2f}s" dur="{len(cmd) * step:.2f}s" calcMode="discrete" fill="freeze"/>'
            f'</rect></clipPath><g clip-path="url(#c{n})"><text x="{x(col):.1f}" y="{y(row)}">{escape(cmd)}</text></g>',
            start + len(cmd) * step + 0.25)


def streaks(days):
    longest = run = 0
    for _, n in days:
        run = run + 1 if n else 0
        longest = max(longest, run)
    current = 0
    for i, (_, n) in enumerate(reversed(days)):
        if n:
            current += 1
        elif i:  # today may still be empty
            break
    return longest, current


# --- the picture -------------------------------------------------------------

def render(d):
    out, t = [], 0.2
    cmd, t = typed(0, "neofetch", t, 1)
    out.append(cmd)

    # logo
    for i, row in enumerate(LOGO):
        out.append(line(2 + i, 0, [span(row, mix(LOGO_FROM, LOGO_TO, i / (len(LOGO) - 1)), True)], t + i * 0.02))

    # info
    months = (d["now"].year - d["created"].year) * 12 + d["now"].month - d["created"].month - (d["now"].day < d["created"].day)
    uptime = ", ".join(f"{n} {u}{'s' if n != 1 else ''}" for n, u in ((months // 12, "year"), (months % 12, "month")) if n)
    langs = []
    for name, share, colour in d["languages"]:
        langs += [span(SHORT.get(name, name), readable(colour)), span(f" {share * 100:.0f}%  ", C["dim"])]

    kv = lambda k, *v: [span(k.ljust(10), C["key"], True), *v]
    info = [
        [span("tianqi", C["user"], True), span("@", C["dim"]), span("github", C["user"], True)],
        [span("─" * 13, C["dim"])],
        kv("Role", span("AI Engineer @ Prover")),
        kv("Location", span("Stockholm, Sweden")),
        kv("Uptime", span(uptime)),
        kv("Repos", span(str(d["repos"]))),
        kv("Commits", span(f"{d['commits']:,}")),
        kv("PRs", span(f"{d['prs']:,}")),
        kv("Langs", *langs),
        kv("Building", span("tools for coding agents")),
        kv("Web", span("tianqiz.me")),
        kv("LinkedIn", span("in/terryonzhao")),
    ]
    for i, parts in enumerate(info):
        out.append(line(2 + i, INFO_COL, parts, t + i * 0.02))
    swatch_row = 2 + len(info) + 1
    for r, colours in enumerate(SWATCHES):
        cells = "".join(f'<rect x="{x(INFO_COL + i * 3):.1f}" y="{y(swatch_row + r) - 14}" width="{3 * CW:.1f}" height="{LH - 2}" fill="{c}"/>'
                        for i, c in enumerate(colours))
        out.append(f'<g class="ln" style="animation-delay:{t + (len(info) + r) * 0.02:.2f}s">{cells}</g>')
    t += 0.6

    # contributions
    row = swatch_row + 3
    cmd, t = typed(row, "git contrib --since=1.year", t, 2)
    out.append(cmd)
    weeks = d["weeks"]
    nonzero = sorted(n for w in weeks for _, n in w if n)
    cuts = [nonzero[int((len(nonzero) - 1) * f)] for f in (.25, .5, .75)] if nonzero else [1, 1, 1]
    level = lambda n: 0 if n == 0 else 1 + sum(n > c for c in cuts)

    labels, last = [], -9
    for i, w in enumerate(weeks):
        first = w[0][0]
        if (i == 0 or first.month != weeks[i - 1][0][0].month) and i - last >= 5 and i + 3 <= len(weeks):
            labels.append(f'<text x="{x(i):.1f}" y="{y(row + 1)}" fill="{C["dim"]}">{first.strftime("%b")}</text>')
            last = i
    out.append(f'<g class="ln" style="animation-delay:{t:.2f}s">{"".join(labels)}</g>')

    top = y(row + 2) - 15
    for i, w in enumerate(weeks):
        cells = "".join(
            f'<rect x="{x(i) + .5:.1f}" y="{top + wd * 10 + .5:.1f}" width="{CW - 1.4:.1f}" height="9" rx="1.5" '
            f'fill="{HEAT[level(n) - 1] if n else C["empty"]}"/>'
            for day, n in w for wd in [(day.isoweekday() % 7)]
        )
        out.append(f'<g class="ln" style="animation-delay:{t + i * 0.012:.3f}s">{cells}</g>')

    days = [day for w in weeks for day in w]
    longest, current = streaks(days)
    best_day, best = max(days, key=lambda p: p[1])
    stats = [
        [span(f"{d['contributions']:,}", C["ok"], True), span(" contributions")],
        [span("longest streak".ljust(17), C["dim"]), span(f"{longest} days")],
        [span("current streak".ljust(17), C["dim"]), span(f"{current} day{'s' if current != 1 else ''}")],
        [span("best day".ljust(17), C["dim"]), span(f"{best_day.strftime('%b')} {best_day.day} · {best}")],
    ]
    t2 = t + len(weeks) * 0.012
    for i, parts in enumerate(stats):
        out.append(line(row + 2 + i, HEAT_STATS_COL, parts, t2 + i * 0.03))

    legend_row = row + 6
    legend = [span("less ", C["dim"])]
    out.append(line(legend_row, 0, legend, t2))
    out.append(f'<g class="ln" style="animation-delay:{t2:.2f}s">' + "".join(
        f'<rect x="{x(5 + i) + .5:.1f}" y="{y(legend_row) - 10}" width="{CW - 1.4:.1f}" height="9" rx="1.5" fill="{c}"/>'
        for i, c in enumerate([C["empty"], *HEAT])) + "</g>")
    out.append(line(legend_row, 11, [span("more", C["dim"])], t2))

    end = legend_row + 2
    t2 += 0.3
    out.append(line(end, 0, prompt(), t2))
    out.append(f'<rect class="ln" style="animation-delay:{t2:.2f}s" x="{x(17):.1f}" y="{y(end) - 14}" width="{CW:.1f}" height="18" fill="{C["fg"]}"/>')

    rows = end + 1
    w, h = PAD * 2 + COLS * CW, TITLE + TOP * 2 + rows * LH
    fonts = "".join(
        f"@font-face{{font-family:JBM;font-weight:{wt};src:url(data:font/woff;base64,"
        f"{base64.b64encode(open(os.path.join(HERE, 'fonts', f'jbm-{wt}.woff'), 'rb').read()).decode()}) format('woff')}}"
        for wt in (400, 700))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h}" viewBox="0 0 {w:.0f} {h}" role="img" aria-label="neofetch for tianqi@github: AI Engineer at Prover, Stockholm. {d['commits']} commits, {d['prs']} pull requests, {d['contributions']} contributions in the last year.">
<style>
{fonts}
text {{ font-family: JBM, ui-monospace, 'SF Mono', Menlo, Consolas, monospace; font-size: {FS}px; fill: {C['fg']}; white-space: pre; }}
.ln {{ opacity: 0; animation: show .01s step-end forwards; }}
@keyframes show {{ to {{ opacity: 1; }} }}
@media (prefers-reduced-motion: reduce) {{ .ln {{ animation: none; opacity: 1; }} }}
</style>
<clipPath id="win"><rect width="{w:.0f}" height="{h}" rx="12"/></clipPath>
<g clip-path="url(#win)">
  <rect width="{w:.0f}" height="{h}" fill="{C['bg']}"/>
  <rect width="{w:.0f}" height="{TITLE}" fill="{C['title']}"/>
</g>
<rect x=".5" y=".5" width="{w - 1:.0f}" height="{h - 1}" rx="11.5" fill="none" stroke="{C['ring']}"/>
{''.join(f'<circle cx="{20 + i * 18}" cy="{TITLE / 2}" r="5.5" fill="#2b3038"/>' for i in range(3))}
<text x="{w / 2:.0f}" y="{TITLE / 2 + 4.5}" text-anchor="middle" font-size="12" fill="{C['dim']}">tianqi@github: ~ — {COLS}×{rows}</text>
<g xml:space="preserve">
{chr(10).join(out)}
</g>
</svg>
"""


def main():
    data = fetch()
    out = os.path.join(HERE, "..", "assets")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "neofetch.svg"), "w") as f:
        f.write(render(data))
    print(json.dumps({k: data[k] for k in ("commits", "prs", "repos", "contributions")}))


if __name__ == "__main__":
    main()
