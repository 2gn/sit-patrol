import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.tracker import load_state, run_tracker, save_state


class TestTracker(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)

        # Create dummy config
        self.config_path = self.data_dir / "test_config.yml"
        self.config_path.write_text(
            """
feed:
  title: "Test Feed"
  description: "Test Desc"
  link: "https://example.com"
  max_items: 5

queries:
  - id: "q1"
    name: "Query 1"
    query: "test"
""",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_state_empty(self):
        state = load_state(self.data_dir)
        self.assertEqual(state["seen_ids"], [])
        self.assertEqual(state["items"], [])

    def test_save_and_load_state(self):
        state = {
            "version": 1,
            "last_updated": "2026-10-28T12:00:00Z",
            "seen_ids": ["repo/a"],
            "items": [{"id": "repo/a", "title": "A"}],
        }
        rss_content = "<rss></rss>"
        save_state(self.data_dir, state, rss_content)

        loaded = load_state(self.data_dir)
        self.assertEqual(loaded["seen_ids"], ["repo/a"])
        self.assertTrue((self.data_dir / "rss.xml").exists())

    @patch("src.tracker.GitHubClient")
    def test_run_tracker_new_repo_detected(self, mock_client_cls):
        mock_instance = mock_client_cls.return_value
        mock_instance.search_repositories.return_value = [
            {
                "full_name": "sit-user/project-alpha",
                "name": "project-alpha",
                "owner": {"login": "sit-user"},
                "created_at": "2026-10-28T10:00:00Z",
                "description": "Alpha project",
                "html_url": "https://github.com/sit-user/project-alpha",
                "language": "Python",
                "stargazers_count": 3,
            }
        ]
        mock_instance.get_readme.return_value = "# Project Alpha README"

        new_count = run_tracker(
            config_path=self.config_path,
            data_dir_path=self.data_dir,
            dry_run=False,
        )

        self.assertEqual(new_count, 1)

        # Verify index.json and rss.xml
        state = load_state(self.data_dir)
        self.assertIn("sit-user/project-alpha", state["seen_ids"])
        self.assertEqual(len(state["items"]), 1)
        self.assertIn("Project Alpha README", state["items"][0]["description"])

        rss_text = (self.data_dir / "rss.xml").read_text(encoding="utf-8")
        self.assertIn("sit-user/project-alpha", rss_text)

        # Second run with same mock data: should detect 0 new items
        new_count_2 = run_tracker(
            config_path=self.config_path,
            data_dir_path=self.data_dir,
            dry_run=False,
        )
        self.assertEqual(new_count_2, 0)

    @patch("src.tracker.GitHubClient")
    def test_run_tracker_filters_private_and_excluded_owners(self, mock_client_cls):
        # Configure filters in test config
        filtered_config_path = self.data_dir / "filtered_config.yml"
        filtered_config_path.write_text(
            """
feed:
  title: "Filtered Feed"
  max_items: 10

filters:
  ignore_private: true
  exclude_owners:
    - "blocked-user"
    - "blocked-org"
  exclude_repos:
    - "sit-org/excluded-repo"

queries:
  - id: "q1"
    query: "test"
""",
            encoding="utf-8",
        )

        mock_instance = mock_client_cls.return_value
        mock_instance.search_repositories.return_value = [
            # Private repo -> should be skipped
            {
                "full_name": "other-user/secret-repo",
                "name": "secret-repo",
                "owner": {"login": "other-user"},
                "private": True,
            },
            # Excluded owner -> should be skipped
            {
                "full_name": "blocked-user/internal-tool",
                "name": "internal-tool",
                "owner": {"login": "blocked-user"},
                "private": False,
            },
            # Excluded org -> should be skipped
            {
                "full_name": "blocked-org/internal-wiki",
                "name": "internal-wiki",
                "owner": {"login": "blocked-org"},
                "private": False,
            },
            # Excluded repo sit-org/excluded-repo -> should be skipped
            {
                "full_name": "sit-org/excluded-repo",
                "name": "excluded-repo",
                "owner": {"login": "sit-org"},
                "private": False,
            },
            # Allowed public repo -> should be added
            {
                "full_name": "allowed-user/open-oss",
                "name": "open-oss",
                "owner": {"login": "allowed-user"},
                "private": False,
                "created_at": "2026-10-28T12:00:00Z",
                "description": "Public SIT project",
            },
        ]
        mock_instance.get_readme.return_value = "README content"

        new_count = run_tracker(
            config_path=filtered_config_path,
            data_dir_path=self.data_dir,
            dry_run=False,
        )

        self.assertEqual(new_count, 1)
        state = load_state(self.data_dir)
        self.assertEqual(state["seen_ids"], ["allowed-user/open-oss"])
        self.assertEqual(len(state["items"]), 1)
        self.assertEqual(state["items"][0]["id"], "allowed-user/open-oss")


if __name__ == "__main__":
    unittest.main()
