"""Render the profile header and stats strip as light and dark SVGs into assets/."""

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

SANS = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Inter, 'Helvetica Neue', Arial, sans-serif"
MONO = "ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, monospace"
EASE = "cubic-bezier(.22,1,.36,1)"

THEMES = {
    "light": dict(panel="#f6f6f7", ink="#0b0b0d", muted="#6b6b74", faint="#a3a3ab",
                  ring="rgba(0,0,0,.06)", window="#ffffff", chrome="#e6e6e9",
                  wash_a="#8b7bff", wash_b="#ffb08a", wash_op=".5"),
    "dark": dict(panel="#0e0f13", ink="#f2f2f4", muted="#9b9ba5", faint="#5d5d68",
                 ring="rgba(255,255,255,.07)", window="#16171c", chrome="#2a2b32",
                 wash_a="#6d5cff", wash_b="#ff8a5c", wash_op=".42"),
}
STATE = {"passed": "#22c55e", "working": "#3b82f6", "waiting": "#f59e0b"}


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

    sizes, colors = Counter(), {}
    for repo in user["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name not in SKIP_LANGUAGES:
                sizes[name] += edge["size"]
                colors[name] = edge["node"]["color"] or "#8b8b94"
    total = sum(sizes.values()) or 1
    top = [(n, s / total, colors[n]) for n, s in sizes.most_common(4)]
    rest = 1 - sum(share for _, share, _ in top)
    if rest >= 0.005:
        top.append(("Other", rest, None))

    return dict(commits=commits, prs=user["pullRequests"]["totalCount"],
                repos=user["repositories"]["totalCount"], languages=top)


def style(t):
    return f"""<style>
  .sans {{ font-family: {SANS}; }}
  .mono {{ font-family: {MONO}; }}
  .num {{ font-variant-numeric: tabular-nums; }}
  .in {{ opacity: 0; animation: in .5s {EASE} forwards; }}
  @keyframes in {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}
  @media (prefers-reduced-motion: reduce) {{ .in {{ animation: none; opacity: 1; }} }}
</style>"""


def hero(t):
    rows = [("planner", "plan approved, 4 steps", "passed"),
            ("builder", "editing panel.ts", "working"),
            ("reviewer", "waiting for you", "waiting")]
    wx, wy, ww, wh = 492, 40, 348, 200
    row_svg = "".join(
        f'<g class="in" style="animation-delay:{.35 + i * .12:.2f}s">'
        f'<circle cx="{wx + 22}" cy="{wy + 64 + i * 30}" r="4" fill="{STATE[state]}"/>'
        f'<text x="{wx + 36}" y="{wy + 68 + i * 30}" class="mono" font-size="12" fill="{t["ink"]}">{role}</text>'
        f'<text x="{wx + 118}" y="{wy + 68 + i * 30}" class="mono" font-size="12" fill="{t["muted"]}">{escape(text)}</text></g>'
        for i, (role, text, state) in enumerate(rows)
    )
    done = "3 branches merged"
    char = 7.22  # 12px mono advance
    steps = len(done) + 2
    widths = ";".join(f"{i * char:.1f}" for i in range(steps + 1))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="880" height="280" viewBox="0 0 880 280" role="img" aria-label="Tianqi Zhao, AI engineer at Prover">
{style(t)}
<defs>
  <radialGradient id="wa"><stop offset="0" stop-color="{t['wash_a']}" stop-opacity="{t['wash_op']}"/><stop offset="1" stop-color="{t['wash_a']}" stop-opacity="0"/></radialGradient>
  <radialGradient id="wb"><stop offset="0" stop-color="{t['wash_b']}" stop-opacity="{t['wash_op']}"/><stop offset="1" stop-color="{t['wash_b']}" stop-opacity="0"/></radialGradient>
  <clipPath id="panel"><rect width="880" height="280" rx="20"/></clipPath>
  <clipPath id="type"><rect x="{wx + 18}" y="{wy + wh - 34}" height="20" width="0">
    <animate attributeName="width" values="{widths}" dur=".9s" begin="1.1s" calcMode="discrete" fill="freeze"/>
  </rect></clipPath>
</defs>
<g clip-path="url(#panel)">
  <rect width="880" height="280" fill="{t['panel']}"/>
  <circle cx="650" cy="250" r="280" fill="url(#wa)"/>
  <circle cx="850" cy="40" r="230" fill="url(#wb)"/>
</g>
<rect x=".5" y=".5" width="879" height="279" rx="19.5" fill="none" stroke="{t['ring']}"/>

<g class="in">
  <text x="48" y="76" class="mono" font-size="11" letter-spacing="1.4" fill="{t['faint']}">STOCKHOLM, SWEDEN</text>
  <text x="45" y="138" class="sans" font-size="54" font-weight="500" letter-spacing="-2.2" fill="{t['ink']}">Tianqi Zhao</text>
</g>
<g class="in" style="animation-delay:.12s">
  <text x="48" y="180" class="sans" font-size="20" letter-spacing="-.3" fill="{t['ink']}">AI engineer at Prover.</text>
  <text x="48" y="208" class="sans" font-size="20" letter-spacing="-.3" fill="{t['muted']}">Building tools for coding agents</text>
  <text x="48" y="234" class="sans" font-size="20" letter-spacing="-.3" fill="{t['muted']}">you can actually watch.</text>
</g>

<g class="in" style="animation-delay:.2s">
  <rect x="{wx}" y="{wy}" width="{ww}" height="{wh}" rx="12" fill="{t['window']}"/>
  <rect x="{wx + .5}" y="{wy + .5}" width="{ww - 1}" height="{wh - 1}" rx="11.5" fill="none" stroke="{t['ring']}"/>
  <circle cx="{wx + 18}" cy="{wy + 17}" r="4.5" fill="{t['chrome']}"/>
  <circle cx="{wx + 33}" cy="{wy + 17}" r="4.5" fill="{t['chrome']}"/>
  <circle cx="{wx + 48}" cy="{wy + 17}" r="4.5" fill="{t['chrome']}"/>
  <text x="{wx + ww / 2}" y="{wy + 21}" text-anchor="middle" class="mono" font-size="11" fill="{t['faint']}">agents · 3 roles</text>
  <line x1="{wx}" x2="{wx + ww}" y1="{wy + 34.5}" y2="{wy + 34.5}" stroke="{t['ring']}"/>
  <line x1="{wx + 18}" x2="{wx + ww - 18}" y1="{wy + wh - 46.5}" y2="{wy + wh - 46.5}" stroke="{t['ring']}"/>
</g>
{row_svg}
<g clip-path="url(#type)">
  <text x="{wx + 18}" y="{wy + wh - 20}" class="mono" font-size="12" fill="{STATE['passed']}">✓ <tspan fill="{t['muted']}">{done}</tspan></text>
</g>
</svg>
"""


def stats(t, data):
    numbers = [(f"{data['commits']:,}", "commits"), (f"{data['prs']:,}", "pull requests"),
               (str(data["repos"]), "repositories")]
    num_svg = "".join(
        f'<g class="in" style="animation-delay:{i * .1:.1f}s">'
        f'<text x="{4 + i * 150}" y="60" class="sans num" font-size="46" font-weight="300" letter-spacing="-1.5" fill="{t["ink"]}">{value}</text>'
        f'<text x="{6 + i * 150}" y="88" class="sans" font-size="13" fill="{t["muted"]}">{label}</text></g>'
        for i, (value, label) in enumerate(numbers)
    )

    bx, bw = 500, 376
    segs, labels, x = [], [], bx
    lx, ly = bx, 98
    for name, share, color in data["languages"]:
        color = color or t["chrome"]
        w = bw * share
        segs.append(f'<rect x="{x:.1f}" y="52" width="{max(w - 2, 1):.1f}" height="8" rx="2" fill="{color}"/>')
        x += w
        if name == "Other":
            continue
        text =f"{name} {share * 100:.0f}%"
        width = 14 + len(text) * 6.5
        if lx + width > bx + bw:
            lx, ly = bx, ly + 22
        labels.append(f'<circle cx="{lx + 4}" cy="{ly - 4}" r="3.5" fill="{color}"/>'
                      f'<text x="{lx + 13}" y="{ly}" class="sans" font-size="13" fill="{t["muted"]}">'
                      f'{escape(name)} <tspan class="num" fill="{t["faint"]}">{share * 100:.0f}%</tspan></text>')
        lx += width + 10

    height = ly + 14
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="880" height="{height}" viewBox="0 0 880 {height}" role="img" aria-label="{data['commits']} commits, {data['prs']} pull requests">
{style(t)}
<defs><clipPath id="grow"><rect x="{bx}" y="48" height="16" width="0">
  <animate attributeName="width" from="0" to="{bw}" dur=".9s" begin=".2s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines=".22 1 .36 1"/>
</rect></clipPath></defs>
{num_svg}
<text x="{bx}" y="30" class="mono" font-size="11" letter-spacing="1.4" fill="{t['faint']}">LANGUAGES</text>
<g clip-path="url(#grow)">{''.join(segs)}</g>
<g class="in" style="animation-delay:.5s">{''.join(labels)}</g>
</svg>
"""


def main():
    data = fetch()
    out = os.path.join(os.path.dirname(__file__), "..", "assets")
    os.makedirs(out, exist_ok=True)
    for name, t in THEMES.items():
        for kind, svg in (("hero", hero(t)), ("stats", stats(t, data))):
            with open(os.path.join(out, f"{kind}-{name}.svg"), "w") as f:
                f.write(svg)
    print(json.dumps(data))


if __name__ == "__main__":
    main()
