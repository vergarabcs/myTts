import hashlib
import re


WHITESPACE_PATTERN = re.compile(r"\s+")


def canonicalize_text(value: str) -> str:
    if value is None:
        return ""
    normalized = WHITESPACE_PATTERN.sub(" ", str(value)).strip().casefold()
    return normalized


def generate_card_id(question: str, answer: str, topic: str) -> str:
    canonical = "|".join(
        [
            canonicalize_text(question),
            canonicalize_text(answer),
            canonicalize_text(topic),
        ]
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest[:12]


def get_or_assign_id(card: dict[str, str]) -> str:
    existing = str(card.get("id", "")).strip()
    if existing:
        return existing

    generated = generate_card_id(
        question=str(card.get("question", "")),
        answer=str(card.get("answer", "")),
        topic=str(card.get("topic", "")),
    )
    card["id"] = generated
    return generated
