"""Bounded, provenance-preserving evidence access for catalog episodes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable

import duckdb
import sqlglot
from sqlglot import exp
import yaml

from catalog_steward.config import REPO_ROOT
from catalog_steward.contract import load_contract
from catalog_steward.episodes import EpisodeWorkspace, reset_episode
from catalog_steward.tools import ToolSpec

_REF = re.compile(r"\{\{\s*ref\(['\"]([^'\"]+)['\"]\)\s*\}\}")
_SOURCE = re.compile(
    r"\{\{\s*source\(['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\)\s*\}\}"
)


# Stable stand-ins for run-specific absolute paths. dbt writes the workspace path
# into its artifacts; the real path varies per run and must never reach a model.
WORKSPACE_PLACEHOLDER = "/workspace"
REPO_PLACEHOLDER = "/repo"
VOLATILE_PLACEHOLDER = "<normalized>"
# dbt artifact fields that change on every invocation without carrying hygiene
# information (timestamps, timings, invocation and anonymous-user IDs).
VOLATILE_DBT_KEYS = frozenset(
    {
        "_invocation_id",
        "completed_at",
        "created_at",
        "elapsed",
        "elapsed_time",
        "execution_time",
        "generated_at",
        "invocation_id",
        "invocation_started_at",
        "load_all_elapsed",
        "read_files_elapsed",
        "run_started_at",
        "started_at",
        "user_id",
    }
)
DUCKDB_CONFIG = {"enable_external_access": False}


def stabilize_dbt_artifact(value: Any) -> Any:
    """Replace per-invocation dbt fields with a constant, keeping structure."""

    if isinstance(value, dict):
        return {
            key: VOLATILE_PLACEHOLDER if key in VOLATILE_DBT_KEYS else stabilize_dbt_artifact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [stabilize_dbt_artifact(item) for item in value]
    return value


class RedactedError(Exception):
    """A tool failure whose message had run-specific paths removed."""

    def __init__(self, display_type: str, message: str) -> None:
        super().__init__(message)
        self.display_type = display_type


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    kind: str
    asset: str | None
    source: str
    content: Any

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _evidence_id(kind: str, asset: str | None, source: str, content: Any) -> str:
    payload = json.dumps(
        {"kind": kind, "asset": asset, "source": source, "content": _jsonable(content)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"ev_{kind}_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:12]}"


def _object_schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


class EvidenceStore:
    def __init__(
        self,
        workspace: EpisodeWorkspace,
        *,
        contract: dict[str, Any] | None = None,
    ) -> None:
        self.workspace = workspace
        self.contract = contract or load_contract()
        self._items: dict[str, EvidenceItem] = {}
        replacements: dict[str, str] = {}
        for path, placeholder in ((REPO_ROOT, REPO_PLACEHOLDER), (workspace.root, WORKSPACE_PLACEHOLDER)):
            for variant in {str(path), os.path.abspath(path), str(Path(path).resolve())}:
                replacements[variant.rstrip(os.sep)] = placeholder
        # Longest first, so a workspace inside the repository maps to the workspace placeholder.
        self._replacements = sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True)

    def redact(self, value: Any) -> Any:
        """Replace run-specific absolute paths in strings, lists, and dict values."""

        if isinstance(value, str):
            for original, placeholder in self._replacements:
                value = value.replace(original, placeholder)
            return value
        if isinstance(value, dict):
            return {key: self.redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        return value

    def guarded(self, handler):
        """Wrap a tool handler so failure messages cannot expose workspace paths."""

        def run(**arguments: Any) -> Any:
            try:
                return handler(**arguments)
            except Exception as exc:
                raise RedactedError(type(exc).__name__, self.redact(str(exc))) from exc

        return run

    def _project_text(self, path: Path) -> str:
        """Read a project file as the model sees it: stable paths and dbt fields."""

        text = self.redact(path.read_text(encoding="utf-8"))
        relative = path.resolve().relative_to(self.workspace.project_dir.resolve())
        if relative.parts and relative.parts[0] == "target" and path.suffix == ".json":
            try:
                document = json.loads(text)
            except json.JSONDecodeError:
                return text
            text = json.dumps(stabilize_dbt_artifact(document), indent=2) + "\n"
        return text

    @property
    def items(self) -> list[EvidenceItem]:
        return list(self._items.values())

    def external_evidence(
        self,
        kind: str,
        *,
        source: Path | str,
        content: Any,
        asset: str | None = None,
    ) -> EvidenceItem:
        """Record bounded evidence produced by a baseline command or checker."""

        return self._record(kind, asset, source, content)

    def _record(self, kind: str, asset: str | None, source: Path | str, content: Any) -> EvidenceItem:
        source_text = self.redact(self._source_pointer(source))
        normalized = self.redact(_jsonable(content))
        item = EvidenceItem(
            id=_evidence_id(kind, asset, source_text, normalized),
            kind=kind,
            asset=asset,
            source=source_text,
            content=normalized,
        )
        self._items[item.id] = item
        return item

    def _source_pointer(self, source: Path | str) -> str:
        if not isinstance(source, Path):
            return source
        resolved = source.resolve()
        for root, prefix in (
            (self.workspace.project_dir.resolve(), "project"),
            (self.workspace.root.resolve(), "episode"),
        ):
            if resolved.is_relative_to(root):
                return f"{prefix}/{resolved.relative_to(root)}"
        return str(resolved)

    def catalog_metadata(self, asset: str) -> EvidenceItem:
        catalog_path = self.workspace.project_dir / "catalog/catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        assets = {entry["name"]: dict(entry) for entry in catalog["assets"]}
        override_path = self.workspace.project_dir / "catalog/overrides.json"
        sources = [self._source_pointer(catalog_path)]
        if override_path.exists():
            overrides = json.loads(override_path.read_text(encoding="utf-8"))
            for name, override in overrides.get("assets", {}).items():
                assets.setdefault(name, {"name": name}).update(override)
            sources.append(self._source_pointer(override_path))
        if asset not in assets:
            content = {"present": False, "asset": asset}
        else:
            content = {"present": True, **assets[asset]}
        return self._record("catalog_metadata", asset, "+".join(sources), content)

    def dbt_schema(self, asset: str) -> EvidenceItem:
        matches: list[tuple[Path, dict[str, Any]]] = []
        for path in sorted((self.workspace.project_dir / "models").rglob("*.y*ml")):
            document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for model in document.get("models", []):
                if model.get("name") == asset:
                    matches.append((path, model))
        if len(matches) > 1:
            raise ValueError(f"multiple schema definitions found for {asset}")
        if not matches:
            return self._record(
                "dbt_schema",
                asset,
                "project/models/**/*.yml",
                {"present": False, "asset": asset},
            )
        path, model = matches[0]
        return self._record("dbt_schema", asset, path, {"present": True, **model})

    def sql_facts(self, asset: str) -> EvidenceItem:
        path = self.workspace.project_dir / "models" / f"{asset}.sql"
        if not path.exists():
            raise KeyError(f"no SQL model named {asset}")
        raw = path.read_text(encoding="utf-8")
        rendered = _SOURCE.sub(lambda match: f"{match.group(1)}__{match.group(2)}", raw)
        rendered = _REF.sub(lambda match: match.group(1), rendered)
        try:
            tree = sqlglot.parse_one(rendered, read="duckdb")
        except sqlglot.errors.ParseError as exc:
            raise ValueError(f"could not parse SQL for {asset}: {exc}") from exc

        where = tree.args.get("where")
        group = tree.args.get("group")
        joins = []
        for join in tree.find_all(exp.Join):
            relation = join.this.name if isinstance(join.this, exp.Table) else join.this.sql(dialect="duckdb")
            alias = join.this.alias if isinstance(join.this, exp.Table) else ""
            joins.append(
                {
                    "relation": relation,
                    "alias": alias or None,
                    "kind": join.args.get("kind") or "inner",
                    "on": join.args.get("on").sql(dialect="duckdb") if join.args.get("on") else None,
                }
            )
        aggregates = sorted(
            {node.sql(dialect="duckdb") for node in tree.find_all(exp.AggFunc)}
        )
        group_by = [item.sql(dialect="duckdb") for item in group.expressions] if group else []
        content = {
            "sources": sorted({table.name for table in tree.find_all(exp.Table)}),
            "filters": [where.this.sql(dialect="duckdb")] if where else [],
            "joins": joins,
            "aggregations": aggregates,
            "group_by": group_by,
            "grain_candidates": group_by,
            "select_expressions": [item.sql(dialect="duckdb") for item in tree.expressions],
        }
        return self._record("parsed_sql_facts", asset, path, content)

    def model_sql(self, asset: str) -> EvidenceItem:
        path = self.workspace.project_dir / "models" / f"{asset}.sql"
        if not path.exists():
            raise KeyError(f"no SQL model named {asset}")
        return self._record("dbt_model_sql", asset, path, {"sql": path.read_text(encoding="utf-8")})

    def manifest_node(self, asset: str) -> EvidenceItem:
        manifest_path = self.workspace.project_dir / "target/manifest.json"
        manifest = self._manifest(manifest_path)
        node = stabilize_dbt_artifact(self._node_by_name(manifest, asset))
        return self._record("dbt_manifest", asset, manifest_path, node)

    def lineage(self, asset: str, *, direction: str = "both", max_hops: int = 1) -> EvidenceItem:
        limit = int(self.contract["scope"]["max_lineage_hops"])
        if direction not in {"upstream", "downstream", "both"}:
            raise ValueError("direction must be upstream, downstream, or both")
        if max_hops < 0 or max_hops > limit:
            raise ValueError(f"max_hops must be between 0 and {limit}")
        manifest_path = self.workspace.project_dir / "target/manifest.json"
        manifest = self._manifest(manifest_path)
        nodes = {**manifest.get("nodes", {}), **manifest.get("sources", {})}
        start_id, _ = self._node_entry_by_name(manifest, asset)
        upstream = {node_id: list(node.get("depends_on", {}).get("nodes", [])) for node_id, node in nodes.items()}
        downstream: dict[str, list[str]] = {node_id: [] for node_id in nodes}
        for node_id, parents in upstream.items():
            for parent in parents:
                if parent in downstream:
                    downstream[parent].append(node_id)

        def walk(edges: dict[str, list[str]]) -> list[dict[str, Any]]:
            seen = {start_id}
            frontier = [(start_id, 0)]
            found: list[dict[str, Any]] = []
            while frontier:
                current, distance = frontier.pop(0)
                if distance >= max_hops:
                    continue
                for neighbor in sorted(edges.get(current, [])):
                    if neighbor in seen or neighbor not in nodes:
                        continue
                    seen.add(neighbor)
                    node = nodes[neighbor]
                    found.append(
                        {
                            "name": node.get("name"),
                            "resource_type": node.get("resource_type"),
                            "distance": distance + 1,
                        }
                    )
                    frontier.append((neighbor, distance + 1))
            return found

        content: dict[str, Any] = {"max_hops": max_hops}
        if direction in {"upstream", "both"}:
            content["upstream"] = walk(upstream)
        if direction in {"downstream", "both"}:
            content["downstream"] = walk(downstream)
        return self._record("lineage", asset, manifest_path, content)

    def profile_model(self, asset: str, *, columns: list[str] | None = None) -> EvidenceItem:
        manifest_path = self.workspace.project_dir / "target/manifest.json"
        manifest = self._manifest(manifest_path)
        self._node_by_name(manifest, asset)
        if not self.workspace.warehouse_path.exists():
            raise FileNotFoundError("episode warehouse is missing; reset with build=True")
        relation = f'"main"."{asset.replace(chr(34), chr(34) * 2)}"'
        limit = int(self.contract["scope"]["max_probe_rows"])
        with duckdb.connect(
            str(self.workspace.warehouse_path), read_only=True, config=DUCKDB_CONFIG
        ) as connection:
            described = connection.execute(f"describe select * from {relation}").fetchall()
            types = {str(row[0]): str(row[1]) for row in described}
            selected = columns or list(types)
            unknown = sorted(set(selected) - set(types))
            if unknown:
                raise KeyError(f"unknown columns for {asset}: {unknown}")
            sampled_rows = int(
                connection.execute(
                    f"select count(*) from (select * from {relation} limit {limit})"
                ).fetchone()[0]
            )
            metrics: dict[str, Any] = {}
            for column in selected[:20]:
                quoted = '"' + column.replace('"', '""') + '"'
                nulls, distinct = connection.execute(
                    "with sample as "
                    f"(select * from {relation} limit {limit}) "
                    f"select count(*) filter (where {quoted} is null), count(distinct {quoted}) from sample"
                ).fetchone()
                entry: dict[str, Any] = {
                    "type": types[column],
                    "null_count": int(nulls),
                    "distinct_count": int(distinct),
                    "duplicate_count": max(sampled_rows - int(nulls) - int(distinct), 0),
                }
                if any(token in types[column].upper() for token in ("DATE", "TIME")):
                    minimum, maximum = connection.execute(
                        "with sample as "
                        f"(select * from {relation} limit {limit}) "
                        f"select min({quoted}), max({quoted}) from sample"
                    ).fetchone()
                    entry["min"] = minimum
                    entry["max"] = maximum
                metrics[column] = entry
        content = {
            "sampled_rows": sampled_rows,
            "sample_limit": limit,
            "at_sample_limit": sampled_rows == limit,
            "columns": metrics,
        }
        return self._record("bounded_data_profile", asset, self.workspace.warehouse_path, content)

    def change_diff(self) -> EvidenceItem:
        return self._record(
            "repository_diff_or_history",
            None,
            self.workspace.diff_path,
            {"diff": self.workspace.diff_path.read_text(encoding="utf-8")},
        )

    def project_file(self, relative_path: str, *, max_bytes: int = 50_000) -> EvidenceItem:
        path = (self.workspace.project_dir / relative_path).resolve()
        if not path.is_relative_to(self.workspace.project_dir.resolve()):
            raise ValueError("project file path escapes the episode project")
        if not path.is_file():
            raise FileNotFoundError(relative_path)
        if path.stat().st_size > max_bytes:
            raise ValueError(f"project file exceeds {max_bytes} bytes")
        text = self._project_text(path)
        if len(text.encode("utf-8")) > max_bytes:
            raise ValueError(f"project file exceeds {max_bytes} bytes")
        return self._record(
            "project_file",
            None,
            path,
            {"path": relative_path, "text": text},
        )

    def project_listing(self, *, max_files: int = 250) -> EvidenceItem:
        files = []
        for path in sorted(item for item in self.workspace.project_dir.rglob("*") if item.is_file()):
            if any(part in {"logs", "dbt_packages"} for part in path.parts):
                continue
            files.append(
                {
                    "path": str(path.relative_to(self.workspace.project_dir)),
                    "bytes": self._listed_size(path),
                }
            )
            if len(files) >= max_files:
                break
        return self._record(
            "project_listing",
            None,
            self.workspace.project_dir,
            {"files": files, "max_files": max_files, "at_limit": len(files) == max_files},
        )

    def _listed_size(self, path: Path) -> int | None:
        """Size of a file as read_file would return it; None for binary files.

        Generated dbt files embed paths, timestamps, and IDs, so their raw sizes
        change between otherwise identical runs.
        """

        try:
            return len(self._project_text(path).encode("utf-8"))
        except UnicodeDecodeError:
            return None

    def raw_query(self, sql: str, *, max_rows: int = 200) -> EvidenceItem:
        if not self.workspace.warehouse_path.exists():
            raise FileNotFoundError("episode warehouse is missing; reset with build=True")
        contract_limit = int(self.contract["scope"]["max_probe_rows"])
        if max_rows <= 0 or max_rows > contract_limit:
            raise ValueError(f"max_rows must be between 1 and {contract_limit}")
        try:
            tree = sqlglot.parse_one(sql, read="duckdb")
        except sqlglot.errors.ParseError as exc:
            raise ValueError(f"invalid SQL: {exc}") from exc
        forbidden = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Command)
        if isinstance(tree, forbidden) or any(tree.find_all(*forbidden)):
            raise ValueError("only read-only SELECT queries are allowed")
        if not isinstance(tree, (exp.Select, exp.Union, exp.Subquery)):
            raise ValueError("only read-only SELECT queries are allowed")
        bounded_sql = f"select * from ({tree.sql(dialect='duckdb')}) as raw_query limit {max_rows}"
        # External access is off so SQL cannot read files (for example the episode
        # manifest or workspace labels) through DuckDB's file readers.
        with duckdb.connect(
            str(self.workspace.warehouse_path), read_only=True, config=DUCKDB_CONFIG
        ) as connection:
            cursor = connection.execute(bounded_sql)
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
        content = {
            "sql": tree.sql(dialect="duckdb"),
            "columns": columns,
            "rows": rows,
            "max_rows": max_rows,
            "at_limit": len(rows) == max_rows,
        }
        return self._record("raw_query", None, self.workspace.warehouse_path, content)

    @staticmethod
    def _manifest(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError("dbt manifest is missing; reset the episode with build=True")
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _node_entry_by_name(manifest: dict[str, Any], asset: str) -> tuple[str, dict[str, Any]]:
        candidates = []
        for collection in (manifest.get("nodes", {}), manifest.get("sources", {})):
            candidates.extend((node_id, node) for node_id, node in collection.items() if node.get("name") == asset)
        if len(candidates) != 1:
            raise KeyError(f"expected one manifest node named {asset}, found {len(candidates)}")
        return candidates[0]

    @classmethod
    def _node_by_name(cls, manifest: dict[str, Any], asset: str) -> dict[str, Any]:
        return cls._node_entry_by_name(manifest, asset)[1]


def guard_tools(store: EvidenceStore, tools: list[ToolSpec]) -> list[ToolSpec]:
    """Route every tool failure message through the store's path redaction."""

    return [replace(tool, handler=store.guarded(tool.handler)) for tool in tools]


