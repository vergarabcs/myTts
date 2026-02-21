import json
from pathlib import Path

import numpy as np

from scripts import visualize_memory_map as vm
from src.memory_map.graph import compute_knn_graph, compute_layout


def test_visualize_memory_map_outputs_neighbors_and_coords(tmp_path: Path):
    n_cards = 5
    k_neighbors = 3

    embeddings = np.arange(n_cards * 4, dtype=float).reshape(n_cards, 4)
    ids = [f"card_{index+1}" for index in range(n_cards)]

    embeddings_path = tmp_path / "embeddings.json"
    embeddings_path.write_text(
        json.dumps({"ids": ids, "embeddings": embeddings.tolist()}),
        encoding="utf-8",
    )

    tsv_path = tmp_path / "cards.tsv"
    lines = ["source_id\tquestion\tanswer\ttopic"]
    for card_id in ids:
        lines.append(f"{card_id}\tQuestion {card_id}\tAnswer {card_id}\tTopic")
    tsv_path.write_text("\n".join(lines), encoding="utf-8")

    out_neighbors = tmp_path / "neighbors.json"

    rc = vm.main(
        [
            "--in-embeddings",
            str(embeddings_path),
            "--input-tsv",
            str(tsv_path),
            "--k",
            str(k_neighbors),
            "--layout",
            "pca",
            "--seed",
            "42",
            "--out-neighbors",
            str(out_neighbors),
        ]
    )
    assert rc == 0
    assert out_neighbors.exists()

    payload = json.loads(out_neighbors.read_text(encoding="utf-8"))
    cards = payload["cards"]

    assert [card["id"] for card in cards] == ids

    knn = compute_knn_graph(embeddings, k=k_neighbors)
    for row_index, card in enumerate(cards):
        neighbors = card["neighbors"]
        assert len(neighbors) == k_neighbors
        expected_neighbor_indices = knn[row_index].tolist()
        observed_neighbor_indices = [neighbor["idx"] for neighbor in neighbors]
        assert observed_neighbor_indices == expected_neighbor_indices
        assert row_index not in observed_neighbor_indices
        assert all(0 <= index < n_cards for index in observed_neighbor_indices)
        assert isinstance(card["x"], float)
        assert isinstance(card["y"], float)


def test_compute_layout_pca_is_deterministic_for_seed():
    embeddings = np.arange(30, dtype=float).reshape(6, 5)

    coords_1 = compute_layout(embeddings, method="pca", seed=42)
    coords_2 = compute_layout(embeddings, method="pca", seed=42)

    assert np.array_equal(coords_1, coords_2)
