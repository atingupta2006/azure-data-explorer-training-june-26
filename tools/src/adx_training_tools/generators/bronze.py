"""Bronze batch JSON, CSV, and NDJSON generators."""

from __future__ import annotations

import csv
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from adx_training_tools.config import Profile, load_profile

SEED = 20260611

JSON_TEMPLATES = [
    {
        "EventType": "AuthFailure",
        "SourceIP": "10.20.1.44",
        "DestinationHost": "scada-gw.utility.local",
        "UserPrincipal": "operator@utility.com",
        "Severity": "High",
        "Message": "Failed login after 3 attempts",
        "Facility": "Substation-A",
    },
    {
        "EventType": "AuthFailure",
        "SourceIP": "10.20.1.88",
        "DestinationHost": "scada-gw.utility.local",
        "UserPrincipal": "contractor@utility.com",
        "Severity": "High",
        "Message": "Invalid password",
        "Facility": "Substation-A",
    },
    {
        "EventType": "AuthFailure",
        "SourceIP": "10.20.2.10",
        "DestinationHost": "vpn.utility.local",
        "UserPrincipal": "unknown",
        "Severity": "Critical",
        "Message": "Brute force pattern detected",
        "Facility": "Corporate-VPN",
    },
    {
        "EventType": "AuthSuccess",
        "SourceIP": "10.20.1.12",
        "DestinationHost": "scada-gw.utility.local",
        "UserPrincipal": "operator@utility.com",
        "Severity": "Low",
        "Message": "Login successful",
        "Facility": "Substation-A",
    },
    {
        "EventType": "AuthSuccess",
        "SourceIP": "10.20.1.15",
        "DestinationHost": "scada-gw.utility.local",
        "UserPrincipal": "supervisor@utility.com",
        "Severity": "Low",
        "Message": "Login successful",
        "Facility": "Substation-A",
    },
    {
        "EventType": "FirewallDeny",
        "SourceIP": "203.0.113.10",
        "DestinationHost": "dmz.utility.local",
        "UserPrincipal": "",
        "Severity": "High",
        "Message": "Blocked inbound scan",
        "Facility": "DMZ-Firewall",
    },
    {
        "EventType": "FirewallDeny",
        "SourceIP": "203.0.113.11",
        "DestinationHost": "dmz.utility.local",
        "UserPrincipal": "",
        "Severity": "High",
        "Message": "Blocked port sweep",
        "Facility": "DMZ-Firewall",
    },
    {
        "EventType": "FirewallDeny",
        "SourceIP": "203.0.113.12",
        "DestinationHost": "dmz.utility.local",
        "UserPrincipal": "",
        "Severity": "Medium",
        "Message": "Policy deny",
        "Facility": "DMZ-Firewall",
    },
    {
        "EventType": "FirewallDeny",
        "SourceIP": "203.0.113.13",
        "DestinationHost": "dmz.utility.local",
        "UserPrincipal": "",
        "Severity": "High",
        "Message": "Geo-blocked source",
        "Facility": "DMZ-Firewall",
    },
    {
        "EventType": "FirewallAllow",
        "SourceIP": "10.20.1.20",
        "DestinationHost": "scada-gw.utility.local",
        "UserPrincipal": "",
        "Severity": "Low",
        "Message": "Allowed maintenance window",
        "Facility": "Substation-A",
    },
    {
        "EventType": "FirewallAllow",
        "SourceIP": "10.20.1.21",
        "DestinationHost": "scada-gw.utility.local",
        "UserPrincipal": "",
        "Severity": "Low",
        "Message": "Allowed operator session",
        "Facility": "Substation-A",
    },
    {
        "EventType": "VPNLogin",
        "SourceIP": "10.20.2.50",
        "DestinationHost": "vpn.utility.local",
        "UserPrincipal": "field@utility.com",
        "Severity": "Low",
        "Message": "VPN connected",
        "Facility": "Corporate-VPN",
    },
    {
        "EventType": "VPNLogin",
        "SourceIP": "10.20.2.51",
        "DestinationHost": "vpn.utility.local",
        "UserPrincipal": "auditor@utility.com",
        "Severity": "Medium",
        "Message": "VPN connected",
        "Facility": "Corporate-VPN",
    },
    {
        "EventType": "ConfigChange",
        "SourceIP": "10.20.1.5",
        "DestinationHost": "scada-gw.utility.local",
        "UserPrincipal": "admin@utility.com",
        "Severity": "Medium",
        "Message": "PLC config updated",
        "Facility": "Substation-A",
    },
    {
        "EventType": "PrivilegeEscalation",
        "SourceIP": "10.20.1.99",
        "DestinationHost": "scada-gw.utility.local",
        "UserPrincipal": "svc-account",
        "Severity": "Critical",
        "Message": "Unexpected role assignment",
        "Facility": "Substation-A",
    },
]

