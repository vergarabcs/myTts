import json
import os
from pathlib import Path

import pytest

from scripts import generate_embeddings as ge
from scripts import visualize_memory_map as vm


try:
    import ollama  # type: ignore

    _HAS_OLLAMA = True
except Exception:
    _HAS_OLLAMA = False


@pytest.mark.integration
@pytest.mark.skipif(
    (not _HAS_OLLAMA) or (not os.getenv("OLLAMA_URL")),
    reason="Requires ollama package and OLLAMA_URL for integration test",
)
def test_phase2_end_to_end_generate_then_visualize(tmp_path: Path):
    model = os.getenv("OLLAMA_MODEL", "embeddinggemma:300m")

    input_tsv = Path(__file__).parent / "test_cards.txt"
    out_embeddings = tmp_path / "embeddings.json"
    out_neighbors = tmp_path / "neighbors.json"

    rc_embeddings = ge.main(
        [
            "--input-tsv",
            str(input_tsv),
            "--out-embeddings",
            str(out_embeddings),
            "--model",
            model,
            "--batch-size",
            "2",
        ]
    )
    assert rc_embeddings == 0
    assert out_embeddings.exists()

    rc_visualize = vm.main(
        [
            "--in-embeddings",
            str(out_embeddings),
            "--input-tsv",
            str(input_tsv),
            "--k",
            "2",
            "--layout",
            "pca",
            "--seed",
            "42",
            "--out-neighbors",
            str(out_neighbors),
        ]
    )
    assert rc_visualize == 0
    assert out_neighbors.exists()

    payload = json.loads(out_neighbors.read_text(encoding="utf-8"))
    assert "cards" in payload
    assert "meta" in payload
    assert payload["meta"]["layout"] == "pca"
    assert payload["meta"]["k"] == 2
    assert len(payload["cards"]) > 0

    first_card = payload["cards"][0]
    assert "id" in first_card
    assert isinstance(first_card["x"], float)
    assert isinstance(first_card["y"], float)
    assert isinstance(first_card["neighbors"], list)
