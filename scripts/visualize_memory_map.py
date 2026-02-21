from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.memory_map import graph
from src.memory_map import parser as mm_parser


def visualize_memory_map(
    in_embeddings: str,
    input_tsv: str,
    out_neighbors: str,
    k: int = 6,
    layout: str = "pca",
    seed: int = 42,
    out_plot: str | None = None,
) -> dict[str, Any]:
    embeddings_payload = _load_embeddings_json(Path(in_embeddings))

    embedding_ids = embeddings_payload["ids"]
    vectors = np.asarray(embeddings_payload["embeddings"], dtype=float)

    if len(embedding_ids) != vectors.shape[0]:
        raise ValueError("Embeddings JSON has mismatched ids and embeddings lengths")

    cards_by_id, cards_in_tsv_order = _load_cards_by_id(Path(input_tsv))

    ordered_cards: list[dict[str, Any]] = []
    for card_id in embedding_ids:
        if card_id in cards_by_id:
            ordered_cards.append(cards_by_id[card_id])
            continue

        if isinstance(card_id, str) and card_id.startswith("card_"):
            suffix = card_id[len("card_") :]
            if suffix.isdigit():
                tsv_index = int(suffix) - 1
                if 0 <= tsv_index < len(cards_in_tsv_order):
                    ordered_cards.append(cards_in_tsv_order[tsv_index])
                    continue

        raise ValueError(f"Embedding id not found in input TSV cards: {card_id}")

    neighbor_indices = graph.compute_knn_graph(vectors, k=k)
    coords = graph.compute_layout(vectors, method=layout, seed=seed)

    cards_out: list[dict[str, Any]] = []
    for row_index, card in enumerate(ordered_cards):
        neighbors = []
        for rank, neighbor_index in enumerate(neighbor_indices[row_index].tolist(), start=1):
            neighbor_id = embedding_ids[neighbor_index]
            neighbors.append(
                {
                    "rank": rank,
                    "idx": int(neighbor_index),
                    "id": neighbor_id,
                }
            )

        cards_out.append(
            {
                "id": embedding_ids[row_index],
                "question": str(card.get("question", "")),
                "answer": str(card.get("answer", "")),
                "topic": str(card.get("topic", "")),
                "x": float(coords[row_index, 0]),
                "y": float(coords[row_index, 1]),
                "neighbors": neighbors,
            }
        )

    output_payload = {
        "cards": cards_out,
        "meta": {
            "k": int(k),
            "layout": layout,
            "seed": int(seed),
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
            "source_embeddings": str(in_embeddings),
            "source_tsv": str(input_tsv),
        },
    }

    out_neighbors_path = Path(out_neighbors)
    out_neighbors_path.parent.mkdir(parents=True, exist_ok=True)
    out_neighbors_path.write_text(json.dumps(output_payload, ensure_ascii=False), encoding="utf-8")

    if out_plot:
        _write_plot(coords=coords, cards=cards_out, out_plot_path=Path(out_plot))

    return output_payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build k-NN graph and 2D visualization metadata")
    ap.add_argument("--in-embeddings", required=True, help="Input embeddings JSON from Phase 2.1")
    ap.add_argument("--input-tsv", required=True, help="Input Phase 1 TSV file")
    ap.add_argument("--k", type=int, default=6, help="Number of nearest neighbors per card")
    ap.add_argument("--layout", default="pca", choices=["pca", "umap"], help="Layout method")
    ap.add_argument("--seed", type=int, default=42, help="Seed for layout algorithms")
    ap.add_argument("--out-neighbors", required=True, help="Output JSON path for neighbor metadata")
    ap.add_argument("--out-plot", default=None, help="Optional output image path for scatter plot")
    args = ap.parse_args(argv)

    visualize_memory_map(
        in_embeddings=args.in_embeddings,
        input_tsv=args.input_tsv,
        out_neighbors=args.out_neighbors,
        k=args.k,
        layout=args.layout,
        seed=args.seed,
        out_plot=args.out_plot,
    )
    print(f"Wrote neighbors metadata to {args.out_neighbors}")
    if args.out_plot:
        print(f"Wrote plot image to {args.out_plot}")
    return 0


def _load_embeddings_json(path: Path) -> dict[str, Any]:
    raw_bytes = path.read_bytes()

    decoded_text: str | None = None
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            decoded_text = raw_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if decoded_text is None:
        raise ValueError(f"Unable to decode embeddings JSON file: {path}")

    data = json.loads(decoded_text)

    if "ids" not in data or "embeddings" not in data:
        raise ValueError("Embeddings file must contain 'ids' and 'embeddings'")

    if not isinstance(data["ids"], list):
        raise ValueError("Embeddings file 'ids' must be a list")
    if not isinstance(data["embeddings"], list):
        raise ValueError("Embeddings file 'embeddings' must be a list")

    return data


def _load_cards_by_id(path: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    _, rows = mm_parser.read_tsv(str(path))
    cards = [mm_parser.normalize_card(row) for row in rows]

    by_id: dict[str, dict[str, Any]] = {}
    for index, card in enumerate(cards):
        card_id = str(card.get("source_id") or card.get("id") or f"card_{index+1}")
        if card_id in by_id:
            raise ValueError(f"Duplicate card id in input TSV: {card_id}")
        by_id[card_id] = card
    return by_id, cards


def _write_plot(coords: np.ndarray, cards: list[dict[str, Any]], out_plot_path: Path) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "Plot output requested but matplotlib is not installed. "
            "Install with `pip install matplotlib` or omit --out-plot."
        ) from exc

    out_plot_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(coords[:, 0], coords[:, 1], s=18)
    ax.set_title("Memory Map")
    ax.set_xlabel("x")
    ax.set_ylabel("y")

    for row_index, card in enumerate(cards):
        card_id = card["id"]
        ax.annotate(card_id, (coords[row_index, 0], coords[row_index, 1]), fontsize=7, alpha=0.75)

    fig.tight_layout()
    fig.savefig(out_plot_path)
    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
