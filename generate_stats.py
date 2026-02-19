#!/usr/bin/env python3
"""
Generate GitHub stats SVG cards for PeterBenc.
- Stars: personal repos + manually defined org repos you founded
- Commits/PRs/Issues: from contributionsCollection (includes all orgs)
- Lines changed: from repos where user actually contributed
- Languages: from repos where user actually contributed
"""

import os
import json
import requests
import math
import time

USERNAME = "PeterBenc"

# ============================================================
# EDIT THIS LIST to control which org repos count toward stars.
# Only add repos you founded or are the primary author of.
# ============================================================
STAR_REPOS = [
    "vacuumlabs/cardano-hw-cli",
    "vacuumlabs/adalite",
    "nufi-official/nufi",
    "nufi-official/nufi-snap",
]

# Orgs to scan for contributions (lines changed + languages)
ORGS = ["nufi-official", "vacuumlabs", "trezor"]

TOKEN = os.environ["GH_TOKEN"]
API_URL = "https://api.github.com/graphql"
HEADERS = {"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"}
REST_HEADERS = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}


def graphql(query, variables=None):
    r = requests.post(API_URL, json={"query": query, "variables": variables or {}}, headers=HEADERS)
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        print(f"GraphQL errors: {data['errors']}")
    return data.get("data", {})


def get_user_stats():
    query = """
    query($login: String!) {
      user(login: $login) {
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
          nodes {
            nameWithOwner
            stargazerCount
          }
        }
        contributionsCollection {
          totalCommitContributions
          restrictedContributionsCount
          totalPullRequestContributions
          totalIssueContributions
        }
      }
    }
    """
    return graphql(query, {"login": USERNAME})


def get_repo_stars(owner, name):
    query = """
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        stargazerCount
      }
    }
    """
    data = graphql(query, {"owner": owner, "name": name})
    return data.get("repository", {}).get("stargazerCount", 0)


def get_contributor_stats(repo_full_name):
    """Get lines changed by USERNAME in a repo. Returns (additions, deletions).
    The /stats/contributors endpoint may return 202 on first call while computing."""
    url = f"https://api.github.com/repos/{repo_full_name}/stats/contributors"
    for attempt in range(3):
        r = requests.get(url, headers=REST_HEADERS)
        if r.status_code == 200:
            break
        if r.status_code == 202:
            time.sleep(3)
            continue
        return 0, 0

    if r.status_code != 200:
        return 0, 0

    contributors = r.json()
    if not isinstance(contributors, list):
        return 0, 0

    for c in contributors:
        if c.get("author", {}).get("login", "").lower() == USERNAME.lower():
            additions = sum(w.get("a", 0) for w in c.get("weeks", []))
            deletions = sum(w.get("d", 0) for w in c.get("weeks", []))
            return additions, deletions

    return 0, 0


def get_repo_languages(repo_full_name):
    url = f"https://api.github.com/repos/{repo_full_name}/languages"
    r = requests.get(url, headers=REST_HEADERS)
    if r.status_code != 200:
        return {}
    return r.json()


def get_org_repos_list(org):
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/orgs/{org}/repos?per_page=100&page={page}&type=all"
        r = requests.get(url, headers=REST_HEADERS)
        if r.status_code != 200:
            break
        data = r.json()
        if not data:
            break
        repos.extend([repo["full_name"] for repo in data])
        if len(data) < 100:
            break
        page += 1
    return repos


LANG_COLORS = {
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "HTML": "#e34c26",
    "CSS": "#563d7c", "Python": "#3572A5", "Rust": "#dea584",
    "Solidity": "#AA6746", "Shell": "#89e051", "Nix": "#7e7eff",
    "Haskell": "#5e5086", "C": "#555555", "C++": "#f34b7d",
    "Go": "#00ADD8", "Java": "#b07219", "Dockerfile": "#384d54",
    "SCSS": "#c6538c", "Vue": "#41b883", "Svelte": "#ff3e00",
    "Dart": "#00B4AB", "Kotlin": "#A97BFF", "Swift": "#F05138",
    "Ruby": "#701516", "PHP": "#4F5D95", "Cadence": "#00ef8b",
}


