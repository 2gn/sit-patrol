import base64
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        self.token = token.strip() if token else None

    def _build_request(self, path: str, params: Optional[Dict[str, Any]] = None) -> urllib.request.Request:
        url = f"{self.BASE_URL}{path}"
        if params:
            query_string = urllib.parse.urlencode(params)
            url = f"{url}?{query_string}"

        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("User-Agent", "sit-patrol-bot")

        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")

        return req

    def _execute(self, req: urllib.request.Request) -> Dict[str, Any]:
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                remaining = response.headers.get("x-ratelimit-remaining")
                if remaining is not None and int(remaining) < 5:
                    reset_time = int(response.headers.get("x-ratelimit-reset", 0))
                    wait_sec = max(reset_time - int(time.time()), 0)
                    logger.warning("GitHub API rate limit low (remaining: %s). Reset in %ds", remaining, wait_sec)

                charset = response.headers.get_content_charset() or "utf-8"
                data = response.read().decode(charset)
                return json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}
            if e.code in (403, 429):
                reset_time = e.headers.get("x-ratelimit-reset")
                logger.error("Rate limited by GitHub API (HTTP %d). Reset: %s", e.code, reset_time)
            error_body = e.read().decode("utf-8", errors="replace")
            logger.error("HTTP error %d accessing %s: %s", e.code, req.full_url, error_body)
            raise

    def search_repositories(
        self, query: str, sort: str = "created", order: str = "desc", per_page: int = 30
    ) -> List[Dict[str, Any]]:
        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": min(per_page, 100),
        }
        req = self._build_request("/search/repositories", params)
        res = self._execute(req)
        return res.get("items", [])

    def get_readme(self, owner: str, repo: str, max_chars: int = 15000) -> Optional[str]:
        req = self._build_request(f"/repos/{owner}/{repo}/readme")
        try:
            res = self._execute(req)
            if not res or "content" not in res:
                return None
            encoding = res.get("encoding", "base64")
            raw_content = res["content"]
            if encoding == "base64":
                decoded = base64.b64decode(raw_content).decode("utf-8", errors="replace")
            else:
                decoded = str(raw_content)

            if len(decoded) > max_chars:
                decoded = decoded[:max_chars] + "\n\n... (README truncated for feed display) ..."
            return decoded
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            logger.warning("Could not fetch README for %s/%s: %s", owner, repo, e)
            return None
        except Exception as e:
            logger.warning("Error decoding README for %s/%s: %s", owner, repo, e)
            return None
