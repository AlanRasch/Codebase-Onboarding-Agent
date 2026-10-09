# Codebase Onboarding Agent

A command-line assistant that helps a new developer understand an unfamiliar code repository quickly.

Point it at a project folder and it will:

- **Summarise the repository**: languages, folder layout, entry points, how to run it, dependencies and tests.
- **Write an onboarding guide** (`ONBOARDING.md`) that you can share with new team members. It includes a reading order, the modules that others depend on most, a table of key definitions and a first-week checklist.
- **Answer questions** such as "where are orders created?" or "how is a payment charged?". Answers point to exact files and line numbers.
- **Find definitions** by name, for example every class or function that contains "cart".

It works fully offline. If you add a Claude API key, the questions are answered in full sentences based only on the most relevant code.

---

## Contents

1. [How it works](#how-it-works)
2. [Installation](#installation)
3. [Quick start](#quick-start)
4. [Commands](#commands)
5. [Example output](#example-output)
6. [Offline mode and Claude mode](#offline-mode-and-claude-mode)
7. [Supported languages](#supported-languages)
8. [Limitations](#limitations)
9. [Privacy](#privacy)
10. [Project structure](#project-structure)
11. [Running the tests](#running-the-tests)
12. [Extending the tool](#extending-the-tool)
13. [Troubleshooting](#troubleshooting)

---

## How it works

```
 repository folder
        |
        v
  scanner.py      walks the folder, skips node_modules, build output, binaries
        |
        +--> analyzer.py   languages, entry points, run commands, dependencies,
        |                  tests, docs, most-imported Python modules
        |
        +--> symbols.py    classes, functions and methods with line numbers
        |                  (Python uses the real parser; other languages use patterns)
        |
        +--> index.py      splits files into 40-line chunks and ranks them for a question (BM25)
                 |
                 +--> qa.py       answers questions (Claude, or an offline list of locations)
                 +--> guide.py    writes ONBOARDING.md
```

Everything runs locally. The tool reads your files; it never changes them, except for the files it writes on purpose (`ONBOARDING.md` and `.onboarding/index.json`).

---

## Installation

You need **Python 3.10 or newer**.

### macOS and Linux

```bash
cd codebase-onboarder
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .          # optional: makes the `onboard` command available
```

### Windows (PowerShell)

```powershell
cd codebase-onboarder
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .          # optional: makes the `onboard` command available
```

If PowerShell blocks the activation script, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Without `pip install -e .`, run the tool with `python -m onboarder` instead of `onboard`. The examples below use `onboard`.

### Optional: Claude API key

```bash
cp .env.example .env      # Windows: copy .env.example .env
```

Open `.env` and set `ANTHROPIC_API_KEY`. Leave it empty to use offline mode.

---

## Quick start

Suppose you have just cloned a project called `shop-api`:

```bash
onboard scan ~/code/shop-api                  # overview in the terminal
onboard guide ~/code/shop-api                 # writes ~/code/shop-api/ONBOARDING.md
onboard ask "where is the checkout flow?" --repo ~/code/shop-api
onboard find Order --repo ~/code/shop-api     # every definition with "Order" in its name
```

On Windows, use paths such as `C:\code\shop-api`.

---

## Commands

| Command | What it does |
|---|---|
| `onboard scan [REPO]` | Prints the summary: size, languages, entry points, run commands |
| `onboard guide [REPO] [-o FILE]` | Writes the onboarding guide (default: `ONBOARDING.md` in the repository) |
| `onboard ask "QUESTION" [--repo REPO]` | Answers a question with file and line references |
| `onboard find NAME [--repo REPO]` | Lists classes, functions and methods whose names contain NAME |
| `onboard index [REPO]` | Saves the search index to `.onboarding/index.json` for inspection or other tools |

`REPO` defaults to the current folder.

---

## Example output

```
$ onboard scan ./shop-api
Repository: shop-api
Files: 84   Lines: 9,412   Definitions: 311   Tests: 17
Languages: Python (7,980 lines), TypeScript (1,102 lines), YAML (330 lines)
Entry points:
  app.py  conventional application entry point
  worker/main.py  conventional Python entry point
How to run:
  npm run dev  (package.json)
  make test  (Makefile)
```

```
$ onboard ask "how is a payment charged" --repo ./shop-api
Most relevant code (set ANTHROPIC_API_KEY for a written answer):
- shop/payments.py:1-40 - defines charge, refund
- shop/orders.py:1-40 - defines OrderService, OrderService.create

Matching definitions:
- charge (function) at shop/payments.py:12: Charge a payment card.
```

---

## Offline mode and Claude mode

| | Offline (no key) | Claude mode (`ANTHROPIC_API_KEY` set) |
|---|---|---|
| `scan`, `guide`, `find`, `index` | Full support | Full support |
| `ask` | Lists the most relevant code locations and matching definitions | Written answer in plain language, with file and line citations |
| Network use | None | Sends your question and the matching code excerpts to the Anthropic API |

The offline search is keyword-based. If a question uses different words from the code, try the names of functions or files you expect to see.

---

## Supported languages

| Language | Definitions found by | Imports used for "most-imported modules" |
|---|---|---|
| Python | Real parser (`ast`), with docstrings and methods | Yes |
| JavaScript, TypeScript | Pattern matching (functions, classes, arrow functions assigned to `const`) | No |
| Java, Kotlin | Pattern matching (classes, interfaces, enums, Kotlin `fun`) | No |
| Go, Rust, Ruby | Pattern matching (functions, types) | No |

Files are read for any language, but definitions are only extracted for the languages above. Run-command detection reads `package.json` scripts, `Makefile` targets and `pyproject.toml` console scripts. Dependency detection reads `requirements*.txt`, `package.json`, `pyproject.toml`, `go.mod` and `Cargo.toml`.

---

## Limitations

- **Pattern matching is not a full parser** for languages other than Python. It finds most top-level definitions but may miss some, or report a few that are not real definitions.
- **`.gitignore` is not read.** Folders that are normally ignored are skipped by a built-in list (for example `node_modules`, `venv`, `dist`, `build`, `target`). Other generated folders will be scanned.
- **Limits protect large repositories:** at most 5,000 files, and files over 300 KB are skipped.
- **Dynamic imports are not followed** (for example `importlib` or string-based plugin loading), so the "most-imported modules" list can miss some links.
- **Offline answers are search results, not explanations.** Use Claude mode for full answers.
- **The guide describes the code, not the team.** Architecture decisions, deployment steps and secrets belong in documentation written by people.

---

## Privacy

- Nothing leaves your computer in offline mode.
- In Claude mode, only your question and the matching code excerpts (about 40 lines each, up to six excerpts) are sent to the Anthropic API.
- The tool writes `.onboarding/index.json` inside the repository. Add `.onboarding/` to your `.gitignore` (the included `.gitignore` for this project already does).
- Keep `.env` out of version control. It holds your API key.

---

## Project structure

```
codebase-onboarder/
├── onboarder/
│   ├── __init__.py     version
│   ├── __main__.py     allows: python -m onboarder
│   ├── analyzer.py     overview: languages, entry points, commands, dependencies, tests, hot modules
│   ├── cli.py          the onboard commands
│   ├── config.py       settings from .env
│   ├── guide.py        writes ONBOARDING.md
│   ├── index.py        chunking, tokenising and BM25 search
│   ├── qa.py           answers questions (Claude or offline)
│   ├── scanner.py      finds source files, skips ignored folders and binaries
│   └── symbols.py      finds classes, functions and methods per language
├── tests/
│   └── test_onboarder.py   14 offline tests
├── .env.example
├── .gitignore
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## Running the tests

```bash
python -m pytest -q
```

The tests build a small sample repository in a temporary folder and check scanning, symbol extraction, analysis, search, offline answers, the guide, and a project check that no file contains emoji characters. They need no API key and make no network calls.

---

## Extending the tool

**Add a language for definitions:** add a list of `(regular expression, kind)` pairs to `PATTERNS` in `onboarder/symbols.py`. Each pattern must have exactly one group that captures the name. Add the file extension to `LANGUAGES` in `onboarder/scanner.py`.

**Add an entry-point file name:** add it to `ENTRY_FILES` in `onboarder/analyzer.py`.

**Add a dependency format or run-command source:** extend `_dependencies` or `_commands` in `onboarder/analyzer.py`, then add a test in `tests/test_onboarder.py`.

**Change the answer style:** edit `SYSTEM_PROMPT` in `onboarder/qa.py`.

---

## Troubleshooting

| Problem | What to try |
|---|---|
| `Error: ... is not a folder` | Check the path. Use quotes around paths with spaces. |
| `Entry points: none found` | The project may use an unusual layout. Read the README and the largest folder first. |
| `I could not find matching code` | Use words that appear in the code, such as a function or file name. |
| Answers are only file lists | Set `ANTHROPIC_API_KEY` in `.env`, then run the command again. |
| A generated folder appears in the results | Add its name to `IGNORED_DIRS` in `onboarder/scanner.py`. |
| `onboard: command not found` | Run `pip install -e .` in the activated environment, or use `python -m onboarder`. |
| Windows: activation script blocked | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once. |

---

**Author:** Dr. Firend Alan Rasch
**License:** MIT (or your preferred license)
