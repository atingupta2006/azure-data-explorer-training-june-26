"""Execute full lab plan against live ADX."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from adx_training_tools.adx.client import AdxClient
from adx_training_tools.adx.dry_run import run_checkpoints
from adx_training_tools.adx.executor import execute_statement, load_run_config
from adx_training_tools.adx.kql_parser import KqlStatement, parse_kql_statements
from adx_training_tools.adx.lab_plan import LabStep, build_day_plan, build_lab_plan
from adx_training_tools.config import find_gh_root
from adx_training_tools.azure_cli import ensure_subscription, load_subscription_id


def _fallback_blocks(text: str, block: int) -> list[KqlStatement]:
    """Extract block 1 (Event Hub) or block 2 (IoT) from fallback script."""
    statements = parse_kql_statements(text)
    if block == 1:
        return statements[:2]  # set-or-append EH + verify
    return statements[2:4]  # set-or-append IoT + verify


def run_lab_file(
    path: Path,
    client: AdxClient | None = None,
    storage_account: str | None = None,
    fallback_block: int | None = None,
    stop_on_error: bool = True,
) -> dict[str, Any]:
    adx = client or AdxClient()
    if not path.is_file():
        return {"pass": False, "error": f"File not found: {path}"}

    raw = path.read_text(encoding="utf-8")
    if fallback_block is not None:
        statements = _fallback_blocks(raw, fallback_block)
    else:
        statements = parse_kql_statements(raw)

    runs: list[dict[str, Any]] = []
    for stmt in statements:
        result = execute_statement(
            adx, stmt, adx.config.database, storage_account
        )
        runs.append(result)
        if not result.get("pass") and stop_on_error:
            break

    return {
        "operation": "run_lab_file",
        "file": str(path),
        "database": adx.config.database,
        "statements_total": len(statements),
        "pass": all(r.get("pass") for r in runs),
        "runs": runs,
    }


def run_reset(client: AdxClient | None = None) -> dict[str, Any]:
    """Run 00-reset-logsdb.kql drop statements."""
    path = find_gh_root() / "internal" / "scripts" / "00-reset-logsdb.kql"
    adx = client or AdxClient()
    statements = [
        s for s in parse_kql_statements(path.read_text(encoding="utf-8"))
        if s.text.startswith(".drop")
    ]
    runs = []
    for stmt in statements:
        runs.append(execute_statement(adx, stmt, adx.config.database, None))
    return {
        "operation": "reset_database",
        "pass": all(r.get("pass") for r in runs),
        "runs": runs,
    }


def run_lab_plan(
    day: int | None = None,
    profile_name: str = "lab",
    reset_first: bool = False,
    checkpoint_after_day: bool = True,
    stop_on_error: bool = True,
) -> dict[str, Any]:
    """Run ordered lab steps; optional reset and per-day checkpoints."""
    if load_subscription_id():
        try:
            ensure_subscription()
        except Exception as exc:  # noqa: BLE001
            return {"pass": False, "error": f"Subscription setup failed: {exc}"}

    cfg = load_run_config()
    use_fallback = cfg["use_fallback"]
    adx = AdxClient()
    steps = build_lab_plan(use_fallback) if day is None else build_day_plan(day, use_fallback)

    payload: dict[str, Any] = {
        "operation": "run_lab_plan",
        "profile": profile_name,
        "database": adx.config.database,
        "cluster": adx.config.cluster_uri,
        "storage_account": cfg["storage_account"],
        "use_streaming_fallback": use_fallback,
        "steps": [],
        "checkpoints": [],
    }

    if reset_first:
        payload["reset"] = run_reset(adx)
        if not payload["reset"].get("pass"):
            payload["pass"] = False
            return payload

    fallback_block_cursor = 0
    last_day = 0

    for step in steps:
        fb_block = None
        if step.use_fallback_streaming:
            fallback_block_cursor += 1
            fb_block = fallback_block_cursor

        if step.send_streaming:
            from adx_training_tools.streaming_sender import send_streaming_samples

            stream_result = send_streaming_samples(step.send_streaming)
            result = {
                "pass": stream_result.get("pass"),
                "operation": "send_streaming",
                "streaming": stream_result,
            }
        elif step.path is None:
            result = {"pass": False, "error": "Lab step has no query file or action"}
        else:
            result = run_lab_file(
                step.path,
                client=adx,
                storage_account=cfg["storage_account"],
                fallback_block=fb_block,
                stop_on_error=stop_on_error,
            )
        step_report = {
            "day": step.day,
            "step_id": step.step_id,
            "label": step.label,
            "file": str(step.path) if step.path else None,
            "send_streaming": step.send_streaming,
            "pass": result.get("pass"),
            "runs": result.get("runs"),
            "streaming": result.get("streaming"),
            "error": result.get("error"),
        }
        payload["steps"].append(step_report)

        if step.step_id == "4.7" and result.get("pass"):
            wait = cfg["mv_wait_seconds"]
            time.sleep(wait)
            step_report["mv_wait_seconds"] = wait

        if not result.get("pass") and stop_on_error:
            payload["pass"] = False
            return payload

        if checkpoint_after_day and step.day != last_day and last_day > 0:
            cp = run_checkpoints(profile_name=profile_name, day=last_day, client=adx)
            payload["checkpoints"].append(cp)

        last_day = step.day

    if checkpoint_after_day and last_day > 0:
        cp = run_checkpoints(profile_name=profile_name, day=last_day, client=adx)
        payload["checkpoints"].append(cp)

    payload["pass"] = all(s.get("pass") for s in payload["steps"]) and all(
        c.get("pass") for c in payload["checkpoints"]
    )
    return payload


def lab_plan_inventory() -> dict[str, Any]:
    """Static inventory of all lab steps (no Azure required)."""
    steps = build_lab_plan()
    return {
        "operation": "lab_plan_inventory",
        "total_steps": len(steps),
        "days": sorted({s.day for s in steps}),
        "steps": [
            {
                "day": s.day,
                "step_id": s.step_id,
                "label": s.label,
                "file": str(s.path) if s.path else None,
                "requires_storage": s.requires_storage,
                "use_fallback_streaming": s.use_fallback_streaming,
                "send_streaming": s.send_streaming,
            }
            for s in steps
        ],
    }
