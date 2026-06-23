# ADX data producer

Python scripts that **generate the sample files** consumed by ADX in this course. Same pattern works for any domain: produce files → stage on Blob/ADLS → ingest into ADX.

**No pip packages required** — Python 3.10+ standard library only.

---

## End-to-end flow

```text
  produce.py (this folder)
        |
        v
  NDJSON / CSV files  ----upload---->  ADLS training-data/...
        |                                    |
        |                                    v
        +---------------------------->  ADX .ingest (Day 2)
        |                              Event Hub / IoT replay (Day 3)
        v
  data/bronze/, data/streaming/, data/iot/
```

Committed files under [`data/`](../data/) were built with this producer. Course maintainers can regenerate at any scale (not part of the student repo tooling).

---

## Quick start

From this directory:

```bash
# Regenerate all course files (1500 + 1000 + 500 + 500 rows)
python produce.py --write-all-course-files

# Regenerate Day 1 practice seed KQL (2000 rows; AuthFailure 400; High+Critical 800)
python produce.py --write-practice-seed

# Regenerate maintainer fallback when Event Hub / IoT Hub unavailable (500 + 500 rows)
python produce.py --write-fallback-streaming-kql

# One feed only
python produce.py --feed batch-json -n 1500 -o ../data/bronze/sec-app-logs.json
python produce.py --feed batch-csv --format csv -n 1000 -o ../data/bronze/sec-web-logs.csv
python produce.py --feed eventhub -n 500 -o ../data/streaming/sec-events-sample.json
python produce.py --feed iot -n 500 -o ../data/iot/device-telemetry.json
```

---

## Feeds and lab files

| `--feed` | Output shape | ADX path | Day |
|----------|--------------|----------|-----|
| `batch-json` | NDJSON security app logs | `SecLogsRaw` via Blob | Day 2 |
| `batch-csv` | CSV or NDJSON web logs | `SecLogsRaw` via Blob | Day 2 |
| `eventhub` | NDJSON stream events | Event Hub → `SecLogsRaw` | Day 3 |
| `iot` | NDJSON device telemetry | IoT Hub → `SecLogsRaw` | Day 3 |

Default counts match lab checkpoints: **2500** Bronze after Day 2, **3500** after Day 3. Event-type distributions are **exact** (not approximate) — e.g. AuthFailure **700** in Silver after Day 3 (**300** JSON + **200** CSV + **200** Event Hub). See [`data/README.md`](../data/README.md) and `tools/profiles/lab.yaml`.

---

## Extend to another use case

1. Copy `utility_cyber.py` → `my_domain.py` with your event templates.
2. Subclass `EventProducer` in `produce.py` (see `UtilityCyberBatchJsonProducer`).
3. Register under `SCENARIOS["my-domain"]`.
4. Run `python produce.py --scenario my-domain --feed batch-json -n 5000 -o out.ndjson`.

Each event dict should include **`Timestamp`** (ISO-8601 UTC) plus fields your ADX Silver update policy will parse from `RawPayload`.

Example skeleton:

```python
class RetailClickstreamProducer(EventProducer):
    def event_at(self, index: int, base_time: datetime) -> dict[str, Any]:
        return {
            "Timestamp": (base_time + timedelta(seconds=index)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "SessionId": f"s-{index % 100}",
            "Page": "/checkout",
            "UserId": f"user-{index % 50}",
        }
```

Stage the file on Blob, create an ingestion mapping, and `.ingest into table` — same ADX path as this course.

---

## Reproducibility

`--seed` fixes IP variation and jitter so two runs with the same count produce identical files. Course default seed: **20260611**.

**ThreatIntel IPs (Day 4):** `utility_cyber.PINNED_SOURCE_IPS` lists SourceIP values in `ThreatIntelRef` (`10.20.1.44`, `203.0.113.50`, …). The producer **does not vary** these addresses so join labs return `BruteForceTarget`, `ExternalScanner`, and related categories.

---

See also: [`data/README.md`](../data/README.md) · [Day 2 batch ingest](../day-02/README.md)
