"""Generate the midway-report / demo-video charts and results table from a pilot run.

Usage (from the repository root):

    uv run --group report python writeups/midway_report/make_figures.py \
        experiments/results/<run>/ [--out writeups/midway_report/figures] \
        [--update-report writeups/midway_report/report.md] \
        [--findings-chart] [--dpi 200]

Reads ``<run>/summary.json`` (the shape written by ``catalog_steward.evaluation``)
and the episode manifest, then writes into ``--out``:

* ``success_by_category.{pdf,png}``: episode successes per condition, faceted by
  episode category (remediation / flawed change / clean control).
* ``outcome_grid.{pdf,png}``: one cell per episode x condition, labelled
  success / partial / missed / false alarm / error / pending.
* ``architecture.{pdf,png}``: the steward's implemented architecture (drawn, not
  read from the run), with the planned per-issue checks dashed.
* ``findings_vs_false_alarms.{pdf,png}`` (only with ``--findings-chart``): expected
  issues found and false alarms per condition, as two small-multiple panels.
* ``results_table.md`` and ``results_summary.md``: the Markdown table and summary
  sentence the report uses. With ``--update-report`` they are also written into
  the matching ``<!-- BEGIN GENERATED: ... -->`` regions of the report source.

Conditions listed in the run's config but absent from its records are drawn as
"pending", so the same script works on the static-only run and on the full
three-condition pilot without edits. No number is typed by hand anywhere.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import yaml  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "data/episodes/manifest.yaml"
DEFAULT_OUT = Path(__file__).resolve().parent / "figures"

CONDITION_LABELS = {"static": "Static checks", "generic": "Generic agent", "steward": "Steward"}
CATEGORIES = ["remediation", "flawed_change", "clean_control"]
CATEGORY_LABELS = {
    "remediation": "Remediation",
    "flawed_change": "Flawed change",
    "clean_control": "Clean control",
}

# Palette: the dataviz skill's validated reference instance (light mode).
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
NEUTRAL = "#f0efec"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
# Outcome = state, so it uses the reserved status palette, always with a text label.
OUTCOME_STYLE = {
    "success": ("#0ca30c", "#ffffff"),
    "partial": ("#fab219", INK),
    "missed": ("#ec835a", "#ffffff"),
    "false alarm": ("#ec835a", "#ffffff"),
    "error": ("#d03b3b", "#ffffff"),
    "pending": (NEUTRAL, MUTED),
}
GRID_GROUP_LABELS = {"remediation": "remediation", "flawed_change": "flawed change", "clean_control": "clean"}
OUTCOME_ORDER = ["success", "partial", "missed", "false alarm", "error", "pending"]


@dataclass(frozen=True)
class Cell:
    episode: str
    category: str
    condition: str
    outcome: str
    expected: int
    true_positives: int | None
    false_positives: int | None
    false_negatives: int | None
    cost: float


def load_manifest(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {episode["id"]: episode for episode in data.get("episodes", [])}


def categorize(episode_id: str, manifest: dict[str, dict[str, Any]]) -> tuple[str, int]:
    """Return (category, number of expected findings) for an episode."""
    entry = manifest.get(episode_id)
    if entry is not None:
        expected = len(entry.get("expected_findings") or [])
        if entry.get("mode") == "remediation":
            return "remediation", expected
        return ("flawed_change" if expected else "clean_control"), expected
    for prefix, category in (("rem_", "remediation"), ("change_", "flawed_change"), ("clean_", "clean_control")):
        if episode_id.startswith(prefix):
            return category, 0 if category == "clean_control" else 1
    raise ValueError(f"cannot categorize episode {episode_id!r}: not in manifest and unknown prefix")


def classify(record: dict[str, Any] | None, expected: int) -> str:
    if record is None:
        return "pending"
    result, score = record.get("result", {}), record.get("score", {})
    if result.get("status") == "error":
        return "error"
    if score.get("episode_success"):
        return "success"
    if score.get("true_positives", 0) > 0:
        return "partial"
    if expected == 0 and score.get("false_positives", 0) > 0:
        return "false alarm"
    return "missed"


def build_cells(summary: dict[str, Any], manifest: dict[str, dict[str, Any]]) -> tuple[list[str], list[str], list[Cell]]:
    config = summary.get("config", {})
    records = summary.get("records", [])
    conditions = list(config.get("conditions") or [])
    episodes = list(config.get("episodes") or [])
    for record in records:
        result = record.get("result", {})
        if result.get("condition") not in conditions:
            conditions.append(result["condition"])
        if result.get("episode_id") not in episodes:
            episodes.append(result["episode_id"])
    lookup = {(r["result"]["episode_id"], r["result"]["condition"]): r for r in records}
    cells = []
    for episode in episodes:
        category, expected = categorize(episode, manifest)
        for condition in conditions:
            record = lookup.get((episode, condition))
            score = (record or {}).get("score", {})
            outcome = classify(record, expected)
            complete = record is not None and outcome != "error"
            cells.append(
                Cell(
                    episode=episode,
                    category=category,
                    condition=condition,
                    outcome=outcome,
                    expected=expected,
                    true_positives=score.get("true_positives") if complete else (0 if record else None),
                    false_positives=score.get("false_positives") if complete else (0 if record else None),
                    # An errored run produced no scorable findings: all expected findings count as missed.
                    false_negatives=score.get("false_negatives") if complete else (expected if record else None),
                    cost=float(score.get("cost_usd", 0.0)) if record else 0.0,
                )
            )
    episodes.sort(key=lambda e: CATEGORIES.index(categorize(e, manifest)[0]))
    return conditions, episodes, cells


def condition_color(conditions: list[str], condition: str) -> str:
    # Fixed slot per condition (config order), never by rank.
    return SERIES[conditions.index(condition) % len(SERIES)]


def label(condition: str) -> str:
    return CONDITION_LABELS.get(condition, condition)


def style_axes(ax: Any) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(colors=INK_2, length=0)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_success_by_category(conditions: list[str], cells: list[Cell], out: Path, source: str) -> None:
    fig, axes = plt.subplots(1, len(CATEGORIES), figsize=(5.5, 1.75), sharey=True)
    fig.patch.set_facecolor(SURFACE)
    for ax, category in zip(axes, CATEGORIES):
        style_axes(ax)
        n = len({c.episode for c in cells if c.category == category})
        for i, condition in enumerate(conditions):
            group = [c for c in cells if c.category == category and c.condition == condition]
            if all(c.outcome == "pending" for c in group):
                ax.text(i, 0.04, "pending", ha="center", va="bottom", rotation=90, fontsize=8, color=MUTED)
                continue
            wins = sum(c.outcome == "success" for c in group)
            rate = wins / n if n else 0.0
            ax.bar(i, rate, width=0.55, color=condition_color(conditions, condition), linewidth=0)
            ax.text(i, rate + 0.03, f"{wins}/{n}", ha="center", va="bottom", fontsize=8.5, color=INK)
        ax.set_title(f"{CATEGORY_LABELS[category]} (n={n})", fontsize=9, color=INK, loc="left")
        ax.set_xticks(range(len(conditions)), [label(c).replace(" ", "\n") for c in conditions], fontsize=7.5)
        ax.set_xlim(-0.6, len(conditions) - 0.4)
        ax.set_ylim(0, 1.15)
        ax.set_yticks([0, 0.5, 1.0], ["0%", "50%", "100%"], fontsize=7.5)
    axes[0].set_ylabel("Episodes succeeded", fontsize=8, color=INK_2)
    fig.text(0.01, 0.01, f"Source: {source}", fontsize=6, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save(fig, out / "success_by_category")


def plot_outcome_grid(conditions: list[str], episodes: list[str], cells: list[Cell], out: Path, source: str) -> None:
    by_key = {(c.episode, c.condition): c for c in cells}
    rows, cols = len(episodes), len(conditions)
    fig, ax = plt.subplots(figsize=(5.5, 0.2 * rows + 0.75))
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    gap = 0.04  # surface gap between touching cells
    for r, episode in enumerate(episodes):
        for k, condition in enumerate(conditions):
            cell = by_key[(episode, condition)]
            fill, text_color = OUTCOME_STYLE[cell.outcome]
            ax.add_patch(Rectangle((k + gap, r + gap), 1 - 2 * gap, 1 - 2 * gap, color=fill, linewidth=0))
            text = cell.outcome
            if cell.outcome not in ("pending", "error") and cell.expected:
                text += f"  {cell.true_positives}/{cell.expected} found"
            elif cell.outcome != "pending" and cell.false_positives:
                text += f" ({cell.false_positives})"
            ax.text(k + 0.5, r + 0.5, text, ha="center", va="center", fontsize=7, color=text_color)
    # Category separators, with each group's name at the right edge.
    groups: list[tuple[str, int, int]] = []
    for r, episode in enumerate(episodes):
        category = by_key[(episode, conditions[0])].category
        if groups and groups[-1][0] == category:
            groups[-1] = (category, groups[-1][1], r + 1)
        else:
            if groups:
                ax.axhline(r, color=INK_2, linewidth=0.8)
            groups.append((category, r, r + 1))
    for category, start, end in groups:
        ax.text(cols + 0.06, (start + end) / 2, GRID_GROUP_LABELS[category], rotation=270,
                ha="left", va="center", fontsize=7, color=INK_2)
    ax.set_xlim(0, cols)
    ax.set_ylim(rows, 0)
    ax.set_xticks([k + 0.5 for k in range(cols)], [label(c) for c in conditions], fontsize=8, color=INK)
    ax.xaxis.tick_top()
    ax.set_yticks(
        [r + 0.5 for r in range(rows)],
        episodes,
        fontsize=6.5,
        color=INK_2,
        family="monospace",
    )
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    present = [o for o in OUTCOME_ORDER if any(c.outcome == o for c in cells)]
    handles = [Rectangle((0, 0), 1, 1, color=OUTCOME_STYLE[o][0]) for o in present]
    fig.legend(handles, present, loc="lower center", ncol=len(present), frameon=False, fontsize=7.5,
               bbox_to_anchor=(0.55, 0.0), handlelength=1.0)
    fig.text(0.01, 0.005, f"Source: {source}", fontsize=6, color=MUTED)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    save(fig, out / "outcome_grid")


PNG_DPI = 200


def plot_findings(conditions: list[str], cells: list[Cell], out: Path, source: str) -> None:
    """Expected issues found vs false alarms per condition (two panels, one axis each)."""
    run_conditions = [c for c in conditions if any(x.condition == c and x.outcome != "pending" for x in cells)]
    stats = condition_stats(run_conditions, cells)
    expected = {c: sum(x.expected for x in cells if x.condition == c) for c in run_conditions}
    panels = [
        ("Expected issues found", lambda c: stats[c]["tp"], lambda c: f"{stats[c]['tp']}/{expected[c]}"),
        ("False alarms", lambda c: stats[c]["fp"], lambda c: str(stats[c]["fp"])),
    ]
    top = max([max(expected.values(), default=1)] + [stats[c]["fp"] for c in run_conditions]) * 1.18
    fig, axes = plt.subplots(1, 2, figsize=(5.5, 2.0), sharey=True)
    fig.patch.set_facecolor(SURFACE)
    for ax, (title, value, text) in zip(axes, panels):
        style_axes(ax)
        for i, condition in enumerate(run_conditions):
            v = value(condition)
            ax.bar(i, v, width=0.55, color=condition_color(conditions, condition), linewidth=0)
            ax.text(i, v + top * 0.02, text(condition), ha="center", va="bottom", fontsize=8.5, color=INK)
        ax.set_title(title, fontsize=9, color=INK, loc="left")
        ax.set_xticks(range(len(run_conditions)), [label(c).replace(" ", "\n") for c in run_conditions],
                      fontsize=7.5)
        ax.set_xlim(-0.6, len(run_conditions) - 0.4)
        ax.set_ylim(0, top)
        ax.tick_params(axis="y", labelsize=7.5)
    axes[0].set_ylabel("Findings (all episodes)", fontsize=8, color=INK_2)
    fig.text(0.01, 0.01, f"Source: {source}", fontsize=6, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save(fig, out / "findings_vs_false_alarms")


# Architecture diagram tints: one light wash per role.
ARCH_TRIGGER = "#e9f1fb"  # blue: entry points
ARCH_CHECK = NEUTRAL  # neutral: deterministic evidence, checks, and records
ARCH_MODEL = "#fdeee7"  # orange: the language model and its plan
ARCH_OUTPUT = "#e6f5ee"  # green: action outcomes


def plot_architecture(out: Path) -> None:
    """Steward architecture as implemented in src/catalog_steward/; the one planned part is dashed."""
    width, height = 5.5, 2.46  # inches; the axes use inch coordinates, so font sizes are true point sizes
    fig = plt.figure(figsize=(width, height))
    fig.patch.set_facecolor(SURFACE)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")
    pad, line_step = 0.05, 0.128
    boxes: list[tuple[Any, list[Any]]] = []

    def box(x, y, w, h, title, lines=(), fill=ARCH_CHECK, dashed=False):
        patch = FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.04", facecolor=fill,
            edgecolor=MUTED if dashed else BASELINE, linewidth=0.8, linestyle=(0, (3, 2)) if dashed else "-",
        )
        ax.add_patch(patch)
        color = MUTED if dashed else INK
        texts = [ax.text(x + pad, y + h - pad, title, ha="left", va="top", fontsize=7.5, fontweight="bold",
                         color=color)]
        for i, line in enumerate(lines, start=1):
            texts.append(ax.text(x + pad, y + h - pad - 0.02 - line_step * i, line, ha="left", va="top",
                                 fontsize=7, color=MUTED if dashed else INK_2))
        boxes.append((patch, texts))

    def arrow(start, end, both=False):
        ax.add_patch(FancyArrowPatch(
            start, end, arrowstyle="<|-|>" if both else "-|>", mutation_scale=7, color=INK_2,
            linewidth=0.8, shrinkA=0, shrinkB=0,
        ))

    gap = 0.12
    widths = {"trigger": 0.98, "inspect": 1.18, "plan": 0.84, "validate": 0.96, "act": 1.06}
    left, x = {}, 0.0
    for name, w in widths.items():
        left[name] = x
        x += w + gap
    right = {name: left[name] + widths[name] for name in widths}
    for name, header in (("trigger", "Trigger"), ("inspect", "1 Inspect"), ("plan", "2 Plan"),
                         ("validate", "3 Validate"), ("act", "4 Act + verify")):
        ax.text(left[name], height - 0.03, header.upper(), ha="left", va="top", fontsize=7, color=MUTED,
                fontweight="bold")

    # Main band: two rows (a over b) under the stage headers; the lower band holds tools and the ledger.
    top = height - 0.2
    band = 1.6
    bottom = top - band
    row = (band - 0.06) / 2
    a_y, b_y = top - row, bottom
    a_mid, b_mid = a_y + row / 2, b_y + row / 2
    low_top = bottom - 0.1

    # Two entry points feed one shared workflow.
    box(left["trigger"], a_y, widths["trigger"], row, "Remediation", ["existing hygiene", "debt in scope"],
        fill=ARCH_TRIGGER)
    box(left["trigger"], b_y, widths["trigger"], row, "Change review", ["proposed change;", "adds its diff"],
        fill=ARCH_TRIGGER)
    join = (left["inspect"], bottom + band / 2)
    arrow((right["trigger"], a_mid), join)
    arrow((right["trigger"], b_mid), join)

    # 1 Inspect: the evidence bundle, collected without labels; tools the model may call while planning.
    box(left["inspect"], bottom, widths["inspect"], band, "Evidence bundle", [
        "catalog metadata",
        "dbt schema, manifest",
        "model SQL",
        "parsed SQL facts",
        "1-hop lineage",
        "bounded profile",
        "change diff (review)",
        "content-hashed IDs",
    ])
    tools_h = 0.5
    box(0.0, low_top - tools_h, right["plan"], tools_h, "9 read-only, schema-checked tools for planning", [
        "catalog, dbt schema, model SQL, SQL facts, manifest node,",
        "lineage (2 hops), bounded profile, diff, confined file read",
    ])

    # 2 Plan: the model loop returns a structured plan.
    box(left["plan"], b_y, widths["plan"], row, "LLM agent", ["calls tools,", "≤12 turns,", "1 repair turn"],
        fill=ARCH_MODEL)
    box(left["plan"], a_y, widths["plan"], row, "Plan (JSON)", ["≤5 findings:", "each: claim,", "evidence IDs,",
                                                               "action"], fill=ARCH_MODEL)
    arrow((right["inspect"], b_mid), (left["plan"], b_mid))
    plan_x = left["plan"] + widths["plan"] / 2
    arrow((plan_x, b_y + row), (plan_x, a_y))
    arrow((plan_x, low_top), (plan_x, b_y), both=True)

    # 3 Validate: schema and risk-aware action policy; a rejected plan goes back for one repair turn.
    box(left["validate"], bottom, widths["validate"], band, "Validator", [
        "plan schema",
        "asset in scope",
        "known issue type",
        "action class",
        "  allowed for type",
        "required evidence",
        "  kinds cited",
        "cited IDs resolve",
    ])
    arrow((right["plan"], a_mid), (left["validate"], a_mid))
    arrow((left["validate"], b_mid), (right["plan"], b_mid))

    # 4 Act + verify: route each finding by its action class.
    act_x, act_w = left["act"], widths["act"]
    small = 0.33
    patch_h = band - 2 * small - 2 * 0.04
    box(act_x, top - patch_h, act_w, patch_h, "Patch", ["override file only;", "check value = plan,", "dbt parse"],
        fill=ARCH_OUTPUT)
    box(act_x + 0.05, top - patch_h + 0.05, act_w - 0.1, 0.2, "", dashed=True)
    ax.text(act_x + 0.1, top - patch_h + 0.15, "per-issue checks", ha="left", va="center", fontsize=7,
            color=MUTED, style="italic")
    propose_y = top - patch_h - 0.04 - small
    box(act_x, propose_y, act_w, small, "Propose", ["review request"], fill=ARCH_OUTPUT)
    box(act_x, bottom, act_w, small, "Report", ["finding only"], fill=ARCH_OUTPUT)
    for mid in (top - patch_h / 2, propose_y + small / 2, bottom + small / 2):
        arrow((right["validate"], mid), (act_x, mid))

    # Every executed finding is appended to the ledger.
    ledger_x = left["validate"]
    ledger_h = 0.36
    box(ledger_x, low_top - ledger_h, width - ledger_x, ledger_h, "Append-only ledger",
        ["findings, evidence IDs, actions, checks"])
    ax.text(width, 0.0, "dashed: planned, not implemented", ha="right", va="bottom", fontsize=7, color=MUTED,
            style="italic")
    arrow((act_x + act_w / 2, bottom), (act_x + act_w / 2, low_top))

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    overflow = []
    for patch, texts in boxes:
        frame = patch.get_window_extent(renderer)
        for text in texts:
            extent = text.get_window_extent(renderer)
            if text.get_text() and (extent.x1 > frame.x1 - 2 or extent.y0 < frame.y0 + 2):
                overflow.append(text.get_text())
    if overflow:
        raise RuntimeError(f"architecture text overflows its box: {overflow}")
    save(fig, out / "architecture")


def save(fig: Any, stem: Path) -> None:
    fig.savefig(stem.with_suffix(".pdf"), facecolor=SURFACE)
    fig.savefig(stem.with_suffix(".png"), dpi=PNG_DPI, facecolor=SURFACE)
    plt.close(fig)


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}" + ("" if count == 1 else "s")


def fmt_ratio(num: int, den: int) -> str:
    return f"{num / den:.2f}" if den else "n/a"


def condition_stats(conditions: list[str], cells: list[Cell]) -> dict[str, dict[str, Any]]:
    stats = {}
    for condition in conditions:
        group = [c for c in cells if c.condition == condition]
        run = [c for c in group if c.outcome != "pending"]
        tp = sum(c.true_positives or 0 for c in run)
        fp = sum(c.false_positives or 0 for c in run)
        fn = sum(c.false_negatives or 0 for c in run)
        stats[condition] = {
            "pending": not run,
            "partial_run": bool(run) and len(run) < len(group),
            "runs": len(run),
            "episodes": len(group),
            "successes": sum(c.outcome == "success" for c in run),
            "by_category": {
                cat: (
                    sum(c.outcome == "success" for c in run if c.category == cat),
                    sum(1 for c in group if c.category == cat),
                )
                for cat in CATEGORIES
            },
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "errors": sum(c.outcome == "error" for c in run),
            "cost": sum(c.cost for c in run),
        }
    return stats


def results_table(conditions: list[str], stats: dict[str, dict[str, Any]], source: str) -> str:
    header = ["Condition", "Remed.", "Flawed", "Clean", "All", "TP/FP/FN", "Micro P/R", "Errors"]
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join([":--"] + ["--:"] * (len(header) - 1)) + "|"]
    for condition in conditions:
        s = stats[condition]
        if s["pending"]:
            row = [f"{label(condition)} (pending)"] + ["--"] * (len(header) - 1)
        else:
            row = [label(condition)]
            row += [f"{w}/{n}" for w, n in (s["by_category"][c] for c in CATEGORIES)]
            row.append(f"{s['successes']}/{s['episodes']}")
            row.append(f"{s['tp']}/{s['fp']}/{s['fn']}")
            row.append(f"{fmt_ratio(s['tp'], s['tp'] + s['fp'])}/{fmt_ratio(s['tp'], s['tp'] + s['fn'])}")
            row.append(str(s["errors"]))
        lines.append("| " + " | ".join(row) + " |")
    caption = (
        "Table: Episode successes by condition and category (remediation, flawed change, clean control), "
        "finding counts, and micro precision/recall; an errored run counts its expected findings as missed. "
        f"Source: `{source}`. {{#tbl:results}}"
    )
    return "\n".join(lines) + "\n\n" + caption + "\n"


def results_summary(conditions: list[str], stats: dict[str, dict[str, Any]]) -> str:
    parts = []
    for condition in conditions:
        s = stats[condition]
        if s["pending"]:
            parts.append(f"{label(condition)}: **pending** (not yet run).")
            continue
        partial = f" ({s['runs']} of {s['episodes']} episodes run)" if s["partial_run"] else ""
        parts.append(
            f"{label(condition)}: {s['successes']}/{s['episodes']} episode successes{partial}, "
            f"{plural(s['tp'], 'true positive')}, {plural(s['fp'], 'false positive')}, "
            f"{plural(s['fn'], 'false negative')} "
            f"(micro precision {fmt_ratio(s['tp'], s['tp'] + s['fp'])}, "
            f"micro recall {fmt_ratio(s['tp'], s['tp'] + s['fn'])}), {plural(s['errors'], 'errored run')}."
        )
    return " ".join(parts) + "\n"


def update_region(text: str, name: str, content: str) -> str:
    pattern = re.compile(
        rf"(<!-- BEGIN GENERATED: {re.escape(name)} [^\n]*-->\n).*?(<!-- END GENERATED: {re.escape(name)} -->)",
        re.DOTALL,
    )
    if not pattern.search(text):
        raise ValueError(f"report has no generated region named {name!r}")
    return pattern.sub(lambda m: m.group(1) + content + m.group(2), text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("results", type=Path, help="results folder containing summary.json")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--update-report", type=Path, help="Markdown report whose generated regions to refresh")
    parser.add_argument("--findings-chart", action="store_true",
                        help="also write findings_vs_false_alarms.{pdf,png} (used by the demo video)")
    parser.add_argument("--dpi", type=int, default=200, help="PNG resolution (default 200)")
    args = parser.parse_args(argv)
    global PNG_DPI
    PNG_DPI = args.dpi

    summary_path = args.results / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    try:
        source = summary_path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        source = summary_path.as_posix()
    manifest = load_manifest(args.manifest)
    conditions, episodes, cells = build_cells(summary, manifest)

    args.out.mkdir(parents=True, exist_ok=True)
    plot_success_by_category(conditions, cells, args.out, source)
    plot_outcome_grid(conditions, episodes, cells, args.out, source)
    plot_architecture(args.out)
    if args.findings_chart:
        plot_findings(conditions, cells, args.out, source)
    stats = condition_stats(conditions, cells)
    table = results_table(conditions, stats, source)
    sentence = results_summary(conditions, stats)
    (args.out / "results_table.md").write_text(table, encoding="utf-8")
    (args.out / "results_summary.md").write_text(sentence, encoding="utf-8")

    if args.update_report:
        text = args.update_report.read_text(encoding="utf-8")
        for name, content in (("results_summary", sentence), ("results_table", table)):
            if f"BEGIN GENERATED: {name} " in text:
                text = update_region(text, name, content)
        args.update_report.write_text(text, encoding="utf-8")
    print(f"wrote figures and tables for {len(conditions)} conditions x {len(episodes)} episodes to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
