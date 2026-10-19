"""Language model factory supporting Gemini, scripted demo, and fake test models."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from campaign.config import get_settings


class FakeToolModel(GenericFakeChatModel):
    """Fake model returning predefined sequence of AIMessages while binding tools."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> FakeToolModel:
        return self


def get_chat_model(
    llm_mode: str | None = None,
    fake_messages: list[Any] | None = None,
) -> Any:
    """Return configured chat model based on execution mode or fake messages."""
    if fake_messages is not None:
        return FakeToolModel(messages=iter(fake_messages))

    settings = get_settings()
    mode = llm_mode if llm_mode is not None else settings.llm_mode

    if mode == "gemini":
        key = settings.gemini_api_key.get_secret_value()
        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=key,
            temperature=0,
            max_retries=2,
            timeout=60,
            max_output_tokens=settings.max_output_tokens,
        )

    if mode == "scripted":
        # Lazy import of scripted demo model (implemented in T11)
        from campaign.scripted import ScriptedChatModel

        return ScriptedChatModel()

    raise ValueError(f"Unknown LLM mode: '{mode}'. Expected 'gemini' or 'scripted'")
