"""Build a high-level overview of a repository: languages, entry points, how to run it,
dependencies, tests, documentation and the modules that others depend on most."""

from __future__ import annotations

import ast
import json
import re
from collections import Counter
from dataclasses import dataclass, field

from .scanner import SourceFile

ENTRY_FILES = {
    "main.py": "conventional Python entry point",
    "app.py": "conventional application entry point",
    "manage.py": "Django management script",
    "__main__.py": "runs when the package is executed with python -m",
    "server.py": "server entry point",
    "cli.py": "command-line entry point",
    "index.js": "JavaScript entry point",
    "index.ts": "TypeScript entry point",
    "server.js": "Node server entry point",
    "app.js": "Node application entry point",
    "main.go": "Go program entry point",
    "main.rs": "Rust program entry point",
    "Program.cs": "C# program entry point",
    "Main.java": "Java program entry point",
}


MAIN_GUARD = re.compile(r"^if __name__ == ['\"]__main__['\"]\s*:", re.M)


@dataclass
class Overview:
    name: str
    files: int = 0
    lines: int = 0
    languages: dict[str, int] = field(default_factory=dict)        # language -> lines
    top_dirs: dict[str, int] = field(default_factory=dict)         # folder -> files
    entry_points: list[tuple[str, str]] = field(default_factory=list)   # (path, reason)
    commands: list[tuple[str, str]] = field(default_factory=list)       # (command, source file)
    dependencies: dict[str, list[str]] = field(default_factory=dict)    # manifest -> packages
    tests: list[str] = field(default_factory=list)
    docs: list[str] = field(default_factory=list)
    hot_modules: list[tuple[str, int]] = field(default_factory=list)    # (file, times imported)


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def _is_test(path: str) -> bool:
    parts = path.lower().split("/")
    name = parts[-1]
    in_test_folder = any(p in ("test", "tests", "__tests__", "spec") for p in parts[:-1])
    return in_test_folder or name.startswith("test_") or bool(re.search(r"(_test|\.test|\.spec)\.\w+$", name))


def _is_doc(path: str) -> bool:
    name = _basename(path).lower()
    if name.startswith(("readme", "contributing", "changelog", "architecture", "install")):
        return True
    return path.lower().startswith("docs/") and path.lower().endswith(".md")


def python_imports(text: str) -> list[str]:
    """Absolute module names imported by a Python file (relative imports are skipped)."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.append(node.module)
    return modules


def _module_name(path: str) -> str:
    parts = path[:-3].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _entry_points(files: list[SourceFile]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for f in files:
        if _is_test(f.path):
            continue
        base = _basename(f.path)
        if base == "Dockerfile":
            found.append((f.path, "container image build"))
        elif base in ENTRY_FILES:
            found.append((f.path, ENTRY_FILES[base]))
        elif f.language == "Python" and MAIN_GUARD.search(f.text):
            found.append((f.path, "runs when executed directly"))
    return found[:15]


def _toml_section(text: str, name: str) -> str:
    match = re.search(rf"^\[{re.escape(name)}\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
    return match.group(1) if match else ""


def _commands(files: list[SourceFile]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for f in files:
        base = _basename(f.path)
        if base == "package.json":
            try:
                scripts = json.loads(f.text).get("scripts") or {}
            except (json.JSONDecodeError, AttributeError):
                scripts = {}
            found.extend((f"npm run {name}", f.path) for name in scripts)
        elif base == "Makefile":
            targets = re.findall(r"^([A-Za-z][\w-]*)\s*:", f.text, re.M)
            found.extend((f"make {t}", f.path) for t in targets[:10])
        elif base == "pyproject.toml":
            section = _toml_section(f.text, "project.scripts")
            found.extend((m.group(1), f.path) for m in re.finditer(r'^([\w.-]+)\s*=\s*"', section, re.M))
    return found[:20]


def _dependencies(files: list[SourceFile]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for f in files:
        base = _basename(f.path)
        names: list[str] = []
        if re.match(r"requirements.*\.txt$", base):
            for line in f.text.splitlines():
                match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9_.\-]*)", line)
                if match and not line.lstrip().startswith("#"):
                    names.append(match.group(1))
        elif base == "package.json":
            try:
                data = json.loads(f.text)
                names = list((data.get("dependencies") or {}).keys()) + list((data.get("devDependencies") or {}).keys())
            except (json.JSONDecodeError, AttributeError):
                names = []
        elif base == "go.mod":
            names = re.findall(r"^\s*(?:require\s+)?([\w./\-]+)\s+v\d", f.text, re.M)
        elif base == "Cargo.toml":
            names = re.findall(r"^([\w-]+)\s*=", _toml_section(f.text, "dependencies"), re.M)
        elif base == "pyproject.toml":
            match = re.search(r"dependencies\s*=\s*\[(.*?)\]", _toml_section(f.text, "project"), re.S)
            if match:
                names = re.findall(r'"\s*([A-Za-z0-9][\w.\-]*)', match.group(1))
        if names:
            result[f.path] = names
    return result


def _hot_modules(files: list[SourceFile]) -> list[tuple[str, int]]:
    python_files = [f for f in files if f.language == "Python"]
    module_to_file = {_module_name(f.path): f.path for f in python_files}
    counts: Counter[str] = Counter()
    for f in python_files:
        for imported in python_imports(f.text):
            candidate = imported
            while candidate:
                if candidate in module_to_file:
                    if module_to_file[candidate] != f.path:
                        counts[module_to_file[candidate]] += 1
                    break
                candidate = candidate.rsplit(".", 1)[0] if "." in candidate else ""
    return counts.most_common(8)


def analyze(name: str, files: list[SourceFile]) -> Overview:
    languages: Counter[str] = Counter()
    top_dirs: Counter[str] = Counter()
    total_lines = 0
    for f in files:
        lines = len(f.text.splitlines())
        total_lines += lines
        languages[f.language] += lines
        top = f.path.split("/")[0] if "/" in f.path else "(root)"
        top_dirs[top] += 1
    return Overview(
        name=name,
        files=len(files),
        lines=total_lines,
        languages=dict(languages.most_common()),
        top_dirs=dict(top_dirs.most_common()),
        entry_points=_entry_points(files),
        commands=_commands(files),
        dependencies=_dependencies(files),
        tests=[f.path for f in files if _is_test(f.path)],
        docs=[f.path for f in files if _is_doc(f.path)],
        hot_modules=_hot_modules(files),
    )