def format_number(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def generate_stats_svg(stats):
    items = [
        ("Total Stars Earned", format_number(stats["stars"])),
        ("Total Commits", format_number(stats["commits"])),
        ("Total PRs", format_number(stats["prs"])),
        ("Total Issues", format_number(stats["issues"])),
        ("Lines of Code Changed", format_number(stats["lines_changed"])),
    ]

    icons = [
        '<path d="M7 0.452l2.146 4.432 4.878 0.674-3.551 3.414 0.866 4.848L7 11.586l-4.339 2.234 0.866-4.848L0 5.558l4.878-0.674z" fill="white"/>',
        '<circle cx="7" cy="7" r="3" stroke="white" stroke-width="1.5" fill="none"/><line x1="7" y1="10" x2="7" y2="14" stroke="white" stroke-width="1.5"/>',
        '<circle cx="5" cy="4" r="2.5" stroke="white" stroke-width="1.3" fill="none"/><circle cx="9" cy="10" r="2.5" stroke="white" stroke-width="1.3" fill="none"/><line x1="5" y1="6.5" x2="5" y2="14" stroke="white" stroke-width="1.3"/>',
        '<circle cx="7" cy="7" r="6" stroke="white" stroke-width="1.3" fill="none"/><line x1="7" y1="4" x2="7" y2="8" stroke="white" stroke-width="1.5"/><circle cx="7" cy="10" r="0.8" fill="white"/>',
        '<path d="M5 3L1 7l4 4M9 3l4 4-4 4" stroke="white" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
    ]

    row_height = 32
    padding_top = 55
    card_height = padding_top + len(items) * row_height + 15
    card_width = 420

    rows_svg = ""
    for i, ((label, value), icon_svg) in enumerate(zip(items, icons)):
        y = padding_top + i * row_height
        rows_svg += f"""
        <g transform="translate(25, {y})">
            <g transform="translate(0, -10)">{icon_svg}</g>
            <text x="22" y="0" fill="white" font-size="14" font-family="Segoe UI, Ubuntu, sans-serif">{label}:</text>
            <text x="{card_width - 55}" y="0" fill="white" font-size="14" font-family="Segoe UI, Ubuntu, sans-serif" text-anchor="end" font-weight="bold">{value}</text>
        </g>"""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{card_width}" height="{card_height}" viewBox="0 0 {card_width} {card_height}" fill="none">
    <text x="25" y="30" fill="white" font-size="18" font-weight="bold" font-family="Segoe UI, Ubuntu, sans-serif">Peter Benc's GitHub Statistics</text>
    <line x1="25" y1="38" x2="{card_width - 25}" y2="38" stroke="rgba(255,255,255,0.2)" stroke-width="1"/>
    {rows_svg}
</svg>"""
    return svg


def generate_langs_svg(languages):
    sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)[:10]
    total = sum(v for _, v in sorted_langs)
    if total == 0:
        return '<svg xmlns="http://www.w3.org/2000/svg"></svg>'

    card_width = 420
    bar_y = 48
    bar_height = 8
    padding_top = 72

    bar_svg = ""
    x_offset = 25.0
    bar_width = card_width - 50
    for i, (lang, size) in enumerate(sorted_langs):
        width = max((size / total) * bar_width, 1)
        color = LANG_COLORS.get(lang, "#ffffff")
        bar_svg += f'<rect x="{x_offset:.1f}" y="{bar_y}" width="{width:.1f}" height="{bar_height}" fill="{color}"/>'
        x_offset += width

    labels_svg = ""
    col_width = (card_width - 50) / 2
    for i, (lang, size) in enumerate(sorted_langs):
        pct = (size / total) * 100
        col = i % 2
        row = i // 2
        x = 25 + col * col_width
        y = padding_top + row * 25
        color = LANG_COLORS.get(lang, "#ffffff")
        labels_svg += f"""
        <g transform="translate({x}, {y})">
            <circle cx="6" cy="-4" r="6" fill="{color}"/>
            <text x="18" y="0" fill="white" font-size="12" font-family="Segoe UI, Ubuntu, sans-serif">{lang} {pct:.2f}%</text>
        </g>"""

    num_rows = math.ceil(len(sorted_langs) / 2)
    card_height = padding_top + num_rows * 25 + 15

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{card_width}" height="{card_height}" viewBox="0 0 {card_width} {card_height}" fill="none">
    <text x="25" y="30" fill="white" font-size="18" font-weight="bold" font-family="Segoe UI, Ubuntu, sans-serif">Most Used Languages</text>
    <line x1="25" y1="38" x2="{card_width - 25}" y2="38" stroke="rgba(255,255,255,0.2)" stroke-width="1"/>
    {bar_svg}
    {labels_svg}
</svg>"""
    return svg


def main():
    os.makedirs("profile", exist_ok=True)

    # 1. User stats
    print("Fetching user stats...")
    user_data = get_user_stats()
    user = user_data.get("user", {})
    user_repos = user.get("repositories", {}).get("nodes", [])
    contrib = user.get("contributionsCollection", {})

    total_commits = contrib.get("totalCommitContributions", 0) + contrib.get("restrictedContributionsCount", 0)
    total_prs = contrib.get("totalPullRequestContributions", 0)
    total_issues = contrib.get("totalIssueContributions", 0)

    # 2. Stars: personal repos
    personal_stars = sum(r.get("stargazerCount", 0) for r in user_repos)
    print(f"Personal repo stars: {personal_stars}")

    # 3. Stars: manually listed org repos
    org_stars = 0
    for repo_full in STAR_REPOS:
        owner, name = repo_full.split("/")
        stars = get_repo_stars(owner, name)
        print(f"  {repo_full}: {stars} stars")
        org_stars += stars

    total_stars = personal_stars + org_stars

    # 4. Lines changed + languages: scan all repos user contributed to
    print("\nScanning for contributions across orgs...")
    total_additions = 0
    total_deletions = 0
    languages = {}
    seen_repos = set()

    # Personal repos first
    for repo in user_repos:
        full_name = repo.get("nameWithOwner", "")
        if not full_name:
            continue
        seen_repos.add(full_name)
        a, d = get_contributor_stats(full_name)
        if a + d > 0:
            print(f"  {full_name}: +{a} -{d}")
            total_additions += a
            total_deletions += d
            langs = get_repo_languages(full_name)
            for lang, bytes_count in langs.items():
                languages[lang] = languages.get(lang, 0) + bytes_count

    # Org repos
    for org in ORGS:
        print(f"\nScanning {org}...")
        org_repos = get_org_repos_list(org)
        for repo_full in org_repos:
            if repo_full in seen_repos:
                continue
            seen_repos.add(repo_full)
            a, d = get_contributor_stats(repo_full)
            if a + d > 0:
                print(f"  {repo_full}: +{a} -{d}")
                total_additions += a
                total_deletions += d
                langs = get_repo_languages(repo_full)
                for lang, bytes_count in langs.items():
                    languages[lang] = languages.get(lang, 0) + bytes_count

    lines_changed = total_additions + total_deletions

    stats = {
        "stars": total_stars,
        "commits": total_commits,
        "prs": total_prs,
        "issues": total_issues,
        "lines_changed": lines_changed,
    }

    print(f"\n{'='*50}")
    print(f"Final stats: {json.dumps(stats, indent=2)}")
    top_langs = dict(sorted(languages.items(), key=lambda x: x[1], reverse=True)[:10])
    print(f"Top languages: {json.dumps(top_langs, indent=2)}")

    stats_svg = generate_stats_svg(stats)
    langs_svg = generate_langs_svg(languages)

    with open("profile/stats.svg", "w") as f:
        f.write(stats_svg)
    with open("profile/top-langs.svg", "w") as f:
        f.write(langs_svg)

    print("\nDone! SVGs written to profile/")


if __name__ == "__main__":
    main()