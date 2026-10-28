from dataclasses import dataclass
from datetime import datetime, timezone
import email.utils
import html
from typing import List, Optional
import xml.etree.ElementTree as ET


@dataclass
class FeedItem:
    id: str  # e.g., repo full_name: "owner/repo"
    title: str
    link: str
    published_at: str  # ISO 8601 or RFC 822
    description: str
    author: Optional[str] = None
    language: Optional[str] = None
    stars: int = 0
    query_name: Optional[str] = None


def to_rfc822(dt_str: Optional[str]) -> str:
    """Converts ISO 8601 string or returns RFC 822 string."""
    if not dt_str:
        return email.utils.format_datetime(datetime.now(timezone.utc))
    try:
        # Normalize trailing Z to +00:00 for fromisoformat
        clean_str = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return email.utils.format_datetime(dt)
    except Exception:
        return email.utils.format_datetime(datetime.now(timezone.utc))


def generate_rss(
    title: str,
    description: str,
    link: str,
    items: List[FeedItem],
) -> str:
    """Generates standard RSS 2.0 XML."""
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")

    c_title = ET.SubElement(channel, "title")
    c_title.text = title

    c_link = ET.SubElement(channel, "link")
    c_link.text = link

    c_desc = ET.SubElement(channel, "description")
    c_desc.text = description

    c_build_date = ET.SubElement(channel, "lastBuildDate")
    c_build_date.text = email.utils.format_datetime(datetime.now(timezone.utc))

    c_generator = ET.SubElement(channel, "generator")
    c_generator.text = "SIT-Patrol"

    for item in items:
        item_el = ET.SubElement(channel, "item")

        i_title = ET.SubElement(item_el, "title")
        i_title.text = item.title

        i_link = ET.SubElement(item_el, "link")
        i_link.text = item.link

        i_guid = ET.SubElement(item_el, "guid", {"isPermaLink": "false"})
        i_guid.text = item.id

        i_pub_date = ET.SubElement(item_el, "pubDate")
        i_pub_date.text = to_rfc822(item.published_at)

        if item.author:
            i_author = ET.SubElement(item_el, "author")
            i_author.text = item.author

        # Build HTML formatted description
        desc_parts = []
        if item.query_name:
            desc_parts.append(f"<p><strong>検知カテゴリ:</strong> {html.escape(item.query_name)}</p>")

        meta_parts = []
        if item.language:
            meta_parts.append(f"言語: {html.escape(item.language)}")
        if item.stars is not None:
            meta_parts.append(f"★ {item.stars}")
        if meta_parts:
            desc_parts.append(f"<p><strong>情報:</strong> {' | '.join(meta_parts)}</p>")

        if item.description:
            desc_parts.append("<hr />")
            desc_parts.append(f"<pre style='white-space: pre-wrap; font-family: sans-serif;'>{html.escape(item.description)}</pre>")

        i_desc = ET.SubElement(item_el, "description")
        i_desc.text = "".join(desc_parts)

    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_string = ET.tostring(rss, encoding="utf-8").decode("utf-8")
    return xml_declaration + xml_string
