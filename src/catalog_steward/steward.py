"""Shared inspect-plan-act-verify workflow for both steward triggers."""

from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import jsonschema

from catalog_steward.agent import AgentConfig, AgentResult, AgentSession
from catalog_steward.config import REPO_ROOT
from catalog_steward.contract import issue_by_id, load_contract
from catalog_steward.episodes import EpisodeWorkspace, episode_by_id, load_manifest, reset_episode
from catalog_steward.evidence import EvidenceItem, EvidenceStore, evidence_tools
from catalog_steward.llm import ChatModel, LM

PLAN_SCHEMA_PATH = REPO_ROOT / "design/steward_plan.schema.json"
LEDGER_NAME = "steward_ledger.jsonl"
ALLOWED_PATCH_FIELDS = {"description", "owner", "lifecycle", "grain", "canonical"}


@dataclass(frozen=True)
class FindingOutcome:
    finding_key: str
    issue_type: str
    asset: str
    action_class: str
    status: str
    verification: dict[str, Any]
    patch_path: str | None = None


@dataclass(frozen=True)
class StewardResult:
    episode_id: str
    mode: str
    status: str
    summary: str
    outcomes: list[FindingOutcome]
    unresolved_questions: list[str]
    agent: AgentResult
    plan_path: str
    ledger_path: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["agent"] = asdict(self.agent)
        return payload


