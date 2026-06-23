"""Checkpoint definitions aligned with 99-checkpoints.kql and lab profile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from adx_training_tools.config import Profile


@dataclass
class Checkpoint:
    id: str
    day: int
    query: str
    expected: dict[str, Any]
    compare: str = "eq"  # eq | gte


def build_checkpoints(profile: Profile) -> list[Checkpoint]:
    c = profile.counts
    return [
        Checkpoint(
            id="day1_practice",
            day=1,
            query="""
PracticeSecurityEvents
| summarize
    TotalRows = count(),
    AuthFailureCount = countif(EventType == "AuthFailure"),
    FirewallDenyCount = countif(EventType == "FirewallDeny"),
    DistinctEventTypes = dcount(EventType)
""",
            expected={
                "TotalRows": c.practice_security_events,
                "AuthFailureCount": c.auth_failure_day1,
                "FirewallDenyCount": c.firewall_deny_day1,
                "DistinctEventTypes": 8,
            },
        ),
        Checkpoint(
            id="day2_bronze",
            day=2,
            query="""
SecLogsRaw
| summarize
    TotalRows = count(),
    JsonRows = countif(RecordFormat == "JSON"),
    CsvRows = countif(RecordFormat == "CSV"),
    SourceFiles = dcount(SourceFile)
""",
            expected={
                "TotalRows": c.bronze_batch,
                "JsonRows": c.bronze_json,
                "CsvRows": c.bronze_csv,
                "SourceFiles": 2,
            },
        ),
        Checkpoint(
            id="day3_bronze",
            day=3,
            query="""
SecLogsRaw
| summarize
    TotalRows = count(),
    EventHubRows = countif(RecordFormat == "EventHub"),
    IoTRows = countif(RecordFormat == "IoT")
""",
            expected={
                "TotalRows": c.bronze_total,
                "EventHubRows": c.eventhub,
                "IoTRows": c.iot,
            },
        ),
        Checkpoint(
            id="day3_silver",
            day=3,
            query="""
SecLogsParsed
| summarize
    TotalRows = count(),
    AuthFailureCount = countif(EventType == "AuthFailure"),
    SourceSystems = dcount(SourceSystem)
""",
            expected={
                "TotalRows": c.silver,
                "AuthFailureCount": c.auth_failure_silver,
                "SourceSystems": c.source_systems,
            },
        ),
        Checkpoint(
            id="day4_threat_intel",
            day=4,
            query="ThreatIntelRef | count",
            expected={"Count": c.threat_intel},
        ),
        Checkpoint(
            id="day4_gold",
            day=4,
            query="SecLogsHourly | summarize TotalEvents = sum(EventCount)",
            expected={"TotalEvents": c.gold_sum_event_count},
        ),
        Checkpoint(
            id="day5_pipeline_ready",
            day=5,
            query="""
print Ready = (
    toscalar(SecLogsParsed | count) == 3500
    and toscalar(ThreatIntelRef | count) == 8
    and toscalar(SecLogsHourly | summarize sum(EventCount)) == 3500
)
""",
            expected={"Ready": True},
        ),
        Checkpoint(
            id="day5_totals_match",
            day=5,
            query="""
print TotalsMatch = (
    toscalar(SecLogsParsed | count) == toscalar(SecLogsHourly | summarize sum(EventCount))
)
""",
            expected={"TotalsMatch": True},
        ),
        Checkpoint(
            id="day5_rls",
            day=5,
            query="RlsDemoEvents | count",
            expected={"Count": c.rls_demo},
        ),
        Checkpoint(
            id="day5_scada_auth_failure",
            day=5,
            query="""
SecLogsParsed
| where DestinationHost == "scada-gw.utility.local" and EventType == "AuthFailure"
| count
""",
            expected={"Count": 1},
            compare="gte",
        ),
        Checkpoint(
            id="day5_scada_threat_enriched",
            day=5,
            query="""
SecLogsParsed
| where DestinationHost == "scada-gw.utility.local" and EventType == "AuthFailure"
| join hint.strategy=shuffle kind=inner (
    ThreatIntelRef | where MatchType == "SourceIP" | project MatchKey
) on $left.SourceIP == $right.MatchKey
| count
""",
            expected={"Count": 1},
            compare="gte",
        ),
        Checkpoint(
            id="day5_threat_join",
            day=5,
            query="""
SecLogsParsed
| join kind=leftouter (
    ThreatIntelRef
    | where MatchType == "SourceIP"
) on $left.SourceIP == $right.MatchKey
| where isnotempty(ThreatCategory)
| count
""",
            expected={"Count": 1},
            compare="gte",
        ),
    ]
