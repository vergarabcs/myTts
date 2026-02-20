from pathlib import Path

import pytest

from src.memory_map import ids, parser


def test_parse_sample_file_assigns_stable_ids():
    sample_path = Path("sample") / "anki_out.txt"
    headers, rows = parser.read_tsv(str(sample_path))

    assert headers
    assert rows

    cards = []
    invalid_count = 0
    for row in rows:
        card = parser.normalize_card(row)
        try:
            parser.validate_card(card)
        except ValueError:
            invalid_count += 1
            continue
        card["_id"] = ids.get_or_assign_id(card)
        cards.append(card)

    assert len(cards) + invalid_count == len(rows)
    assert cards
    assert all(card.get("_id") for card in cards)


def test_duplicate_card_content_gets_same_id():
    card_a = {"question": "What is AWS?", "answer": "A cloud platform", "topic": "Cloud"}
    card_b = {"question": "  what  is aws? ", "answer": "A cloud platform", "topic": "cloud"}

    assert ids.get_or_assign_id(card_a) == ids.get_or_assign_id(card_b)


def test_normalize_card_coalesces_choices_into_options():
    normalized = parser.normalize_card(
        {
            "question": "Q",
            "answer": "A",
            "topic": "T",
            "choices": '["A", "B", "C"]',
        }
    )

    assert normalized["options"] == '["A", "B", "C"]'


@pytest.mark.parametrize(
    "card",
    [
        {"question": "", "answer": "A"},
        {"question": "Q", "answer": ""},
    ],
)
def test_validate_card_rejects_missing_required_fields(card):
    with pytest.raises(ValueError):
        parser.validate_card(card)


def test_ids_are_deterministic_across_reruns():
    sample_path = Path("sample") / "anki_out.txt"
    _, rows_first = parser.read_tsv(str(sample_path))
    _, rows_second = parser.read_tsv(str(sample_path))

    first_ids = []
    for row in rows_first:
        card = parser.normalize_card(row)
        try:
            parser.validate_card(card)
        except ValueError:
            continue
        first_ids.append(ids.get_or_assign_id(card))

    second_ids = []
    for row in rows_second:
        card = parser.normalize_card(row)
        try:
            parser.validate_card(card)
        except ValueError:
            continue
        second_ids.append(ids.get_or_assign_id(card))

    assert first_ids == second_ids
