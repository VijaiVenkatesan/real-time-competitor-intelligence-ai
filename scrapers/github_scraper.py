"""
GitHub API Scraper - Tech stack, repository activity, contributor trends
Uses: GitHub REST API (optional token for higher rate limits)
"""

import os
import requests
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _get_headers() -> dict:
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "CompetitorIntelligenceBot/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def search_org(company_name: str) -> str | None:
    """Search GitHub for the most likely org handle for a company."""
    try:
        resp = requests.get(
            f"{GITHUB_API}/search/users",
            params={"q": f"{company_name} type:org", "per_page": 1},
            headers=_get_headers(),
            timeout=10,
        )
        items = resp.json().get("items", [])
        if items:
            return items[0]["login"]
    except Exception as e:
        logger.warning(f"GitHub org search failed: {e}")
    return None


def get_github_data(company_name: str) -> dict:
    """
    Fetch GitHub data: top repos, languages, commit activity, stars, contributors.
    """
    result = {
        "source": "GitHub API",
        "company": company_name,
        "fetched_at": datetime.utcnow().isoformat(),
        "org_handle": None,
        "total_public_repos": None,
        "total_stars": 0,
        "total_forks": 0,
        "top_languages": [],
        "top_repos": [],
        "recent_activity": None,
        "open_source_presence": None,
        "error": None,
    }

    org = search_org(company_name)
    if not org:
        result["error"] = "Could not find GitHub organization"
        return result

    result["org_handle"] = org

    try:
        # Org details
        org_resp = requests.get(f"{GITHUB_API}/orgs/{org}", headers=_get_headers(), timeout=10)
        if org_resp.status_code == 200:
            org_data = org_resp.json()
            result["total_public_repos"] = org_data.get("public_repos", 0)

        # Repos (sorted by stars)
        repos_resp = requests.get(
            f"{GITHUB_API}/orgs/{org}/repos",
            params={"sort": "stars", "per_page": 10, "type": "public"},
            headers=_get_headers(),
            timeout=10,
        )
        if repos_resp.status_code == 200:
            repos = repos_resp.json()
            lang_counts: dict[str, int] = {}
            top_repos = []
            for repo in repos:
                stars = repo.get("stargazers_count", 0)
                forks = repo.get("forks_count", 0)
                result["total_stars"] += stars
                result["total_forks"] += forks
                lang = repo.get("language")
                if lang:
                    lang_counts[lang] = lang_counts.get(lang, 0) + stars
                top_repos.append(
                    {
                        "name": repo.get("name"),
                        "stars": stars,
                        "forks": forks,
                        "language": lang,
                        "description": (repo.get("description") or "")[:150],
                        "updated_at": repo.get("updated_at", ""),
                        "url": repo.get("html_url"),
                    }
                )
            result["top_repos"] = top_repos
            result["top_languages"] = sorted(lang_counts, key=lang_counts.get, reverse=True)[:5]  # type: ignore

        # Assess activity by checking most recently pushed repos
        if result["total_public_repos"] and result["total_public_repos"] > 0:
            if result["total_stars"] > 10000:
                result["open_source_presence"] = "Strong"
            elif result["total_stars"] > 1000:
                result["open_source_presence"] = "Moderate"
            else:
                result["open_source_presence"] = "Low"

        # Check recent commit activity on the top repo
        if top_repos:
            top_repo_name = top_repos[0]["name"]
            commits_resp = requests.get(
                f"{GITHUB_API}/repos/{org}/{top_repo_name}/commits",
                params={"per_page": 10, "since": (datetime.utcnow() - timedelta(days=30)).isoformat()},
                headers=_get_headers(),
                timeout=10,
            )
            if commits_resp.status_code == 200:
                recent_commits = len(commits_resp.json())
                result["recent_activity"] = {
                    "repo": top_repo_name,
                    "commits_last_30d": recent_commits,
                }

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"GitHub API error for {company_name}: {e}")

    return result
