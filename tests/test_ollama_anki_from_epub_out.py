import json

import ollama_anki_from_epub_out as module


def _sample_card() -> dict:
    return {
        "question": "What is Q?",
        "answer": "A",
        "options": ["A", "B", "C"],
        "explanation": "Because.",
        "topic": "Topic",
        "tags": ["tag1"],
    }


def test_parse_cards_content_accepts_object_json():
    content = json.dumps({"cards": [_sample_card()]})
    cards = module.parse_cards_content(content)
    assert cards == [_sample_card()]


def test_parse_cards_content_accepts_list_json():
    content = json.dumps([_sample_card()])
    cards = module.parse_cards_content(content)
    assert cards == [_sample_card()]


def test_parse_cards_content_accepts_object_value():
    cards = module.parse_cards_content({"cards": [_sample_card()]})
    assert cards == [_sample_card()]


def test_parse_cards_content_accepts_list_value():
    cards = module.parse_cards_content([_sample_card()])
    assert cards == [_sample_card()]


def test_parse_cards_content_accepts_case_mismatch_answer():
    card = _sample_card()
    card["answer"] = "aws"
    card["options"] = ["AWS", "IaaS", "Compute"]
    content = json.dumps({"cards": [card]})
    cards = module.parse_cards_content(content)
    assert cards[0]["answer"] == "AWS"
