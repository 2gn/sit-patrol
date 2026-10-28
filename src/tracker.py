import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Set

from src.config import AppConfig
from src.github_client import GitHubClient
from src.rss_generator import FeedItem, generate_rss

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("sit-patrol")


def load_state(data_dir: Path) -> Dict[str, Any]:
    index_file = data_dir / "index.json"
    if not index_file.exists():
        logger.info("index.json not found in %s, initializing empty state", data_dir)
        return {"version": 1, "last_updated": None, "seen_ids": [], "items": []}

    try:
        with index_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {"version": 1, "last_updated": None, "seen_ids": [], "items": []}
            return data
    except Exception as e:
        logger.warning("Failed to parse index.json (%s), creating fresh state", e)
        return {"version": 1, "last_updated": None, "seen_ids": [], "items": []}


def is_repo_allowed(
    repo_id: str,
    is_private: bool,
    owner: str,
    filters: Any,
) -> bool:
    if filters.ignore_private and is_private:
        return False
    owner_lower = owner.lower() if owner else ""
    repo_lower = repo_id.lower() if repo_id else ""
    current_repo = os.getenv("GITHUB_REPOSITORY", "").lower()
    if current_repo and repo_lower == current_repo:
        return False
    if owner_lower in filters.exclude_owners:
        return False
    if repo_lower in filters.exclude_repos:
        return False
    return True


def save_state(data_dir: Path, state: Dict[str, Any], rss_content: str) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    index_file = data_dir / "index.json"
    rss_file = data_dir / "rss.xml"

    temp_index = data_dir / "index.json.tmp"
    temp_rss = data_dir / "rss.xml.tmp"

    with temp_index.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    temp_index.replace(index_file)

    with temp_rss.open("w", encoding="utf-8") as f:
        f.write(rss_content)
    temp_rss.replace(rss_file)

    logger.info("Updated state saved to %s and %s", index_file, rss_file)


def run_tracker(
    config_path: str | Path,
    data_dir_path: str | Path,
    token: str | None = None,
    dry_run: bool = False,
) -> int:
    config = AppConfig.load_from_file(config_path)
    data_dir = Path(data_dir_path)

    state = load_state(data_dir)
    seen_ids: Set[str] = set(state.get("seen_ids", []))
    existing_items: List[Dict[str, Any]] = state.get("items", [])

    auth_token = token or os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN")
    client = GitHubClient(token=auth_token)

    new_feed_items: List[FeedItem] = []
    run_seen_this_batch: Set[str] = set()

    logger.info("Executing %d patrol queries...", len(config.queries))

    for q in config.queries:
        logger.info("Running query '%s': %s", q.name, q.query)
        try:
            repos = client.search_repositories(
                query=q.query,
                sort=q.sort,
                order=q.order,
                per_page=30,
            )
            logger.info("Found %d repositories for query '%s'", len(repos), q.name)
        except Exception as e:
            logger.error("Query failed for '%s': %s", q.name, e)
            continue

        for repo in repos:
            repo_id = repo.get("full_name")
            if not repo_id:
                continue

            is_private = bool(repo.get("private", False))
            owner = repo.get("owner", {}).get("login", "")

            # Check if repo is allowed by filter settings
            if not is_repo_allowed(repo_id, is_private, owner, config.filters):
                logger.info("Skipping filtered repository: %s (private=%s, owner=%s)", repo_id, is_private, owner)
                continue

            # Skip if already seen in past runs or earlier in this run
            if repo_id in seen_ids or repo_id in run_seen_this_batch:
                continue

            run_seen_this_batch.add(repo_id)

            owner = repo.get("owner", {}).get("login", "")
            repo_name = repo.get("name", "")
            created_at = repo.get("created_at") or datetime.now(timezone.utc).isoformat()
            repo_desc = repo.get("description") or "説明なし"
            html_url = repo.get("html_url") or f"https://github.com/{repo_id}"
            language = repo.get("language")
            stars = repo.get("stargazers_count", 0)

            logger.info("New repository detected: %s (query: %s)", repo_id, q.name)

            readme_text = client.get_readme(owner, repo_name)
            content_desc = repo_desc
            if readme_text:
                content_desc = f"{repo_desc}\n\n--- README ---\n{readme_text}"

            item = FeedItem(
                id=repo_id,
                title=f"[新着リポジトリ] {repo_id}",
                link=html_url,
                published_at=created_at,
                description=content_desc,
                author=owner,
                language=language,
                stars=stars,
                query_name=q.name,
            )
            new_feed_items.append(item)

    logger.info("Total new items found in this patrol run: %d", len(new_feed_items))

    # Convert existing stored dicts to FeedItem objects, applying exclusion filters
    existing_feed_items: List[FeedItem] = []
    purged_ids: Set[str] = set()
    for d in existing_items:
        item_id = d.get("id", "")
        author = d.get("author") or (item_id.split("/")[0] if "/" in item_id else "")
        if not is_repo_allowed(item_id, is_private=False, owner=author, filters=config.filters):
            logger.info("Purging excluded repository from existing state: %s", item_id)
            purged_ids.add(item_id)
            continue

        existing_feed_items.append(
            FeedItem(
                id=item_id,
                title=d.get("title", ""),
                link=d.get("link", ""),
                published_at=d.get("published_at", ""),
                description=d.get("description", ""),
                author=author,
                language=d.get("language"),
                stars=d.get("stars", 0),
                query_name=d.get("query_name"),
            )
        )

    all_items = new_feed_items + existing_feed_items
    # Truncate to maximum items specified in config
    max_items = config.feed.max_items
    all_items = all_items[:max_items]

    # Update seen_ids list, removing purged items
    updated_seen_ids = [i for i in seen_ids.union(run_seen_this_batch) if i not in purged_ids]
    # Cap seen_ids to last 1000 items to avoid infinite unbounded growth
    if len(updated_seen_ids) > 1000:
        updated_seen_ids = updated_seen_ids[-1000:]

    now_iso = datetime.now(timezone.utc).isoformat()
    updated_state = {
        "version": 1,
        "last_updated": now_iso,
        "seen_ids": updated_seen_ids,
        "items": [
            {
                "id": it.id,
                "title": it.title,
                "link": it.link,
                "published_at": it.published_at,
                "description": it.description,
                "author": it.author,
                "language": it.language,
                "stars": it.stars,
                "query_name": it.query_name,
            }
            for it in all_items
        ],
    }

    rss_xml = generate_rss(
        title=config.feed.title,
        description=config.feed.description,
        link=config.feed.link,
        items=all_items,
    )

    if dry_run:
        logger.info("[Dry Run] Would write %d items to RSS feed", len(all_items))
        return len(new_feed_items)

    save_state(data_dir, updated_state, rss_xml)
    return len(new_feed_items)


def main() -> None:
    parser = argparse.ArgumentParser(description="SIT Patrol GitHub Tracker")
    parser.add_argument("--config", default="config.yml", help="Path to config.yml")
    parser.add_argument("--data-dir", default="data", help="Directory containing index.json and rss.xml")
    parser.add_argument("--token", default=None, help="GitHub Personal Access Token")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing files")

    args = parser.parse_args()

    try:
        run_tracker(
            config_path=args.config,
            data_dir_path=args.data_dir,
            token=args.token,
            dry_run=args.dry_run,
        )
    except Exception as e:
        logger.exception("Tracker failed with unhandled exception: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
