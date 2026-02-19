import json
from typing import Any

from ollama import Client


def make_prompt(
    main_block: str,
    context_before: str,
    context_after: str,
) -> str:
    # Import here to avoid a circular import at module import time
    from ollama_anki_from_epub_out import CardsPayload

    schema_json = json.dumps(CardsPayload.model_json_schema(), ensure_ascii=False)
    return (
        "You create high-quality MultipleChoice Anki cards from study text.  Prefer questions that will likely appear in AWS certification exams."
        "Rules:\n"
        "- Make the cards self-contained. Provide enough context so that question is answerable. IMPORTANT: Do not assume the learner has read the main block."
        "- Use facts from MAIN_BLOCK only when writing questions/answers.\n"
        "- CONTEXT_BEFORE and CONTEXT_AFTER are for understanding only; do not create cards from info found only in context.\n"
        "- options must have exactly 3 choices and include the answer.\n"
        "- Keep cards factual and strictly grounded in MAIN_BLOCK.\n"
        "- Do not make repetitive cards; cover different facts/concepts in each card.\n"
        "- In the explanation, briefly explain why the answer is correct and the other options are incorrect.\n"
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
    """Call Ollama and return the raw response content.

    If `stream` is True this returns the iterator/generator from `client.chat()` so
    the caller can iterate over streaming chunks (including `chunk.message.thinking`).

    `think` may be passed through to the API (e.g. 'low', 'medium', 'high' for
    GPT-OSS models). If `think` is None it isn't sent.

    The caller is responsible for parsing/validating the response.
    """
    # Import here to avoid circular imports at module import time
    from ollama_anki_from_epub_out import CardsPayload

    client = Client()
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
