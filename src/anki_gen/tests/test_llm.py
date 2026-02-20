import os
from types import SimpleNamespace

import pytest

from src.anki_gen import llm


class FakeOllamaClient:
    def __init__(self, response):
        self.response = response
        self.last_kwargs = None

    def chat(self, **kwargs):
        self.last_kwargs = kwargs
        return self.response


def test_call_ollama_non_stream_returns_content(monkeypatch):
    client = FakeOllamaClient({"message": {"content": "ollama-result"}})
    monkeypatch.setattr(llm, "_create_ollama_client", lambda: client)

    result = llm.call_ollama(
        prompt="hello",
        model="gpt-oss:120b-cloud",
        think="medium",
        stream=False,
    )

    assert result == "ollama-result"
    assert client.last_kwargs["model"] == "gpt-oss:120b-cloud"
    assert client.last_kwargs["think"] == "medium"
    assert client.last_kwargs["stream"] is False
    assert client.last_kwargs["messages"] == [{"role": "user", "content": "hello"}]


def test_call_ollama_stream_joins_only_content_chunks(monkeypatch):
    chunk_with_dict = {"message": {"content": "hello "}}
    chunk_with_object = SimpleNamespace(message=SimpleNamespace(content="world"))
    chunk_with_thinking = {"message": {"thinking": "..."}}
    chunk_without_message = SimpleNamespace()
    stream_response = [
        chunk_with_dict,
        chunk_with_object,
        chunk_with_thinking,
        chunk_without_message,
    ]

    client = FakeOllamaClient(stream_response)
    monkeypatch.setattr(llm, "_create_ollama_client", lambda: client)

    result = llm.call_ollama(
        prompt="hello",
        model="gpt-oss:120b-cloud",
        stream=True,
    )

    assert result == "hello world"
    assert client.last_kwargs["stream"] is True


def test_call_openai_uses_real_client_and_env_key():
    api_key = os.getenv("OPEN_AI_KEY")
    if not api_key:
        pytest.skip("OPEN_AI_KEY is not set")

    model = os.getenv("OPENAI_TEST_MODEL", "gpt-4o-mini")
    result = llm.call_openai(
        prompt="Respond with exactly: OK",
        model=model,
        stream=False,
    )

    print(result)

    assert isinstance(result, str)
    assert result.strip() != ""

def test_call_llm_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        llm.call_llm(prompt="p", model="m", provider="unknown")
