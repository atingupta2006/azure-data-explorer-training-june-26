"""Public search API for indexed Microsoft Learn docs."""

from __future__ import annotations

from typing import Any

from adx_training_tools.docs.index import manifest_path, search_index


def search_docs(query: str, *, n_results: int = 8, topic: str | None = None) -> dict[str, Any]:
    hits = search_index(query, n_results=n_results, topic=topic)
    manifest = {}
    if manifest_path().exists():
        import json

        manifest = json.loads(manifest_path().read_text(encoding="utf-8"))
    return {"query": query, "topic_filter": topic, "manifest": manifest, "results": hits}
