"""Write an onboarding guide in Markdown from the analysis. Works offline and is repeatable."""

from __future__ import annotations

from datetime import date

from .analyzer import Overview
from .symbols import Symbol


def _cell(text: str) -> str:
    return (text or "-").replace("|", "\\|").replace("\n", " ")


def make_guide(ov: Overview, symbols: list[Symbol]) -> str:
    out: list[str] = [
        f"# Onboarding guide: {ov.name}",
        "",
        f"Generated on {date.today().isoformat()} from the code in this repository. "
        "Regenerate it after large changes.",
        "",
        "## At a glance",
        "",
        "| Measure | Value |",
        "|---|---|",
        f"| Source files | {ov.files} |",
        f"| Lines of code | {ov.lines:,} |",
        f"| Test files | {len(ov.tests)} |",
        "",
        "## Languages",
        "",
        "| Language | Lines |",
        "|---|---|",
    ]
    out += [f"| {lang} | {count:,} |" for lang, count in ov.languages.items()]

    out += ["", "## Folder layout", ""]
    out += [f"- `{folder}`: {count} file(s)" for folder, count in ov.top_dirs.items()]

    out += ["", "## How to run it", ""]
    if ov.commands:
        out += [f"- `{cmd}` (from `{source}`)" for cmd, source in ov.commands]
    else:
        out.append("No standard run command was found. Start with the entry points below and the README.")

    out += ["", "## Where to start reading", ""]
    if ov.entry_points:
        out += [f"- `{path}`: {reason}" for path, reason in ov.entry_points]
    else:
        out.append("No obvious entry point was found. Start with the README and the largest folder.")
    if ov.hot_modules:
        out += ["", "Modules that other modules depend on most (read these early):", ""]
        out += [f"- `{path}`: imported {count} time(s)" for path, count in ov.hot_modules]

    out += ["", "## Dependencies", ""]
    if ov.dependencies:
        for manifest, packages in ov.dependencies.items():
            shown = ", ".join(packages[:30]) + (" ..." if len(packages) > 30 else "")
            out.append(f"- **`{manifest}`**: {shown}")
    else:
        out.append("No dependency file was found.")

    out += ["", "## Key definitions", ""]
    main_defs = [s for s in symbols if s.kind in ("class", "function", "type")]
    main_defs.sort(key=lambda s: (s.doc == "", s.file, s.line))
    if main_defs:
        out += ["| Name | Kind | Location | Summary |", "|---|---|---|---|"]
        out += [f"| `{_cell(s.name)}` | {s.kind} | `{s.file}:{s.line}` | {_cell(s.doc)} |" for s in main_defs[:30]]
    else:
        out.append("No definitions were recognised in the supported languages.")

    out += ["", "## Tests", ""]
    if ov.tests:
        out.append(f"{len(ov.tests)} test file(s), for example:")
        out += [f"- `{path}`" for path in ov.tests[:10]]
    else:
        out.append("No test files were found. Consider adding tests before changing code.")

    out += ["", "## Documentation found", ""]
    out += [f"- `{path}`" for path in ov.docs] or ["None. Consider writing a README first."]

    out += [
        "",
        "## First-week checklist",
        "",
        "- [ ] Run the project with a command from the list above and reproduce one feature.",
        "- [ ] Read the entry point and follow one request from start to finish.",
        "- [ ] Run the tests and note anything that fails.",
        "- [ ] Read the most-imported module and its tests.",
        "- [ ] Make one small change (a comment, a log line or a test) and open a pull request.",
        "- [ ] Ask the onboarding tool about anything that is still unclear.",
    ]
    return "\n".join(out) + "\n"