class StewardRun:
    def __init__(
        self,
        workspace: EpisodeWorkspace,
        *,
        manifest: dict[str, Any] | None = None,
        contract: dict[str, Any] | None = None,
    ) -> None:
        self.workspace = workspace
        self.manifest = manifest or load_manifest()
        self.contract = contract or load_contract()
        self.episode = episode_by_id(self.manifest, workspace.episode_id)
        self.store = EvidenceStore(workspace, contract=self.contract)
        self.bundle_errors: list[str] = []

    def collect_evidence(self) -> list[EvidenceItem]:
        """Systematically collect bounded facts without using evaluation labels."""

        max_assets = int(self.contract["scope"]["max_assets"])
        scope = self.episode["asset_scope"][:max_assets]
        for asset in scope:
            self._try(lambda asset=asset: self.store.catalog_metadata(asset))
            self._try(lambda asset=asset: self.store.dbt_schema(asset))
            if (self.workspace.project_dir / "models" / f"{asset}.sql").exists():
                self._try(lambda asset=asset: self.store.model_sql(asset))
                self._try(lambda asset=asset: self.store.sql_facts(asset))
            if (self.workspace.project_dir / "target/manifest.json").exists():
                self._try(lambda asset=asset: self.store.manifest_node(asset))
                self._try(lambda asset=asset: self.store.lineage(asset, max_hops=1))
                self._try(lambda asset=asset: self.store.profile_model(asset))
        if self.episode["mode"] == "change_review":
            self._try(self.store.change_diff)
        return self.store.items

    def _try(self, operation) -> None:
        try:
            operation()
        except (FileNotFoundError, KeyError, ValueError) as exc:
            self.bundle_errors.append(str(exc))

    def run(self, model: ChatModel) -> StewardResult:
        evidence = self.collect_evidence()
        prompt = self._prompt(evidence)
        session = AgentSession(
            model,
            evidence_tools(self.store),
            AgentConfig(max_turns=12, system_prompt=self._system_prompt()),
        )
        agent_result = session.send(prompt)
        if agent_result.status != "done":
            raise RuntimeError(f"steward planning did not finish: {agent_result.status}: {agent_result.text}")
        plan = self._validate_plan(agent_result.text)
        artifacts = self.workspace.root / "artifacts"
        artifacts.mkdir(exist_ok=True)
        plan_path = artifacts / "plan.json"
        plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        outcomes = [self._execute_finding(finding, artifacts) for finding in plan["findings"]]
        self._append_run_summary(plan, outcomes)
        status = "complete" if all(
            outcome.status in {"verified", "proposed", "reported", "already_verified"}
            for outcome in outcomes
        ) else "verification_failed"
        return StewardResult(
            episode_id=self.workspace.episode_id,
            mode=self.episode["mode"],
            status=status,
            summary=plan["summary"],
            outcomes=outcomes,
            unresolved_questions=plan["unresolved_questions"],
            agent=agent_result,
            plan_path=str(plan_path),
            ledger_path=str(self.workspace.root / LEDGER_NAME),
        )

    def _system_prompt(self) -> str:
        issue_contract = [
            {
                "id": issue["id"],
                "required_evidence": issue["required_evidence"],
                "allowed_actions": issue["allowed_actions"],
                "forbidden_actions": issue["forbidden_actions"],
            }
            for issue in self.contract["issue_types"]
        ]
        schema = json.loads(PLAN_SCHEMA_PATH.read_text(encoding="utf-8"))
        return (
            "You are a specialized data-catalog hygiene steward. Inspect the supplied evidence and use "
            "the read-only tools if a required fact is missing. Return only the agent protocol's final "
            "response, whose content must itself be JSON matching the steward plan schema. Do not use "
            "evaluation ground truth, invent business meaning, or exceed five prioritized findings.\n\n"
            f"Hygiene issue contract:\n{json.dumps(issue_contract, sort_keys=True)}\n\n"
            f"Steward plan JSON Schema:\n{json.dumps(schema, sort_keys=True)}"
        )

    def _prompt(self, evidence: list[EvidenceItem]) -> str:
        task = {
            "episode_id": self.workspace.episode_id,
            "trigger": self.episode["mode"],
            "asset_scope": self.episode["asset_scope"],
            "evidence": [item.to_dict() for item in evidence],
            "collection_errors": sorted(set(self.bundle_errors)),
        }
        return "Inspect, prioritize, and plan hygiene actions for this bounded task:\n" + json.dumps(
            task,
            sort_keys=True,
        )

    def _validate_plan(self, text: str) -> dict[str, Any]:
        try:
            plan = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"steward final content is not JSON: {exc}") from exc
        schema = json.loads(PLAN_SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(plan)
        evidence_ids = {item.id for item in self.store.items}
        scope = set(self.episode["asset_scope"])
        for finding in plan["findings"]:
            if finding["asset"] not in scope:
                raise ValueError(f"finding asset is outside episode scope: {finding['asset']}")
            issue = issue_by_id(self.contract, finding["issue_type"])
            action_class = finding["action"]["class"]
            if action_class not in issue["allowed_actions"]:
                raise ValueError(
                    f"{action_class} is not allowed for issue {finding['issue_type']}"
                )
            unknown = set(finding["evidence_ids"]) - evidence_ids
            if unknown:
                raise ValueError(f"finding cites unknown evidence IDs: {sorted(unknown)}")
            by_id = {item.id: item.kind for item in self.store.items}
            provided = {by_id[evidence_id] for evidence_id in finding["evidence_ids"]}
            if "bounded_data_profile" in provided:
                provided.add("bounded_uniqueness_probe")
            missing = set(issue["required_evidence"]) - provided
            if missing:
                raise ValueError(
                    f"finding {finding['issue_type']} lacks required evidence kinds: {sorted(missing)}"
                )
        return plan

    def _execute_finding(self, finding: dict[str, Any], artifacts: Path) -> FindingOutcome:
        finding_key = self._finding_key(finding)
        prior = self._verified_keys()
        if finding_key in prior:
            return FindingOutcome(
                finding_key=finding_key,
                issue_type=finding["issue_type"],
                asset=finding["asset"],
                action_class=finding["action"]["class"],
                status="already_verified",
                verification={"passed": True, "checks": ["matching verified ledger entry"]},
            )

        action = finding["action"]
        patch_path: Path | None = None
        if action["class"] == "patch":
            status, verification, patch_path = self._apply_catalog_patch(
                finding_key,
                finding["asset"],
                action,
                artifacts,
            )
        elif action["class"] == "propose":
            status = "proposed"
            verification = {
                "passed": True,
                "checks": ["action allowed by issue contract", "all cited evidence IDs resolved"],
            }
        else:
            status = "reported"
            verification = {
                "passed": True,
                "checks": ["action allowed by issue contract", "all cited evidence IDs resolved"],
            }
        outcome = FindingOutcome(
            finding_key=finding_key,
            issue_type=finding["issue_type"],
            asset=finding["asset"],
            action_class=action["class"],
            status=status,
            verification=verification,
            patch_path=str(patch_path) if patch_path else None,
        )
        self._append_ledger(finding, outcome)
        return outcome

    def _apply_catalog_patch(
        self,
        finding_key: str,
        asset: str,
        action: dict[str, Any],
        artifacts: Path,
    ) -> tuple[str, dict[str, Any], Path]:
        field = action["field"]
        if field not in ALLOWED_PATCH_FIELDS:
            raise ValueError(f"catalog field is not patchable: {field}")
        override_path = self.workspace.project_dir / "catalog/overrides.json"
        original_exists = override_path.exists()
        original = override_path.read_text(encoding="utf-8") if original_exists else ""
        payload = json.loads(original) if original else {"assets": {}}
        payload.setdefault("assets", {}).setdefault(asset, {})[field] = copy.deepcopy(action["value"])
        updated = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        patch = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                updated.splitlines(keepends=True),
                fromfile="a/catalog/overrides.json",
                tofile="b/catalog/overrides.json",
            )
        )
        patch_path = artifacts / f"{finding_key}.patch"
        patch_path.write_text(patch, encoding="utf-8")
        override_path.parent.mkdir(parents=True, exist_ok=True)
        override_path.write_text(updated, encoding="utf-8")

        checks: list[str] = []
        metadata = self.store.catalog_metadata(asset)
        verification = action["verification"]
        field_matches = metadata.content.get(verification["field"]) == verification["equals"]
        checks.append(f"catalog {verification['field']} equals expected value: {field_matches}")
        dbt_ok = self._dbt_parse()
        checks.append(f"dbt parse succeeds after patch: {dbt_ok}")
        passed = field_matches and dbt_ok
        if not passed:
            if original_exists:
                override_path.write_text(original, encoding="utf-8")
            else:
                override_path.unlink(missing_ok=True)
        return (
            "verified" if passed else "verification_failed",
            {"passed": passed, "checks": checks, "post_change_evidence_id": metadata.id},
            patch_path,
        )

    def _dbt_parse(self) -> bool:
        env = os.environ.copy()
        env["CATALOG_STEWARD_WAREHOUSE_PATH"] = str(self.workspace.warehouse_path.resolve())
        result = subprocess.run(
            [
                "dbt",
                "parse",
                "--project-dir",
                str(self.workspace.project_dir),
                "--profiles-dir",
                str(self.workspace.project_dir),
            ],
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        log_path = self.workspace.root / "steward_verify.log"
        log_path.write_text(result.stdout, encoding="utf-8")
        return result.returncode == 0

    @staticmethod
    def _finding_key(finding: dict[str, Any]) -> str:
        payload = json.dumps(
            {
                "issue_type": finding["issue_type"],
                "asset": finding["asset"],
                "claim": finding["claim"],
                "action": finding["action"],
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _verified_keys(self) -> set[str]:
        path = self.workspace.root / LEDGER_NAME
        if not path.exists():
            return set()
        keys = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("verification", {}).get("passed"):
                keys.add(row.get("finding_key"))
        return keys

    def _append_ledger(self, finding: dict[str, Any], outcome: FindingOutcome) -> None:
        path = self.workspace.root / LEDGER_NAME
        row = {
            "ts": round(time.time(), 3),
            "episode_id": self.workspace.episode_id,
            "mode": self.episode["mode"],
            "finding_key": outcome.finding_key,
            "finding": finding,
            "status": outcome.status,
            "verification": outcome.verification,
            "patch_path": outcome.patch_path,
            "unresolved_questions": [],
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    def _append_run_summary(
        self,
        plan: dict[str, Any],
        outcomes: list[FindingOutcome],
    ) -> None:
        path = self.workspace.root / LEDGER_NAME
        row = {
            "ts": round(time.time(), 3),
            "event": "run_summary",
            "episode_id": self.workspace.episode_id,
            "mode": self.episode["mode"],
            "summary": plan["summary"],
            "outcome_statuses": [outcome.status for outcome in outcomes],
            "unresolved_questions": plan["unresolved_questions"],
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one catalog-steward episode")
    parser.add_argument("episode_id")
    parser.add_argument("--salt", default="")
    args = parser.parse_args(argv)
    workspace = reset_episode(args.episode_id, build=True)
    result = StewardRun(workspace).run(LM(tag=f"steward/{args.episode_id}", salt=args.salt))
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())

