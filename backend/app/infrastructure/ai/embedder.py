"""Embedding adapters: local deterministic trigram-hash embedder (384-d)."""

import hashlib
import math
import re

EMBEDDING_DIM = 384


class DeterministicHashEmbedder:
    """Zero-dependency 384-dim normalized bag-of-ngrams embedder for local/offline RAG."""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self._dim = dim

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        tokens = re.findall(r"[a-z0-9áéíóúñü]+", text.lower())
        for token in tokens:
            grams = [token]
            if len(token) >= 3:
                grams.extend(token[i : i + 3] for i in range(len(token) - 2))
            for gram in grams:
                digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
                idx = int.from_bytes(digest[:4], "little") % self._dim
                sign = 1.0 if (digest[4] & 1) == 0 else -1.0
                vec[idx] += sign

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return normalized 384-dim vectors for each input string."""
        return [self._embed_one(t) for t in texts]
