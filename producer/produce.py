#!/usr/bin/env python3
"""
Generate sample files for ADX batch and streaming ingest labs.

Flow:  Python producer  -->  NDJSON/CSV files  -->  ADLS/Blob  -->  ADX .ingest / data connections

Extend for your own domain:
  1. Subclass EventProducer with your templates in event_at().
  2. Register the scenario in SCENARIOS below.
  3. Run: python produce.py --scenario my-domain --feed batch-json --count 1000 -o out.json
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from counts import expand_event_types, pick_template
from utility_cyber import (
    CSV_EVENT_COUNTS,
    CSV_HEADER,
    CSV_TEMPLATES,
    DEFAULT_BASE,
    EVENTHUB_EVENT_COUNTS,
    EVENTHUB_TEMPLATES,
    IOT_TEMPLATES,
    JSON_EVENT_COUNTS,
    JSON_TEMPLATES,
    PINNED_SOURCE_IPS,
    PRACTICE_EVENT_COUNTS,
)


def _vary_ip(base_ip: str, rng: random.Random, index: int) -> str:
    if base_ip in PINNED_SOURCE_IPS:
        return base_ip
    parts = base_ip.split(".")
    if len(parts) == 4 and parts[0] == "10":
        parts[3] = str((int(parts[3]) + index + rng.randint(0, 9)) % 250 + 1)
        return ".".join(parts)
    return base_ip


class EventProducer(ABC):
    """Base class — implement event_at() for a new use case."""

    def __init__(self, seed: int = 20260611) -> None:
        self.rng = random.Random(seed)

    @abstractmethod
    def event_at(self, index: int, base_time: datetime) -> dict[str, Any]:
        """Return one event dict (must include Timestamp for ADX Silver parsing)."""

    def iter_events(self, count: int, base_time: datetime | None = None) -> Iterator[dict[str, Any]]:
        base = base_time or DEFAULT_BASE
        for i in range(count):
            yield self.event_at(i, base)


class WeightedJsonProducer(EventProducer):
    """Course batch JSON — exact event-type counts from JSON_EVENT_COUNTS."""

    def __init__(self, seed: int = 20260611) -> None:
        super().__init__(seed)
        self._sequence = expand_event_types(JSON_EVENT_COUNTS, seed)

    def event_at(self, index: int, base_time: datetime) -> dict[str, Any]:
        event_type = self._sequence[index]
        row = dict(
            pick_template(JSON_TEMPLATES, event_type, index, lambda t: t["EventType"])
        )
        row["SourceIP"] = _vary_ip(str(row["SourceIP"]), self.rng, index)
        row["Timestamp"] = (base_time + timedelta(minutes=index, seconds=self.rng.randint(0, 30))).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        return row


class WeightedCsvProducer(EventProducer):
    """Course batch CSV/NDJSON — exact event-type counts from CSV_EVENT_COUNTS."""

    def __init__(self, seed: int = 20260611) -> None:
        super().__init__(seed)
        self._sequence = expand_event_types(CSV_EVENT_COUNTS, seed + 1)

    def event_at(self, index: int, base_time: datetime) -> dict[str, Any]:
        event_type = self._sequence[index]
        t = pick_template(CSV_TEMPLATES, event_type, index, lambda row: row[0])
        ts = (base_time + timedelta(minutes=index)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ip = _vary_ip(t[1], self.rng, index)
        return {
            "Timestamp": ts,
            "EventType": t[0],
            "SourceIP": ip,
            "DestinationHost": "scada-gw.utility.local",
            "UserPrincipal": t[2],
            "Severity": t[3],
            "Message": t[4],
            "Facility": t[5],
        }


class WeightedEventHubProducer(EventProducer):
    """Course Event Hub stream — exact counts from EVENTHUB_EVENT_COUNTS."""

    def __init__(self, seed: int = 20260611) -> None:
        super().__init__(seed)
        self._sequence = expand_event_types(EVENTHUB_EVENT_COUNTS, seed + 2)

    def event_at(self, index: int, base_time: datetime) -> dict[str, Any]:
        event_type = self._sequence[index]
        row = dict(
            pick_template(EVENTHUB_TEMPLATES, event_type, index, lambda t: t["EventType"])
        )
        row["SourceIP"] = _vary_ip(str(row["SourceIP"]), self.rng, index)
        row["Timestamp"] = (base_time + timedelta(minutes=index, seconds=index % 60)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        return row


class UtilityCyberIotProducer(EventProducer):
    def event_at(self, index: int, base_time: datetime) -> dict[str, Any]:
        row = dict(IOT_TEMPLATES[index % len(IOT_TEMPLATES)])
        row["SourceIP"] = _vary_ip(str(row["SourceIP"]), self.rng, index)
        row["Timestamp"] = (base_time + timedelta(minutes=index, seconds=index % 45)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        return row


SCENARIOS: dict[str, dict[str, type[EventProducer]]] = {
    "utility-cyber": {
        "batch-json": WeightedJsonProducer,
        "batch-csv": WeightedCsvProducer,
        "eventhub": WeightedEventHubProducer,
        "iot": UtilityCyberIotProducer,
    },
}

DEFAULT_COUNTS = {
    "batch-json": sum(JSON_EVENT_COUNTS.values()),
    "batch-csv": sum(CSV_EVENT_COUNTS.values()),
    "eventhub": sum(EVENTHUB_EVENT_COUNTS.values()),
    "iot": 500,
}

PRACTICE_BASE = datetime(2026, 6, 10, 8, 0, 0, tzinfo=timezone.utc)
PRACTICE_HOSTS = [
    "vpn.utility.local",
    "scada-gw.utility.local",
    "scada-gw.utility.local",
    "vpn.utility.local",
    "scada-gw.utility.local",
]
PRACTICE_FACILITIES = [
    "Substation-A",
    "Substation-B",
    "Corporate-VPN",
    "DMZ-Firewall",
    "SCADA-Gateway",
]


def _practice_severity(event_type: str, index: int) -> str:
    """Locked: 800 rows with High or Critical (400 AuthFailure + 400 FirewallDeny High)."""
    if event_type == "AuthFailure":
        return "High"
    if event_type == "FirewallDeny":
        return "High" if index < 400 else "Low"
    if event_type in ("AuthSuccess", "FirewallAllow", "VPNLogin", "VPNLogout", "PrivilegeEscalation"):
        return "Low"
    return "Medium"


def _practice_message(event_type: str) -> str:
    messages = {
        "AuthFailure": "Failed login after 3 attempts",
        "AuthSuccess": "Login successful",
        "FirewallDeny": "Blocked inbound scan",
        "FirewallAllow": "Allowed outbound HTTPS",
        "VPNLogin": "VPN session started",
        "VPNLogout": "VPN session ended",
        "ConfigChange": "Firewall rule updated",
        "PrivilegeEscalation": "Role elevation detected",
    }
    return messages.get(event_type, "Security event")


def _practice_user(event_type: str, index: int) -> str:
    if event_type in ("FirewallDeny", "FirewallAllow", "VPNLogout"):
        return ""
    users = ["field@utility.com", "operator@utility.com", "supervisor@utility.com", "admin@utility.com"]
    return users[index % len(users)]


def build_practice_rows(seed: int = 20260610) -> list[dict[str, Any]]:
    sequence = expand_event_types(PRACTICE_EVENT_COUNTS, seed)
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    fd_index = 0
    for i, event_type in enumerate(sequence):
        if event_type == "FirewallDeny":
            severity = _practice_severity(event_type, fd_index)
            fd_index += 1
        else:
            severity = _practice_severity(event_type, i)
        ts = (PRACTICE_BASE + timedelta(minutes=i, seconds=rng.randint(0, 45))).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        rows.append(
            {
                "Timestamp": ts,
                "EventType": event_type,
                "SourceIP": f"10.20.{(i % 5) + 1}.{(i % 250) + 1}",
                "DestinationHost": PRACTICE_HOSTS[i % len(PRACTICE_HOSTS)],
                "UserPrincipal": _practice_user(event_type, i),
                "Severity": severity,
                "Message": _practice_message(event_type),
                "Facility": PRACTICE_FACILITIES[i % len(PRACTICE_FACILITIES)],
            }
        )
    return rows


def write_practice_seed_kql(path: Path, seed: int = 20260610) -> None:
    rows = build_practice_rows(seed)
    high_crit = sum(1 for r in rows if r["Severity"] in ("High", "Critical"))
    auth = sum(1 for r in rows if r["EventType"] == "AuthFailure")
    fd = sum(1 for r in rows if r["EventType"] == "FirewallDeny")
    if len(rows) != 2000 or auth != 400 or fd != 500 or high_crit != 800:
        raise RuntimeError(
            f"practice seed mismatch: rows={len(rows)} auth={auth} fd={fd} high+crit={high_crit}"
        )

    lines = [
        "// Day 01 — Seed practice data (2000 rows)",
        "// Database: LogsDB_u01 (select in Web UI before running)",
        "// .set-or-replace reloads all rows — re-run for a clean 2000-row dataset",
        "",
        ".set-or-replace PracticeSecurityEvents <|",
        "datatable(Timestamp:datetime, EventType:string, SourceIP:string, DestinationHost:string, UserPrincipal:string, Severity:string, Message:string, Facility:string)",
        "[",
    ]
    for r in rows:
        ts = f'datetime({r["Timestamp"]})'
        up = r["UserPrincipal"].replace('"', '\\"')
        lines.append(
            f'    {ts}, "{r["EventType"]}", "{r["SourceIP"]}", "{r["DestinationHost"]}", '
            f'"{up}", "{r["Severity"]}", "{r["Message"]}", "{r["Facility"]}",'
        )
    lines.extend(
        [
            "]",
            "",
            "// Verification (expected: 2000 rows; AuthFailure 400; High+Critical 800)",
            "PracticeSecurityEvents",
            "| summarize Total = count(), AuthFailure = countif(EventType == \"AuthFailure\"), "
            "HighCritical = countif(Severity in (\"High\", \"Critical\"))",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_ndjson(path: Path, events: Iterator[dict[str, Any]], count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for i, event in enumerate(events):
            f.write(json.dumps(event, separators=(",", ":")) + "\n")
            if count >= 5000 and (i + 1) % 5000 == 0:
                print(f"  wrote {i + 1:,}/{count:,}", file=sys.stderr)


def write_csv(path: Path, events: Iterator[dict[str, Any]], count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        for i, event in enumerate(events):
            writer.writerow({k: event.get(k, "") for k in CSV_HEADER})
            if count >= 5000 and (i + 1) % 5000 == 0:
                print(f"  wrote {i + 1:,}/{count:,}", file=sys.stderr)


def _kql_dynamic(payload: dict[str, Any]) -> str:
    return f"dynamic({json.dumps(payload, separators=(',', ':'))})"


def _bronze_append_lines(
    events: list[dict[str, Any]], source_file: str, record_format: str
) -> list[str]:
    lines: list[str] = []
    for event in events:
        ts = event["Timestamp"]
        lines.append(
            f'    datetime({ts}), "{source_file}", "{record_format}", {_kql_dynamic(event)},'
        )
    return lines


def write_fallback_streaming_kql(path: Path, seed: int = 20260611) -> None:
    """Maintainer fallback when live Event Hub / IoT Hub are unavailable — 500 + 500 rows."""
    eh_producer = WeightedEventHubProducer(seed)
    iot_producer = UtilityCyberIotProducer(seed)
    eh_events = list(eh_producer.iter_events(DEFAULT_COUNTS["eventhub"]))
    iot_events = list(iot_producer.iter_events(DEFAULT_COUNTS["iot"]))

    lines = [
        "// Maintainer fallback — simulate Event Hub + IoT streaming into SecLogsRaw",
        "// Use when live Event Hub / IoT Hub connections are unavailable",
        "// Database: LogsDB_u01 (select in Web UI before running)",
        "// Prerequisite: SecLogsRaw exists with Day 2 batch rows (count = 2500)",
        "// Regenerate: producer/produce.py --write-fallback-streaming-kql",
        "",
        "// ========== BLOCK 1 — Event Hub simulation (500 rows) ==========",
        "// Expected after: SecLogsRaw count = 3000, EventHub = 500",
        "",
        ".set-or-append SecLogsRaw <|",
        "datatable(IngestionTime:datetime, SourceFile:string, RecordFormat:string, RawPayload:dynamic)",
        "[",
        *_bronze_append_lines(eh_events, "sec-events", "EventHub"),
        "]",
        "",
        "SecLogsRaw",
        "| summarize Total = count(), EventHub = countif(RecordFormat == \"EventHub\")",
        "",
        "// ========== BLOCK 2 — IoT Hub simulation (500 rows) ==========",
        "// Expected after: SecLogsRaw count = 3500, IoT = 500",
        "",
        ".set-or-append SecLogsRaw <|",
        "datatable(IngestionTime:datetime, SourceFile:string, RecordFormat:string, RawPayload:dynamic)",
        "[",
        *_bronze_append_lines(iot_events, "iot-device-telemetry", "IoT"),
        "]",
        "",
        "SecLogsRaw",
        "| summarize Total = count(), IoT = countif(RecordFormat == \"IoT\")",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate ADX training sample data files.")
    p.add_argument(
        "--scenario",
        default="utility-cyber",
        choices=sorted(SCENARIOS),
        help="Use case / domain (default: utility-cyber)",
    )
    p.add_argument(
        "--feed",
        choices=["batch-json", "batch-csv", "eventhub", "iot"],
        help="Which data feed to simulate",
    )
    p.add_argument(
        "--format",
        choices=["ndjson", "csv"],
        default="ndjson",
        help="Output format (csv only valid for batch-csv feed)",
    )
    p.add_argument("-o", "--output", type=Path, help="Output file path")
    p.add_argument("-n", "--count", type=int, help="Row count (defaults match course lab locks)")
    p.add_argument("--seed", type=int, default=20260611, help="Random seed for reproducibility")
    p.add_argument(
        "--write-all-course-files",
        action="store_true",
        help="Write all feeds to ../data/ with default course counts",
    )
    p.add_argument(
        "--write-practice-seed",
        action="store_true",
        help="Regenerate day-01/queries/03-seed-practice-data.kql (2000 practice rows)",
    )
    p.add_argument(
        "--write-fallback-streaming-kql",
        action="store_true",
        help="Regenerate internal/scripts/fallback-streaming-bronze.kql (500 EH + 500 IoT rows)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.write_practice_seed:
        path = Path(__file__).resolve().parent.parent / "day-01" / "queries" / "03-seed-practice-data.kql"
        write_practice_seed_kql(path, seed=args.seed)
        print(f"Wrote practice seed -> {path}")
        return 0

    if args.write_fallback_streaming_kql:
        path = (
            Path(__file__).resolve().parent.parent
            / "internal"
            / "scripts"
            / "fallback-streaming-bronze.kql"
        )
        write_fallback_streaming_kql(path, seed=args.seed)
        print(f"Wrote fallback streaming KQL -> {path}")
        return 0

    if args.write_all_course_files:
        root = Path(__file__).resolve().parent.parent / "data"
        targets = [
            ("batch-json", root / "bronze" / "sec-app-logs.json", "ndjson"),
            ("batch-csv", root / "bronze" / "sec-web-logs.csv", "csv"),
            ("batch-csv", root / "bronze" / "sec-web-logs.ndjson", "ndjson"),
            ("eventhub", root / "streaming" / "sec-events-sample.json", "ndjson"),
            ("iot", root / "iot" / "device-telemetry.json", "ndjson"),
        ]
        for feed, path, fmt in targets:
            count = DEFAULT_COUNTS[feed]
            producer_cls = SCENARIOS["utility-cyber"][feed]
            producer = producer_cls(seed=args.seed)
            events = producer.iter_events(count)
            if fmt == "csv":
                write_csv(path, events, count)
            else:
                write_ndjson(path, events, count)
            print(f"Wrote {count} rows -> {path}")
        return 0

    if not args.feed or not args.output:
        print("error: --feed and -o/--output are required unless using --write-all-course-files", file=sys.stderr)
        return 2

    if args.format == "csv" and args.feed != "batch-csv":
        print("error: --format csv only applies to --feed batch-csv", file=sys.stderr)
        return 2

    count = args.count if args.count is not None else DEFAULT_COUNTS[args.feed]
    producer_cls = SCENARIOS[args.scenario][args.feed]
    producer = producer_cls(seed=args.seed)
    events = producer.iter_events(count)

    if args.format == "csv":
        write_csv(args.output, events, count)
    else:
        write_ndjson(args.output, events, count)

    print(f"Wrote {count} rows -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
