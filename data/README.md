# Sample data

**Domain:** Energy and Utility — Cyber Security  
**Used in:** Day 2 (Bronze batch), Day 3 (Event Hub + IoT streaming), Day 5 (capstone references)

---

## Layout

```text
data/
  bronze/
    sec-app-logs.json           # 1500 NDJSON — Day 2 Lab 4
    sec-web-logs.csv            # 1000 rows + header — Day 2 Lab 5 ingest
    sec-web-logs.ndjson         # same 1000 rows as NDJSON (derived copy for tooling)
  streaming/
    sec-events-sample.json      # 500 NDJSON — Day 3 Lab 2 (Event Hub)
  iot/
    device-telemetry.json       # 500 NDJSON — Day 3 Lab 3 (IoT Hub)
```

---

## Bronze files (Day 2)

| File | Format | Rows | Staged ADLS path |
|------|--------|------|------------------|
| `bronze/sec-app-logs.json` | NDJSON | **1500** | `training-data/bronze/sec-app-logs.json` |
| `bronze/sec-web-logs.csv` | CSV | **1000** | `training-data/bronze/sec-web-logs.csv` |
| `bronze/sec-web-logs.ndjson` | NDJSON | **1000** | `training-data/bronze/sec-web-logs.ndjson` (derived; not used in labs) |

**`SecLogsRaw` after Day 2:** **2500** rows (1500 JSON + 1000 CSV)

Lab 5 ingests **`sec-web-logs.csv`** with native **`format='csv'`** into staging table **`SecLogsCsvStg`**, then promotes to Bronze with **`RecordFormat = CSV`**. The NDJSON copy is kept for data tooling parity only.

---

## Streaming files (Day 3)

| File | Format | Rows | Use |
|------|--------|------|-----|
| `streaming/sec-events-sample.json` | NDJSON | **500** | Published to Event Hub `sec-events` during Lab 2 |
| `iot/device-telemetry.json` | NDJSON | **500** | Published through IoT Hub during Lab 3 |

Lab steps: [day-03/labs.md](../day-03/labs.md) (Before Labs 2–3 + Labs 2–3).

**`SecLogsRaw` after Day 3 Labs 2–3:** **3500** rows (+500 EventHub, +500 IoT)  
**`SecLogsParsed` after Day 3 Lab 5:** **3500** rows

---

## Event type reference (AuthFailure = 700 in Silver after Day 3)

| Source | AuthFailure count |
|--------|-------------------|
| Batch JSON | 300 |
| Batch CSV | 200 |
| Event Hub stream | 200 |
| IoT stream | 0 |
| **Total** | **700** |

---

## Field schema (all files)

`Timestamp`, `EventType`, `SourceIP`, `DestinationHost`, `UserPrincipal`, `Severity`, `Message`, `Facility`

IoT lines may include `deviceId` and IoT-specific **`EventType`** values such as **`SensorAnomaly`**, **`DeviceHeartbeat`**, **`ConfigChange`**, and **`FirewallDeny`**. Bronze stores the full object in `RawPayload`; Silver extracts typed columns via update policy.

**ThreatIntel join (Day 4):** five SourceIP keys in `ThreatIntelRef` are preserved in generated data (`10.20.1.44`, `203.0.113.50`, `203.0.113.80`, `10.20.8.1`, `10.20.9.3`) so **`BruteForceTarget`** and other categories enrich on join. The last IP is prominent in IoT **`SensorAnomaly`** at **`Substation-D`** (Labs 8–9).

## Day 5 capstone (SCADA gateway)

**Lab 7 ticket:** authentication failures against **`scada-gw.utility.local`**.

| Anchor | Value | Source |
|--------|-------|--------|
| Destination host | `scada-gw.utility.local` | Batch JSON + Event Hub stream |
| Threat IP | **`10.20.1.44`** | Batch JSON (`bronze/sec-app-logs.json`) |
| Threat category | **`BruteForceTarget`** | `ThreatIntelRef` (Day 4 Lab 2) |
| Facility | **`Substation-A`** | AuthFailure rows on gateway |
| Gold KPI | `SecLogsHourly` AuthFailure buckets | Day 4 Lab 7 MV |

Event Hub stream adds many additional **`AuthFailure`** rows on the same gateway host (different SourceIPs). Capstone Step 3 matches when **`10.20.1.44`** appears in Step 2 — batch JSON path.

---

**IoT telemetry event mix (500 rows in `iot/device-telemetry.json`):**

| EventType | Count |
|-----------|------:|
| `SensorAnomaly` | **200** |
| `DeviceHeartbeat` | **100** |
| `ConfigChange` | **100** |
| `FirewallDeny` | **100** |

| deviceId | Count |
|----------|------:|
| `substation-sensor-01` | **200** |
| `substation-sensor-02` | **200** |
| `substation-sensor-03` | **100** |

---

## Regenerate sample files

Course files are produced by the [Python data producer](../producer/README.md):

```bash
cd producer
python produce.py --write-all-course-files
```

Use `--feed`, `--count`, and `-o` to generate custom volumes for your own ADLS paths or extended use cases.

