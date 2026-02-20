import json
import os
from pathlib import Path

import pytest

from scripts import generate_embeddings as ge
from src.memory_map import parser as mm_parser


try:
    import ollama  # type: ignore
    _HAS_OLLAMA = True
except Exception:
    _HAS_OLLAMA = False


@pytest.mark.integration
@pytest.mark.skipif(not _HAS_OLLAMA, reason="Requires ollama Python package to run integration test")
def test_generate_embeddings_integration(tmp_path: Path):
    tsv_path = tmp_path / "cards.tsv"
    out_path = tmp_path / "embeddings.json"

    model = "embeddinggemma:300m"

    # Use the provided test data file that ships with the tests
    test_data = Path(__file__).parent / "test_cards.txt"

    # Compute expected number of cards from the TSV used in the test
    _, expected_rows = mm_parser.read_tsv(str(test_data))
    expected_n = len(expected_rows)

    rc = ge.main([
        "--input-tsv",
        str(test_data),
        "--out-embeddings",
        str(out_path),
        "--model",
        model,
        "--batch-size",
        "2",
    ])

    assert rc == 0
    assert out_path.exists()

    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert "ids" in data and "embeddings" in data
    assert len(data["ids"]) == expected_n
    assert isinstance(data["embeddings"], list)
    assert len(data["embeddings"]) == expected_n

    for emb in data["embeddings"]:
        assert isinstance(emb, list)
        assert len(emb) > 0
        for v in emb:
            assert isinstance(v, float)

    assert data.get("meta", {}).get("model") == model
