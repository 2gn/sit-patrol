from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List
import yaml


@dataclass
class QueryConfig:
    id: str
    name: str
    query: str
    sort: str = "created"
    order: str = "desc"


@dataclass
class FeedConfig:
    title: str = "SIT Patrol"
    description: str = "Shibaura Institute of Technology GitHub Tracker"
    link: str = "https://github.com/2gn/sit-patrol"
    max_items: int = 50


@dataclass
class FilterConfig:
    ignore_private: bool = True
    exclude_owners: List[str] = field(default_factory=list)
    exclude_repos: List[str] = field(default_factory=list)


@dataclass
class AppConfig:
    feed: FeedConfig = field(default_factory=FeedConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    queries: List[QueryConfig] = field(default_factory=list)

    @classmethod
    def load_from_file(cls, path: str | Path) -> "AppConfig":
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        with file_path.open("r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f) or {}

        feed_data = raw_data.get("feed", {})
        feed_config = FeedConfig(
            title=feed_data.get("title", "SIT Patrol"),
            description=feed_data.get("description", "Shibaura Institute of Technology GitHub Tracker"),
            link=feed_data.get("link", "https://github.com/2gn/sit-patrol"),
            max_items=int(feed_data.get("max_items", 50)),
        )

        filter_data = raw_data.get("filters", {})
        filter_config = FilterConfig(
            ignore_private=bool(filter_data.get("ignore_private", True)),
            exclude_owners=[str(o).lower() for o in filter_data.get("exclude_owners", [])],
            exclude_repos=[str(r).lower() for r in filter_data.get("exclude_repos", [])],
        )

        queries_data = raw_data.get("queries", [])
        queries: List[QueryConfig] = []
        for q in queries_data:
            queries.append(
                QueryConfig(
                    id=q.get("id", ""),
                    name=q.get("name", q.get("query", "")),
                    query=q.get("query", ""),
                    sort=q.get("sort", "created"),
                    order=q.get("order", "desc"),
                )
            )

        return cls(feed=feed_config, filters=filter_config, queries=queries)
