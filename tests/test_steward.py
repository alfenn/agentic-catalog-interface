from __future__ import annotations

import json
from pathlib import Path

import pytest

from catalog_steward.llm import ScriptedLM
from catalog_steward.protocol import format_final, format_tool_call
from catalog_steward.episodes import reset_episode
from catalog_steward.steward import StewardRun


def _id(run: StewardRun, kind: str) -> str:
    return next(item.id for item in run.store.items if item.kind == kind)


def _finding(
    *,
    evidence_ids: list[str],
    action: dict,
    issue_type: str = "sql_metadata_drift",
    asset: str = "daily_revenue",
) -> dict:
    return {
        "issue_type": issue_type,
        "asset": asset,
        "claim": "Catalog metadata disagrees with technical evidence.",
        "impact": "high",
        "confidence": "high",
        "evidence_ids": evidence_ids,
        "action": action,
    }


def _plan(finding: dict | None, *, question: str | None = None) -> dict:
    return {
        "summary": "Prioritized evidence-backed hygiene work.",
        "findings": [finding] if finding else [],
        "unresolved_questions": [question] if question else [],
    }


def test_remediation_runs_inspect_patch_verify_and_is_idempotent(tmp_path: Path) -> None:
    workspace = reset_episode(
        "rem_daily_revenue_filter_drift",
        destination=tmp_path / "episode",
    )
    run = StewardRun(workspace)
    run.collect_evidence()
    corrected = (
        "Completed-order revenue at one row per order date; "
        "refunded and cancelled orders are excluded."
    )
    finding = _finding(
        evidence_ids=[
            _id(run, "catalog_metadata"),
            _id(run, "dbt_model_sql"),
            _id(run, "parsed_sql_facts"),
        ],
        action={
            "class": "patch",
            "operation": "update_catalog_field",
            "field": "description",
            "value": corrected,
            "rationale": "The completed-only SQL filter directly contradicts all-orders prose.",
            "verification": {"field": "description", "equals": corrected},
        },
    )
    scripted_plan = format_final(json.dumps(_plan(finding)))

    result = run.run(ScriptedLM([scripted_plan]))

    assert result.status == "complete"
    assert result.mode == "remediation"
    assert result.outcomes[0].status == "verified"
    assert result.outcomes[0].verification["passed"] is True
    assert Path(result.outcomes[0].patch_path).read_text(encoding="utf-8").startswith("--- ")
    assert run.store.catalog_metadata("daily_revenue").content["description"] == corrected
    ledger_rows = [
        json.loads(line)
        for line in Path(result.ledger_path).read_text(encoding="utf-8").splitlines()
    ]
    assert ledger_rows[-1]["event"] == "run_summary"

    repeated = run.run(ScriptedLM([scripted_plan]))
    assert repeated.outcomes[0].status == "already_verified"


def test_change_review_uses_same_loop_and_emits_review_proposal(tmp_path: Path) -> None:
    workspace = reset_episode(
        "change_daily_revenue_filter",
        destination=tmp_path / "episode",
    )
    run = StewardRun(workspace)
    run.collect_evidence()
    finding = _finding(
        evidence_ids=[
            _id(run, "repository_diff_or_history"),
            _id(run, "catalog_metadata"),
            _id(run, "dbt_model_sql"),
            _id(run, "parsed_sql_facts"),
        ],
        action={
            "class": "propose",
            "operation": "request_review",
            "rationale": "A person must decide whether refunded orders belong in revenue.",
        },
    )
    model = ScriptedLM(
        [
            format_tool_call("get_change_diff", {}),
            format_final(json.dumps(_plan(finding, question="Should refunds count as revenue?"))),
        ]
    )

    result = run.run(model)

    assert result.status == "complete"
    assert result.mode == "change_review"
    assert result.outcomes[0].status == "proposed"
    assert result.unresolved_questions == ["Should refunds count as revenue?"]
    assert len(model.calls) == 2


def test_plan_cannot_cite_unknown_evidence(tmp_path: Path) -> None:
    workspace = reset_episode(
        "rem_daily_revenue_filter_drift",
        destination=tmp_path / "episode",
    )
    run = StewardRun(workspace)
    run.collect_evidence()
    finding = _finding(
        evidence_ids=["ev_fake_000000000000"],
        action={
            "class": "report",
            "operation": "report_only",
            "rationale": "Unsupported.",
        },
    )

    with pytest.raises(ValueError, match="unknown evidence"):
        run.run(ScriptedLM([format_final(json.dumps(_plan(finding)))]))


def test_issue_policy_blocks_disallowed_patch(tmp_path: Path) -> None:
    workspace = reset_episode(
        "rem_customer_orders_wrong_grain",
        destination=tmp_path / "episode",
    )
    run = StewardRun(workspace)
    run.collect_evidence()
    evidence_ids = [
        _id(run, "catalog_metadata"),
        _id(run, "dbt_model_sql"),
        _id(run, "parsed_sql_facts"),
    ]
    finding = _finding(
        issue_type="grain_or_join_drift",
        asset="customer_orders",
        evidence_ids=evidence_ids,
        action={
            "class": "patch",
            "operation": "update_catalog_field",
            "field": "grain",
            "value": ["customer_id"],
            "rationale": "Attempt a disallowed automatic grain decision.",
            "verification": {"field": "grain", "equals": ["customer_id"]},
        },
    )

    with pytest.raises(ValueError, match="not allowed"):
        run.run(ScriptedLM([format_final(json.dumps(_plan(finding)))]))


def test_failed_verification_is_visible_and_rolls_back(tmp_path: Path) -> None:
    workspace = reset_episode(
        "rem_daily_revenue_filter_drift",
        destination=tmp_path / "episode",
    )
    run = StewardRun(workspace)
    run.collect_evidence()
    before = (workspace.project_dir / "catalog/overrides.json").read_text(encoding="utf-8")
    finding = _finding(
        evidence_ids=[
            _id(run, "catalog_metadata"),
            _id(run, "dbt_model_sql"),
            _id(run, "parsed_sql_facts"),
        ],
        action={
            "class": "patch",
            "operation": "update_catalog_field",
            "field": "description",
            "value": "Completed orders only.",
            "rationale": "Exercise verification rollback.",
            "verification": {"field": "description", "equals": "A different expected value."},
        },
    )

    result = run.run(ScriptedLM([format_final(json.dumps(_plan(finding)))]))

    assert result.status == "verification_failed"
    assert result.outcomes[0].status == "verification_failed"
    assert result.outcomes[0].verification["passed"] is False
    assert (workspace.project_dir / "catalog/overrides.json").read_text(encoding="utf-8") == before

