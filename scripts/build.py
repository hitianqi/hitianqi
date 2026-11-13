"""Render the profile as a man page, `man tianqi`, in light and dark SVGs into assets/."""

import json
import os
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from xml.sax.saxutils import escape

LOGIN = os.environ.get("LOGIN", "hitianqi")
TOKEN = os.environ["GH_TOKEN"]
# Notebook bytes are mostly cell output, not code.
SKIP_LANGUAGES = {"Jupyter Notebook"}

MONO = "ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, monospace"
EASE = "cubic-bezier(.22,1,.36,1)"

THEMES = {
    "light": dict(panel="#f6f6f7", ink="#0b0b0d", muted="#6b6b74", track="rgba(0,0,0,.08)"),
    "dark": dict(panel="#0e0f13", ink="#e8e8ea", muted="#9b9ba5", track="rgba(255,255,255,.08)"),
}


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
          edges {{ size node {{ name }} }} }} }}
      }}
    }} }}""")

    start = datetime.fromisoformat(user["createdAt"].replace("Z", "+00:00")).year
    now = datetime.now(timezone.utc)
    years = "\n".join(
        f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{min(now.isoformat(), f"{y}-12-31T23:59:59+00:00")}")'
        " { totalCommitContributions restrictedContributionsCount }"
        for y in range(start, now.year + 1)
    )
    per_year = graphql(f'{{ user(login: "{LOGIN}") {{ {years} }} }}')
    commits = sum(c["totalCommitContributions"] + c["restrictedContributionsCount"] for c in per_year.values())

    sizes = Counter()
    for repo in user["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name not in SKIP_LANGUAGES:
                sizes[name] += edge["size"]
    total = sum(sizes.values()) or 1
    top = [(n, s / total) for n, s in sizes.most_common(4)]

    return dict(commits=commits, prs=user["pullRequests"]["totalCount"],
                repos=user["repositories"]["totalCount"], languages=top, date=now.strftime("%B %Y"))


def man_page(t, data):
    left, indent, right = 48, 104, 832
    lines, y = [], 44

    def line(body, gap=20):
        nonlocal y
        lines.append(f'<g class="in" style="animation-delay:{len(lines) * .04:.2f}s">{body(y)}</g>')
        y += gap

    def text(x, s, fill=t["ink"], extra=""):
        return lambda y: f'<text x="{x}" y="{y}" class="mono" font-size="13" fill="{fill}"{extra}>{s}</text>'

    def ends(a, b, c):
        return lambda y: (
            f'<text x="{left}" y="{y}" class="mono" font-size="13" fill="{t["muted"]}">{a}</text>'
            f'<text x="440" y="{y}" text-anchor="middle" class="mono" font-size="13" fill="{t["muted"]}">{b}</text>'
            f'<text x="{right}" y="{y}" text-anchor="end" class="mono" font-size="13" fill="{t["muted"]}">{c}</text>')

    def section(title, body, gap=40):
        line(text(left, title, extra=' font-weight="700"'))
        line(text(indent, body), gap)

    b = '<tspan font-weight="700">{}</tspan>'.format
    u = '<tspan text-decoration="underline">{}</tspan>'.format
    line(ends("TIANQI(1)", "General Commands Manual", "TIANQI(1)"), 40)
    section("NAME", f"{b('tianqi')} - AI Engineer, Stockholm, Sweden")
    section("SYNOPSIS", f"{b('tianqi')} [{u('--build')} tools] [{u('--for')} coding-agents] [{u('--watch')}]")
    section("DESCRIPTION", "Builds tools for coding agents you can actually watch.")
    section("STATISTICS", f"{data['commits']:,} commits, {data['prs']:,} pull requests, {data['repos']} repositories.", 24)
    for name, share in data["languages"]:
        line(lambda y, name=name, share=share: (
            f'<text x="{indent}" y="{y}" class="mono" font-size="13" fill="{t["muted"]}">{escape(name)}</text>'
            f'<rect x="224" y="{y - 9}" width="400" height="9" fill="{t["track"]}"/>'
            f'<rect x="224" y="{y - 9}" width="{max(400 * share, 2):.1f}" height="9" fill="{t["ink"]}"/>'
            f'<text x="676" y="{y}" text-anchor="end" class="mono num" font-size="13" fill="{t["muted"]}">{share * 100:.0f}%</text>'), 19)
    y += 21
    section("SEE ALSO", f"{u('tianqiz.me')}(7), {u('linkedin')}(7)")
    line(ends(LOGIN, data["date"], "TIANQI(1)"), 24)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="880" height="{y}" viewBox="0 0 880 {y}" role="img" aria-label="tianqi(1): Tianqi Zhao, AI Engineer, Stockholm. {data['commits']} commits, {data['prs']} pull requests.">
<style>
  .mono {{ font-family: {MONO}; }}
  .num {{ font-variant-numeric: tabular-nums; }}
  .in {{ opacity: 0; animation: in .45s {EASE} forwards; }}
  @keyframes in {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: none; }} }}
  @media (prefers-reduced-motion: reduce) {{ .in {{ animation: none; opacity: 1; }} }}
</style>
<rect width="880" height="{y}" rx="6" fill="{t['panel']}"/>
{''.join(lines)}
</svg>
"""


def main():
    data = fetch()
    out = os.path.join(os.path.dirname(__file__), "..", "assets")
    os.makedirs(out, exist_ok=True)
    for name, t in THEMES.items():
        with open(os.path.join(out, f"man-{name}.svg"), "w") as f:
            f.write(man_page(t, data))
    print(json.dumps(data))


if __name__ == "__main__":
    main()
