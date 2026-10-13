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


def test_empty_articles_returns_zero(db):
    settings = Settings(_env_file=None, translate_batch_size=10)
    provider = ScriptedProvider(settings, lambda messages, call_no: _payload([0]))

    done, errors = translate_articles(db, [], provider, settings)

    assert (done, errors) == (0, [])
    assert provider.calls == 0


def test_batch_size_zero_uses_single_article_batches(db):
    settings = Settings(_env_file=None, translate_batch_size=0)
    rows = _articles(db, 3)
    provider = ScriptedProvider(settings, lambda messages, call_no: _payload([0]))

    done, errors = translate_articles(db, rows, provider, settings)

    assert provider.calls == 3
    assert done == 3
    assert errors == []


def test_fenced_json_is_accepted(db):
    settings = Settings(_env_file=None, translate_batch_size=10)
    rows = _articles(db, 2)
    fenced = "```json\n" + _payload([0, 1]) + "\n```"
    provider = ScriptedProvider(settings, lambda messages, call_no: fenced)

    done, errors = translate_articles(db, rows, provider, settings)

    assert (done, errors) == (2, [])
    assert provider.calls == 1


def test_non_array_payload_splits(db):
    settings = Settings(_env_file=None, translate_batch_size=2)
    rows = _articles(db, 2)
    provider = ScriptedProvider(settings, lambda messages, call_no: "{}")

    done, errors = translate_articles(db, rows, provider, settings)

    assert provider.calls == 3
    assert done == 0
    assert len(errors) == 2
    assert rows[0].title_zh is None and rows[1].title_zh is None


def test_bool_index_is_rejected(db):
    settings = Settings(_env_file=None, translate_batch_size=10)
    rows = _articles(db, 2)
    payload = json.dumps(
        [{"index": True, "title_zh": "错位", "summary_zh": "x"}],
        ensure_ascii=False,
    )
    provider = ScriptedProvider(settings, lambda messages, call_no: payload)

    done, errors = translate_articles(db, rows, provider, settings)

    assert done == 0
    assert len(errors) == 2
    assert rows[0].title_zh is None and rows[1].title_zh is None


def test_prompt_limits_and_call_arguments(db):
    settings = Settings(_env_file=None, translate_batch_size=10,
                        llm_translate_max_tokens=1234)
    rows = _articles(db, 1)
    rows[0].summary = "x" * 5000
    db.commit()
    seen: dict = {}

    class CaptureProvider(ChatProvider):
        name = "capture"

        def complete(self, messages, temperature=0.2, max_tokens=4000) -> str:
            seen["messages"] = messages
            seen["temperature"] = temperature
            seen["max_tokens"] = max_tokens
            return _payload([0])

    provider = CaptureProvider(settings)

    done, errors = translate_articles(db, rows, provider, settings)

    assert (done, errors) == (1, [])
    content = seen["messages"][0]["content"]
    summary_line = next(line for line in content.splitlines() if line.startswith("[0] 摘要："))
    assert summary_line == "[0] 摘要：" + "x" * 1000
    assert seen["temperature"] == 0.0
    assert seen["max_tokens"] == 1234


def test_commit_failure_does_not_raise(db, monkeypatch):
    settings = Settings(_env_file=None, translate_batch_size=10)

    def boom():
        raise RuntimeError("disk full")

    # 正常翻译路径：写库失败降级为错误，不逃逸
    rows = _articles(db, 2)
    provider = ScriptedProvider(settings, lambda messages, call_no: _payload([0, 1]))
    monkeypatch.setattr(db, "commit", boom)

    done, errors = translate_articles(db, rows, provider, settings)

    assert done == 0
    assert len(errors) == 2
    assert all("disk full" in message for message in errors)

    # 中文原文直接落库路径：同样不逃逸（复用同一来源，避免重复来源冲突）
    monkeypatch.undo()
    articles_repo.insert_articles(db, [
        dict(source_id=rows[0].source_id, category="politics",
             url="https://example.com/zh0", title="中文标题", summary="中文摘要",
             content_text="", published_at=None, lang="zh", dedupe_hash="zh0"),
    ])
    zh_rows = [row for row in articles_repo.list_articles(db) if row.lang == "zh"]
    provider_zh = ScriptedProvider(settings, lambda messages, call_no: "不该被调用")
    monkeypatch.setattr(db, "commit", boom)

    done_zh, errors_zh = translate_articles(db, zh_rows, provider_zh, settings)

    assert done_zh == 0
    assert len(errors_zh) == 1
    assert "disk full" in errors_zh[0]
    assert provider_zh.calls == 0


def test_rollback_failure_does_not_raise(db, monkeypatch):
    settings = Settings(_env_file=None, translate_batch_size=10)
    rows = _articles(db, 1)
    provider = ScriptedProvider(settings, lambda messages, call_no: _payload([0]))

    def boom(*args, **kwargs):
        raise RuntimeError("connection lost")

    monkeypatch.setattr(db, "commit", boom)
    monkeypatch.setattr(db, "rollback", boom)

    done, errors = translate_articles(db, rows, provider, settings)

    assert done == 0
    assert len(errors) == 1
    assert "connection lost" in errors[0]


def test_non_string_title_zh_is_dropped(db):
    settings = Settings(_env_file=None, translate_batch_size=10)
    rows = _articles(db, 2)
    payload = json.dumps(
        [{"index": 0, "title_zh": 123, "summary_zh": "要点"},
         {"index": 1, "title_zh": "标题1", "summary_zh": "要点1"}],
        ensure_ascii=False,
    )
    provider = ScriptedProvider(settings, lambda messages, call_no: payload)

    done, errors = translate_articles(db, rows, provider, settings)

    assert (done, len(errors)) == (1, 1)          # 同一批里另一条照常落库
    assert "模型未返回该条" in errors[0]           # 非法条目按缺项丢弃，不是整批炸掉
    assert rows[0].title_zh is None
    assert rows[1].title_zh == "标题1"


def test_blank_native_title_is_reported(db):
    settings = Settings(_env_file=None)
    articles_repo.insert_articles(db, [
        dict(source_id=_articles(db, 1)[0].source_id, category="politics",
             url="https://example.com/blank", title="", summary="摘要",
             content_text="", published_at=None, lang="zh", dedupe_hash="blank"),
    ])
    blank_rows = [row for row in articles_repo.list_articles(db) if row.url.endswith("/blank")]
    provider = ScriptedProvider(settings, lambda messages, call_no: "不该被调用")

    done, errors = translate_articles(db, blank_rows, provider, settings)

    assert done == 0
    assert len(errors) == 1
    assert "原文标题为空" in errors[0]
    assert provider.calls == 0
