"""Episode manifest validation and reproducible fixture workspace creation."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import jsonschema
import yaml

from catalog_steward.config import REPO_ROOT
from catalog_steward.contract import load_contract

DEFAULT_MANIFEST = REPO_ROOT / "data/episodes/manifest.yaml"
DEFAULT_SCHEMA = REPO_ROOT / "data/episodes/manifest.schema.json"
DEFAULT_RUNS = REPO_ROOT / ".runs"
MARKER = ".catalog_steward_episode"


class FixtureBuildError(RuntimeError):
    pass


def workspace_token(episode_id: str, condition: str = "") -> str:
    """Return an opaque, deterministic directory name for one episode run.

    Episode IDs name the expected finding, and dbt writes workspace paths into
    artifacts a model can read, so run directories must not embed them.
    """

    digest = hashlib.sha256(f"{episode_id}\0{condition}".encode("utf-8")).hexdigest()
    return f"ws_{digest[:12]}"


def dbt_env(workspace: "EpisodeWorkspace") -> dict[str, str]:
    """Environment for dbt commands against one episode workspace.

    Anonymous usage tracking is disabled so dbt makes no network calls and does
    not write a random per-run user ID into the project and its artifacts.
    """

    env = os.environ.copy()
    env["CATALOG_STEWARD_WAREHOUSE_PATH"] = str(workspace.warehouse_path.resolve())
    env["DBT_SEND_ANONYMOUS_USAGE_STATS"] = "false"
    return env


@dataclass(frozen=True)
class EpisodeWorkspace:
    episode_id: str
    root: Path
    before_dir: Path
    project_dir: Path
    diff_path: Path
    warehouse_path: Path
    build_log_path: Path


def load_manifest(
    path: Path = DEFAULT_MANIFEST,
    *,
    schema_path: Path = DEFAULT_SCHEMA,
) -> dict[str, Any]:
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(manifest)
    ids = [episode["id"] for episode in manifest["episodes"]]
    if len(ids) != len(set(ids)):
        raise ValueError("episode IDs must be unique")

    issue_ids = {issue["id"] for issue in load_contract()["issue_types"]}
    for episode in manifest["episodes"]:
        unknown = {
            finding["issue_type"]
            for finding in episode["expected_findings"]
            if finding["issue_type"] not in issue_ids
        }
        if unknown:
            raise ValueError(f"episode {episode['id']} references unknown issue types: {sorted(unknown)}")
        for key in ("base", "setup_overlay", "change_overlay"):
            value = episode["fixture"].get(key)
            if value is not None:
                _repo_path(value, must_exist=True)
    return manifest


def episode_by_id(manifest: dict[str, Any], episode_id: str) -> dict[str, Any]:
    for episode in manifest["episodes"]:
        if episode["id"] == episode_id:
            return episode
    raise KeyError(f"unknown episode: {episode_id}")


def _repo_path(value: str, *, must_exist: bool = False) -> Path:
    path = (REPO_ROOT / value).resolve()
    if not path.is_relative_to(REPO_ROOT):
        raise ValueError(f"episode path escapes the repository: {value}")
    if must_exist and not path.exists():
        raise FileNotFoundError(path)
    return path


def _safe_destination(destination: Path, episode_id: str) -> None:
    resolved = destination.resolve()
    if resolved in {Path.home().resolve(), REPO_ROOT.resolve(), Path("/")}:
        raise ValueError(f"unsafe episode destination: {resolved}")
    if resolved.exists():
        marker = resolved / MARKER
        if not marker.exists() or marker.read_text(encoding="utf-8").strip() != episode_id:
            raise ValueError(f"refusing to replace unmarked directory: {resolved}")
        shutil.rmtree(resolved)


def _copy_overlay(overlay: Path | None, destination: Path) -> None:
    if overlay is None:
        return
    shutil.copytree(overlay, destination, dirs_exist_ok=True)


def _delete_relative(project: Path, relative: str) -> None:
    target = (project / relative).resolve()
    if not target.is_relative_to(project.resolve()):
        raise ValueError(f"delete path escapes project: {relative}")
    if target.is_dir():
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()


def _text_files(root: Path) -> dict[str, list[str]]:
    files: dict[str, list[str]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if any(part in {"target", "logs", "dbt_packages"} for part in path.parts):
            continue
        relative = str(path.relative_to(root))
        files[relative] = path.read_text(encoding="utf-8").splitlines(keepends=True)
    return files


def directory_diff(before: Path, after: Path) -> str:
    old_files = _text_files(before)
    new_files = _text_files(after)
    chunks: list[str] = []
    for relative in sorted(set(old_files) | set(new_files)):
        chunks.extend(
            difflib.unified_diff(
                old_files.get(relative, []),
                new_files.get(relative, []),
                fromfile=f"a/{relative}",
                tofile=f"b/{relative}",
            )
        )
    return "".join(chunks)


def reset_episode(
    episode_id: str,
    *,
    destination: Path | None = None,
    build: bool = False,
    manifest: dict[str, Any] | None = None,
) -> EpisodeWorkspace:
    manifest = manifest or load_manifest()
    episode = episode_by_id(manifest, episode_id)
    destination = destination or DEFAULT_RUNS / episode_id
    _safe_destination(destination, episode_id)
    destination.mkdir(parents=True)
    (destination / MARKER).write_text(episode_id + "\n", encoding="utf-8")

    before_dir = destination / "before"
    project_dir = destination / "project"
    fixture = episode["fixture"]
    shutil.copytree(_repo_path(fixture["base"], must_exist=True), before_dir)
    setup = fixture.get("setup_overlay")
    _copy_overlay(_repo_path(setup, must_exist=True) if setup else None, before_dir)
    shutil.copytree(before_dir, project_dir)
    change = fixture.get("change_overlay")
    _copy_overlay(_repo_path(change, must_exist=True) if change else None, project_dir)
    for relative in fixture.get("delete_paths", []):
        _delete_relative(project_dir, relative)

    diff_path = destination / "input.diff"
    diff_path.write_text(directory_diff(before_dir, project_dir), encoding="utf-8")
    workspace = EpisodeWorkspace(
        episode_id=episode_id,
        root=destination,
        before_dir=before_dir,
        project_dir=project_dir,
        diff_path=diff_path,
        warehouse_path=destination / "warehouse.duckdb",
        build_log_path=destination / "dbt_build.log",
    )
    (destination / "episode.json").write_text(
        json.dumps(episode, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if build:
        build_fixture(workspace)
    return workspace


def build_fixture(workspace: EpisodeWorkspace) -> None:
    env = dbt_env(workspace)
    commands = [
        ["dbt", "seed", "--project-dir", str(workspace.project_dir), "--profiles-dir", str(workspace.project_dir)],
        ["dbt", "run", "--project-dir", str(workspace.project_dir), "--profiles-dir", str(workspace.project_dir)],
        ["dbt", "parse", "--project-dir", str(workspace.project_dir), "--profiles-dir", str(workspace.project_dir)],
    ]
    logs: list[str] = []
    for command in commands:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        logs.append(f"$ {' '.join(command)}\n{result.stdout}")
        if result.returncode != 0:
            workspace.build_log_path.write_text("\n".join(logs), encoding="utf-8")
            raise FixtureBuildError(
                f"fixture build failed for {workspace.episode_id}; see {workspace.build_log_path}"
            )
    workspace.build_log_path.write_text("\n".join(logs), encoding="utf-8")


def list_rows(manifest: dict[str, Any]) -> Iterable[str]:
    for episode in manifest["episodes"]:
        label = "clean" if not episode["expected_findings"] else ",".join(
            finding["issue_type"] for finding in episode["expected_findings"]
        )
        yield f"{episode['id']:<38} {episode['mode']:<13} {label}"


def validate_episodes(manifest: dict[str, Any], *, build: bool = False) -> list[str]:
    validated: list[str] = []
    with tempfile.TemporaryDirectory(prefix="catalog-steward-episodes-") as temporary:
        root = Path(temporary)
        for episode in manifest["episodes"]:
            reset_episode(
                episode["id"],
                destination=root / episode["id"],
                build=build,
                manifest=manifest,
            )
            validated.append(episode["id"])
    return validated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage catalog-steward episodes")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    validate = subparsers.add_parser("validate")
    validate.add_argument("--build", action="store_true")
    reset = subparsers.add_parser("reset")
    reset.add_argument("episode_id")
    reset.add_argument("--destination", type=Path)
    reset.add_argument("--build", action="store_true")
    args = parser.parse_args(argv)
    manifest = load_manifest()
    if args.command == "list":
        print("\n".join(list_rows(manifest)))
        return 0
    if args.command == "validate":
        for episode_id in validate_episodes(manifest, build=args.build):
            print(f"validated {episode_id}")
        return 0
    workspace = reset_episode(
        args.episode_id,
        destination=args.destination,
        build=args.build,
        manifest=manifest,
    )
    print(workspace.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

