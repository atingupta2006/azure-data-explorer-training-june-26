"""Verify generated/static data file row counts vs profile."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from adx_training_tools.config import Profile, load_profile


def _ndjson_count(path: Path) -> int:
    if not path.is_file():
        return -1
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _csv_data_rows(path: Path) -> int:
    if not path.is_file():
        return -1
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    return max(0, len(rows) - 1)


def validate_data_files(profile_name: str = "lab") -> dict[str, Any]:
    profile = load_profile(profile_name)
    checks: list[dict[str, Any]] = []

    def add(name: str, expected: int, actual: int, path: Path) -> None:
        checks.append(
            {
                "name": name,
                "expected": expected,
                "actual": actual,
                "path": str(path),
                "pass": actual == expected,
            }
        )

    add("iot", profile.counts.iot, _ndjson_count(profile.file_path("iot")), profile.file_path("iot"))
    add(
        "eventhub",
        profile.counts.eventhub,
        _ndjson_count(profile.file_path("eventhub")),
        profile.file_path("eventhub"),
    )
    add(
        "bronze_json",
        profile.counts.bronze_json,
        _ndjson_count(profile.file_path("bronze_json")),
        profile.file_path("bronze_json"),
    )
    add(
        "bronze_csv",
        profile.counts.bronze_csv,
        _csv_data_rows(profile.file_path("bronze_csv")),
        profile.file_path("bronze_csv"),
    )
    if "bronze_ndjson" in profile.paths:
        add(
            "bronze_ndjson",
            profile.counts.bronze_csv,
            _ndjson_count(profile.file_path("bronze_ndjson")),
            profile.file_path("bronze_ndjson"),
        )

    batch_actual = checks[2]["actual"] + checks[3]["actual"]
    checks.append(
        {
            "name": "bronze_batch",
            "expected": profile.counts.bronze_batch,
            "actual": batch_actual,
            "path": str(profile.data_path / "bronze"),
            "pass": batch_actual == profile.counts.bronze_batch,
        }
    )

    passed = all(c["pass"] for c in checks)
    return {
        "validator": "data_files",
        "profile": profile_name,
        "pass": passed,
        "checks": checks,
    }
