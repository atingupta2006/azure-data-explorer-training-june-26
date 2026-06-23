"""Verify learn.microsoft.com links in student markdown materials."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import httpx

from adx_training_tools.config import find_gh_root

LINK_RE = re.compile(r"\]\((https://learn\.microsoft\.com[^)]+)\)")
USER_AGENT = "ADX-TCS-LinkVerifier/1.0"


def find_markdown_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.md"))


def extract_learn_links(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    rel = str(path.relative_to(find_gh_root()))
    return [(rel, url.strip()) for url in LINK_RE.findall(text)]


def check_url(url: str, timeout: float = 30.0) -> tuple[int | None, str | None]:
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
            resp = client.head(url)
            if resp.status_code >= 400:
                resp = client.get(url)
            return resp.status_code, None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def verify_markdown_links(
    *,
    scan_root: Path | None = None,
    day: int | None = None,
) -> dict[str, Any]:
    gh = find_gh_root()
    if day is not None:
        root = gh / f"day-{day:02d}"
        files = find_markdown_files(root)
    elif scan_root is not None:
        root = scan_root
        files = find_markdown_files(root)
    else:
        root = gh
        files = []
        for day_dir in sorted(gh.glob("day-*/")):
            if day_dir.is_dir():
                files.extend(find_markdown_files(day_dir))
        readme = gh / "README.md"
        if readme.is_file():
            files.append(readme)
    seen: set[str] = set()
    checks: list[dict[str, Any]] = []
    broken: list[dict[str, Any]] = []

    for file in files:
        for rel, url in extract_learn_links(file):
            if url in seen:
                continue
            seen.add(url)
            status, err = check_url(url)
            item = {"file": rel, "url": url, "status": status, "error": err}
            checks.append(item)
            if err or (status is not None and status >= 400):
                broken.append(item)

    return {
        "scan_root": str(root),
        "files_scanned": len(files),
        "unique_links": len(checks),
        "broken_count": len(broken),
        "broken": broken,
        "pass": len(broken) == 0,
    }
