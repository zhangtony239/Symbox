"""Embedding port configuration and credential exclusion tests."""

from __future__ import annotations

import json

import pytest

from symbox.application.embedding_ports import EmbeddingConfig, load_embedding_config


def test_missing_endpoint_or_model_disables_embedding() -> None:
    assert load_embedding_config({}) is None
    assert load_embedding_config({"SBOX_EMBEDDING_BASE_URL": "https://example.test"}) is None


def test_environment_configuration_loads_without_exposing_api_key() -> None:
    secret = "sk-secret"
    config = load_embedding_config(
        {
            "SBOX_EMBEDDING_BASE_URL": "https://example.test/v1",
            "SBOX_EMBEDDING_MODEL": "embedding-model",
            "SBOX_EMBEDDING_API_KEY": secret,
            "SBOX_SIMILARITY_THRESHOLD": "0.91",
            "SBOX_EMBEDDING_TIMEOUT_SECONDS": "3.5",
        }
    )

    assert config is not None
    assert config.api_key == secret
    assert config.similarity_threshold == 0.91
    public_json = json.dumps(config.public_settings(), sort_keys=True)
    assert secret not in public_json
    assert "api_key" not in public_json
    assert config.public_settings()["credential_configured"] is True


@pytest.mark.parametrize(
    "config",
    [
        {"base_url": "", "model": "model"},
        {"base_url": "url", "model": ""},
        {"base_url": "url", "model": "model", "similarity_threshold": 1.1},
        {"base_url": "url", "model": "model", "timeout_seconds": 0},
    ],
)
def test_invalid_embedding_configuration_is_rejected(config: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        EmbeddingConfig(**config)  # type: ignore[arg-type]


def test_non_numeric_environment_values_are_rejected() -> None:
    with pytest.raises(ValueError, match="numeric"):
        load_embedding_config(
            {
                "SBOX_EMBEDDING_BASE_URL": "url",
                "SBOX_EMBEDDING_MODEL": "model",
                "SBOX_SIMILARITY_THRESHOLD": "not-a-number",
            }
        )
