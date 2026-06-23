"""Send Day 3 streaming sample payloads to Event Hub and IoT Hub."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv

from adx_training_tools.azure_cli import ensure_az_on_path, run_az
from adx_training_tools.config import find_gh_root, tools_root

StreamKind = Literal["eventhub", "iot", "both"]


def load_streaming_config() -> dict[str, str | int]:
    load_dotenv(tools_root() / ".env")
    return {
        "eventhub_namespace": os.getenv("ADX_EVENTHUB_NAMESPACE", "eh-adx-tcs").strip(),
        "eventhub_name": os.getenv("ADX_EVENTHUB_NAME", "sec-events").strip(),
        "iot_hub": os.getenv("ADX_IOT_HUB", "iot-adx-tcs").strip(),
        "resource_group": os.getenv("ADX_RESOURCE_GROUP", "rg-adx-training-tcs").strip(),
        "stream_wait_seconds": int(os.getenv("ADX_STREAM_WAIT_SECONDS", "30")),
    }


def _read_ndjson(path: Path) -> list[str]:
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _eventhub_connection_string(namespace: str) -> str:
    try:
        result = run_az(
            "eventhubs",
            "namespace",
            "authorization-rule",
            "keys",
            "list",
            "--resource-group",
            str(load_streaming_config()["resource_group"]),
            "--namespace-name",
            namespace,
            "--authorization-rule-name",
            "RootManageSharedAccessKey",
            "--query",
            "primaryConnectionString",
            "-o",
            "tsv",
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Could not read Event Hub keys for {namespace}: {exc}. "
            "Need Event Hubs Data Sender or listKeys on the namespace."
        ) from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"Could not read Event Hub connection string for {namespace}: {detail}. "
            "Need Event Hubs Data Sender or listKeys on the namespace."
        )
    conn = (result.stdout or "").strip()
    if not conn:
        raise RuntimeError(f"Could not read Event Hub connection string for {namespace}")
    return conn


def send_eventhub_sample(
    *,
    sample_path: Path | None = None,
    namespace: str | None = None,
    eventhub_name: str | None = None,
) -> dict[str, Any]:
    """Send NDJSON lines from sec-events-sample.json to Event Hub."""
    cfg = load_streaming_config()
    ns = namespace or str(cfg["eventhub_namespace"])
    hub = eventhub_name or str(cfg["eventhub_name"])
    path = sample_path or (find_gh_root() / "data" / "streaming" / "sec-events-sample.json")
    lines = _read_ndjson(path)

    try:
        ensure_az_on_path()
        from azure.eventhub import EventData, EventHubProducerClient

        conn = _eventhub_connection_string(ns)
        client = EventHubProducerClient.from_connection_string(conn, eventhub_name=hub)
        batch = client.create_batch()
        for line in lines:
            batch.add(EventData(line))
        with client:
            client.send_batch(batch)
    except Exception as exc:  # noqa: BLE001
        return {
            "pass": False,
            "kind": "eventhub",
            "namespace": ns,
            "eventhub": hub,
            "messages_sent": 0,
            "messages_expected": len(lines),
            "sample_file": str(path),
            "error": str(exc),
        }

    return {
        "pass": True,
        "kind": "eventhub",
        "namespace": ns,
        "eventhub": hub,
        "messages_sent": len(lines),
        "sample_file": str(path),
    }


def send_iot_sample(
    *,
    sample_path: Path | None = None,
    iot_hub: str | None = None,
    resource_group: str | None = None,
) -> dict[str, Any]:
    """Send device-telemetry.json lines via az iot device send-d2c-message."""
    cfg = load_streaming_config()
    hub = iot_hub or str(cfg["iot_hub"])
    rg = resource_group or str(cfg["resource_group"])
    path = sample_path or (find_gh_root() / "data" / "iot" / "device-telemetry.json")
    lines = _read_ndjson(path)

    sent = 0
    errors: list[str] = []
    for line in lines:
        payload = json.loads(line)
        device_id = payload["deviceId"]
        result = run_az(
            "iot",
            "device",
            "send-d2c-message",
            "--hub-name",
            hub,
            "--device-id",
            device_id,
            "--data",
            line,
            check=False,
        )
        if result.returncode != 0:
            errors.append(f"{device_id}: {(result.stderr or result.stdout or '').strip()}")
        else:
            sent += 1

    return {
        "pass": sent == len(lines) and not errors,
        "kind": "iot",
        "iot_hub": hub,
        "messages_sent": sent,
        "messages_expected": len(lines),
        "sample_file": str(path),
        "errors": errors,
    }


def wait_for_bronze_rows(
    *,
    total: int | None = None,
    eventhub: int | None = None,
    iot: int | None = None,
    timeout_seconds: int = 180,
    poll_seconds: int = 10,
) -> dict[str, Any]:
    """Poll SecLogsRaw until expected streaming row counts appear."""
    from adx_training_tools.adx.client import AdxClient

    query = """
SecLogsRaw
| summarize
    TotalRows = count(),
    EventHubRows = countif(RecordFormat == "EventHub"),
    IoTRows = countif(RecordFormat == "IoT")
"""
    client = AdxClient()
    deadline = time.time() + timeout_seconds
    last: dict[str, int] = {}
    while time.time() < deadline:
        rows = client.execute(query)
        if rows:
            last = {k: int(v) for k, v in rows[0].items()}
            ok = True
            if total is not None and last.get("TotalRows", 0) < total:
                ok = False
            if eventhub is not None and last.get("EventHubRows", 0) < eventhub:
                ok = False
            if iot is not None and last.get("IoTRows", 0) < iot:
                ok = False
            if ok:
                return {"pass": True, "counts": last, "waited_seconds": timeout_seconds - (deadline - time.time())}
        time.sleep(poll_seconds)

    return {
        "pass": False,
        "counts": last,
        "timeout_seconds": timeout_seconds,
        "expected": {"total": total, "eventhub": eventhub, "iot": iot},
    }


def send_streaming_samples(kind: StreamKind = "both") -> dict[str, Any]:
    """Send Event Hub and/or IoT sample files; poll until rows land in SecLogsRaw."""
    cfg = load_streaming_config()
    results: list[dict[str, Any]] = []
    polls: list[dict[str, Any]] = []

    if kind in ("eventhub", "both"):
        results.append(send_eventhub_sample())
        before = wait_for_bronze_rows(eventhub=5, timeout_seconds=120)
        polls.append({"after": "eventhub", **before})

    if kind in ("iot", "both"):
        results.append(send_iot_sample())
        before = wait_for_bronze_rows(iot=5, total=35, timeout_seconds=180)
        polls.append({"after": "iot", **before})

    send_ok = all(r.get("pass") for r in results)
    poll_ok = all(p.get("pass") for p in polls)

    return {
        "operation": "send_streaming_samples",
        "kind": kind,
        "pass": send_ok and poll_ok,
        "results": results,
        "polls": polls,
    }
