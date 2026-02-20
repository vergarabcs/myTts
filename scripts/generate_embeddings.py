"""Generate embeddings for Phase 1 TSV card output.

Example:

    python scripts/generate_embeddings.py \
        --input-tsv sample/anki_out.txt \
        --model embeddinggemma \
        --out-embeddings out/embeddings.json

"""
from __future__ import annotations

import argparse
import json
import datetime
from pathlib import Path
from typing import List

from src.memory_map import parser as mm_parser
from src.memory_map.embeddings import create_embedder


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate embeddings for Anki TSV cards")
    ap.add_argument("--input-tsv", required=True, help="Path to Phase 1 TSV file")
    ap.add_argument("--model", default="embeddinggemma:300m", help="Embedder model to use")
    ap.add_argument("--out-embeddings", required=True, help="Output JSON path for embeddings")
    ap.add_argument("--batch-size", type=int, default=64, help="Batch size for embedder calls")
    args = ap.parse_args(argv)

    headers, rows = mm_parser.read_tsv(args.input_tsv)
    if not rows:
        print("No rows found in input TSV")
        return 1

    cards = [mm_parser.normalize_card(r) for r in rows]

    ids: List[str] = []
    texts: List[str] = []
    for i, card in enumerate(cards):
        cid = card.get("source_id") or card.get("id") or f"card_{i+1}"
        ids.append(cid)
        text = f"{card.get('question','')}\n{card.get('answer','')}"
        texts.append(text)

    embedder = create_embedder(model=args.model)
    embeddings = embedder.embed_texts(texts, batch_size=args.batch_size)

    # Ensure lists (in case of numpy arrays)
    def _to_list(obj):
        try:
            return [float(x) for x in obj]
        except Exception:
            return list(obj)

    embeddings_lists = [_to_list(e) for e in embeddings]

    out = {
        "ids": ids,
        "embeddings": embeddings_lists,
        "meta": {
            "model": args.model,
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
    }

    out_path = Path(args.out_embeddings)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False))
    print(f"Wrote embeddings to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
