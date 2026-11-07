"""Load and validate the versioned midpoint hygiene contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from catalog_steward.config import REPO_ROOT

DEFAULT_CONTRACT = REPO_ROOT / "design/hygiene_contract.yaml"
DEFAULT_SCHEMA = REPO_ROOT / "design/hygiene_contract.schema.json"


def load_contract(
    path: Path = DEFAULT_CONTRACT,
    *,
    schema_path: Path = DEFAULT_SCHEMA,
) -> dict[str, Any]:
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(contract)

    issue_ids = [issue["id"] for issue in contract["issue_types"]]
    if len(issue_ids) != len(set(issue_ids)):
        raise ValueError("hygiene contract issue IDs must be unique")
    return contract


def issue_by_id(contract: dict[str, Any], issue_id: str) -> dict[str, Any]:
    for issue in contract["issue_types"]:
        if issue["id"] == issue_id:
            return issue
    raise KeyError(f"unknown hygiene issue type: {issue_id}")


def summary(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": contract["name"],
        "version": contract["version"],
        "stack": contract["scope"]["stack"],
        "modes": contract["scope"]["modes"],
        "issue_types": [issue["id"] for issue in contract["issue_types"]],
        "action_surface": contract["scope"]["action_surface"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the hygiene contract")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_CONTRACT)
    args = parser.parse_args(argv)
    print(json.dumps(summary(load_contract(args.path)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

