import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError


SPEC = importlib.util.spec_from_file_location(
    "sync_github", Path(__file__).resolve().parents[1] / "scripts/sync_github.py"
)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def repository(name="Example", **fields):
    return {"name": name, "description": "Description", "language": "Swift",
            "homepage": "", "topics": [], "stargazers_count": 5,
            "pushed_at": "2026-10-19T01:00:00Z", **fields}


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.config = {"username": "yueseqaz"}
        self.profile = {"login": "yueseqaz", "name": "Sakura", "bio": "Hello",
                        "avatar_url": "https://avatars.githubusercontent.com/u/140417996?v=4"}

    def build(self, repositories, config=None):
        return sync.build_data(config or self.config, self.profile, repositories,
                               "2026-10-19T00:00:00+00:00")

    def test_profile_and_stars_follow_github(self):
        data = self.build([repository(stargazers_count=42)])
        self.assertEqual(data["profile"]["name"], "Sakura")
        self.assertEqual(data["projects"][0]["stars"], 42)

    def test_manual_website_has_priority(self):
        self.config["overrides"] = {"Example": {"website": "https://official.example"}}
        project = self.build([repository(homepage="https://github-site.example")])["projects"][0]
        self.assertEqual(project["website"], "https://official.example")
        self.assertEqual(project["repository"], "https://github.com/yueseqaz/Example")

    def test_github_homepage_is_next_choice(self):
        project = self.build([repository(homepage="https://github-site.example")])["projects"][0]
        self.assertEqual(project["website"], "https://github-site.example")

    def test_missing_site_means_repository_fallback(self):
        project = self.build([repository(homepage=None)])["projects"][0]
        self.assertEqual(project["website"], "")

    def test_explicit_null_disables_github_homepage(self):
        self.config["overrides"] = {"Example": {"website": None}}
        project = self.build([repository(homepage="https://site.example")])["projects"][0]
        self.assertEqual(project["website"], "")

    def test_preserves_curated_copy_tags_category_and_order(self):
        self.config.update({"order": ["Older"], "overrides": {
            "Older": {"name": "My Tool", "description": "Curated", "tags": ["Handpicked"], "category": "dev"}}})
        projects = self.build([repository("Newer"), repository("Older", pushed_at="2025-01-01")])["projects"]
        self.assertEqual(projects[0]["name"], "My Tool")
        self.assertEqual(projects[0]["description"], "Curated")
        self.assertEqual(projects[0]["tags"], ["Handpicked"])
        self.assertEqual(projects[0]["category"], "dev")

    def test_new_projects_are_included_newest_first(self):
        projects = self.build([repository("Older", pushed_at="2025-01-01"), repository("New")])["projects"]
        self.assertEqual([p["repo"] for p in projects], ["New", "Older"])

    def test_excludes_private_forks_archived_hidden_and_named_repos(self):
        self.config.update({"exclude": ["EXCLUDED"], "overrides": {"Hidden": {"hidden": True}}})
        repos = [repository(), repository("Excluded"), repository("Hidden"),
                 repository("Fork", fork=True), repository("Old", archived=True),
                 repository("Secret", private=True)]
        self.assertEqual(len(self.build(repos)["projects"]), 1)

    def test_forks_and_archived_are_opt_in(self):
        self.config.update({"includeForks": True, "includeArchived": True})
        self.assertEqual(len(self.build([repository(fork=True, archived=True)])["projects"]), 1)

    def test_invalid_remote_website_is_ignored(self):
        for url in ["javascript:alert(1)", "data:text/html,bad", "https://user@host.test", "https://invalid host"]:
            with self.subTest(url=url):
                self.assertEqual(self.build([repository(homepage=url)])["projects"][0]["website"], "")

    def test_invalid_manual_website_fails(self):
        self.config["overrides"] = {"Example": {"website": "javascript:alert(1)"}}
        with self.assertRaises(ValueError):
            self.build([repository()])

    def test_unknown_category_fails(self):
        self.config["overrides"] = {"Example": {"category": "unknown"}}
        with self.assertRaises(ValueError):
            self.build([repository()])

    def test_inputs_are_not_mutated(self):
        repos = [repository()]
        original = copy.deepcopy(repos)
        self.build(repos)
        self.assertEqual(repos, original)

    def test_language_and_topics_provide_default_tags(self):
        project = self.build([repository(language="Python", topics=["cli", "cli", "ai"])])["projects"][0]
        self.assertEqual(project["category"], "dev")
        self.assertEqual(project["tags"], ["Python", "cli", "ai"])

    def test_all_repository_pages_are_fetched(self):
        with patch.object(sync, "request_json", side_effect=[[repository()] * 100, [repository("Last")]]) as request:
            repos = sync.fetch_repositories("yueseqaz", "token")
        self.assertEqual(len(repos), 101)
        self.assertIn("page=2", request.call_args.args[0])

    def test_invalid_page_response_fails(self):
        with patch.object(sync, "request_json", return_value={"message": "Error"}):
            with self.assertRaises(ValueError):
                sync.fetch_repositories("yueseqaz")

    def test_rate_limit_produces_actionable_error(self):
        with patch.object(sync, "urlopen", side_effect=HTTPError("https://api.github.com", 403, "Forbidden", {}, None)):
            with self.assertRaisesRegex(RuntimeError, "GITHUB_TOKEN"):
                sync.request_json("/users/yueseqaz")

    def test_api_failure_keeps_existing_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "projects.config.json").write_text(json.dumps(self.config))
            (root / "data.json").write_text("previous success")
            with patch.object(sync, "ROOT", root), patch("sys.argv", ["sync"]), \
                    patch.object(sync, "request_json", side_effect=RuntimeError("Unavailable")):
                with self.assertRaises(RuntimeError):
                    sync.main()
            self.assertEqual((root / "data.json").read_text(), "previous success")

    def test_avatar_failure_keeps_existing_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "projects.config.json").write_text(json.dumps(self.config))
            (root / "data.json").write_text("previous success")
            with patch.object(sync, "ROOT", root), patch("sys.argv", ["sync"]), \
                    patch.object(sync, "request_json", return_value=self.profile), \
                    patch.object(sync, "fetch_repositories", return_value=[repository()]), \
                    patch.object(sync, "avatar_bytes", side_effect=ValueError("Invalid avatar")):
                with self.assertRaises(ValueError):
                    sync.main()
            self.assertEqual((root / "data.json").read_text(), "previous success")

    def test_avatar_disallows_unexpected_hosts(self):
        with self.assertRaises(ValueError):
            sync.avatar_bytes("https://untrusted.example/image")

    def test_generated_json_and_script_contain_identical_data(self):
        data = self.build([repository(description="Quotes: \" and </script>")])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sync.write_assets(data, b"avatar", root)
            saved = json.loads((root / "data.json").read_text())
            javascript = (root / "assets/data.js").read_text()
            wrapped = json.loads(javascript.removeprefix("window.PORTFOLIO_DATA = ").removesuffix(";\n"))
            self.assertEqual(saved, data)
            self.assertEqual(wrapped, data)
            self.assertEqual((root / "assets/avatar.png").read_bytes(), b"avatar")


if __name__ == "__main__":
    unittest.main()
