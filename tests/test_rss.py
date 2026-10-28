import html
import unittest
import xml.etree.ElementTree as ET

from src.rss_generator import FeedItem, generate_rss, to_rfc822


class TestRSSGenerator(unittest.TestCase):
    def test_to_rfc822_conversion(self):
        iso_date = "2026-10-28T12:00:00Z"
        rfc = to_rfc822(iso_date)
        self.assertIn("28 Oct 2026", rfc)
        self.assertTrue(rfc.endswith("+0000") or rfc.endswith("GMT"))

    def test_generate_valid_rss(self):
        items = [
            FeedItem(
                id="shibaura-org/new-project",
                title="[新着リポジトリ] shibaura-org/new-project",
                link="https://github.com/shibaura-org/new-project",
                published_at="2026-10-28T10:00:00Z",
                description="プロジェクトの概要とREADME説明文 <test & special characters>",
                author="shibaura-org",
                language="Python",
                stars=5,
                query_name="ドメイン検索",
            )
        ]

        xml_output = generate_rss(
            title="SIT Patrol Test",
            description="Test Description",
            link="https://example.com",
            items=items,
        )

        # Parse XML to verify well-formedness
        root = ET.fromstring(xml_output)
        self.assertEqual(root.tag, "rss")
        self.assertEqual(root.attrib.get("version"), "2.0")

        channel = root.find("channel")
        self.assertIsNotNone(channel)
        self.assertEqual(channel.find("title").text, "SIT Patrol Test")

        item_el = channel.find("item")
        self.assertIsNotNone(item_el)
        self.assertEqual(item_el.find("title").text, "[新着リポジトリ] shibaura-org/new-project")
        self.assertEqual(item_el.find("guid").text, "shibaura-org/new-project")
        self.assertEqual(item_el.find("link").text, "https://github.com/shibaura-org/new-project")
        # Ensure special characters were properly escaped for HTML embedding
        desc_text = item_el.find("description").text
        self.assertIn("&lt;test &amp; special characters&gt;", desc_text)
        self.assertIn("<test & special characters>", html.unescape(desc_text))
        self.assertIn("Python", desc_text)


if __name__ == "__main__":
    unittest.main()
