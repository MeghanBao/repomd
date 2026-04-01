"""
GitHub repo analyzer — fetches key files via GitHub API
and extracts signals for CLAUDE.md generation.
"""

import httpx
import base64
import json
from typing import Optional


# Files to fetch for analysis (priority order)
PRIORITY_FILES = [
    "README.md", "readme.md",
    "package.json", "pyproject.toml", "setup.py", "Cargo.toml",
    "go.mod", "pom.xml", "build.gradle",
    "Makefile", "makefile",
    ".github/workflows",       # CI commands
    "docker-compose.yml", "docker-compose.yaml",
    ".eslintrc.js", ".eslintrc.json", "eslint.config.js",
    "pytest.ini", "setup.cfg", "tox.ini",
    "tsconfig.json",
    ".env.example", ".env.sample",
]


def parse_repo_url(url: str) -> tuple[str, str]:
    """Extract owner/repo from GitHub URL or 'owner/repo' shorthand."""
    url = url.strip().rstrip("/")
    if url.startswith("https://github.com/"):
        parts = url.replace("https://github.com/", "").split("/")
        return parts[0], parts[1]
    elif "/" in url and not url.startswith("http"):
        parts = url.split("/")
        return parts[0], parts[1]
    raise ValueError(f"Cannot parse repo: {url}")


def fetch_repo_tree(owner: str, repo: str, token: Optional[str] = None) -> dict:
    """Fetch the full file tree of a repo (shallow)."""
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with httpx.Client(timeout=15) as client:
        # Get default branch
        r = client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
        r.raise_for_status()
        repo_meta = r.json()
        branch = repo_meta.get("default_branch", "main")
        description = repo_meta.get("description", "")
        language = repo_meta.get("language", "")
        topics = repo_meta.get("topics", [])

        # Get tree
        r = client.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
            headers=headers
        )
        r.raise_for_status()
        tree = r.json()

    return {
        "meta": {
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "description": description,
            "language": language,
            "topics": topics,
        },
        "tree": [item["path"] for item in tree.get("tree", []) if item["type"] == "blob"]
    }


def fetch_file(owner: str, repo: str, path: str, token: Optional[str] = None) -> Optional[str]:
    """Fetch a single file's content from GitHub API."""
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with httpx.Client(timeout=10) as client:
        r = client.get(
            f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
            headers=headers
        )
        if r.status_code != 200:
            return None
        data = r.json()
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    return None


def collect_repo_signals(owner: str, repo: str, token: Optional[str] = None) -> dict:
    """
    Main analyzer: fetch tree + priority files,
    return structured signals dict.
    """
    print(f"  Fetching repo tree for {owner}/{repo}...")
    tree_data = fetch_repo_tree(owner, repo, token)
    all_files = set(tree_data["tree"])
    meta = tree_data["meta"]

    # Determine which priority files exist
    found_files = {}
    for target in PRIORITY_FILES:
        # Handle directory entries (e.g. .github/workflows)
        matches = [f for f in all_files if f == target or f.startswith(target + "/")]
        if matches:
            found_files[target] = matches[0]

    # Fetch file contents (limit to avoid rate limits)
    file_contents = {}
    fetch_targets = [
        "README.md", "readme.md",
        "package.json", "pyproject.toml", "setup.py", "Cargo.toml",
        "go.mod", "Makefile", "makefile",
        "docker-compose.yml", "docker-compose.yaml",
        "pytest.ini", "setup.cfg", "tsconfig.json",
        ".env.example",
    ]
    for target in fetch_targets:
        if target in found_files:
            print(f"  Reading {target}...")
            content = fetch_file(owner, repo, found_files[target], token)
            if content:
                # Truncate large files to first 3000 chars
                file_contents[target] = content[:3000]

    # Detect CI workflows
    ci_files = [f for f in all_files if f.startswith(".github/workflows/")]
    if ci_files:
        # Fetch first workflow for command hints
        content = fetch_file(owner, repo, ci_files[0], token)
        if content:
            file_contents["_ci_workflow"] = content[:2000]

    # Detect test directories / patterns
    test_signals = {
        "has_tests": any("test" in f.lower() or "spec" in f.lower() for f in all_files),
        "test_dirs": list({f.split("/")[0] for f in all_files
                          if f.split("/")[0] in ("tests", "test", "__tests__", "spec")}),
    }

    # Directory structure (top-level only)
    top_dirs = sorted({f.split("/")[0] for f in all_files if "/" in f} - {"."})

    return {
        "meta": meta,
        "all_files": list(all_files),
        "file_contents": file_contents,
        "test_signals": test_signals,
        "top_dirs": top_dirs,
        "found_config_files": list(found_files.keys()),
    }
