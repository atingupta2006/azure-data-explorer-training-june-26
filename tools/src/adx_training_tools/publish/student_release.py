"""Publish cumulative day folders from develop → main (no empty placeholders)."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from adx_training_tools.config import find_gh_root

SOURCE_BRANCH = "develop"
TARGET_BRANCH = "main"
REMOTE = "origin"


@dataclass
class PublishResult:
    day: int
    branch: str
    committed: bool
    pushed: bool
    message: str


def _run(args: list[str], cwd: Path, *, check: bool = True, capture: bool = False):
    return subprocess.run(
        args,
        cwd=cwd,
        check=check,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def publish_student_day(
    day: int,
    *,
    push: bool = False,
    source: str = SOURCE_BRANCH,
    target: str = TARGET_BRANCH,
    remote: str = REMOTE,
) -> PublishResult:
    """Copy day-01..day-N from develop onto main; remove unreleased day folders entirely."""
    if day < 1 or day > 5:
        raise ValueError("day must be 1–5")

    gh_root = find_gh_root()
    original = _run(["git", "branch", "--show-current"], gh_root, capture=True).stdout.strip()

    try:
        _run(["git", "checkout", target], gh_root)

        for d in range(1, day + 1):
            _run(["git", "checkout", source, "--", f"day-{d:02d}"], gh_root)

        for d in range(day + 1, 6):
            rel = f"day-{d:02d}"
            _run(["git", "rm", "-rf", rel], gh_root, check=False)
            day_dir = gh_root / rel
            if day_dir.exists():
                shutil.rmtree(day_dir)

        _run(["git", "checkout", source, "--", "data/", ".gitignore", "README.md"], gh_root)
        _run(["git", "add", "-A"], gh_root)

        msg = f"Release Day {day} training materials (day-01 … day-{day:02d})."
        status = _run(["git", "status", "--porcelain"], gh_root, capture=True).stdout.strip()
        committed = bool(status)
        if committed:
            _run(["git", "commit", "-m", msg], gh_root)

        pushed = False
        if push and committed:
            _run(["git", "push", remote, target], gh_root)
            pushed = True

        return PublishResult(
            day=day,
            branch=target,
            committed=committed,
            pushed=pushed,
            message=msg if committed else "No changes.",
        )
    finally:
        _run(["git", "checkout", original], gh_root, check=False)


def init_develop_branch(from_ref: str = "HEAD") -> str:
    gh_root = find_gh_root()
    _run(["git", "branch", "-f", SOURCE_BRANCH, from_ref], gh_root)
    return f"Branch '{SOURCE_BRANCH}' now points at {from_ref}."
