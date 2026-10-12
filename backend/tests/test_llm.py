import pytest

from app.core.config import Settings
from app.services.llm import ChatProvider, get_provider


class FakeProvider(ChatProvider):
    name = "fake"

    def complete(self, messages, temperature=0.2, max_tokens=4000) -> str:
        return "ok"


def test_fake_provider_contract():
    provider = FakeProvider(Settings(_env_file=None))
    assert provider.complete([{"role": "user", "content": "hi"}]) == "ok"


def test_factory_maps_deepseek():
    settings = Settings(_env_file=None, llm_provider="deepseek")
    assert get_provider(settings).name == "deepseek"


def test_missing_key_raises():
    from app.services.llm import DeepSeekProvider

    settings = Settings(_env_file=None, llm_provider="deepseek", deepseek_api_key="")
    provider = DeepSeekProvider(settings)
    with pytest.raises(RuntimeError, match="未配置"):
        provider.complete([{"role": "user", "content": "hi"}])


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _patch_post(monkeypatch, payload: dict):
    monkeypatch.setattr("app.services.llm.httpx.post", lambda *a, **k: _FakeResponse(payload))


def _deepseek():
    from app.services.llm import DeepSeekProvider

    return DeepSeekProvider(Settings(_env_file=None, deepseek_api_key="test-key"))


def test_provider_returns_content(monkeypatch):
    _patch_post(monkeypatch, {"choices": [{"message": {"content": "  正文  "}, "finish_reason": "stop"}]})
    assert _deepseek().complete([{"role": "user", "content": "hi"}]) == "正文"


def test_provider_raises_on_empty_content(monkeypatch):
    _patch_post(monkeypatch, {
        "choices": [{"message": {"content": "", "reasoning_content": "推理占满预算"}, "finish_reason": "length"}],
        "usage": {"completion_tokens_details": {"reasoning_tokens": 4000}},
    })
    with pytest.raises(RuntimeError, match="空内容"):
        _deepseek().complete([{"role": "user", "content": "hi"}])


def test_provider_raises_on_truncated_content(monkeypatch):
    _patch_post(monkeypatch, {"choices": [{"message": {"content": "## 今日要闻\n- 半截"}, "finish_reason": "length"}]})
    with pytest.raises(RuntimeError, match="截断"):
        _deepseek().complete([{"role": "user", "content": "hi"}])


def _capture_payload(monkeypatch) -> dict:
    captured: dict = {}

    def fake_post(url, json=None, headers=None, timeout=None):  # noqa: ANN001
        captured.update(json or {})
        return _FakeResponse(
            {"choices": [{"message": {"content": "正文"}, "finish_reason": "stop"}]}
        )

    monkeypatch.setattr("app.services.llm.httpx.post", fake_post)
    return captured


def test_thinking_disabled_is_sent_to_deepseek(monkeypatch):
    from app.services.llm import DeepSeekProvider

    captured = _capture_payload(monkeypatch)
    settings = Settings(_env_file=None, deepseek_api_key="k", llm_thinking="disabled")
    DeepSeekProvider(settings).complete([{"role": "user", "content": "hi"}])
    assert captured["thinking"] == {"type": "disabled"}


def test_thinking_auto_omits_parameter(monkeypatch):
    from app.services.llm import DeepSeekProvider

    captured = _capture_payload(monkeypatch)
    settings = Settings(_env_file=None, deepseek_api_key="k", llm_thinking="auto")
    DeepSeekProvider(settings).complete([{"role": "user", "content": "hi"}])
    assert "thinking" not in captured


def test_openai_provider_never_sends_thinking(monkeypatch):
    from app.services.llm import OpenAIProvider

    captured = _capture_payload(monkeypatch)
    settings = Settings(_env_file=None, openai_api_key="k", llm_thinking="disabled")
    OpenAIProvider(settings).complete([{"role": "user", "content": "hi"}])
    assert "thinking" not in captured
