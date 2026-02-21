import json
import os
import random
from typing import Any


def make_prompt(
    main_block: str,
    context_before: str,
    context_after: str,
) -> str:
    # Import here to avoid a circular import at module import time
    from src.anki_gen.validator import CardsPayload

    schema_json = json.dumps(CardsPayload.model_json_schema(), ensure_ascii=False)
    # 50% of the time, add an instruction asking the model to make a distractor
    # (an incorrect option) longer/more detailed than the correct answer.
    extra_rule = ""
    try:
        if random.random() < 0.5:
            extra_rule = (
                "- When creating options, make at least one distractor (incorrect option) "
                "longer or more detailed than the correct answer.\n"
            )
    except Exception:
        extra_rule = ""
    return (
        "You create high-quality MultipleChoice Anki cards from study text.  Prefer questions that will likely appear in AWS certification exams."
        "Rules:\n"
        "- Make the cards self-contained. Provide enough context so that question is answerable. IMPORTANT: Do not assume the learner has read the main block. If you need to reference the main block, include the relevant information from it in the question.\n"
        "- CONTEXT_BEFORE and CONTEXT_AFTER are for understanding only; do not create cards from info found only in context.\n"
        "- options must have exactly 3 choices and include the answer.\n"
        "- Do not make repetitive cards; cover different facts/concepts in each card.\n"
        "- Avoid tells on distractors (e.g., the word 'only').\n"
        "- In the explanation, briefly explain why the answer is correct and the other options are incorrect.\n"
        f"{extra_rule}"
        "- Do not include any keys besides: cards, question, answer, options, explanation, topic, tags.\n"
        "- Follow this JSON schema exactly:\n"
        f"{schema_json}\n\n"
        "CONTEXT_BEFORE:\n"
        f"{context_before}\n\n"
        "MAIN_BLOCK:\n"
        f"{main_block}\n\n"
        "CONTEXT_AFTER:\n"
        f"{context_after}"
    )


def call_ollama(prompt: str, model: str, think: Any = None, stream: bool = False) -> Any:
    """Backward-compatible wrapper that calls Ollama provider."""
    return call_llm(
        prompt=prompt,
        model=model,
        provider="ollama",
        think=think,
        stream=stream,
    )


def call_openai(
    prompt: str,
    model: str,
    stream: bool = False,
    api_key: str | None = None,
) -> Any:
    """Call OpenAI and return the raw response content."""
    return call_llm(
        prompt=prompt,
        model=model,
        provider="openai",
        stream=stream,
        api_key=api_key,
    )


def call_llm(
    prompt: str,
    model: str,
    provider: str = "ollama",
    think: Any = None,
    stream: bool = False,
    api_key: str | None = None,
) -> Any:
    """Call a configured LLM provider and return raw content.

    Supported providers: ``ollama`` and ``openai``.
    """
    normalized_provider = provider.strip().lower()
    if normalized_provider == "ollama":
        return _call_ollama(prompt=prompt, model=model, think=think, stream=stream)
    if normalized_provider == "openai":
        return _call_openai(
            prompt=prompt,
            model=model,
            stream=stream,
            api_key=api_key,
        )
    raise ValueError(f"Unsupported LLM provider: {provider}")


def _create_ollama_client() -> Any:
    from ollama import Client

    return Client()


def _create_openai_client(api_key: str) -> Any:
    from openai import OpenAI

    return OpenAI(api_key=api_key)


def _call_ollama(prompt: str, model: str, think: Any = None, stream: bool = False) -> Any:
    """Call Ollama and return response content."""
    # Import here to avoid circular imports at module import time
    from src.anki_gen.validator import CardsPayload

    client = _create_ollama_client()
    messages = [
        {
            "role": "user",
            "content": prompt,
        },
    ]
    try:
        params = {
            "model": model,
            "messages": messages,
            "format": CardsPayload.model_json_schema(),
            "options": {"temperature": 0.2},
            "stream": stream,
        }
        if think is not None:
            params["think"] = think

        response = client.chat(**params)

        if stream:
            # Consume the stream but ignore `thinking` chunks; collect and
            # return the final assembled content string.
            final_parts = []
            for chunk in response:
                # Different client implementations may expose message as a
                # dict-like or object; handle both.
                msg = None
                try:
                    msg = chunk["message"]
                except Exception:
                    msg = getattr(chunk, "message", None)

                if not msg:
                    continue

                # Extract content if present; some chunks may carry `thinking`.
                content = None
                try:
                    content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
                except Exception:
                    content = None

                if content:
                    final_parts.append(content)

            return "".join(final_parts)

        return response["message"]["content"]
    except Exception as exc:
        raise RuntimeError(f"Failed to call Ollama: {exc}") from exc


def _call_openai(
    prompt: str,
    model: str,
    stream: bool = False,
    api_key: str | None = None,
) -> Any:
    """Call OpenAI and return response content."""
    # Import here to avoid circular imports at module import time
    from src.anki_gen.validator import CardsPayload

    resolved_api_key = api_key or os.getenv("OPEN_AI_KEY")
    if not resolved_api_key:
        raise RuntimeError("OPEN_AI_KEY environment variable is required for OpenAI provider")

    client = _create_openai_client(api_key=resolved_api_key)
    messages = [
        {
            "role": "user",
            "content": prompt,
        },
    ]

    try:
        if stream:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
                stream=True,
            )
            final_parts = []
            for chunk in response:
                choices = getattr(chunk, "choices", None)
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                if not delta:
                    continue
                content = getattr(delta, "content", None)
                if content:
                    final_parts.append(content)
            return "".join(final_parts)

        completion = client.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=CardsPayload,
        )
        message = completion.choices[0].message

        refusal = getattr(message, "refusal", None)
        if refusal:
            raise RuntimeError(f"OpenAI refused request: {refusal}")

        parsed = getattr(message, "parsed", None)
        if parsed is None:
            raise RuntimeError("OpenAI response did not include parsed structured output")

        return parsed.model_dump()
    except Exception as exc:
        raise RuntimeError(f"Failed to call OpenAI: {exc}") from exc
