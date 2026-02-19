#!/usr/bin/env python3
"""
Generate GitHub stats SVG cards for PeterBenc across multiple organizations.
Queries GitHub GraphQL API for stars, commits, PRs, issues, and lines changed.
"""

import os
import json
import requests
import math

USERNAME = "PeterBenc"
ORGS = ["nufi-official"]
TOKEN = os.environ["GH_TOKEN"]
API_URL = "https://api.github.com/graphql"
HEADERS = {"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"}

def graphql(query, variables=None):
    r = requests.post(API_URL, json={"query": query, "variables": variables or {}}, headers=HEADERS)
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        print(f"GraphQL errors: {data['errors']}")
    return data.get("data", {})

def get_user_stats():
    """Get user's own repo stars + contribution stats."""
    query = """
    query($login: String!) {
      user(login: $login) {
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
          nodes {
            stargazerCount
            forkCount
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges {
                size
                node { name color }
              }
            }
          }
        }
        contributionsCollection {
          totalCommitContributions
          restrictedContributionsCount
          totalPullRequestContributions
          totalIssueContributions
          totalPullRequestReviewContributions
        }
      }
    }
    """
    return graphql(query, {"login": USERNAME})

def get_org_repos(org):
    """Get all repos from an org (paginated)."""
    repos = []
    cursor = None
    while True:
        query = """
        query($org: String!, $cursor: String) {
          organization(login: $org) {
            repositories(first: 100, after: $cursor) {
              pageInfo { hasNextPage endCursor }
              nodes {
                name
                stargazerCount
                forkCount
                languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
                  edges {
                    size
                    node { name color }
                  }
                }
              }
            }
          }
        }
        """
        data = graphql(query, {"org": org, "cursor": cursor})
        org_data = data.get("organization", {})
        repo_data = org_data.get("repositories", {})
        repos.extend(repo_data.get("nodes", []))
        page_info = repo_data.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info["endCursor"]
    return repos

def get_user_commits_in_org(org):
    """Get user's commit count in an org using contributions collection."""
    query = """
    query($login: String!, $org: ID!) {
      user(login: $login) {
        contributionsCollection(organizationID: $org) {
          totalCommitContributions
          restrictedContributionsCount
          totalPullRequestContributions
          totalIssueContributions
        }
      }
    }
    """
    # First get org ID
    org_query = """
    query($org: String!) {
      organization(login: $org) { id }
    }
    """
    org_data = graphql(org_query, {"org": org})
    org_id = org_data.get("organization", {}).get("id")
    if not org_id:
        return {"commits": 0, "prs": 0, "issues": 0}

    data = graphql(query, {"login": USERNAME, "org": org_id})
    contrib = data.get("user", {}).get("contributionsCollection", {})
    return {
        "commits": contrib.get("totalCommitContributions", 0) + contrib.get("restrictedContributionsCount", 0),
        "prs": contrib.get("totalPullRequestContributions", 0),
        "issues": contrib.get("totalIssueContributions", 0),
    }

def get_lines_changed():
    """Estimate lines changed using REST API for recent repos the user contributed to."""
    total_additions = 0
    total_deletions = 0

    # Get repos user contributed to
    url = f"https://api.github.com/users/{USERNAME}/repos?per_page=100&type=all"
    headers = {"Authorization": f"token {TOKEN}"}
    r = requests.get(url, headers=headers)
    repos = r.json() if r.status_code == 200 else []

    for repo in repos:
        full_name = repo.get("full_name", "")
        stats_url = f"https://api.github.com/repos/{full_name}/stats/contributors"
        r = requests.get(stats_url, headers=headers)
        if r.status_code != 200:
            continue
        contributors = r.json()
        if not isinstance(contributors, list):
            continue
        for c in contributors:
            if c.get("author", {}).get("login", "").lower() == USERNAME.lower():
                for week in c.get("weeks", []):
                    total_additions += week.get("a", 0)
                    total_deletions += week.get("d", 0)

    # Also check org repos where user has contributed
    for org in ORGS:
        url = f"https://api.github.com/orgs/{org}/repos?per_page=100&type=all"
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            continue
        repos = r.json()
        for repo in repos:
            full_name = repo.get("full_name", "")
            stats_url = f"https://api.github.com/repos/{full_name}/stats/contributors"
            r2 = requests.get(stats_url, headers=headers)
            if r2.status_code != 200:
                continue
            contributors = r2.json()
            if not isinstance(contributors, list):
                continue
            for c in contributors:
                if c.get("author", {}).get("login", "").lower() == USERNAME.lower():
                    for week in c.get("weeks", []):
                        total_additions += week.get("a", 0)
                        total_deletions += week.get("d", 0)

    return total_additions + total_deletions

def format_number(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)

