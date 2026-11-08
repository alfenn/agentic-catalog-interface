"""Build the midway report: charts -> report.md generated regions -> report.tex -> report.pdf.

Run from anywhere with ``make report`` (or
``uv run --group report python writeups/midway_report/build_report.py --results <run>``).

report.md is the only file to edit. This script
1. regenerates figures/ and the results table/summary from ``<run>/summary.json``
   (via make_figures.py) and writes them into report.md's generated regions;
2. converts report.md to report.tex with pandoc (pypandoc-binary) and the
   iclr_pandoc.latex template, using natbib citations from references.bib;
3. builds report.pdf with latexmk in a temporary directory (so no LaTeX byproducts
   are left here) and prints the body and total page counts.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pypandoc

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True  # keep __pycache__ out of the report folder
sys.path.insert(0, str(HERE))
import make_figures  # noqa: E402

DEFAULT_RESULTS = make_figures.REPO_ROOT / "experiments/results/midpoint_v1_static"
TEX_HEADER = """\
% GENERATED FILE -- DO NOT EDIT. Edit report.md and run `make report` from the
% repository root (writeups/midway_report/build_report.py), which regenerates
% this file, the figures, and report.pdf. Template: iclr_pandoc.latex.
"""
BYPRODUCTS = [".synctex(busy)", ".aux", ".bbl", ".blg", ".log", ".out", ".fls", ".fdb_latexmk", ".synctex.gz", ".run.xml", ".bcf"]


def page_of(aux: str, label: str) -> int:
    match = re.search(r"\\newlabel\{" + re.escape(label) + r"\}\{\{[^}]*\}\{(\d+)\}", aux)
    if not match:
        raise RuntimeError(f"label {label!r} not found in report.aux")
    return int(match.group(1))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the midway report PDF")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS, help="results folder with summary.json")
    args = parser.parse_args(argv)

    report_md = HERE / "report.md"
    make_figures.main([str(args.results), "--out", str(HERE / "figures"), "--update-report", str(report_md)])

    tex = pypandoc.convert_file(
        str(report_md),
        "latex",
        format="markdown",
        extra_args=[
            "--standalone",
            f"--template={HERE / 'iclr_pandoc.latex'}",
            "--natbib",
            "--top-level-division=section",
            "--wrap=preserve",
            "--columns=200",  # keep pipe tables at natural width instead of wrapped p{} columns
        ],
    )
    (HERE / "report.tex").write_text(TEX_HEADER + tex, encoding="utf-8")

    # Build in a private temporary directory: no byproducts land here, and an editor
    # that auto-compiles report.tex cannot collide with this build.
    with tempfile.TemporaryDirectory(prefix="midway_report_") as build_dir:
        proc = subprocess.run(
            ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", f"-outdir={build_dir}", "report.tex"],
            cwd=HERE,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            sys.stdout.write(proc.stdout[-4000:])
            sys.stderr.write(proc.stderr[-4000:])
            raise SystemExit(f"latexmk failed (exit {proc.returncode}); see output above")
        aux = (Path(build_dir) / "report.aux").read_text(encoding="utf-8")
        shutil.copy2(Path(build_dir) / "report.pdf", HERE / "report.pdf")
    body, total = page_of(aux, "bodyend"), page_of(aux, "reportlastpage")
    print(f"report.pdf: body (title through Timeline) = {body} pages; total = {total} pages")
    clean_byproducts()
    return 0


def clean_byproducts() -> None:
    for suffix in BYPRODUCTS:
        (HERE / f"report{suffix}").unlink(missing_ok=True)
    for stray in HERE.glob("pdflatex*.fls"):
        stray.unlink()
    shutil.rmtree(HERE / "__pycache__", ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