CSV_TEMPLATES = [
    ("AuthFailure", "10.20.3.55", "tech@utility.com", "Medium", "Account locked", "Substation-B"),
    ("AuthFailure", "10.20.3.60", "unknown", "High", "Invalid certificate presented", "Substation-B"),
    ("AuthSuccess", "10.20.3.12", "tech@utility.com", "Low", "Login successful", "Substation-B"),
    ("FirewallDeny", "203.0.113.60", "", "High", "Blocked lateral movement attempt", "DMZ-Firewall"),
    ("FirewallDeny", "203.0.113.61", "", "High", "Blocked outbound C2", "DMZ-Firewall"),
    ("FirewallAllow", "10.20.3.20", "", "Low", "Allowed SCADA read", "Substation-B"),
    ("VPNLogin", "10.20.3.70", "contractor@utility.com", "Low", "VPN session", "Corporate-VPN"),
    ("ConfigChange", "10.20.3.5", "admin@utility.com", "Medium", "Firewall rule change", "DMZ-Firewall"),
    ("PrivilegeEscalation", "10.20.3.99", "svc-account", "Critical", "Role elevation", "Substation-B"),
    ("AuthSuccess", "10.20.3.14", "supervisor@utility.com", "Low", "Login successful", "Substation-B"),
]

CSV_HEADER = [
    "Timestamp",
    "EventType",
    "SourceIP",
    "DestinationHost",
    "UserPrincipal",
    "Severity",
    "Message",
    "Facility",
]

PROGRESS_EVERY = 250_000


def _vary_ip(base_ip: str, rng: random.Random, index: int) -> str:
    parts = base_ip.split(".")
    if len(parts) == 4 and parts[0] in ("10", "203", "198"):
        parts[3] = str((int(parts[3]) + index + rng.randint(0, 50)) % 254 + 1)
        return ".".join(parts)
    return base_ip


def _build_json_rows(profile: Profile) -> list[dict]:
    rng = random.Random(SEED + profile.scale_factor)
    base = datetime(2026, 6, 11, 9, 0, 0, tzinfo=timezone.utc)
    quotas = profile.json_event_types
    by_type: dict[str, list] = {}
    for t in JSON_TEMPLATES:
        by_type.setdefault(t["EventType"], []).append(t)

    rows: list[dict] = []
    minute = 0
    for etype, count in quotas.items():
        pool = by_type.get(etype, JSON_TEMPLATES)
        for i in range(count):
            row = dict(pool[i % len(pool)])
            row["SourceIP"] = _vary_ip(row["SourceIP"], rng, minute)
            row["Timestamp"] = (base + timedelta(minutes=minute, seconds=rng.randint(0, 30))).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            minute += 1
            rows.append(row)

    while len(rows) < profile.counts.bronze_json:
        idx = len(rows) % len(JSON_TEMPLATES)
        row = dict(JSON_TEMPLATES[idx])
        row["SourceIP"] = _vary_ip(row["SourceIP"], rng, len(rows))
        row["Timestamp"] = (base + timedelta(minutes=len(rows))).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows.append(row)
    return rows[: profile.counts.bronze_json]


