"""Find the source files in a repository.

Skips dependency folders, build output, version-control data and binary files,
so the analysis focuses on code that people actually read and change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

IGNORED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", "target", ".next", ".nuxt", "vendor", ".tox", ".mypy_cache",
    ".pytest_cache", ".idea", ".vscode", ".onboarding", "coverage", ".gradle", "out",
}
MAX_FILE_BYTES = 300_000   # larger files are usually generated or data
MAX_FILES = 5_000

LANGUAGES = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".go": "Go", ".rs": "Rust",
    ".java": "Java", ".kt": "Kotlin", ".rb": "Ruby", ".php": "PHP", ".cs": "C#",
    ".c": "C", ".h": "C", ".cpp": "C++", ".hpp": "C++", ".swift": "Swift",
    ".sh": "Shell", ".sql": "SQL", ".html": "HTML", ".css": "CSS",
    ".md": "Markdown", ".yml": "YAML", ".yaml": "YAML", ".toml": "TOML", ".json": "JSON",
}
NAMED_FILES = {"Dockerfile": "Docker", "Makefile": "Make", "go.mod": "Go modules"}


@dataclass
class SourceFile:
    path: str        # relative to the repository root, always with forward slashes
    language: str
    text: str


def language_of(name: str) -> str | None:
    if name in NAMED_FILES:
        return NAMED_FILES[name]
    if name.startswith("requirements") and name.endswith(".txt"):
        return "Requirements"  # pip dependency lists, e.g. requirements-dev.txt
    return LANGUAGES.get(Path(name).suffix.lower())


def scan_repo(root: Path) -> list[SourceFile]:
    root = Path(root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"'{root}' is not a folder")

    found: list[SourceFile] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS)
        for name in sorted(filenames):
            language = language_of(name)
            if language is None:
                continue
            path = Path(dirpath) / name
            if path.is_symlink():
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size == 0 or size > MAX_FILE_BYTES:
                continue
            data = path.read_bytes()
            if b"\0" in data[:4096]:  # binary file
                continue
            found.append(SourceFile(
                path=path.relative_to(root).as_posix(),
                language=language,
                text=data.decode("utf-8", errors="replace"),
            ))
            if len(found) >= MAX_FILES:
                return found
    return found
