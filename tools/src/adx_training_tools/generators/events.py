"""IoT and Event Hub NDJSON generators (deterministic)."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from adx_training_tools.config import Profile, find_gh_root, load_profile

SEED = 20260610

IOT_TEMPLATES: list[dict[str, Any]] = [
    {
        "deviceId": "substation-sensor-01",
        "EventType": "SensorAnomaly",
        "SourceIP": "10.20.9.1",
        "DestinationHost": "iot-gateway.utility.local",
        "UserPrincipal": "",
        "Severity": "High",
        "Message": "Temperature spike near access panel",
        "Facility": "Substation-C",
    },
    {
        "deviceId": "substation-sensor-02",
        "EventType": "DeviceHeartbeat",
        "SourceIP": "10.20.9.2",
        "DestinationHost": "iot-gateway.utility.local",
        "UserPrincipal": "",
        "Severity": "Low",
        "Message": "Device online",
        "Facility": "Substation-C",
    },
    {
        "deviceId": "substation-sensor-01",
        "EventType": "ConfigChange",
        "SourceIP": "10.20.9.1",
        "DestinationHost": "iot-gateway.utility.local",
        "UserPrincipal": "iot-admin@utility.com",
        "Severity": "Medium",
        "Message": "Firmware config push acknowledged",
        "Facility": "Substation-C",
    },
    {
        "deviceId": "substation-sensor-03",
        "EventType": "SensorAnomaly",
        "SourceIP": "10.20.9.3",
        "DestinationHost": "iot-gateway.utility.local",
        "UserPrincipal": "",
        "Severity": "Critical",
        "Message": "Vibration pattern outside baseline",
        "Facility": "Substation-D",
    },
    {
        "deviceId": "substation-sensor-02",
        "EventType": "FirewallDeny",
        "SourceIP": "10.20.9.2",
        "DestinationHost": "dmz.utility.local",
        "UserPrincipal": "",
        "Severity": "High",
        "Message": "Blocked outbound connection from IoT gateway",
        "Facility": "DMZ-Firewall",
    },
]

EVENTHUB_TEMPLATES: list[dict[str, Any]] = [
    {
        "EventType": "AuthFailure",
        "SourceIP": "10.20.8.1",
        "DestinationHost": "vpn.utility.local",
        "UserPrincipal": "field@utility.com",
        "Severity": "High",
        "Message": "Streaming auth failure",
        "Facility": "Corporate-VPN",
    },
    {
        "EventType": "AuthFailure",
        "SourceIP": "10.20.8.2",
        "DestinationHost": "scada-gw.utility.local",
        "UserPrincipal": "unknown",
        "Severity": "Critical",
        "Message": "Invalid token in stream",
        "Facility": "Substation-A",
    },
    {
        "EventType": "FirewallDeny",
        "SourceIP": "203.0.113.80",
        "DestinationHost": "dmz.utility.local",
        "UserPrincipal": "",
        "Severity": "High",
        "Message": "Streaming deny rule triggered",
        "Facility": "DMZ-Firewall",
    },
    {
        "EventType": "VPNLogin",
        "SourceIP": "10.20.8.5",
        "DestinationHost": "vpn.utility.local",
        "UserPrincipal": "contractor@utility.com",
        "Severity": "Low",
        "Message": "VPN session started via stream",
        "Facility": "Corporate-VPN",
    },
    {
        "EventType": "VPNLogin",
        "SourceIP": "10.20.8.6",
        "DestinationHost": "vpn.utility.local",
        "UserPrincipal": "auditor@utility.com",
        "Severity": "Medium",
        "Message": "VPN session started via stream",
        "Facility": "Corporate-VPN",
    },
]


def _expand_by_event_types(
    templates: list[dict[str, Any]],
    event_type_counts: dict[str, int],
    base_time: datetime,
    extra_fields: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build rows matching event-type quotas by cycling templates."""
    by_type: dict[str, list[dict[str, Any]]] = {}
    for t in templates:
        by_type.setdefault(t["EventType"], []).append(t)

    rows: list[dict[str, Any]] = []
    minute = 0
    for etype, count in event_type_counts.items():
        pool = by_type.get(etype, templates)
        for i in range(count):
            src = dict(pool[i % len(pool)])
            row = {**src}
            if extra_fields:
                row.update(extra_fields)
            row["Timestamp"] = (base_time + timedelta(minutes=minute)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            minute += 1
            rows.append(row)
    return rows


def _write_ndjson(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")


def generate_iot(profile: Profile | None = None) -> Path:
    profile = profile or load_profile("heavy-10x")
    rng = random.Random(SEED + profile.scale_factor)
    base = datetime(2026, 6, 12, 9, 0, 0, tzinfo=timezone.utc)

    # IoT: cycle templates with slight IP/device variation
    rows: list[dict[str, Any]] = []
    n = profile.counts.iot
    for i in range(n):
        t = dict(IOT_TEMPLATES[i % len(IOT_TEMPLATES)])
        t["Timestamp"] = (base + timedelta(seconds=15 * i + rng.randint(0, 5))).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        if i >= len(IOT_TEMPLATES):
            octet = 1 + (i % 20)
            t["SourceIP"] = f"10.20.9.{octet}"
            t["deviceId"] = f"substation-sensor-{(i % 5) + 1:02d}"
        rows.append(t)

    out = profile.file_path("iot")
    _write_ndjson(out, rows)
    return out


def generate_eventhub(profile: Profile | None = None) -> Path:
    profile = profile or load_profile("heavy-10x")
    base = datetime(2026, 6, 12, 8, 0, 0, tzinfo=timezone.utc)
    quotas = profile.eventhub_event_types or {
        "AuthFailure": profile.counts.eventhub // 2,
        "FirewallDeny": max(1, profile.counts.eventhub // 10),
        "VPNLogin": profile.counts.eventhub // 2,
    }
    rows = _expand_by_event_types(EVENTHUB_TEMPLATES, quotas, base)
    # Pad to exact count if quotas sum low
    while len(rows) < profile.counts.eventhub:
        idx = len(rows) % len(EVENTHUB_TEMPLATES)
        t = dict(EVENTHUB_TEMPLATES[idx])
        t["Timestamp"] = (base + timedelta(minutes=len(rows))).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        rows.append(t)
    rows = rows[: profile.counts.eventhub]

    out = profile.file_path("eventhub")
    _write_ndjson(out, rows)
    return out


def seed_from_lab(profile_name: str = "lab") -> None:
    """Copy lab-sized files from GH/data when generating lab profile."""
    lab = load_profile("lab")
    target = load_profile(profile_name)
    if target.data_dir == lab.data_dir:
        return
    gh = find_gh_root()
    for key in ("iot", "eventhub", "bronze_json", "bronze_csv"):
        src = lab.file_path(key)
        dst = target.file_path(key)
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
