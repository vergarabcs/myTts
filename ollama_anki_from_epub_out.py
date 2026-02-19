import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import List

from ollama import Client
from pydantic import BaseModel, ConfigDict, RootModel, ValidationError, field_validator, model_validator

from src.anki_gen.json_processor import extract_json_text
from src.anki_gen.validator import build_tsv_row_from_card
from src.anki_gen.llm import make_prompt, call_ollama


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
        if self.answer in self.options:
            return self

        normalized_answer = self.answer.strip().lower()
        for option in self.options:
            if option.strip().lower() == normalized_answer:
                self.answer = option
                return self

        raise ValueError("answer must be present in options")
        return self


class CardsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cards: list[AnkiCard]


class CardsList(RootModel[list[AnkiCard]]):
    pass


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
    parser.add_argument(
        "--limit-chunks",
        type=int,
        default=None,
        help="Stop after processing this many chunks total",
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
                    "main_start": main_start,
                    "main_end": main_end,
                    "before_start": before_start,
                    "before_end": before_end,
                    "after_start": after_start,
                    "after_end": after_end,
                }
            )

    return chunks





def parse_cards_content(content: object) -> list[dict]:
    if isinstance(content, dict):
        payload = CardsPayload.model_validate(content)
        return [card.model_dump() for card in payload.cards]

    if isinstance(content, list):
        payload = CardsList.model_validate(content)
        return [card.model_dump() for card in payload.root]

    if not isinstance(content, str):
        raise ValueError("Ollama response content must be a string, list, or dict")

    raw_text = content.strip()
    if raw_text.startswith("{") or raw_text.startswith("["):
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            payload = CardsPayload.model_validate(parsed)
            return [card.model_dump() for card in payload.cards]
        if isinstance(parsed, list):
            payload = CardsList.model_validate(parsed)
            return [card.model_dump() for card in payload.root]

    json_text = extract_json_text(content)
    try:
        payload = CardsPayload.model_validate_json(json_text)
        return [card.model_dump() for card in payload.cards]
    except ValidationError:
        payload = CardsList.model_validate_json(json_text)
        return [card.model_dump() for card in payload.root]





def gather_txt_files(input_dir: Path) -> List[Path]:
    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    files = sorted(input_dir.glob("*.txt"))
    if not files:
        raise ValueError(f"No .txt files found in: {input_dir}")
    return files


def log_failed_chunk(
    failed_log_path: Path,
    txt_file: Path,
    chunk_index: int,
    chunk_total: int,
    chunk: dict,
    error: str,
    model: str,
    deck: str,
    chunk_size: int,
    overlap: int,
) -> None:
    entry = {
        "file": str(txt_file),
        "chunk_index": chunk_index,
        "chunk_total": chunk_total,
        "error": error,
        "main_block": chunk.get("main_block"),
        "model": model,
        "deck": deck,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "main_start": chunk.get("main_start"),
        "main_end": chunk.get("main_end"),
        "before_start": chunk.get("before_start"),
        "before_end": chunk.get("before_end"),
        "after_start": chunk.get("after_start"),
        "after_end": chunk.get("after_end"),
    }
    failed_log_path.parent.mkdir(parents=True, exist_ok=True)
    with failed_log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def generate_anki_file(
    input_dir: Path,
    output_file: Path,
    model: str,
    deck: str,
    chunk_size: int,
    overlap: int,
    limit_chunks: int | None,
) -> int:
    txt_files = gather_txt_files(input_dir)
    failed_log_path = output_file.with_suffix(".failed.jsonl")

    rows: List[str] = []
    seen = set()
    id_prefix = output_file.name
    next_id = 1
    processed_chunks = 0

    for txt_file in txt_files:
        text = txt_file.read_text(encoding="utf-8", errors="ignore")
        chunks = split_text_with_overlap(
            text,
            chunk_size=chunk_size,
            overlap=overlap,
        )

        for index, chunk in enumerate(chunks, start=1):
            if limit_chunks is not None and processed_chunks >= limit_chunks:
                break
            prompt = make_prompt(
                main_block=chunk["main_block"],
                context_before=chunk["context_before"],
                context_after=chunk["context_after"],
            )
            response_content = None
            cards = None
            last_exc = None
            for attempt in range(3):
                try:
                    response_content = call_ollama(prompt=prompt, model=model, think="medium")
                    cards = parse_cards_content(response_content)
                    break
                except RuntimeError as exc:
                    last_exc = exc
                    if attempt < 2:
                        print(
                            f"Call failed for {txt_file.name} chunk {index}/{len(chunks)} (attempt {attempt+1}/3), retrying...",
                            file=sys.stderr,
                        )
                        time.sleep(1)
                        continue
                    log_failed_chunk(
                        failed_log_path=failed_log_path,
                        txt_file=txt_file,
                        chunk_index=index,
                        chunk_total=len(chunks),
                        chunk=chunk,
                        error=str(exc),
                        model=model,
                        deck=deck,
                        chunk_size=chunk_size,
                        overlap=overlap,
                    )
                    print(
                        f"Failed {txt_file.name} chunk {index}/{len(chunks)} -> logged to {failed_log_path.name}",
                        file=sys.stderr,
                    )
                except Exception as exc:
                    last_exc = exc
                    if attempt < 2:
                        print(
                            f"Parse failed for {txt_file.name} chunk {index}/{len(chunks)} (attempt {attempt+1}/3), retrying...",
                            file=sys.stderr,
                        )
                        time.sleep(1)
                        continue
                    log_failed_chunk(
                        failed_log_path=failed_log_path,
                        txt_file=txt_file,
                        chunk_index=index,
                        chunk_total=len(chunks),
                        chunk=chunk,
                        error=f"Failed to parse response after 3 attempts: {exc}",
                        model=model,
                        deck=deck,
                        chunk_size=chunk_size,
                        overlap=overlap,
                    )
                    print(
                        f"Failed to parse {txt_file.name} chunk {index}/{len(chunks)} -> logged to {failed_log_path.name}",
                        file=sys.stderr,
                    )
            if cards is None:
                continue

            chunk_rows = 0
            for card in cards:
                dedupe_key = json.dumps(
                    {key: value for key, value in card.items() if key != "id"},
                    sort_keys=True,
                    ensure_ascii=False,
                )
                if dedupe_key in seen:
                    continue

                card_with_id = dict(card)
                card_with_id["id"] = f"{id_prefix}__{next_id:04d}"
                next_id += 1

                try:
                    row = build_tsv_row_from_card(card_with_id, deck=deck)
                except ValueError:
                    continue

                seen.add(dedupe_key)
                rows.append(row)
                chunk_rows += 1

            processed_chunks += 1

            print(
                f"Processed {txt_file.name} chunk {index}/{len(chunks)} -> {chunk_rows} card row(s)",
                file=sys.stderr,
            )

        if limit_chunks is not None and processed_chunks >= limit_chunks:
            break

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
        limit_chunks=args.limit_chunks,
    )
    print(f"Wrote {total} Anki row(s) to {args.output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
