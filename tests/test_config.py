import tempfile
import unittest
from pathlib import Path

from src.config import AppConfig


class TestConfig(unittest.TestCase):
    def test_load_config(self):
        config = AppConfig.load_from_file("config.yml")
        self.assertEqual(config.feed.title, "SIT Patrol (芝浦工業大学 関連リポジトリ)")
        self.assertGreaterEqual(len(config.queries), 2)
        self.assertTrue(any("shibaura-it" in q.query for q in config.queries))

    def test_missing_file_raises_error(self):
        with self.assertRaises(FileNotFoundError):
            AppConfig.load_from_file("non_existent_config.yml")

    def test_default_feed_config(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".yml", delete=False) as f:
            f.write("queries:\n  - id: test\n    query: sit\n")
            f_path = f.name

        try:
            cfg = AppConfig.load_from_file(f_path)
            self.assertEqual(cfg.feed.title, "SIT Patrol")
            self.assertEqual(len(cfg.queries), 1)
            self.assertEqual(cfg.queries[0].id, "test")
        finally:
            Path(f_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
