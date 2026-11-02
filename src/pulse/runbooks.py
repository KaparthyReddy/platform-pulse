from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pulse import config

STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "for", "how", "in", "is", "it", "my", "of", "on",
        "or", "our", "that", "the", "this", "to", "what", "why", "with", "not",
    }
)


@dataclass(frozen=True)
class Runbook:
    name: str
    title: str
    services: tuple[str, ...]
    keywords: frozenset[str]
    body: str


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1 and t not in STOPWORDS]


def _line_value(text: str, label: str) -> str:
    match = re.search(rf"^{label}:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _section(body: str, heading: str) -> str:
    match = re.search(rf"^## {heading}\s*\n(.*?)(?=^## |\Z)", body, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""


def _parse(path: Path) -> Runbook:
    text = path.read_text(encoding="utf-8")
    title_match = re.search(r"^# (.+)$", text, re.MULTILINE)
    services = tuple(s.strip().lower() for s in _line_value(text, "Services").split(",") if s.strip())
    return Runbook(
        name=path.stem,
        title=title_match.group(1).strip() if title_match else path.stem,
        services=services,
        keywords=frozenset(tokenize(_line_value(text, "Keywords"))),
        body=text,
    )


def load_runbooks(directory: Path | str | None = None) -> list[Runbook]:
    root = Path(directory) if directory is not None else config.RUNBOOK_DIR
    if not root.exists():
        return []
    return [_parse(p) for p in sorted(root.glob("*.md"))]


def _score(runbook: Runbook, tokens: list[str]) -> float:
    title_tokens = set(tokenize(runbook.title))
    body_counts = Counter(tokenize(runbook.body))
    score = 0.0
    for token in set(tokens):
        if token in runbook.keywords:
            score += 3.0
        if token in title_tokens:
            score += 2.0
        score += min(body_counts.get(token, 0), 3) * 0.5
    return score


def search_runbooks(
    query: str,
    service: str | None = None,
    limit: int = 3,
    directory: Path | str | None = None,
) -> list[dict[str, Any]]:
    tokens = tokenize(query)
    if not tokens:
        return []
    wanted = service.lower() if service else None
    ranked: list[tuple[float, Runbook]] = []
    for runbook in load_runbooks(directory):
        if wanted and wanted not in runbook.services:
            continue
        score = _score(runbook, tokens)
        if score > 0:
            ranked.append((score, runbook))
    ranked.sort(key=lambda item: (-item[0], item[1].name))
    return [
        {
            "name": rb.name,
            "title": rb.title,
            "services": list(rb.services),
            "score": round(score, 1),
            "symptoms": _section(rb.body, "Symptoms"),
        }
        for score, rb in ranked[:limit]
    ]


def get_runbook(name: str, directory: Path | str | None = None) -> dict[str, Any] | None:
    for runbook in load_runbooks(directory):
        if runbook.name == name:
            return {
                "name": runbook.name,
                "title": runbook.title,
                "services": list(runbook.services),
                "diagnosis": _section(runbook.body, "Diagnosis"),
                "mitigation": _section(runbook.body, "Mitigation"),
                "escalation": _section(runbook.body, "Escalation"),
            }
    return None
