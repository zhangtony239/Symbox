"""Generate a stable pytest skeleton for every OpenSpec scenario."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).parents[2]
SPEC_ROOT = (
    REPOSITORY_ROOT / "openspec" / "changes" / "initialize-symbox-v0.6" / "specs"
)
SCENARIO_PATTERN = re.compile(r"^#### Scenario: (.+)$", re.MULTILINE)
EXPECTED_CAPABILITIES = {
    "attribute-state",
    "backup-management",
    "object-model",
    "state-query",
    "svk-assertions",
    "truth-maintenance",
    "worry-monitoring",
}


def _scenario_contracts() -> list[tuple[str, str]]:
    contracts: list[tuple[str, str]] = []
    for spec_path in sorted(SPEC_ROOT.glob("*/spec.md")):
        capability = spec_path.parent.name
        scenarios = SCENARIO_PATTERN.findall(spec_path.read_text(encoding="utf-8"))
        contracts.extend((capability, scenario) for scenario in scenarios)
    return contracts


CONTRACTS = _scenario_contracts()


def test_all_capabilities_have_contract_scenarios() -> None:
    discovered = {capability for capability, _ in CONTRACTS}
    assert discovered == EXPECTED_CAPABILITIES
    assert all(scenario.strip() for _, scenario in CONTRACTS)


def test_contract_scenario_ids_are_unique() -> None:
    assert len(CONTRACTS) == len(set(CONTRACTS))


@pytest.mark.contract
@pytest.mark.parametrize(
    ("capability", "scenario"),
    CONTRACTS,
    ids=[f"{capability}::{scenario}" for capability, scenario in CONTRACTS],
)
def test_scenario_is_tracked_by_pytest(capability: str, scenario: str) -> None:
    """Keep each normative scenario visible as an independently selected test item."""
    spec_text = (SPEC_ROOT / capability / "spec.md").read_text(encoding="utf-8")
    assert f"#### Scenario: {scenario}" in spec_text
