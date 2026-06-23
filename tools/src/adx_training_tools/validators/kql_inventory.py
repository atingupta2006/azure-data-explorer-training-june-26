"""Cross-check labs.md query references and day query folders."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from adx_training_tools.config import find_gh_root

KQL_REF = re.compile(r"`([^`]+\.kql)`|queries/([^\s`]+\.kql)")
FORBIDDEN_DAY1 = re.compile(r"\b(union|materialize|evaluate\s+python)\b", re.I)
DAY1_JOIN_ALLOWED = frozenset({"07-scenario-investigations.kql"})


def _day_dirs() -> list[Path]:
    return sorted(p for p in find_gh_root().glob("day-*/") if p.is_dir())


def validate_kql_inventory(day: int | None = None) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    days = _day_dirs()
    if day is not None:
        days = [d for d in days if d.name == f"day-{day:02d}"]

    for day_dir in days:
        day_name = day_dir.name
        labs = day_dir / "labs.md"
        queries_dir = day_dir / "queries"
        if not labs.is_file():
            issues.append({"day": day_name, "issue": "missing labs.md"})
            continue

        text = labs.read_text(encoding="utf-8")
        refs = set()
        for m in KQL_REF.finditer(text):
            if "../" in m.group(0):
                continue
            ref = m.group(1) or m.group(2)
            qpath = day_dir / "queries" / Path(ref).name
            if m.group(1) and "/" not in ref and not qpath.is_file():
                continue
            refs.add(ref)

        for ref in sorted(refs):
            qpath = day_dir / "queries" / Path(ref).name
            if not qpath.is_file():
                issues.append(
                    {"day": day_name, "issue": f"labs.md references missing query: {ref}"}
                )

        if queries_dir.is_dir():
            for qfile in sorted(queries_dir.glob("*.kql")):
                if qfile.name not in {Path(r).name for r in refs}:
                    # informational only — queries may be used in README
                    pass

        if day_name == "day-01":
            for qfile in queries_dir.glob("*.kql") if queries_dir.is_dir() else []:
                content = qfile.read_text(encoding="utf-8")
                if qfile.name in DAY1_JOIN_ALLOWED and re.search(r"\bjoin\b", content, re.I):
                    if re.search(r"\|\s*join\b", content, re.I):
                        issues.append(
                            {
                                "day": day_name,
                                "issue": f"Day 1 Lab 7 should use let/in correlation, not join: {qfile.name}",
                            }
                        )
                    continue
                if FORBIDDEN_DAY1.search(content):
                    issues.append(
                        {
                            "day": day_name,
                            "issue": f"Day 1 query uses forbidden operator: {qfile.name}",
                        }
                    )
                if qfile.name not in DAY1_JOIN_ALLOWED and re.search(r"\bjoin\b", content, re.I):
                    issues.append(
                        {
                            "day": day_name,
                            "issue": f"Day 1 query uses forbidden operator join: {qfile.name}",
                        }
                    )

    return {
        "validator": "kql_inventory",
        "pass": len(issues) == 0,
        "issue_count": len(issues),
        "issues": issues,
    }
