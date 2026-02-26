import re
from book_to_abook.llm_preprocess import describe_and_replace_codes


def test_fenced_and_inline_replacement():
    text = (
        "Before code:\n`````python\nprint(\"Hello World\")\n```\n"
        "And inline `x = 1` afterwards."
    )

    def fake_ollama(prompt: str) -> str:
        # prompt is the LLM prompt + two newlines + the code; extract code
        parts = prompt.split("\n\n", 1)
        code = parts[1] if len(parts) > 1 else prompt
        return f"Explains: {code.strip()}"

    out = describe_and_replace_codes(text, ollama_fn=fake_ollama, model="test-model")

    assert "[Code description]\nExplains: print(\"Hello World\")\n" in out
    assert "[code: Explains: x = 1]" in out


def test_cache_prevents_duplicate_calls():
    text = "First:\n```\nx = 42\n```\nSecond:\n```\nx = 42\n```\n"

    calls = {"count": 0}

    def fake_ollama(prompt: str) -> str:
        calls["count"] += 1
        parts = prompt.split("\n\n", 1)
        code = parts[1] if len(parts) > 1 else prompt
        return f"Desc: {code.strip()}"

    out = describe_and_replace_codes(text, ollama_fn=fake_ollama, model="test-model")

    # Both fenced blocks should be replaced
    assert out.count("[Code description]") == 2
    # But the LLM should have been called only once due to caching
    assert calls["count"] == 1
