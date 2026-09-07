from app.services.urlutil import dedupe_hash, normalize_title, normalize_url


def test_normalize_url_strips_tracking_and_fragment():
    assert normalize_url("HTTPS://Example.com/Path/?utm_source=x&a=1#frag") == "https://example.com/Path?a=1"


def test_normalize_title_strips_update_markers():
    assert normalize_title("Update: Breaking  News  Now") == "breaking news now"


def test_dedupe_hash_stable():
    h1 = dedupe_hash("https://x.com/a/?utm_source=t", "Update: Fed Hikes Rates")
    h2 = dedupe_hash("https://x.com/a/", "Fed hikes rates")
    assert h1 == h2
