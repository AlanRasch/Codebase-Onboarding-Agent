"""A searchable index of the code, using BM25 ranking (a standard keyword-search method).

Each file is split into chunks of about 40 lines. Words in file names and definition
names count more, so a question about "payments" finds payments.py first.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .scanner import SourceFile
from .symbols import Symbol

CHUNK_LINES = 40
K1, B = 1.5, 0.75
STOP_WORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "any", "can", "has", "how", "its",
    "our", "out", "was", "who", "why", "with", "what", "where", "which", "does", "this", "that",
    "from", "into", "about", "there", "their", "they", "them", "is", "it", "of", "to", "in", "on",
    "a", "an", "be", "do", "by", "or", "at", "as", "if", "so", "me", "my", "we", "i", "does",
}


def tokenize(text: str) -> list[str]:
    """Split text into lowercase words. 'parseHTTPHeader' -> ['parse', 'http', 'header']."""
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 1 and w not in STOP_WORDS]


@dataclass
class Chunk:
    file: str
    start: int          # first line, 1-based
    end: int            # last line, 1-based
    text: str
    symbols: list[str] = field(default_factory=list)


class CodeIndex:
    def __init__(self, files: list[SourceFile], symbols: list[Symbol], chunk_lines: int = CHUNK_LINES):
        self.files = files
        self.symbols = symbols
        self.chunks = self._make_chunks(files, symbols, chunk_lines)
        self._tokens = [self._tokens_for(c) for c in self.chunks]
        self._tf = [Counter(t) for t in self._tokens]
        self._lengths = [len(t) for t in self._tokens]
        self._avg_len = (sum(self._lengths) / len(self._lengths)) if self._lengths else 1.0
        self._df: Counter[str] = Counter()
        for tokens in self._tokens:
            self._df.update(set(tokens))

    @staticmethod
    def _make_chunks(files: list[SourceFile], symbols: list[Symbol], n: int) -> list[Chunk]:
        by_file: dict[str, list[Symbol]] = {}
        for s in symbols:
            by_file.setdefault(s.file, []).append(s)
        chunks: list[Chunk] = []
        for f in files:
            lines = f.text.splitlines()
            for offset in range(0, len(lines), n):
                start, end = offset + 1, min(offset + n, len(lines))
                names = [s.name for s in by_file.get(f.path, []) if start <= s.line <= end]
                chunks.append(Chunk(f.path, start, end, "\n".join(lines[offset:end]), names))
        return chunks

    @staticmethod
    def _tokens_for(c: Chunk) -> list[str]:
        return tokenize(c.text) + tokenize(c.file) * 3 + tokenize(" ".join(c.symbols)) * 3

    def search(self, query: str, k: int = 6) -> list[tuple[float, Chunk]]:
        terms = set(tokenize(query))
        if not terms or not self.chunks:
            return []
        n = len(self.chunks)
        scored: list[tuple[float, int]] = []
        for i, tf in enumerate(self._tf):
            score = 0.0
            for term in terms:
                freq = tf.get(term, 0)
                if not freq:
                    continue
                df = self._df[term]
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                norm = freq * (K1 + 1) / (freq + K1 * (1 - B + B * self._lengths[i] / self._avg_len))
                score += idf * norm
            if score > 0:
                scored.append((score, i))
        scored.sort(reverse=True)
        return [(score, self.chunks[i]) for score, i in scored[:k]]

    def find_symbols(self, name: str) -> list[Symbol]:
        needle = name.lower()
        return [s for s in self.symbols if needle in s.name.lower()]

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "files": [{"path": f.path, "language": f.language, "lines": len(f.text.splitlines())}
                      for f in self.files],
            "symbols": [asdict(s) for s in self.symbols],
            "chunks": [asdict(c) for c in self.chunks],
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
