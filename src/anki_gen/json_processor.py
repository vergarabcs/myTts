import json


def extract_json_text(raw_response: str) -> str:
    text = raw_response.strip()
    if not text:
        raise ValueError("Empty response from Ollama")

    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            text = "\n".join(lines[1:-1]).strip()

    first_curly = text.find("{")
    last_curly = text.rfind("}")
    if first_curly != -1 and last_curly != -1 and last_curly > first_curly:
        return text[first_curly : last_curly + 1]

    first_bracket = text.find("[")
    last_bracket = text.rfind("]")
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        return text[first_bracket : last_bracket + 1]

    raise ValueError("No JSON object/array found in Ollama response")


def parse_cards_payload(raw_response: str) -> list[dict]:
    json_text = extract_json_text(raw_response)
    parsed = json.loads(json_text)

    if isinstance(parsed, list):
        cards = parsed
    elif isinstance(parsed, dict):
        cards = parsed.get("cards", [])
    else:
        raise ValueError("JSON response must be a list of card objects")

    if not isinstance(cards, list):
        raise ValueError("Card payload must be a list")

    return [card for card in cards if isinstance(card, dict)]