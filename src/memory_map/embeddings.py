"""Pluggable embedding providers for memory map.

Currently provides an Ollama-backed embedder via `create_embedder`.
"""
from __future__ import annotations

import datetime
from typing import Iterable, List


class OllamaEmbedder:
    def __init__(self, model: str):
        try:
            from ollama import Client
        except Exception as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("ollama package is required for OllamaEmbedder") from exc

        self.client = Client()
        self.model = model

    def embed_texts(self, texts: Iterable[str], batch_size: int = 64) -> List[List[float]]:
        """Compute embeddings for an iterable of texts.

        Returns a list of lists of floats in the same order as `texts`.
        """
        results: List[List[float]] = []
        batch: List[str] = []
        for text in texts:
            batch.append(text)
            if len(batch) >= batch_size:
                results.extend(self._embed_batch(batch))
                batch = []

        if batch:
            results.extend(self._embed_batch(batch))

        return results

    def _embed_batch(self, batch: List[str]) -> List[List[float]]:
        # Try several possible client signatures to maximize compatibility
        response = None
        errors: List[str] = []

        # Variant 0: top-level `ollama.embed(...)`
        def _try_module_embed():
            try:
                import ollama  # type: ignore

                return ollama.embed(model=self.model, input=batch)
            except Exception:
                # Some versions may expose `embed` differently; re-raise to be
                # handled by the caller.
                raise

        call_variants = [
            _try_module_embed,
            lambda: self.client.embeddings(model=self.model, input=batch),
            lambda: self.client.embeddings(model=self.model, inputs=batch),
            lambda: self.client.embeddings(model=self.model, texts=batch),
            lambda: self.client.embeddings(model=self.model, text=batch),
            lambda: self.client.embed(model=self.model, input=batch),
            lambda: self.client.embed(model=self.model, inputs=batch),
            lambda: self.client.embed(batch, model=self.model),
            lambda: self.client.embeddings(batch, model=self.model),
            lambda: self.client.embeddings(batch),
            lambda: self.client.embed(batch),
        ]

        for fn in call_variants:
            try:
                response = fn()
                break
            except Exception as exc:  # pragma: no cover - runtime dependent
                errors.append(str(exc))

        if response is None:
            raise RuntimeError(f"Ollama embeddings call failed: {' | '.join(errors)}")

        # Support different client return shapes. Prefer response['embeddings']
        embeddings: List[List[float]] = []

        # Case: module-level or client returns {'embeddings': [...]}
        if isinstance(response, dict) and "embeddings" in response:
            for emb in response["embeddings"]:
                embeddings.append(list(emb))
            return embeddings

        # Case: response is an object with `.embeddings` attribute (EmbedResponse)
        if hasattr(response, "embeddings"):
            try:
                for emb in getattr(response, "embeddings"):
                    embeddings.append(list(emb))
                return embeddings
            except Exception:
                pass

        # Case: responses with 'data' list containing {'embedding': [...]}
        if isinstance(response, dict) and "data" in response:
            for item in response["data"]:
                emb = item.get("embedding") or item.get("vector")
                embeddings.append(list(emb))
            return embeddings

        # Case: response object with `.data` attribute
        if hasattr(response, "data"):
            try:
                for item in getattr(response, "data"):
                    if isinstance(item, dict):
                        emb = item.get("embedding") or item.get("vector")
                    else:
                        emb = getattr(item, "embedding", None) or getattr(item, "vector", None)
                    embeddings.append(list(emb))
                return embeddings
            except Exception:
                pass

        # Fallback: assume iterable of embeddings or items containing embedding
        try:
            for item in response:
                if isinstance(item, dict):
                    emb = item.get("embedding") or item.get("vector") or item.get("embeddings") or item.get("embedding_vector")
                else:
                    emb = getattr(item, "embedding", None) or getattr(item, "vector", None)

                # If item itself is a numeric sequence, treat it as embedding
                if emb is None and hasattr(item, "__iter__"):
                    emb = item

                embeddings.append(list(emb))
            return embeddings
        except Exception as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"Unexpected embeddings response format: {exc}") from exc


def create_embedder(model: str = "embeddinggemma:300m") -> OllamaEmbedder:
    """Factory to create a default embedder.

    Currently returns an OllamaEmbedder instance.
    """
    return OllamaEmbedder(model=model)
