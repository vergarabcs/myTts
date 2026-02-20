import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.memory_map import ids, parser, utils


def parse_args() -> argparse.Namespace:
    cli_parser = argparse.ArgumentParser(
        description="Phase 1 memory-map scaffold: parse TSV and assign stable IDs."
    )
    cli_parser.add_argument("--input-tsv", type=Path, required=True, help="Input Anki TSV path")
    cli_parser.add_argument("--out-dir", type=Path, default=Path("memory_map_out"))
    cli_parser.add_argument("--model", default="all-MiniLM-L6-v2")
    cli_parser.add_argument("--provider", default="sentence-transformers")
    cli_parser.add_argument("--k", type=int, default=6)
    cli_parser.add_argument("--device", default="cpu")
    cli_parser.add_argument("--layout", default="pca")
    cli_parser.add_argument("--seed", type=int, default=42)
    return cli_parser.parse_args()


def main() -> None:
    args = parse_args()
    utils.setup_logging()

    headers, rows = parser.read_tsv(str(args.input_tsv))

    cards = []
    skipped_cards = 0
    for row in rows:
        card = parser.normalize_card(row)
        try:
            parser.validate_card(card)
        except ValueError:
            skipped_cards += 1
            continue
        card["_id"] = ids.get_or_assign_id(card)
        cards.append(card)

    print(f"Parsed {len(cards)} valid cards with stable IDs.")
    print(f"Skipped {skipped_cards} invalid cards.")
    print(f"Headers: {headers}")
    if cards:
        print(f"Sample card: {cards[0]}")


if __name__ == "__main__":
    main()
