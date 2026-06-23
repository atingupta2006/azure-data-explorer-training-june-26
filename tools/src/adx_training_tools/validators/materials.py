"""Validate training material structure and locked counts in labs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from adx_training_tools.config import find_gh_root, load_profile

LAB_HEADER = re.compile(r"^#\s+Lab\s+\d+\s+—", re.M)
FORBIDDEN_STUDENT = re.compile(
    r"\b(workaround|internal/|instructor-only)\b", re.I
)


def _day_dirs() -> list[Path]:
    return sorted(p for p in find_gh_root().glob("day-*/") if p.is_dir())


EXPECTED_LABS_BY_DAY: dict[str, int] = {
    "day-01": 7,
    "day-02": 7,
    "day-03": 9,
    "day-04": 7,
    "day-05": 7,
}


def validate_day_structure(day_dir: Path) -> list[str]:
    issues: list[str] = []
    for name in ("README.md", "labs.md"):
        if not (day_dir / name).is_file():
            issues.append(f"{day_dir.name}: missing {name}")

    labs = day_dir / "labs.md"
    if labs.is_file():
        text = labs.read_text(encoding="utf-8")
        lab_count = len(LAB_HEADER.findall(text))
        expected = EXPECTED_LABS_BY_DAY.get(day_dir.name, 7)
        if expected and lab_count != expected:
            issues.append(f"{day_dir.name}: expected {expected} labs, found {lab_count}")
        if "Success criteria" not in text:
            issues.append(f"{day_dir.name}: labs.md missing Success criteria sections")
        if FORBIDDEN_STUDENT.search(text):
            issues.append(f"{day_dir.name}: labs.md contains forbidden instructor/troubleshoot text")

    readme = day_dir / "README.md"
    if readme.is_file() and FORBIDDEN_STUDENT.search(readme.read_text(encoding="utf-8")):
        issues.append(f"{day_dir.name}: README.md contains forbidden instructor text")

    return issues


def _expected_outcomes_block(labs_path: Path) -> str | None:
    if not labs_path.is_file():
        return None
    text = labs_path.read_text(encoding="utf-8")
    outcomes = re.search(
        r"## Expected outcomes\s*\n(.*?)(?:\n---|\n## |\n# Lab)",
        text,
        re.S,
    )
    return outcomes.group(1) if outcomes else None


def _check_outcome_patterns(
    block: str,
    checks: list[tuple[str, int, str]],
    day_label: str,
    issues: list[str],
) -> None:
    for pattern, expected, label in checks:
        m = re.search(pattern, block, re.I)
        if not m:
            issues.append(f"{day_label}: could not find {label} in Expected outcomes")
            continue
        found = int(m.group(1))
        if found != expected:
            issues.append(
                f"{day_label} labs: {label} documented as {found}, profile expects {expected}"
            )


def validate_locked_counts() -> list[str]:
    """Spot-check Expected outcomes tables for locked counts (Days 3–4)."""
    profile = load_profile("lab")
    issues: list[str] = []
    gh = find_gh_root()

    day3_block = _expected_outcomes_block(gh / "day-03" / "labs.md")
    if not day3_block:
        issues.append("day-03: missing Expected outcomes table")
    else:
        _check_outcome_patterns(
            day3_block,
            [
                (r"Lab 2.*EventHub\s*=\s*\*\*(\d+)\*\*", profile.counts.eventhub, "eventhub"),
                (r"Lab 3.*IoT\s*=\s*\*\*(\d+)\*\*", profile.counts.iot, "iot"),
                (r"Lab 3.*Bronze\s*=\s*\*\*(\d+)\*\*", profile.counts.bronze_total, "bronze_total"),
                (r"Lab 5.*Silver\s*=\s*\*\*(\d+)\*\*", profile.counts.silver, "silver"),
            ],
            "day-03",
            issues,
        )

    day4_block = _expected_outcomes_block(gh / "day-04" / "labs.md")
    if not day4_block:
        issues.append("day-04: missing Expected outcomes table")
    else:
        _check_outcome_patterns(
            day4_block,
            [
                (r"Lab 1.*Silver\s*=\s*\*\*(\d+)\*\*", profile.counts.silver, "silver"),
                (
                    r"Lab 1.*AuthFailure\s*=\s*\*\*(\d+)\*\*",
                    profile.counts.auth_failure_silver,
                    "auth_failure_silver",
                ),
                (
                    r"Lab 2.*ThreatIntelRef\s*=\s*\*\*(\d+)\*\*",
                    profile.counts.threat_intel,
                    "threat_intel",
                ),
                (
                    r"Lab 7 Q3.*=\s*\*\*(\d+)\*\*",
                    profile.counts.gold_sum_event_count,
                    "gold_sum_event_count",
                ),
            ],
            "day-04",
            issues,
        )
        if not re.search(r"Lab 2.*≥\s*\*\*300\*\*", day4_block):
            issues.append("day-04: missing join enriched threshold ≥ **300** in Expected outcomes")

    day5_block = _expected_outcomes_block(gh / "day-05" / "labs.md")
    if not day5_block:
        issues.append("day-05: missing Expected outcomes table")
    else:
        _check_outcome_patterns(
            day5_block,
            [
                (
                    r"Lab 4 Q3.*\*\*(\d+)\*\*.*\*\*(\d+)\*\*",
                    profile.counts.gold_sum_event_count,
                    "gold parity totals",
                ),
                (r"Lab 5 Q6.*\*\*(\d+)\*\*", profile.counts.rls_demo, "rls_demo"),
            ],
            "day-05",
            issues,
        )
        if not re.search(r"Gate.*Silver\s*\*\*3500\*\*", day5_block):
            issues.append("day-05: missing gate Silver **3500** in Expected outcomes")
        if not re.search(r"ThreatIntel\s*\*\*8\*\*", day5_block):
            issues.append("day-05: missing ThreatIntel **8** in Expected outcomes")
        if not re.search(r"Gold sum\s*\*\*3500\*\*", day5_block):
            issues.append("day-05: missing Gold sum **3500** in Expected outcomes")
        if not re.search(r"Lab 5 Q6.*\*\*10\*\*|Lab 5 Q8.*\*\*10\*\*|Lab 5.*RlsDemoEvents.*\*\*10\*\*", day5_block):
            issues.append("day-05: missing RlsDemoEvents **10** in Expected outcomes")
        if not re.search(r"CapstoneReady.*\*\*true\*\*", day5_block):
            issues.append("day-05: missing CapstoneReady **true** in Expected outcomes")
        if not re.search(r"scada-gw\.utility\.local", day5_block):
            issues.append("day-05: missing scada-gw capstone host in Expected outcomes")

    return issues


def validate_assignments() -> list[str]:
    """Days 4–5 include scenario assignment packs (student scenarios only; keys in internal/)."""
    issues: list[str] = []
    gh = find_gh_root()
    for day_name in ("day-04", "day-05"):
        day_dir = gh / day_name
        if not (day_dir / "assignments.md").is_file():
            issues.append(f"{day_name}: missing assignments.md")
    return issues


def validate_materials(day: int | None = None) -> dict[str, Any]:
    days = _day_dirs()
    if day is not None:
        days = [d for d in days if d.name == f"day-{day:02d}"]

    issues: list[str] = []
    for d in days:
        issues.extend(validate_day_structure(d))
    issues.extend(validate_locked_counts())
    issues.extend(validate_assignments())

    return {
        "validator": "materials",
        "pass": len(issues) == 0,
        "issue_count": len(issues),
        "issues": issues,
    }
