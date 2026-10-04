"""Clause-level index over the OCR'd regulation corpus (ocr_docs/typhoon_ocr).

Two access paths:
- get_clause(doc_hint, clause): exact lookup used to ground rule citations.
- search(query, k): lexical retrieval used to give drafters relevant context.

Thai has no word boundaries, so BM25 runs over character trigrams; good enough for
legal text with stable terminology and needs no tokenizer dependency.
"""
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Dict

from app.config import settings

THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
CLAUSE_START = re.compile(r"^\s*(มาตรา|ข้อ)\s*([๐-๙0-9]+(?:/[๐-๙0-9]+)?)\s")
PAGE_MARKER = re.compile(r"<!--.*?-->|^---\s*$", re.MULTILINE)


def normalize(text: str) -> str:
    return text.translate(THAI_DIGITS)


@dataclass
class Clause:
    doc: str          # file stem
    category: str     # parent folder, e.g. "พรบ", "ระเบียบกระทรวงการคลัง"
    label: str        # normalized, e.g. "มาตรา 9", "ข้อ 162"
    text: str

    @property
    def ref(self) -> str:
        return f"{self.doc} {self.label}"


def _chunk_document(path: Path) -> List[Clause]:
    raw = PAGE_MARKER.sub("", path.read_text(encoding="utf-8"))
    clauses: List[Clause] = []
    label, buf = "preamble", []

    def flush():
        body = "\n".join(buf).strip()
        if body:
            clauses.append(Clause(path.stem, path.parent.name, label, body))

    for line in raw.splitlines():
        m = CLAUSE_START.match(line)
        if m:
            flush()
            label, buf = f"{m.group(1)} {normalize(m.group(2))}", [line]
        else:
            buf.append(line)
    flush()
    return clauses


def _trigrams(text: str) -> List[str]:
    s = re.sub(r"\s+", " ", normalize(text))
    return [s[i:i + 3] for i in range(max(len(s) - 2, 0))]


class RegulationIndex:
    def __init__(self, root: str, k1: float = 1.5, b: float = 0.75):
        self.clauses: List[Clause] = []
        for p in sorted(Path(root).rglob("*.md")):
            self.clauses.extend(_chunk_document(p))
        self.k1, self.b = k1, b
        self._tf = [Counter(_trigrams(c.text)) for c in self.clauses]
        self._len = [sum(tf.values()) for tf in self._tf]
        self._avg = (sum(self._len) / len(self._len)) if self._len else 0.0
        df: Counter = Counter()
        for tf in self._tf:
            df.update(tf.keys())
        n = len(self.clauses)
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def get_clause(self, doc_hint: str, clause: str) -> Optional[Clause]:
        """doc_hint is a substring of the file stem; clause like 'มาตรา ๙' or 'ข้อ 162'."""
        want = normalize(re.sub(r"\s+", " ", clause.strip()))
        for c in self.clauses:
            if doc_hint in c.doc and c.label == want:
                return c
        return None

    def search(self, query: str, k: int = 3, categories: Optional[List[str]] = None) -> List[Clause]:
        q = Counter(_trigrams(query))
        scores: Dict[int, float] = {}
        for i, tf in enumerate(self._tf):
            if categories and self.clauses[i].category not in categories:
                continue
            norm = self.k1 * (1 - self.b + self.b * self._len[i] / (self._avg or 1))
            s = 0.0
            for t in q:
                f = tf.get(t)
                if f:
                    s += self._idf[t] * f * (self.k1 + 1) / (f + norm)
            if s > 0:
                scores[i] = s
        top = sorted(scores, key=scores.get, reverse=True)[:k]
        return [self.clauses[i] for i in top]


@lru_cache(maxsize=1)
def get_regulation_index() -> RegulationIndex:
    return RegulationIndex(settings.REGULATION_CORPUS_DIR)
