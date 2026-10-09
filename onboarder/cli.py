"""Command-line interface:  onboard <command> <repository> ..."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analyzer import analyze
from .config import Settings
from .guide import make_guide
from .index import CodeIndex
from .qa import answer
from .scanner import scan_repo
from .symbols import extract_symbols


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="onboard", description="Explain an unfamiliar codebase to a new developer.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="Summarise a repository: languages, entry points, how to run it")
    s.add_argument("repo", nargs="?", default=".")

    i = sub.add_parser("index", help="Build the search index and save it to .onboarding/index.json")
    i.add_argument("repo", nargs="?", default=".")

    a = sub.add_parser("ask", help="Ask a question about the code")
    a.add_argument("question")
    a.add_argument("--repo", default=".", help="repository folder (default: current folder)")

    g = sub.add_parser("guide", help="Write an ONBOARDING.md guide for the repository")
    g.add_argument("repo", nargs="?", default=".")
    g.add_argument("-o", "--output", help="file to write (default: ONBOARDING.md in the repository)")

    f = sub.add_parser("find", help="Find classes and functions by name")
    f.add_argument("name")
    f.add_argument("--repo", default=".")
    return p


def _load(repo: str):
    root = Path(repo).resolve()
    files = scan_repo(root)
    symbols = extract_symbols(files)
    return root, files, symbols


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    try:
        return dispatch(args, settings)
    except (OSError, ValueError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print()
        return 130


def dispatch(args, settings: Settings) -> int:
    if args.cmd == "scan":
        root, files, symbols = _load(args.repo)
        ov = analyze(root.name, files)
        print(f"Repository: {ov.name}")
        print(f"Files: {ov.files}   Lines: {ov.lines:,}   Definitions: {len(symbols)}   Tests: {len(ov.tests)}")
        print("Languages: " + ", ".join(f"{k} ({v:,} lines)" for k, v in ov.languages.items()))
        print("Entry points:")
        for path, reason in ov.entry_points or [("none found", "")]:
            print(f"  {path}  {reason}".rstrip())
        print("How to run:")
        for cmd, source in ov.commands or [("none found", "")]:
            print(f"  {cmd}  {f'({source})' if source else ''}".rstrip())

    elif args.cmd == "index":
        root, files, symbols = _load(args.repo)
        index = CodeIndex(files, symbols)
        target = root / ".onboarding" / "index.json"
        index.save(target)
        print(f"Indexed {len(files)} files, {len(symbols)} definitions, {len(index.chunks)} chunks.")
        print(f"Saved to {target}")

    elif args.cmd == "ask":
        root, files, symbols = _load(args.repo)
        index = CodeIndex(files, symbols)
        print(answer(args.question, index, settings.api_key, settings.model))

    elif args.cmd == "guide":
        root, files, symbols = _load(args.repo)
        ov = analyze(root.name, files)
        target = Path(args.output) if args.output else root / "ONBOARDING.md"
        target.write_text(make_guide(ov, symbols), encoding="utf-8")
        print(f"Guide written to {target}")

    elif args.cmd == "find":
        _, _, symbols = _load(args.repo)
        matches = CodeIndex([], symbols).find_symbols(args.name)
        if not matches:
            print(f"No definitions match '{args.name}'.")
        for s in matches:
            note = f"  - {s.doc}" if s.doc else ""
            print(f"{s.name} ({s.kind})  {s.file}:{s.line}{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
