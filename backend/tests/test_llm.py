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