def _write_json_ndjson(path: Path, rows: list[dict], *, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    total = len(rows)
    with path.open("w", encoding="utf-8") as f:
        for i, row in enumerate(rows):
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
            if total > PROGRESS_EVERY and (i + 1) % PROGRESS_EVERY == 0:
                print(f"  {label}: wrote {i + 1:,}/{total:,} rows", file=sys.stderr)


def _stream_json_rows(profile: Profile, path: Path) -> int:
    """Write JSON rows without holding all rows in memory (large profiles)."""
    rng = random.Random(SEED + profile.scale_factor)
    base = datetime(2026, 6, 11, 9, 0, 0, tzinfo=timezone.utc)
    target = profile.counts.bronze_json
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for i in range(target):
            row = dict(JSON_TEMPLATES[i % len(JSON_TEMPLATES)])
            row["SourceIP"] = _vary_ip(row["SourceIP"], rng, i)
            row["Timestamp"] = (base + timedelta(minutes=i % (60 * 24 * 30), seconds=i % 60)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
            if target > PROGRESS_EVERY and (i + 1) % PROGRESS_EVERY == 0:
                print(f"  bronze JSON: wrote {i + 1:,}/{target:,} rows", file=sys.stderr)
    return target


def _csv_row_dict(row: list[str]) -> dict:
    return {
        "Timestamp": row[0],
        "EventType": row[1],
        "SourceIP": row[2],
        "DestinationHost": row[3],
        "UserPrincipal": row[4],
        "Severity": row[5],
        "Message": row[6],
        "Facility": row[7],
    }


def _stream_csv_and_ndjson(profile: Profile, csv_path: Path, ndjson_path: Path) -> int:
    rng = random.Random(SEED + profile.scale_factor + 1)
    base = datetime(2026, 6, 11, 10, 0, 0, tzinfo=timezone.utc)
    target = profile.counts.bronze_csv
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", encoding="utf-8", newline="") as cf, ndjson_path.open(
        "w", encoding="utf-8"
    ) as nf:
        writer = csv.writer(cf)
        writer.writerow(CSV_HEADER)
        for i in range(target):
            t = CSV_TEMPLATES[i % len(CSV_TEMPLATES)]
            ts = (base + timedelta(minutes=i % (60 * 24 * 30))).strftime("%Y-%m-%dT%H:%M:%SZ")
            ip = _vary_ip(t[1], rng, i)
            csv_row = [ts, t[0], ip, "scada-gw.utility.local", t[2], t[3], t[4], t[5]]
            writer.writerow(csv_row)
            nf.write(json.dumps(_csv_row_dict(csv_row), separators=(",", ":")) + "\n")
            if target > PROGRESS_EVERY and (i + 1) % PROGRESS_EVERY == 0:
                print(f"  bronze CSV/NDJSON: wrote {i + 1:,}/{target:,} rows", file=sys.stderr)
    return target


def generate_bronze(profile: Profile | None = None) -> dict[str, Path]:
    profile = profile or load_profile("heavy-100x")
    json_path = profile.file_path("bronze_json")
    csv_path = profile.file_path("bronze_csv")
    ndjson_path = profile.file_path("bronze_ndjson") if "bronze_ndjson" in profile.paths else csv_path.with_suffix(".ndjson")

    if profile.counts.bronze_json > 50_000:
        _stream_json_rows(profile, json_path)
    else:
        _write_json_ndjson(json_path, _build_json_rows(profile), label="bronze JSON")

    if profile.counts.bronze_csv > 50_000:
        _stream_csv_and_ndjson(profile, csv_path, ndjson_path)
    else:
        base = datetime(2026, 6, 11, 10, 0, 0, tzinfo=timezone.utc)
        csv_rows: list[list[str]] = []
        for i in range(profile.counts.bronze_csv):
            t = CSV_TEMPLATES[i % len(CSV_TEMPLATES)]
            ts = (base + timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
            csv_rows.append([ts, t[0], t[1], "scada-gw.utility.local", t[2], t[3], t[4], t[5]])
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)
            writer.writerows(csv_rows)
        _write_json_ndjson(
            ndjson_path,
            [_csv_row_dict(r) for r in csv_rows],
            label="bronze NDJSON",
        )

    return {"bronze_json": json_path, "bronze_csv": csv_path, "bronze_ndjson": ndjson_path}
