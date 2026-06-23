"""Execute ADX checkpoints and day query files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from adx_training_tools.adx.checkpoints import Checkpoint, build_checkpoints
from adx_training_tools.adx.client import AdxClient
from adx_training_tools.adx.executor import execute_statement, load_run_config
from adx_training_tools.adx.kql_parser import parse_kql_statements
from adx_training_tools.config import find_gh_root, load_profile


def _evaluate_checkpoint(cp: Checkpoint, row: dict[str, Any]) -> dict[str, Any]:
    mismatches: list[str] = []
    for key, expected in cp.expected.items():
        actual = row.get(key)
        if cp.compare == "gte":
            ok = actual is not None and actual >= expected
        else:
            ok = actual == expected
        if not ok:
            mismatches.append(f"{key}: expected {expected}, got {actual}")
    return {
        "id": cp.id,
        "day": cp.day,
        "pass": len(mismatches) == 0,
        "result": row,
        "expected": cp.expected,
        "mismatches": mismatches,
    }


def run_checkpoints(
    profile_name: str = "lab",
    day: int | None = None,
    client: AdxClient | None = None,
) -> dict[str, Any]:
    profile = load_profile(profile_name)
    checkpoints = build_checkpoints(profile)
    if day is not None:
        checkpoints = [cp for cp in checkpoints if cp.day == day]

    adx = client or AdxClient()
    results: list[dict[str, Any]] = []
    for cp in checkpoints:
        try:
            rows = adx.execute(cp.query)
            row = rows[0] if rows else {}
            results.append(_evaluate_checkpoint(cp, row))
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "id": cp.id,
                    "day": cp.day,
                    "pass": False,
                    "error": str(exc),
                }
            )

    return {
        "operation": "adx_checkpoints",
        "profile": profile_name,
        "database": adx.config.database,
        "cluster": adx.config.cluster_uri,
        "pass": all(r.get("pass") for r in results),
        "results": results,
    }


def dry_run_day_queries(
    day: int,
    client: AdxClient | None = None,
    stop_on_error: bool = True,
) -> dict[str, Any]:
    """Run each KQL statement in every query file for a day."""
    day_dir = find_gh_root() / f"day-{day:02d}" / "queries"
    if not day_dir.is_dir():
        return {"pass": False, "error": f"No queries folder: {day_dir}"}

    cfg = load_run_config()
    adx = client or AdxClient()
    files = sorted(day_dir.glob("*.kql"))
    file_runs: list[dict[str, Any]] = []

    for qfile in files:
        statements = parse_kql_statements(qfile.read_text(encoding="utf-8"))
        if not statements:
            file_runs.append({"file": qfile.name, "pass": True, "skipped": "empty"})
            continue

        stmt_runs: list[dict[str, Any]] = []
        for stmt in statements:
            result = execute_statement(
                adx, stmt, adx.config.database, cfg["storage_account"]
            )
            stmt_runs.append(result)
            if not result.get("pass") and stop_on_error:
                break

        file_runs.append(
            {
                "file": qfile.name,
                "pass": all(r.get("pass") for r in stmt_runs),
                "statements": stmt_runs,
            }
        )
        if not file_runs[-1]["pass"] and stop_on_error:
            break

    return {
        "operation": "adx_dry_run_day",
        "day": day,
        "database": adx.config.database,
        "pass": all(r.get("pass") for r in file_runs),
        "runs": file_runs,
    }