def evidence_tools(store: EvidenceStore) -> list[ToolSpec]:
    asset = {"type": "string", "minLength": 1}
    return guard_tools(store, [
        ToolSpec(
            "get_catalog_metadata",
            "Get merged catalog metadata for one asset.",
            _object_schema({"asset": asset}, ["asset"]),
            lambda asset: store.catalog_metadata(asset).to_dict(),
        ),
        ToolSpec(
            "get_dbt_schema",
            "Get dbt schema documentation and tests for one model.",
            _object_schema({"asset": asset}, ["asset"]),
            lambda asset: store.dbt_schema(asset).to_dict(),
        ),
        ToolSpec(
            "get_model_sql",
            "Get the defining SQL for one model.",
            _object_schema({"asset": asset}, ["asset"]),
            lambda asset: store.model_sql(asset).to_dict(),
        ),
        ToolSpec(
            "get_sql_facts",
            "Parse technical sources, filters, joins, aggregates, and grouping from a model.",
            _object_schema({"asset": asset}, ["asset"]),
            lambda asset: store.sql_facts(asset).to_dict(),
        ),
        ToolSpec(
            "get_manifest_node",
            "Get one dbt manifest node.",
            _object_schema({"asset": asset}, ["asset"]),
            lambda asset: store.manifest_node(asset).to_dict(),
        ),
        ToolSpec(
            "get_lineage",
            "Get bounded upstream/downstream dbt lineage.",
            _object_schema(
                {
                    "asset": asset,
                    "direction": {"enum": ["upstream", "downstream", "both"]},
                    "max_hops": {"type": "integer", "minimum": 0, "maximum": 2},
                },
                ["asset", "direction", "max_hops"],
            ),
            lambda asset, direction, max_hops: store.lineage(
                asset,
                direction=direction,
                max_hops=max_hops,
            ).to_dict(),
        ),
        ToolSpec(
            "profile_model",
            "Run a bounded read-only profile for selected model columns.",
            _object_schema(
                {
                    "asset": asset,
                    "columns": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                },
                ["asset", "columns"],
            ),
            lambda asset, columns: store.profile_model(asset, columns=columns or None).to_dict(),
        ),
        ToolSpec(
            "get_change_diff",
            "Get the proposed repository change for this episode.",
            _object_schema({}, []),
            lambda: store.change_diff().to_dict(),
        ),
        ToolSpec(
            "read_project_file",
            "Read one bounded text file inside the episode project.",
            _object_schema({"relative_path": {"type": "string", "minLength": 1}}, ["relative_path"]),
            lambda relative_path: store.project_file(relative_path).to_dict(),
        ),
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect episode evidence")
    parser.add_argument("episode_id")
    parser.add_argument("asset")
    parser.add_argument(
        "--kind",
        choices=["catalog", "schema", "sql", "lineage", "profile", "diff"],
        default="sql",
    )
    args = parser.parse_args(argv)
    workspace = reset_episode(args.episode_id, build=args.kind in {"lineage", "profile"})
    store = EvidenceStore(workspace)
    actions = {
        "catalog": lambda: store.catalog_metadata(args.asset),
        "schema": lambda: store.dbt_schema(args.asset),
        "sql": lambda: store.sql_facts(args.asset),
        "lineage": lambda: store.lineage(args.asset),
        "profile": lambda: store.profile_model(args.asset),
        "diff": store.change_diff,
    }
    print(json.dumps(actions[args.kind]().to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

