import numpy as np

from src.memory_map.graph import compute_knn_graph, compute_layout


def test_compute_knn_graph_known_distances_k1_to_k3():
    embeddings = np.array(
        [
            [0.0, 0.0],
            [1.0, 0.0],
            [3.0, 0.0],
            [10.0, 0.0],
        ],
        dtype=float,
    )

    knn_k1 = compute_knn_graph(embeddings, k=1)
    assert knn_k1.tolist() == [[1], [0], [1], [2]]

    knn_k2 = compute_knn_graph(embeddings, k=2)
    assert knn_k2.tolist() == [[1, 2], [0, 2], [1, 0], [2, 1]]

    knn_k3 = compute_knn_graph(embeddings, k=3)
    assert knn_k3.tolist() == [[1, 2, 3], [0, 2, 3], [1, 0, 3], [2, 1, 0]]


def test_compute_layout_pca_shape_and_repeatability():
    embeddings = np.arange(24, dtype=float).reshape(6, 4)

    coords_1 = compute_layout(embeddings, method="pca", seed=42)
    coords_2 = compute_layout(embeddings, method="pca", seed=42)

    assert coords_1.shape == (6, 2)
    assert coords_2.shape == (6, 2)
    assert np.array_equal(coords_1, coords_2)
