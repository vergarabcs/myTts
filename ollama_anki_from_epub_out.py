import argparse
import json
import math
import sys
from pathlib import Path
from typing import List

from ollama import Client
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from src.anki_gen.json_processor import extract_json_text
from src.anki_gen.validator import extract_rows_from_cards


HEADER_LINES = [
    "#separator:tab",
    "#html:true",
    "#notetype column:1",
    "#deck column:2",
    "#tags column:14",
]


class AnkiCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    answer: str
    options: list[str]
    explanation: str
    topic: str
    tags: list[str] = []

    @field_validator("question", "answer", "explanation", "topic")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty")
        return cleaned

    @field_validator("options")
    @classmethod
    def validate_options(cls, value: list[str]) -> list[str]:
        options = [option.strip() for option in value if option.strip()]
        if len(options) != 3:
            raise ValueError("options must contain exactly 3 non-empty choices")
        return options

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        return [tag.strip() for tag in value if tag.strip()]

    @model_validator(mode="after")
    def validate_answer_is_option(self) -> "AnkiCard":
        if self.answer not in self.options:
            raise ValueError("answer must be present in options")
        return self


class CardsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cards: list[AnkiCard]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Anki cards from chapter txt files using Ollama."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("sample") / "epub_out",
        help="Directory containing chapter txt files (default: sample/epub_out)",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("sample") / "anki_out.txt",
        help="Output TSV file for Anki import (default: sample/anki_out.txt)",
    )
    parser.add_argument(
        "--model",
        default="gpt-oss:120b-cloud",
        help="Ollama model name (default: gpt-oss:120b-cloud)",
    )
    parser.add_argument(
        "--deck",
        default="Audio::Everything",
        help="Anki deck name for column 2 (default: Audio::Everything)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=3500,
        help="Main block size in characters (default: 3500)",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=500,
        help="Chunk overlap in characters (default: 500)",
    )
    return parser.parse_args()


def build_main_ranges(text_length: int, chunk_size: int) -> List[tuple[int, int]]:
    if text_length <= 0:
        return []

    block_count = max(1, math.ceil(text_length / chunk_size))
    base_size = text_length // block_count
    remainder = text_length % block_count

    ranges: List[tuple[int, int]] = []
    start = 0
    for index in range(block_count):
        current_size = base_size + (1 if index < remainder else 0)
        end = min(start + current_size, text_length)
        ranges.append((start, end))
        start = end
    return ranges


def split_text_with_overlap(text: str, chunk_size: int, overlap: int) -> List[dict]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if not text.strip():
        return []

    chunks: List[dict] = []
    ranges = build_main_ranges(len(text), chunk_size)

    for main_start, main_end in ranges:
        before_start = max(0, main_start - overlap)
        before_end = main_start
        after_start = main_end
        after_end = min(len(text), main_end + overlap)

        main_block = text[main_start:main_end].strip()
        context_before = text[before_start:before_end].strip()
        context_after = text[after_start:after_end].strip()

        if main_block:
            chunks.append(
                {
                    "main_block": main_block,
                    "context_before": context_before,
                    "context_after": context_after,
                }
            )

    return chunks


def make_prompt(
    main_block: str,
    context_before: str,
    context_after: str,
) -> str:
    schema_json = json.dumps(CardsPayload.model_json_schema(), ensure_ascii=False)
    return (
        "You create high-quality MultipleChoice Anki cards from study text. Make the cards self-contained. Provide enough context so that question is answerable. Do not assume the learner has access to the original text."
        "Return ONLY valid JSON (no markdown, no code fences, no extra text).\n\n"
        "Return this exact shape:\n"
        "{\n"
        "  \"cards\": [\n"
        "    {\n"
        "      \"question\": \"...\",\n"
        "      \"answer\": \"...\",\n"
        "      \"options\": [\"opt1\", \"opt2\", \"opt3\"],\n"
        "      \"explanation\": \"...\",\n"
        "      \"topic\": \"...\",\n"
        "      \"tags\": [\"tag1\", \"tag2\"]\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Generate only MultipleChoice cards.\n"
        "- Use facts from MAIN_BLOCK only when writing questions/answers.\n"
        "- CONTEXT_BEFORE and CONTEXT_AFTER are for understanding only; do not create cards from info found only in context.\n"
        "- options must have exactly 3 choices and include the answer.\n"
        "- Keep cards factual and strictly grounded in MAIN_BLOCK.\n"
        "- If uncertain, skip.\n"
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


def call_ollama(prompt: str, model: str) -> list[dict]:
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
        json_text = extract_json_text(response["message"]["content"])
        payload = CardsPayload.model_validate_json(json_text)
        return [card.model_dump() for card in payload.cards]
    except ValidationError as exc:
        raise RuntimeError(f"Ollama response failed schema validation: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to call Ollama: {exc}") from exc


def extract_rows(cards: list[dict], deck: str) -> List[str]:
    return extract_rows_from_cards(cards, deck=deck)


def gather_txt_files(input_dir: Path) -> List[Path]:
    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    files = sorted(input_dir.glob("*.txt"))
    if not files:
        raise ValueError(f"No .txt files found in: {input_dir}")
    return files


def generate_anki_file(
    input_dir: Path,
    output_file: Path,
    model: str,
    deck: str,
    chunk_size: int,
    overlap: int,
) -> int:
    txt_files = gather_txt_files(input_dir)

    rows: List[str] = []
    seen = set()

    for txt_file in txt_files:
        text = txt_file.read_text(encoding="utf-8", errors="ignore")
        chunks = split_text_with_overlap(
            text,
            chunk_size=chunk_size,
            overlap=overlap,
        )

        for index, chunk in enumerate(chunks, start=1):
            prompt = make_prompt(
                main_block=chunk["main_block"],
                context_before=chunk["context_before"],
                context_after=chunk["context_after"],
            )
            cards = call_ollama(prompt=prompt, model=model)
            chunk_rows = extract_rows(cards, deck=deck)

            for row in chunk_rows:
                if row not in seen:
                    seen.add(row)
                    rows.append(row)

            print(
                f"Processed {txt_file.name} chunk {index}/{len(chunks)} -> {len(chunk_rows)} card row(s)",
                file=sys.stderr,
            )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(HEADER_LINES + rows) + "\n"
    output_file.write_text(content, encoding="utf-8")

    return len(rows)


def main() -> int:
    args = parse_args()
    total = generate_anki_file(
        input_dir=args.input_dir,
        output_file=args.output_file,
        model=args.model,
        deck=args.deck,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )
    print(f"Wrote {total} Anki row(s) to {args.output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
