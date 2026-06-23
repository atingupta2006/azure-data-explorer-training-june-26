# Day 03 — Streaming Ingestion, IoT Hub & Silver Layer

## Learning objectives

* Ingest streaming events via Event Hub and IoT Hub data connections
* **Analyze IoT device telemetry** on Bronze and Silver (Labs 8–9)
* Create **`SecLogsParsed`** and apply update policy with backfill
* Verify Silver locked counts (**3500** rows, AuthFailure **700**)
* Investigate typed Silver columns and **`SourceSystem`** lineage

**Prerequisite:** Day 2 — `SecLogsRaw` with **2500** Bronze rows in **your database**.

**Hands-on:** [labs.md](labs.md) | **Queries:** [queries/](queries/) | **Policies:** [policies-guide.md](policies-guide.md) (Labs 4–5) | **Sample files:** [data/README.md](../data/README.md)

**New to policies?** Read [policies-guide.md](policies-guide.md) before Labs 4–5.

### Document map

| Section | Topic | Labs |
|---------|--------|------|
| [1](#1-pipeline-recap--bronze-to-silver) | Pipeline recap, locked counts | Lab 1 |
| [2](#2-streaming-ingestion-concepts) | Batch vs streaming, engines, policies | Before Labs 2–3 |
| [3](#3-streaming-data-connections-event-hub--iot-hub) | Event Hub & IoT (summary) | Labs 2–3 |
| [3.7](#37-analyzing-iot-telemetry-on-bronze-lab-8) | IoT telemetry analysis on Bronze | **Lab 8** |
| — | **Class lead hub setup (Portal)** | [labs.md — Before Labs 2–3](labs.md#before-labs-23) |
| — | **Send sample file → hub (reference)** | [labs.md — Send sample file → hub](labs.md#send-sample-file--hub-in-class--reference-for-later) |
| — | **Event Hub E2E troubleshooting** | [eventhub-ingest-troubleshooting-runbook.md](eventhub-ingest-troubleshooting-runbook.md) |
| [4](#4-day-2-prerequisite--batch-bronze-recap) | Day 2 batch recap (native CSV path) | Lab 1 gate |
| [5](#5-kafka-and-logstash-architecture-only) | Kafka / Logstash architecture | Lab 6 (discussion) |
| [6](#6-silver--seclogsparsed-and-update-policies) | Silver schema, update policy, backfill | Labs 4–5 |
| [6.10](#610-iot-telemetry-on-silver-lab-9) | IoT telemetry analysis on Silver | **Lab 9** |
| [7](#7-silver-investigation-lab-7) | Investigation queries on typed Silver | Lab 7 |

---


# 1. Pipeline recap — Bronze to Silver

Day 3 completes **Bronze/Silver end-to-end**. Earlier modules taught KQL and **batch landing** in Bronze. Here you **extend Bronze with streaming**, then **parse into Silver** using an ADX **update policy** ([Microsoft — update policy overview](https://learn.microsoft.com/en-us/kusto/management/update-policy?view=microsoft-fabric)).

## 1.1 What this module adds to the pipeline

```text
  ALREADY IN BRONZE (batch)             THIS MODULE

  PracticeSecurityEvents                (KQL practice table — not in pipeline)
  SecLogsRaw (2500 batch rows)   +    +500 Event Hub stream
                                    +500 IoT Hub stream
                                    ──► SecLogsRaw (3500)
                                              │
                                              │ update policy
                                              ▼
                                        SecLogsParsed (3500 typed rows)
```

| Step | Mechanism | Microsoft doc anchor |
|------|-----------|----------------------|
| Verify Bronze baseline | KQL `count` | Lab 1 |
| Stream to Bronze | Event Hub / IoT **data connections** | [Ingest from Event Hubs](https://learn.microsoft.com/en-us/azure/data-explorer/ingest-data-event-hub-overview) |
| Parse to Silver | **Update policy** on target table | [Update policy overview](https://learn.microsoft.com/en-us/kusto/management/update-policy?view=microsoft-fabric) · [policies-guide.md](policies-guide.md) |
| Backfill Silver | `.set-or-append` (one-time) | [Update policy tutorial](https://learn.microsoft.com/en-us/kusto/management/update-policy-tutorial?view=microsoft-fabric) |

## 1.2 Medallion layers — Bronze and Silver roles

| Layer | Table | Schema style | Action in this module |
|-------|--------|--------------|------------------------|
| **Bronze** | `SecLogsRaw` | 4 columns + **`RawPayload` dynamic** | Add **1000** streaming rows → **3500** total |
| **Silver** | `SecLogsParsed` | **Typed** security columns | Create table + **update policy** + backfill → **3500** rows |
| **Gold** | `SecLogsHourly` | Hourly aggregates | Materialized view (separate module) |

```text
  BRONZE (land)                         SILVER (parse)

  IngestionTime                         Timestamp
  SourceFile                            EventType, SourceIP, ...
  RecordFormat                          SourceSystem  ← lineage
  RawPayload { dynamic }    ──policy──►  typed columns for SOC queries
```

Bronze answers: *what arrived and from which source?* Silver answers: *what are the typed fields for investigation and dashboards?*

## 1.3 Bronze state before streaming labs

After batch ingest labs, **`SecLogsRaw`** should contain **2500 rows** from batch ingest only:

| RecordFormat | SourceFile | Rows | Origin |
|--------------|------------|------|--------|
| `JSON` | `sec-app-logs.json` | **1500** | Blob `.ingest` + `SecLogsRaw_JsonMapping` (Day 2 Lab 4) |
| `CSV` | `sec-web-logs.csv` | **1000** | Native CSV → `SecLogsCsvStg` → `.append` to Bronze (Day 2 Lab 5) |

You may also see staging table **`SecLogsCsvStg`** in `.show tables` — that is the Day 2 CSV landing table; Bronze rows use **`RecordFormat = CSV`** and **`SourceFile = sec-web-logs.csv`** after promotion.

**Lab 1** verifies this baseline before any streaming or Silver work. If count ≠ **2500**, stop and complete Day 2 Labs 4–5 before continuing.

```kql
SecLogsRaw | count                                              // expect 2500
SecLogsRaw | summarize count() by RecordFormat, SourceFile   // Lab 1
```

## 1.4 Locked counts — Day 3 checkpoints

| Checkpoint | Table | Query | Expected |
|------------|-------|-------|----------|
| After Lab 1 | Bronze | `SecLogsRaw \| count` | **2500** |
| After Lab 2 | Bronze | `RecordFormat == "EventHub"` | **500** (total **3000**) |
| After Lab 3 | Bronze | `RecordFormat == "IoT"` | **500** (total **3500**) |
| After Lab 5 | Silver | `SecLogsParsed \| count` | **3500** |
| After Lab 7 | Silver | AuthFailure filter | **700** |
| After Lab 7 | Silver | `dcount(SourceSystem)` | **4** |

Reference: locked counts in [labs.md](labs.md).

### SourceSystem values (Silver lineage)

| SourceSystem | Bronze origin |
|--------------|---------------|
| `Batch-JSON` | Batch JSON file |
| `Batch-CSV` | Batch CSV export |
| `EventHub` | Event Hub stream |
| `IoT-Hub` | IoT Hub stream |

# 2. Streaming ingestion concepts

Batch files land with **`.ingest`**. **Continuous ingest** uses **Event Hub** and **IoT Hub data connections** into the same **`SecLogsRaw`** table. This section explains how streaming fits the pipeline before streaming labs.

## 2.1 Batch vs continuous

| Dimension | Batch | Streaming |
|-----------|-------|-----------|
| **Transport** | Blob / ADLS files | Event Hub, IoT Hub |
| **Trigger** | Manual `.ingest` or blob event | Messages arrive continuously |
| **Latency (typical)** | Seconds–minutes (queued) | Seconds (streaming policy + connection) |
| **Utility cyber use** | Nightly exports, backfill | Live auth failures, device anomalies |
| **ADX mechanism** | **`.ingest into table`** | **Data connection** + mapping |
| **Bronze growth (labs)** | **2500** rows | **+1000** streaming rows → **3500** total |

```text
  BATCH (Blob)                          STREAMING (hubs)

  sec-app-logs.json   ──.ingest──►      Event Hub sec-events ──connection──►
  sec-web-logs.csv    ──.ingest──►      IoT Hub iot-adx-tcs   ──connection──►
        │                                        │
        └──────────────── SecLogsRaw (same Bronze table) ────────────────┘
```

Day 2 CSV uses staging table **`SecLogsCsvStg`** then **`.append`** to `SecLogsRaw` — the diagram above shows the **logical** landing in Bronze, not the staging step.

## 2.2 Two axes — transport vs engine (do not conflate)

Keep both axes in mind:

```text
  AXIS 1 — SOURCE                       AXIS 2 — ADX ENGINE

  Continuous Event Hub / IoT           Queued ingestion (default, high throughput)
  (not a file drop)                    Streaming ingestion (low latency, table policy)
```

| Term | Meaning in this course |
|------|------------------------|
| **Streaming source** | Event Hub / IoT Hub publish events continuously |
| **Data connection** | ADX-managed link from hub → table (not `.ingest` per message) |
| **Streaming ingestion policy** | Table-level setting enabling fast landing path |
| **Queued engine** | Microsoft default for high volume ([ingestion overview](https://learn.microsoft.com/en-us/azure/data-explorer/ingest-data-overview#continuous-data-ingestion)) |

Event Hub and IoT Hub connections can use **queued** or **streaming** engine depending on **streaming ingestion policy** on the target table ([configure streaming ingestion](https://learn.microsoft.com/en-us/azure/data-explorer/ingest-data-streaming)).

## 2.3 Data connection vs `.ingest`

| Aspect | Blob `.ingest` | Hub data connection |
|--------|----------------|---------------------|
| Who pulls data | You run a KQL command | ADX service reads from hub continuously |
| Source | Blob URI + managed identity | Event Hub: cluster **managed identity**; IoT Hub: **shared access policy** (`iothubowner`) |
| Mapping | `ingestionMappingReference` in `with` clause | Mapping name on connection |
| Your action | Paste URI, run `.ingest` | Mapping in Web UI; **data connection in Azure Portal** |
| Stops when | File ingested | Connection deleted or hub idle |

```text
  .ingest from Blob                    Data connection from hub

  Analyst runs command               ADX reads hub via your consumer group
         |                                    |
         v                                    v
  Queued ingest job                  Continuous ingest into SecLogsRaw
```

Microsoft pipeline ([Event Hubs overview](https://learn.microsoft.com/en-us/azure/data-explorer/ingest-data-event-hub-overview)): create hub → create target table → create **data connection** → events flow while connection is active.

## 2.4 Prerequisites — cluster capability and table policy

Before Event Hub / IoT messages land in **`SecLogsRaw`**, two layers must be ready:

| Layer | Course action |
|-------|---------------|
| **Cluster** streaming capability | Enabled on `adx-training-tcs` (training cluster) |
| **Table** streaming ingestion policy | [queries/00-enable-streaming-ingest.kql](queries/00-enable-streaming-ingest.kql) in your database |

```kql
.alter table SecLogsRaw policy streamingingestion enable

.show table SecLogsRaw policy streamingingestion
```

Microsoft notes ([streaming ingestion policy](https://learn.microsoft.com/en-us/kusto/management/streaming-ingestion-policy?view=azure-data-explorer)):

* **Cluster-level** streaming must be enabled before table/database policy works.
* Table policy can also be set at **database** level; table setting overrides database.
* If a table receives data **only via update policy**, it may not need its own streaming policy.

Lab scale uses **500 events per hub** — far below production thresholds (streaming suits low-latency; above ~4 GB/hour per table, consider queued — [configure streaming](https://learn.microsoft.com/en-us/azure/data-explorer/ingest-data-streaming)).

## 2.5 Queued vs streaming engine on hub connections

| Engine | Latency | When Microsoft recommends |
|--------|---------|---------------------------|
| **Queued** | Seconds–minutes | **Default** — higher throughput, most scenarios |
| **Streaming** | Near real-time (seconds) | Low-latency monitoring when table policy enabled |

```text
  Event Hub message
         |
         +---- streaming policy ON  ──► streaming engine (fast path)
         |
         +---- streaming policy OFF ──► queued engine (still continuous source)
```

Utility SOC pattern: stream **authentication** and **VPN** events for live dashboards; keep **nightly CSV** on Day 2 batch path from ADLS.

## 2.6 Locked Bronze counts after streaming labs

| After lab | `SecLogsRaw \| count` | Filter check |
|-----------|----------------------|--------------|
| Lab 1 (baseline) | **2500** | JSON 1500 + CSV 1000 |
| Lab 2 (Event Hub) | **3000** | `RecordFormat == "EventHub"` → **500** |
| Lab 3 (IoT Hub) | **3500** | `RecordFormat == "IoT"` → **500** |

```kql
SecLogsRaw | summarize count() by RecordFormat
```

All four formats (`JSON`, `CSV`, `EventHub`, `IoT`) later parse to Silver via **one update policy** (Labs 4–5).

# 3. Streaming data connections (Event Hub & IoT Hub)

Both streaming labs use the same pattern: **mapping (Web UI) → verify mapping (Web UI) → data connection (Portal) → class sends sample → verify (Web UI)**. Hub setup and connection forms are in [labs.md](labs.md) **Before Labs 2–3** and Labs 2–3.

## 3.1 Shared pattern

| Step | Action | Where |
|------|--------|-------|
| 1 | Streaming policy on `SecLogsRaw` ([00-enable-streaming-ingest.kql](queries/00-enable-streaming-ingest.kql)) | **dataexplorer.azure.com** |
| 2 | Create JSON mapping (Step 1 in lab query file) | **dataexplorer.azure.com** |
| 3 | **Verify mapping** with inline ingest ([02-verify-eventhub-mapping.kql](queries/02-verify-eventhub-mapping.kql) or [03-verify-iot-mapping.kql](queries/03-verify-iot-mapping.kql)) | **dataexplorer.azure.com** |
| 4 | Create **data connection** ([labs.md](labs.md) Lab 2 or 3) | **Azure Portal** → **`adx-training-tcs`** → **Databases** → your DB → **Data ingestion** or **Data connections** |
| 5 | Publish **500** messages per hub from sample files | [labs.md — send reference](labs.md#send-sample-file--hub-in-class--reference-for-later) (class lead in room; students use same steps later) |
| 6 | Verify locked counts (Step 2 in query file) | **dataexplorer.azure.com** |

ADX reads message **body** as **MULTIJSON** into the same four Bronze columns as Day 2. Each student needs their **own** consumer group on Event Hub (Lab 2); all students share **`adx`** on IoT Hub (Lab 3, class-precreated). Events must be sent **after** the connection exists.

## 3.2 Event Hub (Lab 2)

| Item | Value |
|------|-------|
| Namespace / hub | `eh-adx-tcs` / **`sec-events`** |
| Consumer group | **New group per student** in ADX form (**+ Create new**; not `$Default`) |
| Mapping | **`SecLogsRaw_EventHubMapping`** — [02-eventhub-connection.kql](queries/02-eventhub-connection.kql) |
| `SourceFile` / `RecordFormat` | `sec-events` / `EventHub` |
| Sample | [sec-events-sample.json](../data/streaming/sec-events-sample.json) — **500** messages |
| Locked count | Bronze **2500 → 3000** |

Hands-on: [labs.md](labs.md) Lab 2.

Mapping: `IngestionTime` ← `$.Timestamp`, `RawPayload` ← `$`, constants for lineage columns.

```kql
.create-or-alter table SecLogsRaw ingestion json mapping 'SecLogsRaw_EventHubMapping' '[{"column":"IngestionTime","properties":{"path":"$.Timestamp"}},{"column":"SourceFile","properties":{"ConstValue":"sec-events"}},{"column":"RecordFormat","properties":{"ConstValue":"EventHub"}},{"column":"RawPayload","properties":{"path":"$"}}]'
```

Full file: [02-eventhub-connection.kql](queries/02-eventhub-connection.kql).

## 3.3 IoT Hub (Lab 3)

| Item | Value |
|------|-------|
| Hub / consumer group | **`iot-adx-tcs`** / select existing **`adx`** (do not create new) |
| Mapping | **`SecLogsRaw_IoTMapping`** — [03-iot-hub-connection.kql](queries/03-iot-hub-connection.kql) |
| `SourceFile` / `RecordFormat` | `iot-device-telemetry` / `IoT` |
| Sample | [device-telemetry.json](../data/iot/device-telemetry.json) — **500** messages |
| Locked count | Bronze **3000 → 3500** |

Hands-on: [labs.md](labs.md) Lab 3.

Payload may include **`deviceId`** in the JSON body (Silver **`SourceSystem = IoT-Hub`** in Lab 5). **Prerequisite:** Lab 2 complete.

```kql
.create-or-alter table SecLogsRaw ingestion json mapping 'SecLogsRaw_IoTMapping' '[{"column":"IngestionTime","properties":{"path":"$.Timestamp"}},{"column":"SourceFile","properties":{"ConstValue":"iot-device-telemetry"}},{"column":"RecordFormat","properties":{"ConstValue":"IoT"}},{"column":"RawPayload","properties":{"path":"$"}}]'
```

Full file: [03-iot-hub-connection.kql](queries/03-iot-hub-connection.kql).

## 3.4 Verify and diagnose

```kql
SecLogsRaw | summarize count() by RecordFormat
// JSON 1500, CSV 1000, EventHub 500, IoT 500 → total 3500
.show ingestion failures
.show table SecLogsRaw ingestion mappings   // expect 3 on SecLogsRaw: Json, EventHub, IoT (Day 2 CSV mapping is on SecLogsCsvStg)
```

| Symptom | Action |
|---------|--------|
| Count unchanged after send | Data connection not ready or events sent too early — wait, then re-run count |
| Mapping error | Run Step 1 in the lab query file |
| Auth error | Report connection error; cluster identity needs Event Hub / IoT Hub access |

## 3.5 Worked example — hub message → Bronze row

Streaming labs reuse the **same four Bronze columns** as Day 2. The hub delivers a JSON **body**; the **ingestion mapping** fills `IngestionTime`, `SourceFile`, `RecordFormat`, and `RawPayload`.

**Event Hub sample message** (one line from [sec-events-sample.json](../data/streaming/sec-events-sample.json)):

```json
{"EventType":"AuthFailure","SourceIP":"10.20.8.1","DestinationHost":"vpn.utility.local","UserPrincipal":"field@utility.com","Severity":"High","Message":"Streaming auth failure","Facility":"Corporate-VPN","Timestamp":"2026-06-11T09:00:00Z"}
```

**`SecLogsRaw_EventHubMapping`** (Lab 2) maps it to:

| Bronze column | Value |
|---------------|-------|
| `IngestionTime` | `2026-06-11T09:00:00Z` (from `$.Timestamp`) |
| `SourceFile` | `sec-events` (constant) |
| `RecordFormat` | `EventHub` (constant) |
| `RawPayload` | entire JSON object (`$`) |

**IoT sample message** (from [device-telemetry.json](../data/iot/device-telemetry.json)):

```json
{"deviceId":"substation-sensor-01","EventType":"SensorAnomaly","SourceIP":"10.20.9.10","DestinationHost":"iot-gateway.utility.local","UserPrincipal":"","Severity":"High","Message":"Temperature spike near access panel","Facility":"Substation-C","Timestamp":"2026-06-11T09:00:00Z"}
```

**`SecLogsRaw_IoTMapping`** sets `SourceFile = iot-device-telemetry`, `RecordFormat = IoT`. Extra fields like **`deviceId`** stay inside `RawPayload` until Silver (Lab 5) extracts typed columns.

```kql
// Peek one streaming row after Labs 2–3
SecLogsRaw
| where RecordFormat == "EventHub"
| take 1
| project IngestionTime, SourceFile, RecordFormat, EventType = RawPayload.EventType, SourceIP = RawPayload.SourceIP
```

## 3.6 Azure hub setup (class demo)

Full Portal steps (including **Send events** demo and IoT test message) are in [labs.md — Before Labs 2–3](labs.md#event-hub--class-lead-creates-before-lab-2). Summary:

**Event Hub** — namespace **`eh-adx-tcs`**, hub **`sec-events`**, IAM **Azure Event Hubs Data Receiver** for **`adx-training-tcs`**, cluster streaming ingestion **On**.

**IoT Hub** — **`iot-adx-tcs`**, devices **`substation-sensor-01..03`**, consumer group **`adx`** on built-in **Events** endpoint. ADX IoT connection uses shared access policy **`iothubowner`** (not managed identity).

## 3.7 Analyzing IoT telemetry on Bronze (Lab 8)

After Lab 3 lands **500** IoT rows, analysts can explore **device telemetry** on **`SecLogsRaw`** before Silver exists. IoT messages use the same four Bronze columns; sensor fields live in **`RawPayload`**.

```text
  device-telemetry.json (500 lines)
           │
           v
  IoT Hub ──connection──► SecLogsRaw  (RecordFormat = IoT)
           │
           │  Lab 8 KQL — query RawPayload.*
           v
  EventType / deviceId / Facility breakdowns
           │
           │  Lab 4–5 update policy
           v
  SecLogsParsed  (SourceSystem = IoT-Hub)  →  Lab 9
```

**Locked IoT telemetry counts** ([device-telemetry.json](../data/iot/device-telemetry.json)):

| Dimension | Breakdown |
|-----------|-----------|
| **Total** | **500** rows |
| **EventType** | `SensorAnomaly` **200**, `DeviceHeartbeat` **100**, `ConfigChange` **100**, `FirewallDeny` **100** |
| **deviceId** | `substation-sensor-01` **200**, `-02` **200**, `-03` **100** |
| **Facility** | `Substation-C` **300**, `Substation-D` **100**, `DMZ-Firewall` **100** |

**Example — event types on Bronze:**

```kql
SecLogsRaw
| where RecordFormat == "IoT"
| summarize EventCount = count() by EventType = tostring(RawPayload.EventType)
| order by EventCount desc
```

**Example — per-device volume:**

```kql
SecLogsRaw
| where RecordFormat == "IoT"
| summarize MessageCount = count() by DeviceId = tostring(RawPayload.deviceId)
| order by DeviceId asc
```

**Why Bronze first?** Ingest debugging and OT engineers often inspect **`RawPayload.deviceId`** before typed Silver exists. **`deviceId` is not a Silver column** in this course — Lab 9 uses `EventType`, `Facility`, and `SourceSystem` on **`SecLogsParsed`**.

Hands-on: [queries/08-iot-telemetry-bronze.kql](queries/08-iot-telemetry-bronze.kql) · [labs.md Lab 8](labs.md#lab-8--iot-telemetry-on-bronze).

# 4. Day 2 prerequisite — batch Bronze recap

Day 3 assumes **Day 2 Labs 3–6** completed in **your database**:

| Day 2 lab | Result in `SecLogsRaw` |
|-----------|------------------------|
| Lab 3 | Empty `SecLogsRaw` table (four columns) |
| Lab 4 | **1500** JSON rows (`RecordFormat == "JSON"`) |
| Lab 5 | **+1000** CSV rows (`RecordFormat == "CSV"`) from **`sec-web-logs.csv`** |
| Lab 6 | Verified **2500** total |

**Native CSV path (Day 2 Lab 5):** CSV file → **`SecLogsCsvStg`** (typed columns + CSV mapping) → **`SecLogsCsvToBronze()`** → **`.append SecLogsRaw`**. Silver update policy (this module) does **not** read `SecLogsCsvStg` directly — it reads **`SecLogsRaw.RawPayload`**, which already contains a packed dynamic object with the same field names as JSON rows.

If Lab 1 fails, common causes:

| Symptom | Likely cause |
|---------|----------------|
| Total &lt; 2500 | Day 2 ingest incomplete — re-run Day 2 Labs 4–5 |
| CSV count 0 | Lab 5 `.append` step skipped |
| Total &gt; 2500 | Duplicate ingest — reset your database or re-run from Lab 1 gate |

# 5. Kafka and Logstash (architecture only)

Discussion-only — [labs.md](labs.md) Lab 6. This course uses **Event Hub** and **IoT Hub** hands-on.

| Enterprise path | Reuses course pattern |
|-----------------|----------------------|
| **Kafka → Event Hub → ADX** | Same as Lab 2 data connection |
| **Logstash → Event Hub → ADX** | Same data connection |
| **Logstash → Blob → ADX** | Same as Day 2 `.ingest` |

```text
  Kafka ──mirror──► Event Hub ──connection──► SecLogsRaw
  Logstash ──► Event Hub or Blob ──► SecLogsRaw ──► SecLogsParsed
```

All paths land in **Bronze**; **Silver update policy** (Section 6) owns parsing.

# 6. Silver — `SecLogsParsed` and update policies

**Silver** is the typed investigation layer. After Labs 2–3, **`SecLogsRaw`** holds **3500** Bronze rows in four formats. Labs **4–5** create **`SecLogsParsed`**, attach an **update policy** on the Silver table, and **backfill** existing Bronze so every row becomes queryable typed columns — including **`SourceSystem`** lineage ([Microsoft — update policy overview](https://learn.microsoft.com/en-us/kusto/management/update-policy?view=microsoft-fabric)).

For policy concepts (all types, FAQ, troubleshooting), see **[policies-guide.md](policies-guide.md)**.

Policy lives on the **target** (Silver) table; it runs on **new** Bronze ingest; Day 2 rows need a **one-time backfill** (Lab 5).

## 6.1 Bronze vs Silver — why two tables

```text
  BRONZE SecLogsRaw (3500)              SILVER SecLogsParsed (3500)

  IngestionTime                       Timestamp      (datetime)
  SourceFile                          EventType      (string)
  RecordFormat                        SourceIP       (string)
  RawPayload { dynamic JSON }  ──►    ... 8 typed cols + SourceSystem
```

| Question | Bronze answer | Silver answer |
|----------|---------------|---------------|
| What arrived? | `SourceFile`, `RecordFormat` | `SourceSystem` |
| When? | `IngestionTime` | `Timestamp` (from payload) |
| Investigate by IP? | Parse `RawPayload.SourceIP` each query | `where SourceIP == "..."` |
| Dashboard-ready? | No — dynamic blob | Yes — typed columns |

Utility SOC pattern: **land everything in Bronze** (batch + stream + IoT); **parse once in Silver** so analysts and Day 4 Gold use one schema.

## 6.2 Locked Silver schema — `SecLogsParsed`

You create this schema in **Lab 4** ([queries/04-create-silver-table.kql](queries/04-create-silver-table.kql)):

| Column | Type | Source in transform |
|--------|------|---------------------|
| `Timestamp` | `datetime` | `RawPayload.Timestamp`, fallback `IngestionTime` |
| `EventType` | `string` | `RawPayload.EventType` |
| `SourceIP` | `string` | `RawPayload.SourceIP` |
| `DestinationHost` | `string` | `RawPayload.DestinationHost` |
| `UserPrincipal` | `string` | `RawPayload.UserPrincipal` |
| `Severity` | `string` | `RawPayload.Severity` |
| `Message` | `string` | `RawPayload.Message` |
| `Facility` | `string` | `RawPayload.Facility` |
| `SourceSystem` | `string` | Derived from Bronze `RecordFormat` |

```kql
.create-merge table SecLogsParsed (
    Timestamp: datetime,
    EventType: string,
    SourceIP: string,
    DestinationHost: string,
    UserPrincipal: string,
    Severity: string,
    Message: string,
    Facility: string,
    SourceSystem: string
)
```

Microsoft rule: update policy query output must **match target column names, types, and order** ([update policy overview](https://learn.microsoft.com/en-us/kusto/management/update-policy?view=microsoft-fabric)). Do not add or reorder columns without altering the table.

Verify after Lab 4:

```kql
.show table SecLogsParsed cslschema
```

## 6.3 SourceSystem — lineage from four Bronze formats

`SourceSystem` is **not** in the raw JSON — the transform derives it from Bronze **`RecordFormat`**:

| SourceSystem | Bronze `RecordFormat` | Rows | Origin |
|--------------|----------------------|------|--------|
| `Batch-JSON` | `JSON` | **1500** | Day 2 `sec-app-logs.json` |
| `Batch-CSV` | `CSV` | **1000** | Day 2 `sec-web-logs.csv` |
| `EventHub` | `EventHub` | **500** | Day 3 Lab 2 stream |
| `IoT-Hub` | `IoT` | **500** | Day 3 Lab 3 telemetry |
| **Total** | | **3500** | |

```text
  RecordFormat          case() in policy query          SourceSystem
  ------------          ----------------------          --------------
  JSON            ──►   "Batch-JSON"              ──►   batch app logs
  CSV             ──►   "Batch-CSV"               ──►   web export
  EventHub        ──►   "EventHub"                ──►   VPN stream
  IoT             ──►   "IoT-Hub"                 ──►   substation sensors
```

Lab 7 expects **`dcount(SourceSystem) == 4`** ([queries/07-silver-investigation.kql](queries/07-silver-investigation.kql)).

## 6.4 Transform logic — parsing `RawPayload`

The same KQL runs inside the **update policy** and the **backfill** command ([queries/05-update-policy-backfill.kql](queries/05-update-policy-backfill.kql)):

```kql
SecLogsRaw
| extend Timestamp = coalesce(todatetime(RawPayload.Timestamp), IngestionTime)
| extend EventType = tostring(RawPayload.EventType)
| extend SourceIP = tostring(RawPayload.SourceIP)
| extend DestinationHost = tostring(RawPayload.DestinationHost)
| extend UserPrincipal = tostring(RawPayload.UserPrincipal)
| extend Severity = tostring(RawPayload.Severity)
| extend Message = tostring(RawPayload.Message)
| extend Facility = tostring(RawPayload.Facility)
| extend SourceSystem = case(
    RecordFormat == "JSON", "Batch-JSON",
    RecordFormat == "CSV", "Batch-CSV",
    RecordFormat == "EventHub", "EventHub",
    RecordFormat == "IoT", "IoT-Hub",
    "Unknown")
| project Timestamp, EventType, SourceIP, DestinationHost, UserPrincipal,
          Severity, Message, Facility, SourceSystem
```

| Step | Why |
|------|-----|
| `coalesce(todatetime(...), IngestionTime)` | Missing timestamp in bad payload still yields a row |
| `tostring(RawPayload.*)` | Unpacks dynamic JSON/CSV fields to typed strings |
| `case(RecordFormat == ...)` | Normalizes batch vs stream lineage |
| `project` | Output schema must match `SecLogsParsed` exactly |

IoT payloads include **`deviceId`** inside `RawPayload` — Silver keeps it in the dynamic blob path only; **`SourceSystem = IoT-Hub`** identifies device telemetry. Advanced courses may project `deviceId` to its own column.

### Worked example — one Bronze row → one Silver row

**Bronze** (batch JSON row, simplified):

| IngestionTime | SourceFile | RecordFormat | RawPayload (key fields) |
|---------------|------------|--------------|-------------------------|
| 2026-06-11T09:09:01Z | sec-app-logs.json | JSON | `EventType=AuthFailure`, `SourceIP=10.20.1.44`, `Facility=Substation-A` |

**After update policy / backfill transform → Silver:**

| Timestamp | EventType | SourceIP | Facility | SourceSystem |
|-----------|-----------|----------|----------|--------------|
| 2026-06-11T09:09:01Z | AuthFailure | 10.20.1.44 | Substation-A | Batch-JSON |

**CSV Bronze row** (from Day 2 native path): `RecordFormat = CSV`, `SourceFile = sec-web-logs.csv` — `RawPayload` is a **packed dynamic object** (not a string). The same `tostring(RawPayload.EventType)` pattern works because `pack()` used the same field names.

```kql
// Compare shapes before enabling policy (run on your data)
SecLogsRaw
| where RecordFormat in ("JSON", "CSV")
| take 2
| extend EventType = tostring(RawPayload.EventType)
| project RecordFormat, SourceFile, EventType, RawPayload
```

## 6.5 Update policy — attach to Silver, source Bronze

Policy is defined on **`SecLogsParsed`**, not on Bronze ([Microsoft model](https://learn.microsoft.com/en-us/kusto/management/update-policy?view=microsoft-fabric)):

```text
  NEW ROW lands in SecLogsRaw
         │
         │  triggers SecLogsParsed.policy.update
         │  Source = "SecLogsRaw"
         v
  Policy Query runs (§6.4)
         │
         v
  Rows APPENDED to SecLogsParsed
```

Lab 5 Step 1 — single-line `.alter table SecLogsParsed policy update` in [05-update-policy-backfill.kql](queries/05-update-policy-backfill.kql):

| Property | Lab value | Notes |
|----------|-----------|-------|
| `IsEnabled` | `true` | Policy active |
| `Source` | `SecLogsRaw` | Bronze triggers transform |
| `Query` | §6.4 transform | One line in management command |
| `IsTransactional` | `false` | Tutorial default; production may use `true` |
| `PropagateIngestionProperties` | `false` | Not needed for this lab |

Inspect policy:

```kql
.show table SecLogsParsed policy update
```

Management command reference: [alter table update policy](https://learn.microsoft.com/en-us/azure/data-explorer/kusto/management/alter-table-update-policy-command).

**Production caution:** a broken policy query can **block Bronze ingest**. Test the transform as a standalone query against `SecLogsRaw | take 10` before enabling.

## 6.6 Backfill — load Day 2 + stream rows already in Bronze

Update policies run when data is **ingested into the source table** after the policy exists ([when policy runs](https://learn.microsoft.com/en-us/kusto/management/update-policy?view=microsoft-fabric#update-policy-is-initiated-following-ingestion)). Bronze rows that landed **before** you enabled the update policy in Lab 5 are **not** auto-forwarded — use **backfill** (Lab 5 Step 2).

```text
  FORWARD (after Lab 5)                 BACKFILL (Lab 5 Step 2, once)

  New Bronze row ──policy──► Silver     .set-or-append SecLogsParsed <|
                                        same transform on ALL SecLogsRaw
```

Lab 5 Step 2:

```kql
.set-or-append SecLogsParsed <| SecLogsRaw
| extend Timestamp = coalesce(todatetime(RawPayload.Timestamp), IngestionTime)
// ... same as §6.4 through project
```

| Scenario | Bronze | Silver | Fix |
|----------|--------|--------|-----|
| Policy only, no backfill | 3500 | 0 | Run Step 2 |
| Backfill only, no policy | 3500 | 3500 | New Bronze won't forward — run Step 1 |
| Both (correct lab) | 3500 | 3500 | Lab 7 ready |

Tutorial walkthrough: [update policy tutorial](https://learn.microsoft.com/en-us/kusto/management/update-policy-tutorial?view=microsoft-fabric).

## 6.7 Lab 5 — policy + backfill

Hands-on: [labs.md](labs.md) Lab 5.

| # | Action | Notes |
|---|--------|-------|
| 1 | Open [05-update-policy-backfill.kql](queries/05-update-policy-backfill.kql) | |
| 2 | Run **Step 1** as **one line** | Do not split the `.alter` command |
| 3 | Confirm `IsEnabled: true` | `.show table SecLogsParsed policy update` |
| 4 | Run **Step 2** backfill block | `.set-or-append` through final `project` |
| 5 | Verify Silver **3500** | `SecLogsParsed \| count` |
| 6 | Run [06-verify-silver.kql](queries/06-verify-silver.kql) Q1–Q4 | Pre-Lab 7 checks |

**Success:** Bronze **3500** = Silver **3500**; four `SourceSystem` values.

## 6.8 Locked counts — Silver verification

| Check | Query | Expected |
|-------|-------|----------|
| Total Silver rows | `SecLogsParsed \| count` | **3500** |
| Bronze parity | Q3 in `06-verify-silver.kql` | `Match = true` |
| Source systems | `summarize count() by SourceSystem` | **4** values — see table below |
| AuthFailure (Lab 7) | `where EventType == "AuthFailure"` | **700** (300 JSON + 200 CSV + 200 EventHub) |
| Streaming only | `SourceSystem in ("EventHub","IoT-Hub")` | **1000** rows |

**Q2 locked breakdown (`06-verify-silver.kql`):**

| SourceSystem | Rows |
|--------------|------|
| `Batch-CSV` | **1000** |
| `Batch-JSON` | **1500** |
| `EventHub` | **500** |
| `IoT-Hub` | **500** |

AuthFailure breakdown: [data/README.md](../data/README.md#event-type-reference-authfailure--700-in-silver-after-day-3).

```kql
SecLogsParsed
| summarize RowCount = count() by SourceSystem
| order by SourceSystem asc
```

## 6.9 Silver verification and investigation (Labs 5 / 7)

Use **`06-verify-silver.kql`** after Lab 5 backfill and before Lab 7:

| Query | Purpose | Expected |
|-------|---------|----------|
| Q1 | Total Silver rows | **3500** |
| Q2 | Rows by `SourceSystem` | **4** values (see §6.8 table) |
| Q3 | Bronze vs Silver parity | `Match` = **true** |
| Q4 | Event mix on Silver | AuthFailure **700**, other types present |

**Lab 7** — **`07-silver-investigation.kql`** applies SOC-style filters on typed Silver:

| Query | Purpose | Expected |
|-------|---------|----------|
| Q1 | AuthFailure count | **700** |
| Q2 | AuthFailure by `SourceSystem` | Batch + streaming sources |
| Q3 | High/Critical in lab window | Summarize completes |
| Q4–Q5 | Facility / OT patterns | Substation and DMZ rows |

Silver is the analyst layer — no `RawPayload` parsing required in these labs.

## 6.10 IoT telemetry on Silver (Lab 9)

After Lab 5, IoT rows appear in Silver as **`SourceSystem == "IoT-Hub"`** (**500** rows) with typed **`EventType`**, **`Facility`**, and **`Severity`** — same event mix as Lab 8 on Bronze.

```text
  BRONZE (Lab 8)                    SILVER (Lab 9)

  RawPayload.deviceId               SourceSystem = IoT-Hub
  RawPayload.EventType       ──►    EventType, Facility, Severity
  RecordFormat = IoT                (deviceId still Bronze-only)
```

| Lab 9 query | Analyst question |
|-------------|------------------|
| Q1 | How many IoT telemetry events reached Silver? (**500**) |
| Q2 | Mix of sensor vs heartbeat vs config vs firewall on IoT stream |
| Q3 | High/Critical alerts by facility (OT vs DMZ) |
| Q4 | Hourly **`SensorAnomaly`** buckets — preview of Day 4 **`bin()`** |
| Q5 | Substation-C/D OT telemetry only (**400** rows) |

**Example — IoT event mix on Silver:**

```kql
SecLogsParsed
| where SourceSystem == "IoT-Hub"
| summarize EventCount = count() by EventType
| order by EventCount desc
```

**Note:** **`10.20.9.3`** appears in **`SensorAnomaly`** at **`Substation-D`** — same IP is a **`ThreatIntelRef`** join key on Day 4.

Hands-on: [queries/09-iot-telemetry-silver.kql](queries/09-iot-telemetry-silver.kql) · [labs.md Lab 9](labs.md#lab-9--iot-telemetry-on-silver).

# 7. Silver investigation (Lab 7)

After Lab 5, **`SecLogsParsed`** holds **3500 typed rows**. Lab 7 proves you can investigate without parsing `RawPayload` on every query.

**Query file:** [queries/07-silver-investigation.kql](queries/07-silver-investigation.kql)

| Query | Purpose | Locked result |
|-------|---------|---------------|
| **Q1** | Total AuthFailure across all sources | **700** |
| **Q2** | AuthFailure by `SourceSystem` | JSON **300**, CSV **200**, EventHub **200**, IoT **0** |
| **Q3** | High/Critical alerts by `Facility` | Non-zero grouped counts |
| **Q4** | Streaming rows only | **1000** rows (`EventHub` + `IoT-Hub`) |
| **Q5** | Distinct source systems | **`dcount(SourceSystem) == 4`** |

**Example Q1:**

```kql
SecLogsParsed
| where EventType == "AuthFailure"
| count
```

**Why IoT AuthFailure = 0:** IoT sample data uses event types like `SensorAnomaly` and `DeviceHeartbeat` — not authentication failures. Event Hub stream carries the **200** streaming AuthFailure rows.

**Bronze vs Silver for analysts:**

| Question | Use table | Example |
|----------|-----------|---------|
| Raw payload / ingest debug | `SecLogsRaw` | `RawPayload`, `RecordFormat` |
| SOC hunt, dashboards, Day 4 Gold | `SecLogsParsed` | `where SourceIP == "..."` |

Hands-on checklist: [labs.md](labs.md) Lab 7.

Close Day 3 with [labs.md](labs.md): Bronze **3500**, Silver **3500**, four `SourceSystem` values, AuthFailure **700**, IoT telemetry analyzed on Bronze (Lab 8) and Silver (Lab 9). Day 4 continues on **`SecLogsParsed`** with advanced KQL and Gold aggregates.
