"""Split page text into overlapping chunks for vector index."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TextChunk:
    chunk_id: str
    url: str
    title: str
    topic: str
    text: str
    ordinal: int


def chunk_text(
    *,
    url: str,
    title: str,
    topic: str,
    text: str,
    chunk_size: int = 1200,
    overlap: int = 150,
) -> list[TextChunk]:
    cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [
            TextChunk(
                chunk_id=f"{url}#0",
                url=url,
                title=title,
                topic=topic,
                text=cleaned,
                ordinal=0,
            )
        ]
    chunks: list[TextChunk] = []
    start = 0
    ordinal = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(
                TextChunk(
                    chunk_id=f"{url}#{ordinal}",
                    url=url,
                    title=title,
                    topic=topic,
                    text=piece,
                    ordinal=ordinal,
                )
            )
            ordinal += 1
        if end >= len(cleaned):
            break
        start = max(end - overlap, start + 1)
    return chunks
