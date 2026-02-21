from __future__ import annotations

from typing import Literal

import numpy as np


def compute_knn_graph(embeddings: np.ndarray | list[list[float]], k: int) -> np.ndarray:
    vectors = _to_2d_float_array(embeddings)
    n_samples = vectors.shape[0]

    if n_samples < 2:
        raise ValueError("At least two embeddings are required to compute k-NN")

    max_k = n_samples - 1
    if k < 1 or k > max_k:
        raise ValueError(f"k must be in [1, {max_k}] for {n_samples} embeddings")

    deltas = vectors[:, None, :] - vectors[None, :, :]
    distances = np.sqrt(np.sum(deltas * deltas, axis=2))
    np.fill_diagonal(distances, np.inf)

    neighbor_indices = np.argsort(distances, axis=1)[:, :k]
    return neighbor_indices


def compute_layout(
    embeddings: np.ndarray | list[list[float]],
    method: Literal["pca", "umap"] = "pca",
    seed: int = 42,
) -> np.ndarray:
    vectors = _to_2d_float_array(embeddings)

    if vectors.shape[0] < 1:
        raise ValueError("At least one embedding is required")

    normalized_method = method.lower()
    if normalized_method == "pca":
        return _compute_pca_layout(vectors)
    if normalized_method == "umap":
        return _compute_umap_layout(vectors, seed=seed)

    raise ValueError(f"Unsupported layout method: {method}")


def _to_2d_float_array(embeddings: np.ndarray | list[list[float]]) -> np.ndarray:
    vectors = np.asarray(embeddings, dtype=float)
    if vectors.ndim != 2:
        raise ValueError("embeddings must be a 2D array-like")
    if vectors.shape[1] < 1:
        raise ValueError("embeddings must have at least one feature column")
    return vectors


def _compute_pca_layout(vectors: np.ndarray) -> np.ndarray:
    centered = vectors - np.mean(vectors, axis=0)

    if centered.shape[0] == 1:
        return np.array([[0.0, 0.0]], dtype=float)

    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    components = vt[:2].T
    coords = centered @ components

    if coords.shape[1] == 1:
        coords = np.hstack([coords, np.zeros((coords.shape[0], 1), dtype=float)])

    return coords.astype(float)


def _compute_umap_layout(vectors: np.ndarray, seed: int) -> np.ndarray:
    try:
        import umap  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "UMAP layout requested but umap-learn is not installed. "
            "Install with `pip install umap-learn` or use --layout pca."
        ) from exc

    reducer = umap.UMAP(n_components=2, random_state=seed)
    coords = reducer.fit_transform(vectors)
    return np.asarray(coords, dtype=float)
