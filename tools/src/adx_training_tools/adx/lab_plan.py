"""Ordered lab execution plan aligned with dry-run-master-execution.md."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from adx_training_tools.config import find_gh_root


@dataclass
class LabStep:
    day: int
    step_id: str
    path: Path | None
    label: str
    requires_storage: bool = False
    use_fallback_streaming: bool = False
    send_streaming: str | None = None  # "eventhub" | "iot"
    optional: bool = False


def _q(day: int, filename: str) -> Path:
    return find_gh_root() / f"day-{day:02d}" / "queries" / filename


def _script(name: str) -> Path:
    return find_gh_root() / "internal" / "scripts" / name


def build_lab_plan(use_streaming_fallback: bool = True) -> list[LabStep]:
    """Full course execution order (Days 1–5)."""
    steps: list[LabStep] = []

    for sid, fname, label in [
        ("1.0", "01-show-cluster-and-database.kql", "Show cluster and databases"),
        ("1.1", "00-create-your-database.kql", "Create your workspace database"),
        ("1.2", "02-create-practice-table.kql", "Create practice table"),
        ("1.3", "03-seed-practice-data.kql", "Seed 2000 practice rows"),
        ("1.4", "04-filters-project-extend.kql", "Filters and extend"),
        ("1.5", "05-summarize-timechart.kql", "Summarize and timechart"),
        ("1.6", "06-parse-and-management.kql", "Parse and management"),
        ("1.7", "07-scenario-investigations.kql", "Scenario SOC investigations"),
    ]:
        steps.append(LabStep(1, sid, _q(1, fname), label))

    for sid, fname, label, storage in [
        ("2.1", "01-ingestion-commands.kql", "Ingestion commands", False),
        ("2.2", "02-create-bronze-table.kql", "Create SecLogsRaw", False),
        ("2.3", "03-create-json-mapping.kql", "JSON mapping", False),
        ("2.4", "04-ingest-json-batch.kql", "Ingest JSON batch", True),
        ("2.5", "05-create-csv-mapping.kql", "CSV mapping", False),
        ("2.6", "06-ingest-csv-batch.kql", "Ingest CSV batch", True),
        ("2.7", "07-verify-bronze.kql", "Verify bronze 2500 rows", False),
    ]:
        steps.append(LabStep(2, sid, _q(2, fname), label, requires_storage=storage))

    steps.append(LabStep(3, "3.1", _q(3, "01-verify-bronze-baseline.kql"), "Verify bronze baseline"))
    steps.append(
        LabStep(3, "3.1b", _q(3, "00-enable-streaming-ingest.kql"), "Enable streaming ingestion on SecLogsRaw")
    )
    steps.append(LabStep(3, "3.2", _q(3, "02-eventhub-connection.kql"), "Event Hub mapping"))
    if use_streaming_fallback:
        steps.append(
            LabStep(
                3,
                "3.2f",
                _script("fallback-streaming-bronze.kql"),
                "Fallback Event Hub simulation (500 rows)",
                use_fallback_streaming=True,
            )
        )
    else:
        steps.append(
            LabStep(
                3,
                "3.2b",
                None,
                "Send 5 Event Hub sample messages",
                send_streaming="eventhub",
            )
        )
    steps.append(LabStep(3, "3.3", _q(3, "03-iot-hub-connection.kql"), "IoT mapping"))
    if use_streaming_fallback:
        steps.append(
            LabStep(
                3,
                "3.3f",
                _script("fallback-streaming-bronze.kql"),
                "Fallback IoT simulation (500 rows)",
                use_fallback_streaming=True,
            )
        )
    else:
        steps.append(
            LabStep(
                3,
                "3.3b",
                None,
                "Send 5 IoT sample messages",
                send_streaming="iot",
            )
        )
    steps.append(
        LabStep(3, "3.8", _q(3, "08-iot-telemetry-bronze.kql"), "IoT telemetry bronze analysis")
    )
    for sid, fname, label in [
        ("3.4", "04-create-silver-table.kql", "Create SecLogsParsed"),
        ("3.5", "05-update-policy-backfill.kql", "Update policy + backfill"),
        ("3.6", "06-verify-silver.kql", "Verify silver"),
        ("3.9", "09-iot-telemetry-silver.kql", "IoT telemetry silver analysis"),
        ("3.7", "07-silver-investigation.kql", "Silver investigation"),
    ]:
        steps.append(LabStep(3, sid, _q(3, fname), label))

    for sid, fname, label in [
        ("4.1", "01-verify-silver-baseline.kql", "Silver baseline"),
        ("4.2", "02-threatintel-join.kql", "Threat intel join"),
        ("4.2v", "02-verify-threatintel.kql", "Verify ThreatIntelRef"),
        ("4.3", "03-time-series.kql", "Time series"),
        ("4.4", "04-anomaly-detection.kql", "Anomaly detection"),
        ("4.5", "05-window-functions.kql", "Window functions"),
        ("4.6", "06-create-udf.kql", "Create UDFs"),
        ("4.7", "07-gold-materialized-view.kql", "Gold materialized view"),
        ("4.7v", "07-verify-gold.kql", "Verify Gold MV"),
    ]:
        steps.append(LabStep(4, sid, _q(4, fname), label))

    for sid, fname, label in [
        ("5.0", "00-verify-pipeline-baseline.kql", "Pipeline gate"),
        ("5.1", "01-query-optimization.kql", "Query optimization"),
        ("5.2", "02-ingestion-tuning.kql", "Ingestion tuning"),
        ("5.3", "03-hint-strategy.kql", "hint.strategy"),
        ("5.4", "04-mv-vs-ondemand.kql", "MV vs on-demand"),
        ("5.4v", "04-verify-mv-parity.kql", "Verify MV parity"),
        ("5.5", "05-security-rbac-rls.kql", "Security RBAC RLS"),
        ("5.5v", "05-verify-rlsdemo.kql", "Verify RlsDemoEvents"),
        ("5.6", "06-monitoring-diagnostics.kql", "Monitoring"),
        ("5.7", "07-capstone-investigation.kql", "Capstone"),
        ("5.7v", "07-verify-capstone.kql", "Verify capstone"),
    ]:
        steps.append(LabStep(5, sid, _q(5, fname), label))

    return steps


def build_day_plan(day: int, use_streaming_fallback: bool = True) -> list[LabStep]:
    return [s for s in build_lab_plan(use_streaming_fallback) if s.day == day]
