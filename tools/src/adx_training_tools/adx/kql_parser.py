"""Split KQL lab files into individually executable statements."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class StatementKind(str, Enum):
    MANAGEMENT = "management"
    QUERY = "query"


@dataclass
class KqlStatement:
    index: int
    kind: StatementKind
    text: str
    has_placeholder: bool


_PLACEHOLDER = re.compile(r"<[a-zA-Z0-9_-]+>")


def _strip_comment_lines(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.strip().startswith("//"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _split_query_tail(text: str) -> list[str]:
    """Split trailing KQL queries after ingest/management blocks."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in paragraphs if p.strip()]


def _split_braced_management(chunk: str) -> list[str]:
    """Keep `.create function` / `.create materialized-view` bodies intact."""
    lines = chunk.splitlines()
    depth = 0
    end = len(lines)
    for i, line in enumerate(lines):
        depth += line.count("{") - line.count("}")
        if depth == 0 and i > 0 and "}" in line:
            end = i + 1
            break
    head = "\n".join(lines[:end]).strip()
    tail = "\n".join(lines[end:]).strip()
    if not tail:
        return [head]
    if tail.lstrip().startswith("."):
        return [head, *_split_management_chunk(tail)]
    return [head, *_split_query_tail(tail)]


def _split_ingest_management(chunk: str) -> list[str]:
    """Keep `.set* <| datatable [...]` separate from following queries."""
    lines = chunk.splitlines()
    close_idx: int | None = None
    seen_pipe = False
    for i, line in enumerate(lines):
        if "<|" in line:
            seen_pipe = True
        if seen_pipe and line.strip() == "]":
            close_idx = i
            break

    if close_idx is None or close_idx + 1 >= len(lines):
        return [chunk]

    tail = "\n".join(lines[close_idx + 1 :]).strip()
    if not tail or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*", tail):
        return [chunk]

    head = "\n".join(lines[: close_idx + 1])
    return [head, *_split_query_tail(tail)]


def _split_management_chunk(chunk: str) -> list[str]:
    """Split one management block from any trailing KQL queries."""
    if not chunk.lstrip().startswith("."):
        return [chunk]
    if re.search(r"<\|\s*datatable\b", chunk, re.IGNORECASE):
        return _split_ingest_management(chunk)
    if "{" in chunk:
        return _split_braced_management(chunk)

    lines = chunk.splitlines()
    query_start = len(lines)
    for i, line in enumerate(lines):
        if i == 0:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        # Next line after <| starts the inline query (e.g. SecLogsRaw), not a new statement.
        if lines[i - 1].rstrip().endswith("<|"):
            continue
        if re.match(r"^(?:let|print)\b", stripped, re.IGNORECASE):
            query_start = i
            break
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*(?:\||$)", stripped):
            query_start = i
            break

    head = "\n".join(lines[:query_start]).strip()
    tail = "\n".join(lines[query_start:]).strip()
    if not tail:
        return [head]
    return [head, *_split_query_tail(tail)]


def parse_kql_statements(text: str) -> list[KqlStatement]:
    """Parse a .kql file into ordered executable statements."""
    body = _strip_comment_lines(text)
    if not body:
        return []

    raw_parts = re.split(r"(?m)(?=^\.)", body)
    chunks: list[str] = []
    for part in raw_parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("."):
            chunks.extend(_split_management_chunk(part))
        else:
            chunks.extend(_split_query_tail(part))

    statements: list[KqlStatement] = []
    for i, chunk in enumerate(chunks):
        kind = (
            StatementKind.MANAGEMENT
            if chunk.lstrip().startswith(".")
            else StatementKind.QUERY
        )
        statements.append(
            KqlStatement(
                index=i + 1,
                kind=kind,
                text=chunk,
                has_placeholder=bool(_PLACEHOLDER.search(chunk)),
            )
        )
    return statements


def apply_env_substitutions(text: str, database: str, storage_account: str | None) -> str:
    """Replace lab placeholders with .env values."""
    out = text.replace("LogsDB_uXX", database)
    out = out.replace("LogsDB_YOUR_SUFFIX", database)
    if database.startswith("LogsDB_"):
        suffix = database[len("LogsDB_") :]
        out = out.replace("YOUR_SUFFIX", suffix)
    if storage_account:
        out = out.replace("<storage-account>", storage_account)
    return out
