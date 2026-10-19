#!/usr/bin/env python3
"""Sync public GitHub metadata into local, static portfolio assets."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = {"mac", "dev", "lab"}


def safe_url(value):
    if not isinstance(value, str) or any(char.isspace() for char in value):
        return ""
    try:
        parsed = urlsplit(value)
        if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username:
            return value
    except ValueError:
        pass
    return ""


def request_json(path, token=""):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "sakura-portfolio-sync",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request("https://api.github.com" + path, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code in {403, 429}:
            raise RuntimeError(
                "GitHub denied the request or its rate limit was reached. "
                "Use GITHUB_TOKEN, or retry later. Existing data is unchanged."
            ) from error
        raise RuntimeError("GitHub request failed: HTTP " + str(error.code)) from error


def fetch_repositories(username, token=""):
    repositories = []
    for page in range(1, 101):
        batch = request_json(
            "/users/" + username + "/repos?type=owner&sort=updated&per_page=100&page=" + str(page),
            token,
        )
        if not isinstance(batch, list):
            raise ValueError("Expected a repository list from GitHub")
        repositories.extend(batch)
        if len(batch) < 100:
            return repositories
    raise RuntimeError("Pagination limit reached; refusing to publish an incomplete list")


def infer_category(repo):
    text = ((repo.get("description") or "") + " " + repo["name"]).lower()
    if repo.get("language") == "Swift" or "macos" in text:
        return "mac"
    if repo.get("language") in {"TypeScript", "Python", "Go", "Rust"}:
        return "dev"
    return "lab"


def build_data(config, profile, repositories, synced_at=None):
    username = config["username"]
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9-]{0,38}", username):
        raise ValueError("Invalid GitHub username")
    excluded = {name.lower() for name in config.get("exclude", [])}
    overrides = {name.lower(): value for name, value in config.get("overrides", {}).items()}
    projects = []
    for repo in repositories:
        name = repo["name"]
        override = overrides.get(name.lower(), {})
        if name.lower() in excluded or override.get("hidden") or repo.get("private"):
            continue
        if repo.get("fork") and not config.get("includeForks", False):
            continue
        if repo.get("archived") and not config.get("includeArchived", False):
            continue
        category = override.get("category", infer_category(repo))
        if category not in CATEGORIES:
            raise ValueError("Invalid category for " + name)
        if "website" in override:
            website = safe_url(override["website"])
            if override["website"] and not website:
                raise ValueError("Invalid website override for " + name)
        else:
            website = safe_url(repo.get("homepage"))
        tags = override.get("tags")
        if tags is None:
            tags = list(dict.fromkeys([repo.get("language")] + repo.get("topics", [])))
            tags = [tag for tag in tags if tag][:3]
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise ValueError("Tags must be a list of strings for " + name)
        projects.append({
            "name": override.get("name", name),
            "repo": name,
            "repository": "https://github.com/" + username + "/" + quote(name, safe=""),
            "website": website,
            "category": category,
            "icon": override.get("icon", "code"),
            "description": override.get("description", repo.get("description") or "项目详情与使用方式，见项目仓库。"),
            "tags": tags,
            "stars": repo.get("stargazers_count", 0),
            "language": repo.get("language"),
            "updatedAt": repo.get("pushed_at"),
            "badge": override.get("badge", ""),
        })

    # Curated projects stay in place; new projects follow, newest first.
    order = {name.lower(): index for index, name in enumerate(config.get("order", []))}
    projects.sort(key=lambda project: (project["updatedAt"] or "", project["repo"]), reverse=True)
    projects.sort(key=lambda project: order.get(project["repo"].lower(), len(order)))
    return {
        "schemaVersion": 1,
        "syncedAt": synced_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "profile": {
            "login": profile["login"],
            "name": profile.get("name") or profile["login"],
            "bio": profile.get("bio") or "",
            "location": profile.get("location") or "",
            "htmlUrl": "https://github.com/" + username,
            "avatarUrl": safe_url(profile.get("avatar_url")),
            "avatarPath": "assets/avatar.png",
            "followers": profile.get("followers", 0),
        },
        "projects": projects,
    }


def avatar_bytes(url):
    # Never send the GitHub API token to the avatar CDN or a third-party host.
    if urlsplit(url).hostname != "avatars.githubusercontent.com":
        raise ValueError("Unexpected GitHub avatar host")
    with urlopen(Request(url, headers={"User-Agent": "sakura-portfolio-sync"}), timeout=30) as response:
        content = response.read(5_000_001)
        if not content or not response.headers.get_content_type().startswith("image/") or len(content) > 5_000_000:
            raise ValueError("Invalid avatar response")
        return content


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    try:
        temporary_path.chmod(0o644)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def write_assets(data, avatar, root=ROOT):
    serialized = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    # A script wrapper also supports double-click/file:// previews without fetch/CORS.
    javascript = "window.PORTFOLIO_DATA = " + serialized.rstrip() + ";\n"
    atomic_write(root / "data.json", serialized.encode("utf-8"))
    atomic_write(root / "assets/data.js", javascript.encode("utf-8"))
    atomic_write(root / "assets/avatar.png", avatar)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fetch and validate without changing files")
    args = parser.parse_args()
    config = json.loads((ROOT / "projects.config.json").read_text(encoding="utf-8"))
    username = config["username"]
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9-]{0,38}", username):
        raise ValueError("Invalid GitHub username")
    token = os.environ.get("GITHUB_TOKEN", "")
    profile = request_json("/users/" + username, token)
    repositories = fetch_repositories(username, token)
    data = build_data(config, profile, repositories)
    avatar = avatar_bytes(data["profile"]["avatarUrl"])
    # Fetch and validate everything before changing the last successful snapshot.
    if not args.check:
        write_assets(data, avatar, ROOT)
    print(("Validated " if args.check else "Synced ") + str(len(data["projects"])) + " projects for " + username)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, KeyError, OSError, URLError) as error:
        print("Sync failed: " + str(error), file=sys.stderr)
        sys.exit(1)
