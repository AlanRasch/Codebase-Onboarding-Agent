"""Find named definitions (classes, functions, types) in each file.

Python is read with the real parser (ast), so docstrings are available.
Other languages use simple, well-tested patterns. They find most top-level
definitions but are not a full parser.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from .scanner import SourceFile


@dataclass
class Symbol:
    name: str
    kind: str        # function, method, class or type
    file: str
    line: int        # 1-based
    doc: str = ""    # first line of the docstring, if any


JS_PATTERNS = [
    (r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)", "function"),
    (r"^\s*(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_$][\w$]*)", "class"),
    (r"^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(", "function"),
]
JAVA_PATTERNS = [
    (r"^\s*(?:(?:public|private|protected|static|final|abstract|sealed)\s+)*(?:class|interface|enum|record)\s+(\w+)", "class"),
]
PATTERNS = {
    "JavaScript": JS_PATTERNS,
    "TypeScript": JS_PATTERNS,
    "Java": JAVA_PATTERNS,
    "Kotlin": JAVA_PATTERNS + [
        (r"^\s*(?:(?:private|internal|public|suspend)\s+)*fun\s+(\w+)", "function"),
    ],
    "Go": [
        (r"^func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)", "function"),
        (r"^type\s+([A-Za-z_]\w*)\s+(?:struct|interface)", "type"),
    ],
    "Rust": [
        (r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+(\w+)", "function"),
        (r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:struct|enum|trait)\s+(\w+)", "type"),
    ],
    "Ruby": [
        (r"^\s*def\s+([\w?!]+)", "function"),
        (r"^\s*(?:class|module)\s+(\w+)", "class"),
    ],
}
COMPILED = {lang: [(re.compile(p), kind) for p, kind in pats] for lang, pats in PATTERNS.items()}


def _first_line(doc: str | None) -> str:
    if not doc:
        return ""
    lines = doc.strip().splitlines()
    return lines[0].strip() if lines else ""


def _python_symbols(f: SourceFile) -> list[Symbol]:
    try:
        tree = ast.parse(f.text)
    except SyntaxError:
        return []
    found: list[Symbol] = []
    funcs = (ast.FunctionDef, ast.AsyncFunctionDef)
    for node in tree.body:
        if isinstance(node, funcs):
            found.append(Symbol(node.name, "function", f.path, node.lineno, _first_line(ast.get_docstring(node))))
        elif isinstance(node, ast.ClassDef):
            found.append(Symbol(node.name, "class", f.path, node.lineno, _first_line(ast.get_docstring(node))))
            for item in node.body:
                if isinstance(item, funcs):
                    found.append(Symbol(f"{node.name}.{item.name}", "method", f.path, item.lineno,
                                        _first_line(ast.get_docstring(item))))
    return found


def _regex_symbols(f: SourceFile, patterns) -> list[Symbol]:
    found: list[Symbol] = []
    for number, line in enumerate(f.text.splitlines(), start=1):
        for pattern, kind in patterns:
            match = pattern.match(line)
            if match:
                found.append(Symbol(match.group(1), kind, f.path, number))
                break  # one definition per line
    return found


def extract_symbols(files: list[SourceFile]) -> list[Symbol]:
    symbols: list[Symbol] = []
    for f in files:
        if f.language == "Python":
            symbols.extend(_python_symbols(f))
        elif f.language in COMPILED:
            symbols.extend(_regex_symbols(f, COMPILED[f.language]))
    return symbols