def generate_stats_svg(stats):
    """Generate a clean white-on-transparent stats card SVG."""
    items = [
        ("⭐", "Total Stars Earned", format_number(stats["stars"])),
        ("📝", "Total Commits", format_number(stats["commits"])),
        ("🔀", "Total PRs", format_number(stats["prs"])),
        ("❗", "Total Issues", format_number(stats["issues"])),
        ("±", "Lines of Code Changed", format_number(stats["lines_changed"])),
    ]

    row_height = 30
    padding_top = 50
    card_height = padding_top + len(items) * row_height + 20
    card_width = 420

    rows_svg = ""
    for i, (icon, label, value) in enumerate(items):
        y = padding_top + i * row_height
        rows_svg += f"""
        <g transform="translate(0, {y})">
            <text x="25" y="0" fill="white" font-size="14" font-family="Segoe UI, Ubuntu, sans-serif">{icon}</text>
            <text x="50" y="0" fill="white" font-size="14" font-family="Segoe UI, Ubuntu, sans-serif">{label}:</text>
            <text x="{card_width - 30}" y="0" fill="white" font-size="14" font-family="Segoe UI, Ubuntu, sans-serif" text-anchor="end" font-weight="bold">{value}</text>
        </g>"""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{card_width}" height="{card_height}" viewBox="0 0 {card_width} {card_height}" fill="none">
    <text x="25" y="30" fill="white" font-size="18" font-weight="bold" font-family="Segoe UI, Ubuntu, sans-serif">Peter Benc's GitHub Statistics</text>
    {rows_svg}
</svg>"""

    return svg

def generate_langs_svg(languages):
    """Generate a top languages card SVG."""
    # Sort by size and take top 10
    sorted_langs = sorted(languages.items(), key=lambda x: x[1]["size"], reverse=True)[:10]
    total = sum(v["size"] for _, v in sorted_langs)
    if total == 0:
        return "<svg></svg>"

    card_width = 420
    bar_y = 45
    bar_height = 8
    padding_top = 70

    # Progress bar segments
    bar_svg = ""
    x_offset = 25
    bar_width = card_width - 50
    for lang, data in sorted_langs:
        width = (data["size"] / total) * bar_width
        color = data.get("color", "#ffffff") or "#ffffff"
        bar_svg += f'<rect x="{x_offset}" y="{bar_y}" width="{width}" height="{bar_height}" fill="{color}" rx="1"/>'
        x_offset += width

    # Language labels (2 columns)
    labels_svg = ""
    col_width = (card_width - 50) / 2
    for i, (lang, data) in enumerate(sorted_langs):
        pct = (data["size"] / total) * 100
        col = i % 2
        row = i // 2
        x = 25 + col * col_width
        y = padding_top + row * 25
        color = data.get("color", "#ffffff") or "#ffffff"
        labels_svg += f"""
        <g transform="translate({x}, {y})">
            <circle cx="6" cy="-4" r="6" fill="{color}"/>
            <text x="18" y="0" fill="white" font-size="12" font-family="Segoe UI, Ubuntu, sans-serif">{lang} {pct:.1f}%</text>
        </g>"""

    num_rows = math.ceil(len(sorted_langs) / 2)
    card_height = padding_top + num_rows * 25 + 20

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{card_width}" height="{card_height}" viewBox="0 0 {card_width} {card_height}" fill="none">
    <text x="25" y="30" fill="white" font-size="18" font-weight="bold" font-family="Segoe UI, Ubuntu, sans-serif">Most Used Languages</text>
    {bar_svg}
    {labels_svg}
</svg>"""

    return svg

def main():
    os.makedirs("profile", exist_ok=True)

    print("Fetching user stats...")
    user_data = get_user_stats()
    user = user_data.get("user", {})
    user_repos = user.get("repositories", {}).get("nodes", [])
    contrib = user.get("contributionsCollection", {})

    # Stars and forks from personal repos
    total_stars = sum(r.get("stargazerCount", 0) for r in user_repos)
    total_forks = sum(r.get("forkCount", 0) for r in user_repos)

    # Commits, PRs, issues from personal contributions
    total_commits = contrib.get("totalCommitContributions", 0) + contrib.get("restrictedContributionsCount", 0)
    total_prs = contrib.get("totalPullRequestContributions", 0)
    total_issues = contrib.get("totalIssueContributions", 0)

    # Languages from personal repos
    languages = {}
    for repo in user_repos:
        for edge in repo.get("languages", {}).get("edges", []):
            name = edge["node"]["name"]
            color = edge["node"].get("color", "#ffffff")
            size = edge.get("size", 0)
            if name in languages:
                languages[name]["size"] += size
            else:
                languages[name] = {"size": size, "color": color}

    # Add org stats
    for org in ORGS:
        print(f"Fetching org repos: {org}...")
        org_repos = get_org_repos(org)
        total_stars += sum(r.get("stargazerCount", 0) for r in org_repos)
        total_forks += sum(r.get("forkCount", 0) for r in org_repos)

        # Languages from org repos
        for repo in org_repos:
            for edge in repo.get("languages", {}).get("edges", []):
                name = edge["node"]["name"]
                color = edge["node"].get("color", "#ffffff")
                size = edge.get("size", 0)
                if name in languages:
                    languages[name]["size"] += size
                else:
                    languages[name] = {"size": size, "color": color}

        print(f"Fetching contributions in {org}...")
        org_contrib = get_user_commits_in_org(org)
        # Don't double-count — the user's contributionsCollection already includes org contributions
        # We only add org repo stars/forks/languages, not commits (those are already counted)

    print("Fetching lines changed (this may take a while)...")
    lines_changed = get_lines_changed()

    stats = {
        "stars": total_stars,
        "commits": total_commits,
        "prs": total_prs,
        "issues": total_issues,
        "lines_changed": lines_changed,
    }

    print(f"Stats: {json.dumps(stats, indent=2)}")

    # Generate SVGs
    stats_svg = generate_stats_svg(stats)
    langs_svg = generate_langs_svg(languages)

    with open("profile/stats.svg", "w") as f:
        f.write(stats_svg)

    with open("profile/top-langs.svg", "w") as f:
        f.write(langs_svg)

    print("Done! SVGs written to profile/")

if __name__ == "__main__":
    main()