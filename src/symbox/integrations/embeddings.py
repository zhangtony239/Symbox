"""OpenAI-compatible embedding adapter, cosine similarity, and optional cache."""

from __future__ import annotations

import math

import httpx

from symbox.application.embedding_ports import EmbeddingConfig, EmbeddingError


class OpenAIEmbeddingProvider:
    """Call an OpenAI-compatible ``/embeddings`` endpoint with bounded timeout."""

    def __init__(
        self,
        config: EmbeddingConfig,
        *,
        transport: httpx.BaseTransport | None = None,
        cache: dict[tuple[str, str, str], tuple[float, ...]] | None = None,
    ) -> None:
        self.config = config
        self._transport = transport
        self._cache = cache

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """Return validated vectors in input order, using cache only as an optimization."""
        if not texts:
            return ()
        cached: dict[int, tuple[float, ...]] = {}
        missing: list[tuple[int, str]] = []
        for index, text in enumerate(texts):
            if not isinstance(text, str) or not text:
                raise EmbeddingError("embedding input texts must be non-empty strings")
            key = self._cache_key(text)
            vector = self._cache.get(key) if self._cache is not None else None
            if vector is None:
                missing.append((index, text))
            else:
                cached[index] = vector

        if missing:
            fetched = self._request(tuple(text for _, text in missing))
            for (index, text), vector in zip(missing, fetched, strict=True):
                cached[index] = vector
                if self._cache is not None:
                    self._cache[self._cache_key(text)] = vector
        return tuple(cached[index] for index in range(len(texts)))

    def _request(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        endpoint = f"{self.config.base_url.rstrip('/')}/embeddings"
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        try:
            with httpx.Client(
                transport=self._transport,
                timeout=self.config.timeout_seconds,
            ) as client:
                response = client.post(
                    endpoint,
                    headers=headers,
                    json={"model": self.config.model, "input": list(texts)},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise EmbeddingError(f"embedding request failed: {error}") from error
        return _parse_vectors(payload, len(texts))

    def _cache_key(self, text: str) -> tuple[str, str, str]:
        return self.config.base_url, self.config.model, text


def _parse_vectors(payload: object, expected_count: int) -> tuple[tuple[float, ...], ...]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise EmbeddingError("embedding response must contain a data array")
    data = payload["data"]
    if len(data) != expected_count:
        raise EmbeddingError("embedding response count does not match request")
    indexed: dict[int, tuple[float, ...]] = {}
    dimensions: int | None = None
    for fallback_index, item in enumerate(data):
        if not isinstance(item, dict) or not isinstance(item.get("embedding"), list):
            raise EmbeddingError("embedding response item is malformed")
        index = item.get("index", fallback_index)
        if not isinstance(index, int) or isinstance(index, bool) or index in indexed:
            raise EmbeddingError("embedding response indices must be unique integers")
        raw_vector = item["embedding"]
        if not raw_vector:
            raise EmbeddingError("embedding vectors must not be empty")
        all_finite_numbers = all(
            isinstance(value, (int, float)) and math.isfinite(value) for value in raw_vector
        )
        if not all_finite_numbers:
            raise EmbeddingError("embedding vectors must contain finite numbers")
        vector = tuple(float(value) for value in raw_vector)
        dimensions = len(vector) if dimensions is None else dimensions
        if len(vector) != dimensions:
            raise EmbeddingError("embedding vectors must have consistent dimensions")
        indexed[index] = vector
    if set(indexed) != set(range(expected_count)):
        raise EmbeddingError("embedding response indices do not cover every input")
    return tuple(indexed[index] for index in range(expected_count))
