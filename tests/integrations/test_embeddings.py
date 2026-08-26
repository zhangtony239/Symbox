"""OpenAI-compatible provider, validation, timeout, cosine, and cache tests."""

from __future__ import annotations

import httpx
import pytest

from symbox.application.embedding_ports import EmbeddingConfig, EmbeddingError, cosine_similarity
from symbox.integrations.embeddings import OpenAIEmbeddingProvider


def test_provider_sends_openai_compatible_request_and_restores_index_order() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("Authorization")
        seen["body"] = request.read()
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0, 1]},
                    {"index": 0, "embedding": [1, 0]},
                ]
            },
        )

    provider = OpenAIEmbeddingProvider(
        EmbeddingConfig("https://example.test/v1", "model", "secret", timeout_seconds=2),
        transport=httpx.MockTransport(handler),
    )

    assert provider.embed(("first", "second")) == ((1.0, 0.0), (0.0, 1.0))
    assert seen["authorization"] == "Bearer secret"
    assert b'"model":"model"' in seen["body"]  # type: ignore[operator]


def test_optional_cache_avoids_repeated_network_calls() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1, 2]}]})

    cache: dict[tuple[str, str, str], tuple[float, ...]] = {}
    provider = OpenAIEmbeddingProvider(
        EmbeddingConfig("https://example.test", "model"),
        transport=httpx.MockTransport(handler),
        cache=cache,
    )

    assert provider.embed(("key",)) == provider.embed(("key",))
    assert calls == 1


@pytest.mark.parametrize(
    "response",
    [
        {"invalid": []},
        {"data": []},
        {"data": [{"embedding": []}]},
        {"data": [{"embedding": [float("nan")]}]},
        {"data": [{"index": 1, "embedding": [1]}]},
    ],
)
def test_malformed_provider_responses_raise_embedding_error(response: object) -> None:
    provider = OpenAIEmbeddingProvider(
        EmbeddingConfig("https://example.test", "model"),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)),
    )

    with pytest.raises(EmbeddingError):
        provider.embed(("key",))


def test_timeout_and_http_failure_are_wrapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    provider = OpenAIEmbeddingProvider(
        EmbeddingConfig("https://example.test", "model", timeout_seconds=0.1),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(EmbeddingError, match="request failed"):
        provider.embed(("key",))


def test_cosine_similarity_and_invalid_vectors() -> None:
    assert cosine_similarity((1, 0), (1, 0)) == pytest.approx(1.0)
    assert cosine_similarity((1, 0), (0, 1)) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        cosine_similarity((0, 0), (1, 0))
    with pytest.raises(ValueError):
        cosine_similarity((1,), (1, 2))
