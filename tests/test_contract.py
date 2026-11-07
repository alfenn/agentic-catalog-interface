from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest
import yaml

from catalog_steward.contract import issue_by_id, load_contract, summary


def test_default_contract_is_valid_and_midpoint_sized() -> None:
    contract = load_contract()

    assert contract["version"] == "0.1.0"
    assert contract["scope"]["modes"] == ["remediation", "change_review"]
    assert 4 <= len(contract["issue_types"]) <= 6
    assert len({issue["id"] for issue in contract["issue_types"]}) == len(
        contract["issue_types"]
    )
    for issue in contract["issue_types"]:
        assert issue["required_evidence"]
        assert issue["allowed_actions"]
        assert issue["forbidden_actions"]
        assert issue["verification"]


def test_lookup_and_summary() -> None:
    contract = load_contract()

    issue = issue_by_id(contract, "sql_metadata_drift")

    assert "parsed_sql_facts" in issue["required_evidence"]
    assert "patch" in issue["allowed_actions"]
    assert summary(contract)["action_surface"] == "repository_patch_or_proposal"
    with pytest.raises(KeyError, match="unknown hygiene issue"):
        issue_by_id(contract, "not_real")


def test_contract_rejects_missing_verification(tmp_path: Path) -> None:
    contract = deepcopy(load_contract())
    del contract["issue_types"][0]["verification"]
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(contract), encoding="utf-8")

    with pytest.raises(jsonschema.ValidationError):
        load_contract(path)

