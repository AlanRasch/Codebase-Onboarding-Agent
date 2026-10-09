"""Answer questions about the code.

With an API key, Claude writes an answer based only on the most relevant code excerpts,
citing file and line numbers. Without a key, the agent lists where to look instead.
"""

from __future__ import annotations

from .index import CodeIndex, tokenize

SYSTEM_PROMPT = (
    "You help a developer who is new to this codebase. Answer ONLY from the code excerpts provided. "
    "Cite each claim as path:line, for example src/app.py:12. If the excerpts do not contain the answer, "
    "say so and suggest which file to read next. Use plain language and keep the answer short."
)


def answer(question: str, index: CodeIndex, api_key: str | None = None, model: str = "claude-sonnet-5-5") -> str:
    hits = index.search(question, k=6)
    if not hits:
        return ("I could not find matching code. Try other words, such as a feature name, "
                "a function name or a file name.")
    if api_key:
        return _ask_claude(question, hits, api_key, model)
    return _offline(question, index, hits)


def _excerpts(hits) -> str:
    return "\n\n".join(f"[{c.file}:{c.start}-{c.end}]\n{c.text}" for _, c in hits)


def _ask_claude(question, hits, api_key: str, model: str) -> str:
    import anthropic  # imported here so offline use does not need the SDK

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=1200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Question: {question}\n\nCode excerpts:\n{_excerpts(hits)}"}],
    )
    return "\n".join(block.text for block in message.content if block.type == "text").strip()


def _offline(question: str, index: CodeIndex, hits) -> str:
    lines = ["Most relevant code (set ANTHROPIC_API_KEY for a written answer):"]
    for _, chunk in hits:
        defined = f" - defines {', '.join(chunk.symbols[:5])}" if chunk.symbols else ""
        lines.append(f"- {chunk.file}:{chunk.start}-{chunk.end}{defined}")

    terms = set(tokenize(question))
    matches = [s for s in index.symbols if any(t in s.name.lower() for t in terms)][:8]
    if matches:
        lines += ["", "Matching definitions:"]
        for s in matches:
            note = f": {s.doc}" if s.doc else ""
            lines.append(f"- {s.name} ({s.kind}) at {s.file}:{s.line}{note}")
    return "\n".join(lines)
