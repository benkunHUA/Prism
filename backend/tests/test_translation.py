import json

from app.core.config import Settings
from app.models.entities import Article
from app.repositories import articles as articles_repo
from app.repositories import sources as sources_repo
from app.services.llm import ChatProvider
from app.services.translation.translator import translate_articles


class ScriptedProvider(ChatProvider):
    """按调用次序返回预设结果，并记录调用次数。"""

    name = "scripted"

    def __init__(self, settings, script):
        super().__init__(settings)
        self.script = script
        self.calls = 0

    def complete(self, messages, temperature=0.2, max_tokens=4000) -> str:
        self.calls += 1
        return self.script(messages, self.calls)


def _articles(db, count: int, *, lang: str = "en") -> list[Article]:
    src = sources_repo.create_source(db, name="S", url="https://example.com/feed",
                                     feed_type="rss", lang="en", categories=["politics"])
    articles_repo.insert_articles(db, [
        dict(source_id=src.id, category="politics", url=f"https://example.com/a{i}",
             title=f"Title {i}", summary=f"Summary {i}", content_text="",
             published_at=None, lang=lang, dedupe_hash=f"h{i}")
        for i in range(count)
    ])
    return articles_repo.list_articles(db)


def _payload(indexes: list[int]) -> str:
    return json.dumps(
        [{"index": i, "title_zh": f"标题{i}", "summary_zh": f"要点{i}"} for i in indexes],
        ensure_ascii=False,
    )


def test_batch_translates_in_one_call(db):
    settings = Settings(_env_file=None, translate_batch_size=10)
    rows = _articles(db, 3)
    provider = ScriptedProvider(settings, lambda messages, call_no: _payload([0, 1, 2]))

    done, errors = translate_articles(db, rows, provider, settings)

    assert (done, errors) == (3, [])
    assert provider.calls == 1
    assert [row.title_zh for row in rows] == ["标题0", "标题1", "标题2"]
    assert [row.summary_zh for row in rows] == ["要点0", "要点1", "要点2"]


def test_missing_index_keeps_returned_ones(db):
    settings = Settings(_env_file=None, translate_batch_size=10)
    rows = _articles(db, 3)
    provider = ScriptedProvider(settings, lambda messages, call_no: _payload([0]))

    done, errors = translate_articles(db, rows, provider, settings)

    assert done == 1
    assert len(errors) == 2
    assert all("翻译失败" in message for message in errors)
    assert provider.calls == 1  # 缺项不触发减半重试
    assert rows[0].title_zh == "标题0"
    assert rows[1].title_zh is None and rows[2].title_zh is None


def test_duplicate_and_out_of_range_index_are_ignored(db):
    settings = Settings(_env_file=None, translate_batch_size=10)
    rows = _articles(db, 1)
    payload = json.dumps(
        [{"index": 0, "title_zh": "第一次", "summary_zh": "a"},
         {"index": 0, "title_zh": "第二次", "summary_zh": "b"},
         {"index": 9, "title_zh": "越界", "summary_zh": "c"}],
        ensure_ascii=False,
    )
    provider = ScriptedProvider(settings, lambda messages, call_no: payload)

    done, errors = translate_articles(db, rows, provider, settings)

    assert (done, errors) == (1, [])
    assert rows[0].title_zh == "第一次"


def test_invalid_output_splits_down_to_single(db):
    settings = Settings(_env_file=None, translate_batch_size=2)
    rows = _articles(db, 2)

    def script(messages, call_no):
        if call_no == 1:
            return "这不是 JSON"
        if call_no == 2:
            return _payload([0])
        return "这也不是 JSON"

    provider = ScriptedProvider(settings, script)

    done, errors = translate_articles(db, rows, provider, settings)

    assert provider.calls == 3  # 整批 → 拆两半
    assert done == 1
    assert len(errors) == 1
    assert rows[0].title_zh == "标题0"
    assert rows[1].title_zh is None


def test_provider_exception_does_not_raise(db):
    settings = Settings(_env_file=None, translate_batch_size=1)
    rows = _articles(db, 1)

    def script(messages, call_no):
        raise RuntimeError("boom")

    provider = ScriptedProvider(settings, script)

    done, errors = translate_articles(db, rows, provider, settings)

    assert done == 0
    assert len(errors) == 1


def test_chinese_source_written_without_model(db):
    settings = Settings(_env_file=None)
    rows = _articles(db, 2, lang="zh")
    provider = ScriptedProvider(settings, lambda messages, call_no: "不该被调用")

    done, errors = translate_articles(db, rows, provider, settings)

    assert (done, errors) == (2, [])
    assert provider.calls == 0
    # list_articles 按 fetched_at desc 排序，行序非插入序，故按内容断言
    assert all(row.title_zh == row.title for row in rows)


def test_existing_translation_is_not_overwritten(db):
    settings = Settings(_env_file=None)
    rows = _articles(db, 2)
    rows[0].title_zh = "已有译文"
    db.commit()
    provider = ScriptedProvider(settings, lambda messages, call_no: _payload([0]))

    done, errors = translate_articles(db, rows, provider, settings)

    assert (done, errors) == (1, [])
    assert provider.calls == 1
    assert rows[0].title_zh == "已有译文"
    assert rows[1].title_zh == "标题0"
