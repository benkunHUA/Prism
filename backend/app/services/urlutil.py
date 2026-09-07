import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_KEYS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "spm", "from",
}
UPDATE_PREFIX = re.compile(
    r"^\s*(update|breaking|live|exclusive|新闻|快讯|更新)\s*[:：\-–—]?\s*", re.IGNORECASE
)
WS = re.compile(r"\s+")


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parts.path.rstrip("/") if parts.path not in ("", "/") else ""
    query = urlencode(
        sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in TRACKING_KEYS)
    )
    return urlunsplit((scheme, netloc, path, query, ""))


def normalize_title(title: str) -> str:
    title = UPDATE_PREFIX.sub("", title.strip())
    title = WS.sub(" ", title)
    return title.lower()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def dedupe_hash(url: str, title: str) -> str:
    return _sha(f"{normalize_url(url)}|{normalize_title(title)}")
