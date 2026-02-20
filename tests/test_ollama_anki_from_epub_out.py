import json
from pathlib import Path

import pytest

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


def test_parse_chunk_range_accepts_inclusive_1_based_values():
    assert module.parse_chunk_range("1-12") == (1, 12)


@pytest.mark.parametrize("value", ["0-2", "5-1", "abc", "1:2"])
def test_parse_chunk_range_rejects_invalid_values(value: str):
    with pytest.raises(Exception):
        module.parse_chunk_range(value)


def test_generate_anki_file_processes_only_selected_chunk_range(monkeypatch, tmp_path: Path):
    in_dir = tmp_path / "in"
    out_file = tmp_path / "out.tsv"
    in_dir.mkdir(parents=True, exist_ok=True)
    (in_dir / "chapter.txt").write_text("unused", encoding="utf-8")

    chunks = [
        {
            "main_block": "chunk1",
            "context_before": "",
            "context_after": "",
            "main_start": 0,
            "main_end": 1,
            "before_start": 0,
            "before_end": 0,
            "after_start": 1,
            "after_end": 1,
        },
        {
            "main_block": "chunk2",
            "context_before": "",
            "context_after": "",
            "main_start": 1,
            "main_end": 2,
            "before_start": 1,
            "before_end": 1,
            "after_start": 2,
            "after_end": 2,
        },
        {
            "main_block": "chunk3",
            "context_before": "",
            "context_after": "",
            "main_start": 2,
            "main_end": 3,
            "before_start": 2,
            "before_end": 2,
            "after_start": 3,
            "after_end": 3,
        },
    ]

    monkeypatch.setattr(module, "split_text_with_overlap", lambda *_args, **_kwargs: chunks)
    monkeypatch.setattr(module, "make_prompt", lambda main_block, **_kwargs: main_block)

    seen_prompts: list[str] = []

    def _fake_call_llm(prompt: str, **_kwargs):
        seen_prompts.append(prompt)
        index = len(seen_prompts)
        return {
            "cards": [
                {
                    "question": f"Q{index}",
                    "answer": "A",
                    "options": ["A", "B", "C"],
                    "explanation": "Because",
                    "topic": "Topic",
                    "tags": ["tag"],
                }
            ]
        }

    monkeypatch.setattr(module, "call_llm", _fake_call_llm)

    total = module.generate_anki_file(
        input_dir=in_dir,
        output_file=out_file,
        model="m",
        provider="openai",
        deck="D",
        chunk_size=100,
        overlap=0,
        limit_chunks=None,
        chunk_range=(1, 2),
    )

    assert seen_prompts == ["chunk1", "chunk2"]
    assert total == 2
