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
        "You create high-quality MultipleChoice Anki cards from study text. Make the cards self-contained. Provide enough context so that question is answerable. Do not assume the learner has access to the original text. Put in as many card as you can without being repetitive"
        "Rules:\n"
        "- Use facts from MAIN_BLOCK only when writing questions/answers.\n"
        "- CONTEXT_BEFORE and CONTEXT_AFTER are for understanding only; do not create cards from info found only in context.\n"
        "- options must have exactly 3 choices and include the answer.\n"
        "- Keep cards factual and strictly grounded in MAIN_BLOCK.\n"
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


def call_ollama(prompt: str, model: str) -> Any:
    """Call Ollama and return the raw response content.

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
        response = client.chat(
            model=model,
            messages=messages,
            format=CardsPayload.model_json_schema(),
            options={"temperature": 0.2},
            stream=False,
        )
        return response["message"]["content"]
    except Exception as exc:
        raise RuntimeError(f"Failed to call Ollama: {exc}") from exc
