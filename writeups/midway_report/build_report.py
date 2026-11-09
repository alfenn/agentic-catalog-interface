"""Build the midway report: charts -> report.md generated regions -> report.tex -> report.pdf,
plus the separate appendix: appendix.md -> appendix.tex -> appendix.pdf.

Run from anywhere with ``make report`` (or
``uv run --group report python writeups/midway_report/build_report.py --results <run>``).

report.md and appendix.md are the only files to edit. This script
1. regenerates the architecture figure and the results table (via make_figures.py)
   from the steward pilot ``--results`` and the Codex baseline ``--codex-results``,
   and writes the table into report.md's generated region;
2. converts report.md and appendix.md to report.tex and appendix.tex with pandoc
   (pypandoc-binary) and the iclr_pandoc.latex template, using natbib citations from
   references.bib;
3. builds report.pdf and appendix.pdf with latexmk in a temporary directory (so no
   LaTeX byproducts are left here) and prints the page where the report's references
   end and each document's total page count.
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

DEFAULT_RESULTS = make_figures.REPO_ROOT / "experiments/results/midpoint_v1_2_pilot"
TEX_HEADER = """\
% GENERATED FILE -- DO NOT EDIT. Edit {source} and run `make report` from the
% repository root (writeups/midway_report/build_report.py), which regenerates
% this file and {stem}.pdf. Template: iclr_pandoc.latex.
"""
BYPRODUCTS = [".synctex(busy)", ".aux", ".bbl", ".blg", ".log", ".out", ".fls", ".fdb_latexmk", ".synctex.gz", ".run.xml", ".bcf"]


def page_of(aux: str, label: str) -> int:
    match = re.search(r"\\newlabel\{" + re.escape(label) + r"\}\{\{[^}]*\}\{(\d+)\}", aux)
    if not match:
        raise RuntimeError(f"label {label!r} not found in the LaTeX aux file")
    return int(match.group(1))


def build_document(stem: str) -> str:
    """Convert <stem>.md to <stem>.tex and <stem>.pdf; return the LaTeX aux file's text."""

    tex = pypandoc.convert_file(
        str(HERE / f"{stem}.md"),
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
    (HERE / f"{stem}.tex").write_text(TEX_HEADER.format(source=f"{stem}.md", stem=stem) + tex, encoding="utf-8")

    # Build from a private copy of the sources: no byproducts land here, and an editor
    # that auto-compiles the .tex file in place (writing its own .aux file here) cannot
    # feed a half-written aux file to this build's bibtex run.
    with tempfile.TemporaryDirectory(prefix="midway_report_") as build_dir:
        for name in [f"{stem}.tex", "references.bib", "iclr2025_conference.sty", "iclr2025_conference.bst"]:
            shutil.copy2(HERE / name, Path(build_dir) / name)
        shutil.copytree(HERE / "figures", Path(build_dir) / "figures")
        proc = subprocess.run(
            ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", f"{stem}.tex"],
            cwd=build_dir,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            sys.stdout.write(proc.stdout[-4000:])
            sys.stderr.write(proc.stderr[-4000:])
            raise SystemExit(f"latexmk failed for {stem}.tex (exit {proc.returncode}); see output above")
        aux = (Path(build_dir) / f"{stem}.aux").read_text(encoding="utf-8")
        shutil.copy2(Path(build_dir) / f"{stem}.pdf", HERE / f"{stem}.pdf")
    return aux


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the midway report and appendix PDFs")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS, help="steward pilot results folder")
    parser.add_argument("--codex-results", type=Path, default=make_figures.DEFAULT_CODEX_RESULTS,
                        help="Codex baseline results folder")
    args = parser.parse_args(argv)

    report_md = HERE / "report.md"
    make_figures.main([str(args.results), "--codex-results", str(args.codex_results), "--out", str(HERE / "figures"),
                       "--update-report", str(report_md)])

    aux = build_document("report")
    references, total = page_of(aux, "referencesend"), page_of(aux, "reportlastpage")
    print(f"report.pdf: title through references = {references} pages; total = {total} pages")
    appendix_pages = page_of(build_document("appendix"), "reportlastpage")
    print(f"appendix.pdf: {appendix_pages} pages")
    clean_byproducts()
    return 0


def clean_byproducts() -> None:
    for stem in ("report", "appendix"):
        for suffix in BYPRODUCTS:
            (HERE / f"{stem}{suffix}").unlink(missing_ok=True)
    for stray in HERE.glob("pdflatex*.fls"):
        stray.unlink()
    shutil.rmtree(HERE / "__pycache__", ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
