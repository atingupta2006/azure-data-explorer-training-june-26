"""Minimal student root README — title only; day folders speak for themselves."""

from __future__ import annotations

from pathlib import Path

ROOT_README = "# Azure Data Explorer (ADX) — TCS Training\n"


def write_release_index_docs(gh_root: Path, max_day: int | None = None) -> None:
    del max_day
    (gh_root / "README.md").write_text(ROOT_README, encoding="utf-8")
