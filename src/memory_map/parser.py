import csv
from pathlib import Path


ANKI_DEFAULT_HEADERS = [
    "note_type",
    "deck",
    "source_id",
    "question",
    "answer",
    "options",
    "explanation",
    "topic",
    "field_9",
    "field_10",
    "field_11",
    "field_12",
    "field_13",
    "tags",
]

HEADER_HINTS = {
    "id",
    "question",
    "answer",
    "topic",
    "options",
    "choices",
    "tags",
    "deck",
}


def read_tsv(path: str, delimiter: str = "\t") -> tuple[list[str], list[dict[str, str]]]:
    rows = _read_raw_rows(Path(path), delimiter)
    if not rows:
        return [], []

    has_header = _looks_like_header(rows[0])
    if has_header:
        headers = [_normalize_header_name(value, index) for index, value in enumerate(rows[0])]
        data_rows = rows[1:]
    else:
        width = max(len(row) for row in rows)
        headers = _build_headers(width)
        data_rows = rows

    normalized_rows = []
    for row in data_rows:
        if not any(cell.strip() for cell in row):
            continue
        row_dict = _row_to_dict(headers, row)
        normalized_rows.append(row_dict)

    return headers, normalized_rows


def normalize_card(row: dict[str, str]) -> dict[str, str]:
    card = {key: (value.strip() if isinstance(value, str) else value) for key, value in row.items()}

    options_value = card.get("options", "")
    choices_value = card.get("choices", "")
    if not options_value and choices_value:
        options_value = choices_value

    card["options"] = options_value
    card.setdefault("question", "")
    card.setdefault("answer", "")
    card.setdefault("topic", "")
    card.setdefault("tags", "")
    return card


def validate_card(card: dict[str, str]) -> None:
    question = str(card.get("question", "")).strip()
    answer = str(card.get("answer", "")).strip()

    if not question:
        raise ValueError("Card is missing required field: question")
    if not answer:
        raise ValueError("Card is missing required field: answer")


def _read_raw_rows(path: Path, delimiter: str) -> list[list[str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        rows = []
        for row in reader:
            if not row:
                continue
            if row[0].startswith("#"):
                continue
            rows.append(row)
    return rows


def _looks_like_header(row: list[str]) -> bool:
    lowered = {cell.strip().lower() for cell in row if cell.strip()}
    return len(lowered.intersection(HEADER_HINTS)) >= 2


def _normalize_header_name(value: str, index: int) -> str:
    cleaned = value.strip()
    if cleaned:
        return cleaned
    return f"field_{index + 1}"


def _build_headers(width: int) -> list[str]:
    if width <= len(ANKI_DEFAULT_HEADERS):
        return ANKI_DEFAULT_HEADERS[:width]

    headers = list(ANKI_DEFAULT_HEADERS)
    for column in range(len(headers) + 1, width + 1):
        headers.append(f"field_{column}")
    return headers


def _row_to_dict(headers: list[str], row: list[str]) -> dict[str, str]:
    padded = list(row)
    if len(padded) < len(headers):
        padded.extend([""] * (len(headers) - len(padded)))
    elif len(padded) > len(headers):
        padded = padded[: len(headers)]

    return {header: value for header, value in zip(headers, padded)}
