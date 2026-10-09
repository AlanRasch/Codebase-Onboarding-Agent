"""Offline tests. No API key needed. Each test builds a small sample repository in a temp folder."""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from onboarder.analyzer import analyze, python_imports  # noqa: E402
from onboarder.guide import make_guide  # noqa: E402
from onboarder.index import CodeIndex, tokenize  # noqa: E402
from onboarder.qa import answer  # noqa: E402
from onboarder.scanner import scan_repo  # noqa: E402
from onboarder.symbols import extract_symbols  # noqa: E402

FILES = {
    "README.md": "# Shop API\n\nA small shop backend. Start it with python app.py.\n",
    "app.py": '"""Shop API entry point."""\n'
              "from shop.orders import place_order\n\n"
              "def main():\n    \"\"\"Start the server.\"\"\"\n    print(place_order(1))\n\n"
              'if __name__ == "__main__":\n    main()\n',
    "shop/__init__.py": "",
    "shop/orders.py": "from shop.payments import charge\n\n"
                      "class OrderService:\n    \"\"\"Creates and tracks orders.\"\"\"\n"
                      "    def create(self, item):\n        return charge(item)\n\n"
                      "def place_order(item):\n    \"\"\"Place an order and charge the customer.\"\"\"\n"
                      "    return charge(item)\n",
    "shop/payments.py": 'def charge(amount):\n    """Charge a payment card."""\n    return amount * 2\n',
    "tests/test_orders.py": "from shop.orders import place_order\n\n"
                            "def test_place_order():\n    assert place_order(2) == 4\n",
    "web/src/cart.js": "export function addToCart(item) { return item; }\nexport class Cart {}\n",
    "package.json": '{"name": "shop-web", "scripts": {"start": "node web/src/cart.js", "test": "jest"}, '
                    '"dependencies": {"express": "^4.0.0"}}',
    "requirements.txt": "requests==2.31.0\n# a comment\n",
    "node_modules/junk/index.js": "function junk() {}\n",
    "blob.py": "print('binary')\x00\x00\x00\n",
}


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "shop"
    for rel, text in FILES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def loaded(repo):
    files = scan_repo(repo)
    symbols = extract_symbols(files)
    return repo, files, symbols


# ---------- scanning ----------
def test_scan_skips_dependencies_and_binary_files(loaded):
    _, files, _ = loaded
    paths = {f.path for f in files}
    assert "app.py" in paths and "web/src/cart.js" in paths
    assert not any(p.startswith("node_modules") for p in paths)
    assert "blob.py" not in paths


# ---------- symbols ----------
def test_python_symbols_include_methods_and_docstrings(loaded):
    _, _, symbols = loaded
    by_name = {s.name: s for s in symbols}
    assert by_name["place_order"].kind == "function"
    assert by_name["place_order"].doc == "Place an order and charge the customer."
    assert by_name["OrderService.create"].kind == "method"
    assert by_name["OrderService"].file == "shop/orders.py"


def test_javascript_symbols_found_by_pattern(loaded):
    _, _, symbols = loaded
    names = {s.name for s in symbols if s.file == "web/src/cart.js"}
    assert {"addToCart", "Cart"} <= names


# ---------- analysis ----------
def test_overview_finds_entry_points_commands_and_dependencies(loaded):
    repo, files, _ = loaded
    ov = analyze(repo.name, files)
    assert any(path == "app.py" for path, _ in ov.entry_points)
    commands = {c for c, _ in ov.commands}
    assert {"npm run start", "npm run test"} <= commands
    assert "requests" in ov.dependencies["requirements.txt"]
    assert "express" in ov.dependencies["package.json"]
    assert "tests/test_orders.py" in ov.tests
    assert "README.md" in ov.docs


def test_hot_modules_show_what_others_depend_on(loaded):
    repo, files, _ = loaded
    hot = dict(analyze(repo.name, files).hot_modules)
    assert hot.get("shop/orders.py") == 2   # imported by app.py and by tests/test_orders.py
    assert hot.get("shop/payments.py") == 1  # imported by orders.py


def test_python_imports_ignore_relative_imports():
    assert python_imports("from . import x\nimport os\nfrom shop.a import b\n") == ["os", "shop.a"]


# ---------- index and questions ----------
def test_tokenize_splits_camel_case_and_snake_case():
    assert {"parse", "http", "header"} <= set(tokenize("parseHTTPHeader"))
    assert {"place", "order"} <= set(tokenize("place_order"))


def test_search_ranks_the_right_file_first(loaded):
    _, files, symbols = loaded
    index = CodeIndex(files, symbols)
    top = index.search("how is a payment card charged", k=3)
    assert top and top[0][1].file == "shop/payments.py"


def test_offline_answer_points_to_code(loaded):
    _, files, symbols = loaded
    index = CodeIndex(files, symbols)
    text = answer("where are orders placed", index, api_key=None)
    assert "shop/orders.py" in text
    assert "ANTHROPIC_API_KEY" in text


def test_answer_when_nothing_matches(loaded):
    _, files, symbols = loaded
    index = CodeIndex(files, symbols)
    assert "could not find" in answer("quantum spaceship galaxy", index)


def test_find_symbols_by_partial_name(loaded):
    _, files, symbols = loaded
    names = {s.name for s in CodeIndex([], symbols).find_symbols("cart")}
    assert names == {"addToCart", "Cart"}


def test_index_saves_json(loaded, tmp_path):
    _, files, symbols = loaded
    target = tmp_path / ".onboarding" / "index.json"
    CodeIndex(files, symbols).save(target)
    assert target.exists() and '"chunks"' in target.read_text(encoding="utf-8")


# ---------- guide ----------
def test_guide_has_all_sections(loaded):
    repo, files, symbols = loaded
    guide = make_guide(analyze(repo.name, files), symbols)
    for heading in ("# Onboarding guide: shop", "## How to run it", "## Where to start reading",
                    "## Dependencies", "## Key definitions", "## Tests", "## First-week checklist"):
        assert heading in guide
    assert "npm run start" in guide and "requests" in guide


# ---------- project hygiene ----------
def _is_emoji(ch: str) -> bool:
    """Checks code point numbers, so this file itself contains no emoji characters."""
    cp = ord(ch)
    return (0x1F300 <= cp <= 0x1FAFF) or (0x2600 <= cp <= 0x27BF) or (0x2B00 <= cp <= 0x2BFF) or cp == 0xFE0F


def test_project_files_contain_no_emoji():
    project = Path(__file__).resolve().parent.parent
    offenders = []
    for path in project.rglob("*"):
        if not path.is_file() or any(part.startswith(".") for part in path.relative_to(project).parts):
            continue
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".zip"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(_is_emoji(ch) for ch in text):
            offenders.append(path.name)
    assert offenders == []
