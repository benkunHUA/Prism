from __future__ import annotations

import time

import httpx

from app.core.config import Settings


class LLMResponseError(RuntimeError):
    """LLM 返回内容不可用：空内容，或被 max_tokens 截断。"""


class ChatProvider:
    name = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def complete(self, messages: list[dict], temperature: float = 0.2,
                 max_tokens: int = 4000) -> str:
        raise NotImplementedError


class _OpenAICompatProvider(ChatProvider):
    api_key_field = "deepseek_api_key"

    def complete(self, messages: list[dict], temperature: float = 0.2,
                 max_tokens: int = 4000) -> str:
        key = getattr(self.settings, self.api_key_field)
        if not key:
            raise RuntimeError(f"{self.api_key_field.upper()} 未配置")
        url = self.settings.llm_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Authorization": f"Bearer {key}"}
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                resp = httpx.post(url, json=payload, headers=headers, timeout=120.0)
            except httpx.HTTPError as exc:
                last_error = exc
                time.sleep(2**attempt)
                continue
            if resp.status_code in (429, 500, 502, 503):
                last_error = RuntimeError(f"LLM HTTP {resp.status_code}: {resp.text[:200]}")
                time.sleep(2**attempt)
                continue
            resp.raise_for_status()
            data = resp.json()
            choice = (data.get("choices") or [{}])[0]
            content = ((choice.get("message") or {}).get("content") or "").strip()
            finish_reason = choice.get("finish_reason")
            if not content:
                raise LLMResponseError(
                    f"LLM 返回空内容（finish_reason={finish_reason}，模型={self.settings.llm_model}）。"
                    "推理模型会把输出预算消耗在 reasoning 上：请调大 LLM_DAILY_MAX_TOKENS / "
                    "LLM_BRIEF_MAX_TOKENS，或改用非推理模型（如 deepseek-chat）"
                )
            if finish_reason == "length":
                raise LLMResponseError(
                    f"LLM 输出被 max_tokens 截断（模型={self.settings.llm_model}），"
                    "已丢弃不完整内容；请调大对应 max_tokens 配置"
                )
            return content
        raise RuntimeError(f"LLM 调用失败: {last_error}")


class DeepSeekProvider(_OpenAICompatProvider):
    name = "deepseek"
    api_key_field = "deepseek_api_key"


class OpenAIProvider(_OpenAICompatProvider):
    name = "openai"
    api_key_field = "openai_api_key"


def get_provider(settings: Settings) -> ChatProvider:
    providers = {"deepseek": DeepSeekProvider, "openai": OpenAIProvider}
    cls = providers.get(settings.llm_provider)
    if cls is None:
        raise RuntimeError(f"未知 LLM provider: {settings.llm_provider}")
    return cls(settings)
