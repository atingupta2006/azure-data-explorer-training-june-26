"""ChromaDB vector index for Microsoft Learn ADX documentation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adx_training_tools.config import tools_root
from adx_training_tools.docs.chunk import TextChunk, chunk_text
from adx_training_tools.docs.fetch import crawl_from_seeds
from adx_training_tools.docs.seeds import iter_seed_urls, load_seed_config


def index_dir() -> Path:
    p = tools_root() / ".doc-index"
    p.mkdir(parents=True, exist_ok=True)
    return p


def manifest_path() -> Path:
    return index_dir() / "manifest.json"


def get_collection():
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(
        path=str(index_dir() / "chroma"),
        settings=Settings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(
        name="adx-learn",
        metadata={"description": "Microsoft Learn ADX/Kusto docs for course authoring"},
    )


def build_index(
    *,
    seeds_file: Path | None = None,
    max_depth: int | None = None,
    max_pages: int = 120,
    reset: bool = False,
) -> dict[str, Any]:
    cfg = load_seed_config(seeds_file)
    depth = max_depth if max_depth is not None else int(cfg.get("max_link_depth", 1))
    seed_pairs = iter_seed_urls(seeds_file)
    pages = crawl_from_seeds(seed_pairs, max_depth=depth, max_pages=max_pages)

    if reset:
        import chromadb
        from chromadb.config import Settings

        client = chromadb.PersistentClient(
            path=str(index_dir() / "chroma"),
            settings=Settings(anonymized_telemetry=False),
        )
        try:
            client.delete_collection("adx-learn")
        except Exception:  # noqa: BLE001
            pass

    collection = get_collection()
    all_chunks: list[TextChunk] = []
    for page in pages:
        if not page.text or page.title.startswith("FETCH_FAILED"):
            continue
        all_chunks.extend(
            chunk_text(
                url=page.url,
                title=page.title,
                topic=page.topic,
                text=page.text,
            )
        )

    if all_chunks:
        # Batch upsert
        ids = [c.chunk_id for c in all_chunks]
        documents = [c.text for c in all_chunks]
        metadatas = [
            {"url": c.url, "title": c.title, "topic": c.topic, "ordinal": c.ordinal}
            for c in all_chunks
        ]
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    failed = [p.url for p in pages if p.title.startswith("FETCH_FAILED")]
    manifest = {
        "pages_crawled": len(pages),
        "pages_indexed": len(pages) - len(failed),
        "chunks_indexed": len(all_chunks),
        "failed_urls": failed,
        "max_depth": depth,
        "seed_count": len(seed_pairs),
    }
    manifest_path().write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def search_index(query: str, *, n_results: int = 8, topic: str | None = None) -> list[dict[str, Any]]:
    collection = get_collection()
    where = {"topic": topic} if topic else None
    result = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where,
    )
    hits: list[dict[str, Any]] = []
    ids = result.get("ids", [[]])[0]
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    dists = result.get("distances", [[]])[0]
    for i, doc_id in enumerate(ids):
        meta = metas[i] if i < len(metas) else {}
        hits.append(
            {
                "id": doc_id,
                "url": meta.get("url"),
                "title": meta.get("title"),
                "topic": meta.get("topic"),
                "distance": dists[i] if i < len(dists) else None,
                "excerpt": (docs[i][:400] + "…") if docs and len(docs[i]) > 400 else (docs[i] if docs else ""),
            }
        )
    return hits
