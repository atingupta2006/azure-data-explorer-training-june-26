"""Load curated Microsoft Learn seed URLs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from adx_training_tools.config import find_gh_root, tools_root


def gh_root() -> Path:
    return find_gh_root()


def tools_dir() -> Path:
    return tools_root()


def seeds_path() -> Path:
    return tools_dir() / "doc-sources" / "adx-learn-seeds.yaml"


def load_seed_config(path: Path | None = None) -> dict[str, Any]:
    p = path or seeds_path()
    with p.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def iter_seed_urls(path: Path | None = None) -> list[tuple[str, str]]:
    """Return (topic, url) pairs from seed file."""
    cfg = load_seed_config(path)
    out: list[tuple[str, str]] = []
    for block in cfg.get("seeds", []):
        topic = block.get("topic", "general")
        for url in block.get("urls", []):
            out.append((topic, url.strip()))
    return out
