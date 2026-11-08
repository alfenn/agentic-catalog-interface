from __future__ import annotations

import json
from pathlib import Path

import pytest

from catalog_steward.evidence import EvidenceStore, evidence_tools
from catalog_steward.episodes import reset_episode
from catalog_steward.protocol import ToolCall
from catalog_steward.tools import ToolRegistry


@pytest.fixture(scope="module")
def built_store(tmp_path_factory: pytest.TempPathFactory) -> EvidenceStore:
    root = tmp_path_factory.mktemp("evidence-built")
    workspace = reset_episode(
        "change_customer_orders_grain",
        destination=root / "episode",
        build=True,
    )
    return EvidenceStore(workspace)


def test_catalog_overrides_are_merged_and_provenanced(tmp_path: Path) -> None:
    workspace = reset_episode(
        "rem_daily_revenue_filter_drift",
        destination=tmp_path / "episode",
    )
    store = EvidenceStore(workspace)

    item = store.catalog_metadata("daily_revenue")

    assert item.content["description"] == "Revenue from all orders at one row per order date."
    assert "catalog/catalog.json" in item.source
    assert "catalog/overrides.json" in item.source
    assert item.id.startswith("ev_catalog_metadata_")


def test_sql_facts_are_technical_and_stable(built_store: EvidenceStore) -> None:
    first = built_store.sql_facts("customer_orders")
    second = built_store.sql_facts("customer_orders")

    assert first.id == second.id
    assert first.content["sources"] == ["raw_order_items", "stg_orders"]
    assert first.content["joins"][0]["relation"] == "raw_order_items"
    assert first.content["joins"][0]["alias"] == "items"
    assert "status = 'completed'" in first.content["filters"][0]
    assert first.content["group_by"] == []
    assert "business_meaning" not in first.content


def test_lineage_is_bounded_and_points_to_manifest(built_store: EvidenceStore) -> None:
    item = built_store.lineage("customer_orders", direction="upstream", max_hops=1)
    names = {node["name"] for node in item.content["upstream"]}

    assert names == {"raw_order_items", "stg_orders"}
    assert item.source.endswith("target/manifest.json")
    with pytest.raises(ValueError, match="between 0 and 2"):
        built_store.lineage("customer_orders", max_hops=3)


def test_profile_is_read_only_bounded_and_detects_duplicate_grain(built_store: EvidenceStore) -> None:
    item = built_store.profile_model("customer_orders", columns=["customer_id", "order_item_id"])

    assert item.content["sample_limit"] == 10_000
    assert item.content["sampled_rows"] < item.content["sample_limit"]
    assert item.content["columns"]["customer_id"]["duplicate_count"] > 0
    assert item.content["columns"]["order_item_id"]["duplicate_count"] == 0
    with pytest.raises(KeyError, match="unknown columns"):
        built_store.profile_model("customer_orders", columns=["not_a_column"])


def test_schema_diff_and_project_file_have_source_pointers(built_store: EvidenceStore) -> None:
    schema = built_store.dbt_schema("customer_orders")
    diff = built_store.change_diff()
    project_file = built_store.project_file("models/customer_orders.sql")

    assert schema.content["present"] is True
    assert "order_item_id" in diff.content["diff"]
    assert diff.source == "episode/input.diff"
    assert project_file.source == "project/models/customer_orders.sql"
    with pytest.raises(ValueError, match="escapes"):
        built_store.project_file("../../outside")


def test_missing_metadata_is_returned_as_evidence_not_invented(tmp_path: Path) -> None:
    workspace = reset_episode(
        "change_new_model_missing_metadata",
        destination=tmp_path / "episode",
    )
    store = EvidenceStore(workspace)

    catalog = store.catalog_metadata("high_value_orders")
    schema = store.dbt_schema("high_value_orders")

    assert catalog.content == {"present": False, "asset": "high_value_orders"}
    assert schema.content == {"present": False, "asset": "high_value_orders"}


def test_evidence_tools_return_addressable_json(built_store: EvidenceStore) -> None:
    registry = ToolRegistry(evidence_tools(built_store))

    result = registry.execute(ToolCall("get_sql_facts", {"asset": "customer_orders"}))
    payload = json.loads(result.content)

    assert result.status == "ok"
    assert payload["id"].startswith("ev_parsed_sql_facts_")
    assert payload["source"] == "project/models/customer_orders.sql"
    assert len(registry.schemas()) == 9


def test_raw_query_is_bounded_and_rejects_mutation(built_store: EvidenceStore) -> None:
    item = built_store.raw_query(
        "select customer_id, count(*) as n from customer_orders group by customer_id",
        max_rows=3,
    )

    assert item.kind == "raw_query"
    assert item.content["max_rows"] == 3
    assert len(item.content["rows"]) <= 3
    with pytest.raises(ValueError, match="read-only SELECT"):
        built_store.raw_query("delete from customer_orders")

