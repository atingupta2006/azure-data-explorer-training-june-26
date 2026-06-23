# Day 04 — Advanced KQL, Data Modeling & Gold Layer

## Learning objectives

* Join **`SecLogsParsed`** to **`ThreatIntelRef`** for **IOC** *(Indicator of Compromise)* enrichment
* Explain **fact**, **dimension**, and **star schema** in utility cyber terms
* Build time-series and anomaly queries on Silver
* Create UDFs and window-function sequences
* Create Gold **`SecLogsHourly`** materialized view

**Prerequisite:** Day 3 — `SecLogsParsed` with **3500** rows in **your database**.

**Hands-on:** [labs.md](labs.md) | **Queries:** [queries/](queries/) | **Practice:** [assignments.md](assignments.md) | **Data:** [data/README.md](../data/README.md) | **Terms:** [GLOSSARY.md](../GLOSSARY.md)

### Document map

| Section | Topic | Labs |
|---------|--------|------|
| [At a glance](#day-4-at-a-glance) | 7-lab arc, Query tab only, end state | All |
| [1](#1-data-modeling--fact-dimension-and-layers) | Fact/dim/**star schema**, medallion layers | Lab 1 |
| [2](#2-joins-and-reference-data) | IOCs, `ThreatIntelRef`, join flavors | Lab 2 (+ [verify](queries/02-verify-threatintel.kql)) |
| [3](#3-time-series-analysis) | `bin()`, `make-series` | Lab 3 |
| [4](#4-anomaly-detection) | `series_decompose_anomalies` | Lab 4 |
| [5](#5-window-functions) | `serialize`, `row_number`, `prev` | Lab 5 |
| [6](#6-materialized-views--gold-seclogshourly) | Gold MV theory | Lab 7 (+ [verify](queries/07-verify-gold.kql)) |
| [7](#7-user-defined-functions-udfs) | `SeverityRank`, `IsOTFacility` | Lab 6 |
| [8](#8-hot-vs-cold-data-retention-and-caching) | Retention/caching `.show` | Lab 7 Q5 |
| [9](#9-day-5-preview) | Performance, security, capstone | — |
| — | [Scenario assignments](assignments.md) (30 KQL tasks + answers) | After labs |

> **Lab order note:** Labs run **UDF (6)** then **Gold MV (7)**. Theory §6–§7 are ordered for concepts (time-series → Gold → UDF). Follow [labs.md](labs.md) for hands-on sequence; use the map above to jump to the right section.

### Day 4 at a glance

**Where you work:** [dataexplorer.azure.com](https://dataexplorer.azure.com) Query tab only — no Azure Portal, no new ingest. You analyze **`SecLogsParsed`** from Days 2–3 and create new objects in **your database**.

```text
  YOUR DAY (labs.md order)

  Lab 1  Verify Silver (3500) ──gate──► stop if not ready
           │
           v
  Lab 2  ThreatIntelRef (8) + joins ──► IOC enrichment (~409 rows)
           │
           v
  Labs 3–5  Advanced KQL on Silver ──► time-series → anomalies → windows (~182)
           │
           v
  Lab 6  UDFs (SeverityRank, IsOTFacility)
           │
           v
  Lab 7  Gold MV SecLogsHourly ──► sum(EventCount) = 3500

  END STATE in your database:
  SecLogsParsed (3500) + ThreatIntelRef (8) + SecLogsHourly (MV) + 2 functions
```

---


# 1. Data modeling — fact, dimension, and layers

Day 4 shifts from **building** the pipeline (Days 2–3) to **analyzing and aggregating** it. Utility cyber analytics maps cleanly to a **star-style** model in ADX: a high-volume **fact** table of events, smaller **dimension** tables for lookups, and **Gold** pre-aggregates for dashboards.

Section **1** defines the model. Section **2** implements the first enrichment with **`join`**. Later sections add time-series, Gold materialized views, and policies.

## 1.1 What Day 4 adds to the week

```text
  COMPLETED (Days 1–3)                 DAY 4 (today)

  KQL fundamentals                     data model (fact / dim / star)
  Bronze SecLogsRaw (3500)             join + IOC enrichment
  Silver SecLogsParsed (3500)          time-series + anomalies
  update policy                        window functions + UDFs
                                       Gold SecLogsHourly (MV)
```

| Day | Focus | Primary tables |
|-----|-------|----------------|
| 1 | KQL on sample data | `PracticeSecurityEvents` |
| 2 | Batch ingest → Bronze | `SecLogsRaw` |
| 3 | Stream + Silver policy | `SecLogsRaw`, `SecLogsParsed` |
| **4** | **Model + advanced KQL + Gold** | **`SecLogsParsed`**, **`ThreatIntelRef`**, **`SecLogsHourly`** |
| 5 | Performance, security, capstone | Full pipeline |

This day operates on the **Bronze → Silver → Gold** path built on Days 2–3, and adds a **star-style logical model** on top of Silver.

## 1.2 Why model data at all?

Without a model, every analyst query starts from raw events and re-implements the same joins and definitions. A **data model** answers:

| Question | Modeled answer |
|----------|----------------|
| Where do **events** live? | **Fact** table — high volume, append-only |
| Where do **lookups** live? | **Dimension** tables — smaller, refreshed on a schedule |
| Where do **dashboard KPIs** live? | **Gold** aggregates — pre-summarized grains |
| How do tables **relate**? | **Star schema** — fact in the center, dimensions on the spokes |

**Real-world utility cyber example:** A regional utility **SOC** *(Security Operations Center — central security analyst team)* ingests **800M firewall events/month** from DMZ sensors, **VPN concentrators**, and **substation IoT gateways**. Analysts do not re-parse JSON on every investigation. They query a typed **fact** table (`SecLogsParsed` in this course), **`join`** a **threat-intel dimension** refreshed from an ISAC feed, and open **Gold** hourly charts for the control-room dashboard. Day 4 teaches that pattern at lab scale (**3500** events).

## 1.3 Fact table vs dimension table

| | **Fact table** | **Dimension table** |
|---|----------------|---------------------|
| **Contains** | Things that **happened** (events, measurements) | Things that **describe** context (who, what, where, watchlists) |
| **Grain** | One row per event (or per transaction) | One row per entity or IOC pattern |
| **Volume** | **Large** — grows every second | **Small** — thousands to millions of rows, not billions |
| **Change rate** | **Append** continuously | **Refresh** hourly / daily / weekly |
| **Typical columns** | `Timestamp`, `SourceIP`, `EventType`, `Severity` | `MatchKey`, `ThreatCategory`, `FacilityName`, `Region` |
| **Course table** | **`SecLogsParsed`** (3500 rows) | **`ThreatIntelRef`** (8 rows) |

```text
  FACT (event stream)                    DIMENSION (lookup)

  ┌─────────────────────────┐          ┌─────────────────────────┐
  │ 2026-06-11 09:04:04     │          │ MatchKey: 203.0.113.50  │
  │ EventType: FirewallDeny │          │ Category: ExternalScanner│
  │ SourceIP: 203.0.113.50  │──join──► │ SeverityHint: High      │
  │ Facility: DMZ-Firewall  │          └─────────────────────────┘
  │ Severity: High          │
  └─────────────────────────┘
       ▲ one row = one event              ▲ one row = one IOC / pattern
```

**Real-world fact examples (utility SOC):**

| Source | Fact row example |
|--------|------------------|
| Corporate VPN | `AuthFailure` from `10.20.8.10` at `Corporate-VPN` |
| DMZ firewall | `FirewallDeny` from external scanner IP `203.0.113.50` |
| Substation IoT | `SensorAnomaly` vibration alert at `Substation-D` |
| Batch SIEM export | Historical `PrivilegeEscalation` on `SCADA-Gateway` |

**Real-world dimension examples (not all used in the lab):**

| Dimension | Purpose | Refresh |
|-----------|---------|---------|
| **`ThreatIntelRef`** (Lab 2) | Known-bad IPs and attack patterns | Daily TI feed |
| Asset / CMDB | Which host is in which substation | Weekly |
| User directory | Map `UserPrincipal` to department | Daily |
| Facility master | Region, NERC CIP zone, OT vs IT | Monthly |

In this course you build **`ThreatIntelRef`** only; other dimensions are discussed as **production patterns**.

## 1.4 Star schema — fact in the center, dimensions on the spokes

A **star schema** places one **fact** table at the center and **dimension** tables around it. Analyst queries **`join`** from the fact outward — they do not join dimension-to-dimension for basic enrichment.

```text
                         ┌──────────────────────┐
                         │   ThreatIntelRef     │  DIMENSION (Lab 2)
                         │   8 IOC / patterns   │
                         └──────────┬───────────┘
                                    │ join SourceIP / EventType
                                    v
    ┌─────────────┐         ┌───────────────────────┐         ┌─────────────────┐
    │  (future)   │         │    SecLogsParsed      │         │  SecLogsHourly  │
    │  AssetRef   │────────►│    FACT (Silver)      │────────►│  GOLD (Lab 7)   │
    │  production │  join   │    3500 events        │  MV     │  hourly KPIs    │
    └─────────────┘         └───────────────────────┘         └─────────────────┘
                                    ▲
                                    │ update policy (Day 3)
                                    │
                            ┌───────┴────────┐
                            │   SecLogsRaw   │  BRONZE (background)
                            │   3500 raw     │
                            └────────────────┘
```

**How to read the diagram:**

| Shape | Role in star | Course object |
|-------|--------------|---------------|
| **Center** | Fact — investigations start here | `SecLogsParsed` |
| **Spoke (top)** | Dimension — enriches fact at query time | `ThreatIntelRef` |
| **Spoke (left, dashed)** | Optional production dimension | Asset / facility master (concept) |
| **Right arrow** | Aggregate — rollups for dashboards | `SecLogsHourly` materialized view |
| **Below** | Ingestion landing — not queried in Day 4 labs | `SecLogsRaw` |

**Real-world star at a utility (production scale):**

```text
                    [ThreatIntelDim]     [AssetDim]     [FacilityDim]
                           \                 |              /
                            \                |             /
                             v               v            v
                         ┌───────────────────────────────────────┐
                         │         SecurityEventFact             │
                         │  billions of rows / hot cache window    │
                         └───────────────────┬───────────────────┘
                                             │ nightly / streaming MV
                                             v
                                    [HourlyKpiGold]
                                    control-room dashboard
```

**Why “star” and not “snowflake”?** Dimensions are kept **flat** (one table per topic). A **snowflake** would normalize `Facility` → `Region` → `Country` into chained joins. ADX investigations favor **simple stars**: one fact, a few wide dimension tables, optional Gold.

**Course star vs lab objects:**

| Star role | Production name (example) | This course |
|-----------|---------------------------|-------------|
| Fact | `SecurityEvents` | `SecLogsParsed` |
| Dimension | `ThreatIntel` | `ThreatIntelRef` (you create in Lab 2) |
| Gold | `SecurityKpiHourly` | `SecLogsHourly` (Lab 7 MV) |

## 1.5 Medallion layers — full stack recap

```text
  BRONZE                 SILVER (fact)              GOLD (aggregate)

  SecLogsRaw        ──►  SecLogsParsed         ──►  SecLogsHourly
  3500 raw rows           3500 typed rows               hourly KPI buckets
  RawPayload             investigation grain         dashboard grain
  4 RecordFormats        SourceSystem lineage        sum(EventCount) = 3500
```

| Layer | Table | Grain | Day 4 use |
|-------|--------|-------|-----------|
| **Bronze** | `SecLogsRaw` | One raw landing row | Background only — queries target Silver+ |
| **Silver** | `SecLogsParsed` | One row per security event | **Fact table** — joins, time-series, windows |
| **Reference** | `ThreatIntelRef` | One row per IOC / pattern | **Dimension** — Lab 2 |
| **Gold** | `SecLogsHourly` | Hourly × Facility × EventType | **Aggregate fact** — Lab 7 MV |

Bronze answers *what landed?* Silver answers *what happened, typed and filterable?* Gold answers *how much per hour/facility for dashboards?*

Silver parsing and update policies are covered in the streaming module README. Gold materialized views are covered in this module.

## 1.6 Fact table — `SecLogsParsed`

The **fact** table holds the measurable events analysts investigate — auth failures, firewall denies, sensor anomalies. Each row is one security event with typed columns (not `RawPayload` dynamic).

| Property | Course value |
|----------|--------------|
| **Grain** | One row = one security event |
| **Row count (labs)** | **3500** |
| **`SourceSystem`** | `Batch-JSON`, `Batch-CSV`, `EventHub`, `IoT-Hub` (4 values) |
| **AuthFailure (Lab 7 / Day 3)** | **700** rows |
| **Primary time column** | `Timestamp` |

```kql
SecLogsParsed
| summarize RowCount = count() by SourceSystem, EventType
| order by SourceSystem, EventType
```

Fact tables grow fastest in production — batch exports, Event Hub streams, IoT telemetry all append rows. Dimensions and Gold aggregates stay comparatively small.

**Example fact rows (from course data):**

| Timestamp | EventType | SourceIP | Facility | SourceSystem |
|-----------|-----------|----------|----------|--------------|
| 2026-06-11 09:00 | AuthFailure | 10.20.8.10 | Corporate-VPN | EventHub |
| 2026-06-11 09:00 | FirewallDeny | 203.0.113.50 | DMZ-Firewall | Batch-CSV |
| 2026-06-11 09:03 | SensorAnomaly | 10.20.9.15 | Substation-D | IoT-Hub |

An analyst question on the fact table: *“Show all High-severity denies at DMZ-Firewall in the last hour.”* — no join required.

## 1.7 Dimension / reference — `ThreatIntelRef` (Lab 2)

**Reference data** changes slowly compared to events: threat intel IPs, watchlist patterns, facility metadata. ADX stores it in a separate table and **`join`**s at query time ([join operator](https://learn.microsoft.com/en-us/kusto/query/join-operator)).

| Role | Table | Rows (lab) | Update pattern |
|------|--------|------------|----------------|
| **Dimension** | `ThreatIntelRef` | **8** | Lab 2 Q2 **seed load** (`.set-or-replace`) — not streaming |
| **Fact** | `SecLogsParsed` | **3500** | Continuous append via ingest + update policy |

```text
  STAR PATTERN (this course — see §1.4 for full diagram)

                    SecLogsParsed (FACT)
                    Timestamp, SourceIP, EventType, ...
                           │
              join on SourceIP or EventType
                           │
                           v
                    ThreatIntelRef (DIMENSION)
                    MatchKey, MatchType, ThreatCategory, SeverityHint
```

**Real-world dimension row (conceptual TI feed):**

| MatchKey | MatchType | ThreatCategory | SeverityHint |
|----------|-----------|----------------|--------------|
| `203.0.113.50` | SourceIP | ExternalScanner | High |
| `10.20.1.44` | SourceIP | BruteForceTarget | Critical |

**Course dimension row (Lab 2 — same shape as production):**

| MatchKey | MatchType | ThreatCategory | SeverityHint |
|----------|-----------|----------------|--------------|
| `203.0.113.50` | SourceIP | ExternalScanner | High |
| `AuthFailure` | EventType | CredentialAttack | High |

Lab 2 **creates** `ThreatIntelRef` and **loads 8 starter IOC rows** (see [What seed means](#what-seed-means)), then enriches facts with **`ThreatCategory`**. Section **2** covers join syntax and the **IOC enrichment report** (Lab 2 Q3).

### What is an IOC?

An **IOC** (Indicator of Compromise) is a observable artifact tied to malicious or suspicious activity — for example a **known-bad IP**, a recurring **attack event type**, or a scanner signature. In utility cyber SOC work, IOCs often come from ISAC feeds, vendor threat intel, or internal watchlists.

In this course, each row in **`ThreatIntelRef`** represents one IOC or watchlist **pattern** (not one security event). Events live in **`SecLogsParsed`**; IOCs live in the reference table.

### What is an “IOC enrichment report”?

An **IOC enrichment report** is not a separate file or Portal export. It is the **result of a KQL join query** that adds threat context to events:

| Before join | After join (Lab 2 Q3) |
|-------------|------------------------|
| `Timestamp`, `SourceIP`, `EventType`, `Facility`, … | Same columns **plus** `ThreatCategory`, `SeverityHint` |

Lab 2 **Q3** produces the enrichment report: every row is a **`SecLogsParsed`** event whose **`SourceIP`** matched a row in **`ThreatIntelRef`**. Analysts use it to answer *“Which of today’s events hit a known IOC?”*

Lab 2 **Q4** is a **summary** enrichment view by `ThreatCategory` and `EventType` (pattern-based IOCs such as all `AuthFailure` → `CredentialAttack`).

The architecture diagram (§1.9) label **“IOC enrichment queries”** means these Lab 2 join queries — not a built-in ADX report type.

### Where `ThreatIntelRef` is created and populated (Lab 2)

**Important:** In the lab, threat intel is **not** ingested from Blob storage, Event Hub, IoT Hub, or an external API. **You create and populate it yourself** in **your database** using KQL in the ADX Web UI.

| Step | What happens | Where |
|------|----------------|-------|
| **Q0** | `.drop table ThreatIntelRef ifexists` — safe re-run in **your** DB | [queries/02-threatintel-join.kql](queries/02-threatintel-join.kql) |
| **Q1** | `.create table ThreatIntelRef (...)` — empty dimension table | Same file |
| **Q2** | `.set-or-replace ThreatIntelRef` — **seed** (load) **8** rows from an inline `datatable(...)` in the query | Same file — **synthetic IOCs written in the KQL** |
| **Verify** | Confirm **8** rows before joins | [queries/02-verify-threatintel.kql](queries/02-verify-threatintel.kql) |
| **Q3–Q4** | Join to **`SecLogsParsed`** — enrichment reports | `02-threatintel-join.kql` |

### What seed means

**Seed** = load the **first rows into a new empty table** — like “seed data” in development.

| Step | What happens |
|------|----------------|
| **Q1** | Creates an **empty** `ThreatIntelRef` table (schema only) |
| **Q2** | **Seeds** the table — inserts **8** IOC rows with `.set-or-replace` and an inline `datatable(...)` |

You are simulating what a production team does when a scheduled job **refreshes** a threat-intel reference table — except in the lab **you** run Q2 manually instead of an automated pipeline.

### Why joins return rows (Lab 2 Q3)

A **`join` only returns rows when keys match on both sides.**

| Left (`SecLogsParsed`) | Right (`ThreatIntelRef`) | Match? |
|------------------------|--------------------------|--------|
| `SourceIP = 203.0.113.50` | `MatchKey = 203.0.113.50` | Yes → enriched row in Q3 |
| `SourceIP = 10.20.8.10` | (not on 8-row watchlist) | No → row omitted from Q3 |

The **8 values in Q2** (`MatchKey` — IPs like `203.0.113.50` and event types like `AuthFailure`) were **chosen by course authors** to **match values already in your `SecLogsParsed` rows** from Days 2–3 (batch JSON/CSV, Event Hub, IoT). That is why Q3 returns hundreds of enriched rows (typically **~409**) instead of zero.

```text
  DAYS 2–3 (already done)              LAB 2 Q2 (you run today)

  SecLogsParsed has events             You seed ThreatIntelRef with 8 IOC rows
  e.g. SourceIP = 203.0.113.50              e.g. MatchKey = 203.0.113.50
       │                                         │
       └──────────── JOIN (Q3) ──────────────────┘
                         │
                         v
              Matched events + ThreatCategory
              (the "IOC enrichment report")
```

If Q2 used random IPs that never appear in your events, Q3 would return **zero rows** — even with **3500** events in Silver. See [data/README.md](../data/README.md) for how course event IPs align with IOC `MatchKey` values.

### Production: where threat intel comes from

In production, **`ThreatIntelRef` plays the same role** (dimension / watchlist) but is **filled by automation**, not inline KQL in the Query tab.

**Typical IOC sources (utility SOC):**

| Source | Examples |
|--------|----------|
| **Sector / ISAC sharing** | Energy-sector ISAC, CISA advisories, peer utility indicators |
| **Commercial TI vendors** | STIX/TAXII or API feeds (Recorded Future, Mandiant, CrowdStrike, etc.) |
| **Microsoft ecosystem** | Defender Threat Intelligence; some teams sync Sentinel TI into ADX |
| **Internal SOC** | SOAR playbooks, analyst watchlists, hunt results promoted to reference |

**How rows reach ADX:**

```text
  EXTERNAL SOURCES                    INGEST / TRANSFORM                 ADX

  ISAC STIX/TAXII feed  ──┐
  Vendor TI API (JSON)  ──┼──►  Azure Function / Logic App  ──►  .set-or-replace
  SOAR export (CSV)     ──┤     or Data Factory pipeline         ThreatIntelRef
  Blob drop (daily file)──┘     (normalize to MatchKey schema)        │
                                                                      │
  SecLogsParsed ◄──────────────── join at query time ────────────────┘
  (events keep streaming via Event Hub / IoT / batch)
```

| | **Lab (Day 4)** | **Production** |
|---|-----------------|----------------|
| Who fills the table? | You run Q2 in Query tab | Scheduled pipeline |
| Update pattern | Once per lab run | Hourly or daily refresh |
| Events | Already in `SecLogsParsed` | Append continuously — **separate lifecycle** |
| Join pattern | Lab 2 Q3 — same KQL idea | Analyst investigations — same KQL idea |

Events and threat intel **do not share the same ingest path**. Logs append continuously; the watchlist **refreshes on a schedule**. Analysts **`join` at query time** — exactly like Lab 2 Q3, but the reference table is maintained by feeds and automation instead of a `datatable` in a query file.

```text
  LAB (this course)                         PRODUCTION

  02-threatintel-join.kql Q2                TI feed / ISAC / SOAR / internal lists
       │                                         │
       v                                         v
  .create table ThreatIntelRef              .set-or-replace / ingest
  .set-or-replace (8 inline rows)            scheduled refresh
       │                                         │
       └──────────── join at query time ─────────┘
                         │
                         v
                  SecLogsParsed (events)
```

No student action is required outside **dataexplorer.azure.com** for Lab 2.

## 1.8 Gold aggregate — `SecLogsHourly` (Lab 7 preview)

**Gold** pre-computes rollups so dashboards do not re-scan all Silver rows every refresh. Day 4 Lab 7 creates **`SecLogsHourly`** as a **materialized view** on `SecLogsParsed` (Section **6**).

| Column | Meaning |
|--------|---------|
| `HourBucket` | `bin(Timestamp, 1h)` |
| `Facility`, `EventType` | Group-by dimensions |
| `EventCount` | Events in bucket |
| `HighSeverityCount` | High + Critical in bucket |

Locked check: `sum(EventCount)` = **3500** — must match Silver row count after full pipeline.

**Real-world Gold use:** A utility control-room dashboard shows **auth failures per hour by facility** without scanning billions of Silver rows. Operators spot a spike at `Corporate-VPN` during off-hours. In the lab, one Gold row might look like:

| HourBucket | Facility | EventType | EventCount | HighSeverityCount |
|------------|----------|-----------|------------|-------------------|
| 2026-06-11 09:00 | Corporate-VPN | AuthFailure | 10 | 10 |
| 2026-06-11 09:00 | DMZ-Firewall | FirewallDeny | 56 | 56 |

Gold is still part of the **star** — it is a **pre-aggregated spoke** optimized for read-heavy dashboards, not a replacement for Silver investigations.

## 1.9 Architecture diagram — joins and materialized view

```text
  SecLogsRaw (Bronze)  ──update policy──►  SecLogsParsed (Silver FACT)
                                                  │
                        ┌─────────────────────────┼─────────────────────────┐
                        │ join (Lab 2)            │ materialized view (Lab 7) │
                        v                         v                         │
                  ThreatIntelRef              SecLogsHourly (GOLD)            │
                  (DIMENSION)                 hourly aggregates               │
                        │                                                   │
                        └──── Lab 2 IOC enrichment queries ────────────────────────┘
```

Advanced KQL today runs mostly on **`SecLogsParsed`**. **`ThreatIntelRef`** enriches; **`SecLogsHourly`** serves rollup queries.

## 1.10 Reading guide — theory vs lab order

| Order | README theory | Labs (hands-on) |
|-------|---------------|-----------------|
| Joins + reference | §2 | Lab 2 |
| Time-series | §3 | Lab 3 |
| Anomalies | §4 | Lab 4 |
| Window functions | §5 | Lab 5 |
| UDFs | §7 | **Lab 6** |
| Gold materialized view | §6 | **Lab 7** |

Theory presents **Gold MV (§6)** before **UDFs (§7)** because MV builds on hourly `bin()` from §3. Labs run **UDF first, then Gold MV** so you finish with the capstone aggregate. Always follow [labs.md](labs.md) for step order.

```text
  THEORY (README)              HANDS-ON (labs.md)
  §2 join                      Lab 2
  §3 time-series               Lab 3
  §4 anomalies                 Lab 4
  §5 windows                   Lab 5
  §6 Gold MV  ───────────────► Lab 7  (capstone)
  §7 UDFs     ───────────────► Lab 6  (before Gold)
```

## 1.11 Locked counts entering Day 4

Verify in **Lab 1** before creating new objects:

| Check | Query / table | Expected |
|-------|---------------|----------|
| Silver total | `SecLogsParsed \| count` | **3500** |
| Source systems | `dcount(SourceSystem)` | **4** |
| AuthFailure | `where EventType == "AuthFailure"` | **700** |
| Bronze unchanged | `SecLogsRaw \| count` | **3500** |

Reference: locked counts in [labs.md](labs.md).

If Silver ≠ **3500**, complete Day 3 Lab 5 backfill before continuing — Gold totals and join labs assume full Silver.

# 2. Joins and reference data

**Reference tables** hold slowly changing lookup data — threat intel, watchlists, asset metadata. **Fact tables** (`SecLogsParsed`) hold high-volume events. **`join`** combines them at query time without duplicating dimension columns into every event row ([Microsoft — join operator](https://learn.microsoft.com/en-us/kusto/query/join-operator)).

Section **1.4** introduced the **star schema**; **§1.7** covers **`ThreatIntelRef`**. This section covers join syntax, join flavors, and Lab 2 enrichment queries.

## 2.1 Why reference data is separate

| Approach | Pros | Cons |
|----------|------|------|
| **Embed IOC in every event at ingest** | Simple queries | Intel changes require re-ingest; stale data |
| **Reference table + join (this course)** | Update dimension independently; smaller fact storage | Join overhead at query time |
| **Materialized enrichment (advanced)** | Pre-joined column for hot paths | Extra storage + refresh logic |

Utility SOC workflow: a production team **refreshes** a threat-intel reference table (same role as **`ThreatIntelRef`**) from ISAC, vendor, and SOAR feeds on a schedule — see [§1.7 production](#production-where-threat-intel-comes-from). **`SecLogsParsed`** keeps appending events; analysts **`join`** at query time to flag known bad IPs and patterns. **In Lab 2 you simulate the refresh** with `.set-or-replace` and the 8 inline rows in Q2 (see [What seed means](#what-seed-means)).

## 2.2 `ThreatIntelRef` — locked dimension schema

Lab 2 creates and seeds the table ([queries/02-threatintel-join.kql](queries/02-threatintel-join.kql)):

| Column | Type | Purpose |
|--------|------|---------|
| `MatchKey` | `string` | Value to match — IP address or `EventType` name |
| `MatchType` | `string` | **`SourceIP`** or **`EventType`** — which fact column to join |
| `ThreatCategory` | `string` | SOC label — e.g. `BruteForceTarget`, `ExternalScanner` |
| `SeverityHint` | `string` | Analyst priority hint — `Critical`, `High`, `Medium` |

**Locked row count:** **8** IOC / pattern rows.

```text
  MatchType = SourceIP          MatchType = EventType
  ─────────────────────         ───────────────────────
  10.20.1.44  BruteForceTarget  AuthFailure  CredentialAttack
  203.0.113.50 ExternalScanner FirewallDeny PerimeterBlock
  ... (5 IP rows)               ... (3 EventType rows)
```

Two join keys in one dimension table — filtered by `MatchType` before join to avoid ambiguous matches.

## 2.3 Join anatomy — KQL syntax

Microsoft join syntax ([join operator](https://learn.microsoft.com/en-us/kusto/query/join-operator)):

```kql
LeftTable
| join [kind=JoinFlavor] (RightTable) on Conditions
```

Course pattern — fact on the left, dimension on the right:

```kql
SecLogsParsed                                          // LEFT — all events
| join kind=leftouter (
    ThreatIntelRef
    | where MatchType == "SourceIP"
    | project MatchKey, ThreatCategory, SeverityHint   // RIGHT — small lookup
) on $left.SourceIP == $right.MatchKey
```

| Clause | Role |
|--------|------|
| `$left` | Columns from left table (`SecLogsParsed`) |
| `$right` | Columns from right table (`ThreatIntelRef`) |
| `on` | Equality condition — must be explicit keys |
| `project` on right | Drop unused dimension columns before join (smaller hash) |

```text
  JOIN FLOW (Lab 2 Q3)

  SecLogsParsed (LEFT)              ThreatIntelRef (RIGHT)
  3500 event rows                   filter MatchType = SourceIP
  SourceIP, EventType, ...    +     5 IP rows only
           │                              │
           └──────── on SourceIP = MatchKey ────┘
                         │
                         v
              rows with ThreatCategory filled in
              filter isnotempty → ~409 enriched rows
```

## 2.4 Join flavors used in this course

| Kind | Keeps | Lab use |
|------|-------|---------|
| **`leftouter`** | All **left** rows; nulls where no match | **Q3** — **IOC enrichment report**; filter `isnotempty(ThreatCategory)` for matches only |
| **`inner`** | Only matching rows from both sides | Production high-volume when you only want hits |

```text
  leftouter (Lab 2 Q3)              inner (production pattern)

  All 3500 Silver rows              Only rows with IOC match
  + ThreatCategory if matched     Smaller result set
  Filter: isnotempty(...)         No filter needed
```

**Left outer** proves how many events **lack** intel (null `ThreatCategory`). **Inner** is appropriate when the question is *only* "show me known-bad IPs."

## 2.5 Lab 2 queries — SourceIP and EventType joins

Lab 2 runs **two joins** on the same dimension table — different **`MatchType`** filter, different analyst question:

```text
  Q3 (SourceIP)                         Q4 (EventType)

  "Which events hit a              "How many events of each
   known-bad IP?"                    type match a pattern IOC?"

  join on SourceIP                 join on EventType
  ~409 enriched rows               3 summary rows (800/700/200)
  row-level report                 aggregate by ThreatCategory
```

### Q3 — enrich by SourceIP

```kql
SecLogsParsed
| join kind=leftouter (
    ThreatIntelRef
    | where MatchType == "SourceIP"
    | project MatchKey, ThreatCategory, SeverityHint
) on $left.SourceIP == $right.MatchKey
| where isnotempty(ThreatCategory)
| project Timestamp, EventType, SourceIP, Facility, ThreatCategory, SeverityHint
| order by Timestamp asc
```

**Expected:** ≥ **300** rows with non-empty `ThreatCategory` (lab data typically **~409**; IPs in both fact and reference data).

Utility example: `10.20.1.44` auth failure tagged **`BruteForceTarget`** / **`Critical`**.

### Q4 — summarize by EventType pattern

```kql
SecLogsParsed
| join kind=leftouter (
    ThreatIntelRef
    | where MatchType == "EventType"
    | project MatchKey, ThreatCategory, SeverityHint
) on $left.EventType == $right.MatchKey
| where isnotempty(ThreatCategory)
| summarize MatchCount = count() by ThreatCategory, EventType
```

Maps event **types** (not IPs) to categories like **`CredentialAttack`** for all `AuthFailure` rows.

**Expected Q4 output (3 rows):**

| ThreatCategory | EventType | MatchCount |
|----------------|-----------|------------|
| `PerimeterBlock` | `FirewallDeny` | **800** |
| `CredentialAttack` | `AuthFailure` | **700** |
| `PrivilegeAbuse` | `PrivilegeEscalation` | **200** |

Q4 matches **every** row of those event types — not just IP-based hits from Q3.

## 2.6 Performance pattern — filter facts before join

Lab data has **3500** rows — joins are trivial. Production fact tables have billions of rows:

```kql
// GOOD — bounded fact table + explicit join keys (lab: fixed June 2026 sample window)
SecLogsParsed
| where Timestamp between (datetime(2026-06-11) .. datetime(2026-06-13))
| join kind=inner (
    ThreatIntelRef
    | where MatchType == "SourceIP"
    | project MatchKey, ThreatCategory
) on $left.SourceIP == $right.MatchKey
```

| Practice | Why |
|----------|-----|
| Filter **`Timestamp`** on facts first | Fewer rows enter hash join |
| **`project`** only needed columns on dimension | Smaller right side |
| Keep dimension table **small** | Broadcast-friendly |

Day 5 covers **`hint.strategy=broadcast`** when the dimension fits in memory ([join hints](https://learn.microsoft.com/en-us/kusto/query/join-operator#join-hints)). Do not use hints in Lab 2 — data is too small to matter.

# 3. Time-series analysis

Security operations teams track **how event volume changes over time** — auth failures spiking after hours, firewall denies clustering around maintenance windows, IoT anomalies during quiet periods. Time-series KQL on **`SecLogsParsed`** follows two steps: **bucket** timestamps with **`bin()`**, then build regular series with **`make-series`** for charting and anomaly functions ([Microsoft — time series analysis](https://learn.microsoft.com/en-us/kusto/query/time-series-analysis)).

Earlier modules introduced **`bin()`** and **`summarize`**. This module adds **`make-series`** — the bridge to anomaly detection and Gold hourly aggregates.

## 3.1 From events to time buckets

Each Silver row has a **`Timestamp`**. Raw row lists are hard to chart — **`bin()`** groups events into fixed-width time windows:

```kql
SecLogsParsed
| summarize EventCount = count() by HourBucket = bin(Timestamp, 1h), EventType
| order by HourBucket asc, EventType asc
```

| Concept | Lab value | Production example |
|---------|-----------|-------------------|
| **Bin size** | **1h** | 15m for active incidents; 1d for compliance trends |
| **Group-by** | `EventType` | `Facility`, `SourceSystem`, `Severity` |
| **Output** | Tabular rows per bucket | Same — feeds dashboards |

```text
  ROW-LEVEL (3500 events)              BUCKETED (Q1 output)

  09:00:01 AuthFailure               2026-06-11 09:00  AuthFailure  count=3
  09:02:15 AuthFailure        ──►    2026-06-11 10:00  AuthFailure  count=2
  10:00:01 AuthFailure               2026-06-12 08:00  VPNLogin     count=2
  ...                                (one row per hour × EventType combo)
```

This **`summarize` + `bin()`** pattern is the same logic inside the **Gold** materialized view (Section **6**) — `bin(Timestamp, 1h)` by `Facility` and `EventType`.

## 3.2 `make-series` — regular arrays for analytics

**`make-series`** converts irregular events into **aligned numeric arrays** — one array per series partition. Microsoft uses this structure for time-series functions, forecasting, and anomaly detection ([time series analysis](https://learn.microsoft.com/en-us/kusto/query/time-series-analysis)).

Syntax pattern:

```kql
Table
| make-series Metric=Aggregation() default=DefaultValue
  on TimestampColumn from StartTime to EndTime step BinSize
  by DimensionColumn
```

Lab 3 Q2 ([queries/03-time-series.kql](queries/03-time-series.kql)):

```kql
SecLogsParsed
| make-series EventCount=count() default=0 on Timestamp from datetime(2026-06-11) to datetime(2026-06-13) step 1h by EventType
| project EventType, EventCount
```

| Clause | Lab 3 value | Purpose |
|--------|-------------|---------|
| `EventCount=count()` | Count per hour | Metric to chart / analyze |
| `default=0` | Zero for empty hours | **Critical** — continuous timeline |
| `from datetime(2026-06-11) to datetime(2026-06-13)` | Lab sample window |
| `step 1h` | Hourly bins | Matches Q1 and Gold MV |
| `by EventType` | One series per type | Compare AuthFailure vs VPNLogin, etc. |

Output: **`EventCount`** is a **`dynamic`** array (e.g. `[0,0,3,2,0,...]`), not a scalar.

```text
  summarize + bin (Q1)                 make-series (Q2)

  Table of rows                        One row per EventType
  HourBucket | EventType | count       EventType | EventCount (dynamic array)
  ─────────────────────────────        AuthFailure | [0,0,3,2,1,...]
  Easy for SQL-style reports           Required for series_* functions
```

## 3.3 Why `default=0` matters

Utility substations may have **quiet hours** with zero security events. Without **`default=0`**, empty bins are **omitted** from the series — charts show disconnected spikes and anomaly algorithms misread gaps as missing data.

| Setting | Empty hour behavior | Chart / ML impact |
|---------|---------------------|-------------------|
| No default | Bin skipped | Gaps in timechart |
| **`default=0`** | Bin present with value 0 | Continuous timeline |

Quiet-period example: **Substation-C** overnight — zero `SensorAnomaly` events still appear as `0` in the hourly array, so a sudden spike at 09:00 stands out visually.

## 3.4 Lab 3 queries — Q1 through Q3

Hands-on file: [queries/03-time-series.kql](queries/03-time-series.kql).

### Q1 — hourly tabular counts

```kql
SecLogsParsed
| summarize EventCount = count() by HourBucket = bin(Timestamp, 1h), EventType
| order by HourBucket asc, EventType asc
```

Inspect which hours contain which event types. Expect sparse rows — lab data spans two calendar days with **3500** total events.

### Q2 — make-series by EventType

```kql
SecLogsParsed
| make-series EventCount=count() default=0 on Timestamp from datetime(2026-06-11) to datetime(2026-06-13) step 1h by EventType
| project EventType, EventCount
```

**Success check:** ≥ **1** `EventType` with a **`dynamic`** `EventCount` array. Multiple event types produce multiple rows.

### Q3 — AuthFailure series only

```kql
SecLogsParsed
| where EventType == "AuthFailure"
| make-series EventCount=count() default=0 on Timestamp from datetime(2026-06-11) to datetime(2026-06-13) step 1h
```

Filters facts **before** `make-series` — same pattern as production ("build series for auth failures only"). Lab data has **700** AuthFailure rows across several hours.

## 3.5 Optional visualization — `render timechart`

After Q1 or Q2, add a chart for discussion:

```kql
SecLogsParsed
| summarize EventCount = count() by bin(Timestamp, 1h), EventType
| render timechart
```

Open the **Chart** tab in ADX Web UI (Day 1 Lab 5 — [../day-01/queries/05-summarize-timechart.kql](../day-01/queries/05-summarize-timechart.kql)).

## 3.6 Connection to Gold layer

Lab 7 creates **`SecLogsHourly`** — a **materialized view** that pre-computes hourly counts so dashboards skip ad-hoc `summarize`:

```kql
// Conceptual — same bin logic as Q1, persisted in Gold (Section 6)
summarize EventCount = count(), HighSeverityCount = countif(...)
  by HourBucket = bin(Timestamp, 1h), Facility, EventType
```

**Today:** run Q1 ad-hoc on Silver. **Lab 7:** create MV so the aggregation runs automatically as Silver grows.

# 4. Anomaly detection

After **`make-series`** builds hourly arrays, **`series_decompose_anomalies`** decomposes each series into **baseline**, **score**, and an **anomaly flag** — surfacing buckets that deviate from expected patterns ([time series analysis — anomalies](https://learn.microsoft.com/en-us/kusto/query/time-series-analysis)).

Lab 4 applies this to security event counts. Lab data is small — flags may be **zero or sparse**; the goal is understanding the **pattern**, not finding real incidents in **3500** rows.

## 4.1 Pipeline — series first, then decompose

```text
  SecLogsParsed (rows)
         │
         │  make-series (Section 3)
         v
  EventCount dynamic array
         │
         │  series_decompose_anomalies
         v
  baseline[], score[], anomalies[]  (1 = flagged hour)
```

You cannot call **`series_decompose_anomalies`** on raw event rows — input must be a **make-series** output column.

## 4.2 Function anatomy

```kql
| extend (anomalies, score, baseline) = series_decompose_anomalies(
    EventCount,    // dynamic array from make-series
    1.5,           // anomaly threshold (seasonality)
    -1,            // trend sensitivity (-1 = auto)
    'linefit'       // decomposition mode
)
```

| Parameter | Lab value | Meaning |
|-----------|-----------|---------|
| **Series column** | `EventCount` | Hourly count array |
| **1.5** | Threshold | Higher = fewer flags; lower = more sensitive |
| **-1** | Trend | Auto-detect trend component |
| **`linefit`** | Model | Linear fit decomposition |

Output columns (all **`dynamic`** arrays aligned with the series):

| Column | Type | Interpretation |
|--------|------|----------------|
| `baseline` | `double[]` | Expected level for each hour |
| `score` | `double[]` | Deviation strength |
| `anomalies` | `long[]` | **`1`** = anomalous bucket; **`0`** = normal |

Filter flagged hours: `where anomalies == 1` (after **`mv-expand`** if you need tabular rows).

## 4.3 Lab 4 queries — Q1 and Q2

File: [queries/04-anomaly-detection.kql](queries/04-anomaly-detection.kql).

### Q1 — FirewallDeny series + decompose

```kql
let series = SecLogsParsed
| where EventType == "FirewallDeny"
| make-series EventCount=count() default=0 on Timestamp from datetime(2026-06-11) to datetime(2026-06-13) step 1h;
series
| extend (anomalies, score, baseline) = series_decompose_anomalies(EventCount, 1.5, -1, 'linefit')
| project EventCount, baseline, score, anomalies
```

Inspect **`dynamic`** arrays in the results grid. Even with no flags, **`baseline`** and **`score`** columns should populate.

### Q2 — expand and list anomalous hours

```kql
SecLogsParsed
| make-series EventCount=count() default=0 on Timestamp from datetime(2026-06-11) to datetime(2026-06-13) step 1h
| extend (anomalies, score, baseline) = series_decompose_anomalies(EventCount, 1.5, -1, 'linefit')
| mv-expand Timestamp to typeof(datetime), EventCount to typeof(long),
           anomalies to typeof(long), score to typeof(double), baseline to typeof(double)
| where anomalies == 1
| project Timestamp, EventCount, score, baseline
```

**`mv-expand`** converts parallel arrays into one row per hour — easier to read than scanning dynamic columns.

**Lab expectation:** **0 or 1** rows on Lab 4 (sparse data at lab scale). Production firewall **TB-scale** series with weeks of history produce meaningful flags.

## 4.4 Reading results for SOC analysts

| Observation | Action |
|-------------|--------|
| `anomalies == 1` and high `score` | Investigate events in that hour — filter `SecLogsParsed` by `Timestamp` |
| Flag on quiet series (mostly zeros) | Lab artifact — need longer history |
| No flags | Lower threshold (e.g. **1.2**) in production tuning — not in locked lab |
| Baseline tracks trend | Normal growth; anomaly = deviation **from** baseline |

```text
  ANOMALY → INVESTIGATION (production pattern)

  Lab 4 flags hour H          drill down to Silver
  anomalies[] = 1      ──►    SecLogsParsed | where Timestamp between (H .. H+1h)
```

Utility example: hourly **FirewallDeny** count at DMZ spikes 3× above baseline → pivot to `Facility == "DMZ-Firewall"` rows in that hour.

# 5. Window functions

Time-series analysis (Section **3**) works on **aggregated buckets**. Window functions work on **ordered rows** — answering *what happened immediately before this event?* and *what sequence number is this within a facility?*

KQL window patterns require **`order by`**, then **`serialize`**, then functions like **`row_number()`** and **`prev()`** ([serialize operator](https://learn.microsoft.com/en-us/kusto/query/serialize-operator), [row_number](https://learn.microsoft.com/en-us/kusto/query/row-number-function), [prev](https://learn.microsoft.com/en-us/kusto/query/prev-function)).

## 5.1 Ordered analysis vs summarize

| Question type | Tool | Example |
|---------------|------|---------|
| How many events per hour? | **`summarize` + `bin()`** | Section **3** Q1 |
| What was the **previous** event type? | **`prev()`** after **`serialize`** | Lab 5 Q2 |
| Event #3 at this substation today? | **`row_number()`** | Lab 5 Q1 |
| Success immediately followed by failure? | **`prev()` + `where`** | Lab 5 Q3 |

```text
  AGGREGATE (Day 4 §3)              SEQUENTIAL (this section)

  3500 rows → bins → counts           3500 rows → sort → row 1, 2, 3...
  Loses individual order            Preserves event order
```

## 5.2 Why `serialize` is required

ADX executes queries in parallel across partitions. **`serialize`** forces **single-threaded, ordered** evaluation so **`prev()`**, **`next()`**, and **`row_number()`** see rows in the order you specified ([serialize](https://learn.microsoft.com/en-us/kusto/query/serialize-operator)).

```kql
SecLogsParsed
| order by Timestamp asc    // 1. Define order FIRST
| serialize                 // 2. Lock evaluation order
| extend PrevEventType = prev(EventType)   // 3. Window function
```

| Step | Skip it and… |
|------|----------------|
| `order by` | Window functions use undefined order |
| `serialize` | `prev()` may return values from wrong rows |
| Window after both | Pattern fails silently or inconsistently |

## 5.3 `row_number()` — sequence within a partition

Lab 5 Q1 ([queries/05-window-functions.kql](queries/05-window-functions.kql)):

```kql
SecLogsParsed
| order by Facility, Timestamp asc
| serialize
| extend EventSeqInFacility = row_number(1, prev(Facility) != Facility)
```

**`row_number(start, restart)`** assigns 1, 2, 3… in sort order. The second argument **`prev(Facility) != Facility`** **restarts the counter** whenever the facility changes — so event #1 at Substation-A is truly the first event at that site (not a global row index across all **3500** rows).

Utility use: identify the **first** or **Nth** event at a substation during an incident window.

## 5.4 `prev()` — prior row values

Lab 5 Q2:

```kql
SecLogsParsed
| order by Timestamp asc
| serialize
| extend PrevEventType = prev(EventType),
         MinutesSincePrev = datetime_diff('minute', Timestamp, prev(Timestamp))
```

| Column | Meaning |
|--------|---------|
| `PrevEventType` | Event type on the **previous row** in time order |
| `MinutesSincePrev` | Gap in minutes between current and previous event |

First row in the ordered set has **null** `prev()` values — expected.

## 5.5 Lab 5 Q3 — success-then-failure pattern

Investigative pattern — auth **success** immediately followed by **failure** at the same **`Facility`** (SCADA gateway compromise indicator):

```kql
SecLogsParsed
| order by Facility, Timestamp asc
| serialize
| extend PrevType = prev(EventType), PrevFacility = prev(Facility)
| where EventType == "AuthFailure" and PrevType == "AuthSuccess" and Facility == PrevFacility
| project Timestamp, Facility, EventType, PrevType, Message
```

Lab data includes **`AuthSuccess`** rows in batch JSON/CSV ([data/bronze](../data/bronze/)). Q3 typically returns **~182** rows — auth **success** immediately followed by **failure** at the same **`Facility`**.

```text
  Q3 pattern (same Facility, consecutive rows)

  ...  AuthSuccess  Substation-A  (row N)
       AuthFailure  Substation-A  (row N+1)  ◄── flagged (~182 in lab data)
```

Investigative use: possible credential misuse or session hijack on SCADA-adjacent hosts.

# 6. Materialized views — Gold `SecLogsHourly`

**Gold** pre-computes aggregates so dashboards query a **smaller, purpose-built** table instead of re-scanning all of Silver. ADX implements Gold here with a **materialized view** — a managed object that **continuously aggregates** `SecLogsParsed` as new Silver rows arrive ([materialized views overview](https://learn.microsoft.com/en-us/azure/data-explorer/kusto/management/materialized-views/materialized-view-overview)).

Section **3** Q1 ran the same **`summarize` + `bin(Timestamp, 1h)`** logic ad-hoc. Lab **7** persists it as **`SecLogsHourly`**.

## 6.1 Materialized view vs update policy

| Mechanism | Source → Target | Course use |
|-----------|-----------------|------------|
| **Update policy** (Day 3) | Bronze → Silver row-level parse | One typed row per Bronze row |
| **Materialized view** (Day 4) | Silver → Gold **aggregated** buckets | Hourly counts — fewer rows than Silver |

```text
  SecLogsParsed (3500 rows)     SecLogsHourly (fewer rows)
  row-level facts      ──MV──►  HourBucket + Facility + EventType
                               EventCount, HighSeverityCount
```

Both run **automatically in the background** after creation — no scheduled job.

```text
  MV LIFECYCLE (Lab 7)

  Q1  .drop + .create MV (backfill=true)
           │
           │  wait 30–60 seconds  ◄── backfill runs async
           v
  Q2–Q3  query SecLogsHourly
           │
           v
  verify  sum(EventCount) = 3500  (must equal Silver row count)
```

## 6.2 Locked Gold schema

| Column | Type | Definition |
|--------|------|------------|
| `HourBucket` | `datetime` | `bin(Timestamp, 1h)` |
| `Facility` | `string` | Substation, VPN, DMZ, … |
| `EventType` | `string` | AuthFailure, SensorAnomaly, … |
| `EventCount` | `long` | Events in bucket |
| `HighSeverityCount` | `long` | `countif(Severity in ("High","Critical"))` |

## 6.3 Create MV with backfill

Silver already holds Day 2–3 history when Lab 7 runs. Without **backfill**, the MV would only aggregate rows ingested **after** creation. Use **`backfill=true`** ([materialized views overview](https://learn.microsoft.com/en-us/azure/data-explorer/kusto/management/materialized-views/materialized-view-overview)):

```kql
.drop materialized-view SecLogsHourly ifexists

.create materialized-view with (backfill=true, effectiveDateTime=datetime(2020-01-01)) SecLogsHourly on table SecLogsParsed
{
    SecLogsParsed
    | summarize
        EventCount = count(),
        HighSeverityCount = countif(Severity in ("High", "Critical"))
      by HourBucket = bin(Timestamp, 1h), Facility, EventType
}
```

| Property | Lab value | Purpose |
|----------|-----------|---------|
| `backfill=true` | On | Include existing **3500** Silver rows |
| `effectiveDateTime` | `2020-01-01` | Start of backfill window |
| Source table | `SecLogsParsed` | Silver fact |

File: [queries/07-gold-materialized-view.kql](queries/07-gold-materialized-view.kql).

## 6.4 Verify — locked total **3500**

Wait **30–60 seconds** after Q1, then:

```kql
SecLogsHourly
| summarize TotalEvents = sum(EventCount), HighSeverityTotal = sum(HighSeverityCount)
```

| Check | Expected |
|-------|----------|
| **`sum(EventCount)`** | **3500** (matches Silver) |
| `.show materialized-views` | `SecLogsHourly` listed |

If Q3 shows **0**, re-run after wait — MV refresh is asynchronous on first create.

## 6.5 Query patterns on Gold

Dashboard-style rollup (Lab 7 Q4):

```kql
SecLogsHourly
| summarize Total = sum(EventCount) by Facility
| top 5 by Total desc
```

Drill-down: filter **`HourBucket`** and **`Facility`**, then return to **`SecLogsParsed`** for row-level detail in that hour.

# 7. User-defined functions (UDFs)

**User-defined functions** store reusable KQL logic in the database — shared across analysts, dashboards, and automation ([create function](https://learn.microsoft.com/en-us/kusto/management/create-function)). Lab **6** creates **`SeverityRank`** and **`IsOTFacility`** in folder **`Training`**.

## 7.1 Why UDFs in utility SOC workflows

```text
  WITHOUT UDF                         WITH UDF

  copy case() in every query    →    SeverityRank(Severity) once
  OT facility list drifts       →    IsOTFacility(Facility) shared
  dashboard breaks on edit      →    update function, all queries fixed
```

| Without UDF | With UDF |
|-------------|----------|
| Copy-paste `case()` severity logic in every query | **`SeverityRank(Severity)`** once |
| Inconsistent OT facility lists | **`IsOTFacility(Facility)`** centralized |
| Dashboard breaks when logic changes | Update function definition |

## 7.2 Create and invoke — `SeverityRank`

Lab 6 Q1 ([queries/06-create-udf.kql](queries/06-create-udf.kql)):

```kql
.create-or-alter function with (
    docstring = "Map severity string to numeric rank",
    folder = "Training"
) SeverityRank(Severity:string)
{
    case(
        Severity == "Low", 1,
        Severity == "Medium", 2,
        Severity == "High", 3,
        Severity == "Critical", 4,
        0)
}
```

Invoke like any function:

```kql
SecLogsParsed
| extend Rank = SeverityRank(Severity)
| where Rank >= 3
| summarize HighCriticalCount = count() by Facility, EventType
```

| Severity | Rank |
|----------|------|
| Low | 1 |
| Medium | 2 |
| High | 3 |
| Critical | 4 |

## 7.3 `IsOTFacility` — OT-adjacent filter

**OT-adjacent** = **Operational Technology–adjacent** — logs from substations, SCADA gateways, or field IoT that sit in or near the OT zone (see [GLOSSARY.md](../GLOSSARY.md)). Not the same as generic corporate IT (VPN, office auth), though both land in ADX for hybrid investigations.

```kql
.create-or-alter function with (
    docstring = "True when Facility is OT-adjacent (substation or SCADA gateway)",
    folder = "Training"
) IsOTFacility(Facility:string)
{
    Facility in ("Substation-A", "Substation-B", "Substation-C", "Substation-D", "SCADA-Gateway")
}
```

```kql
SecLogsParsed
| where IsOTFacility(Facility)
| summarize OTEventCount = count() by Facility, EventType
```

Separates **OT-adjacent** *(substation / SCADA / field IoT)* events from corporate VPN/DMZ facilities for hybrid **IT/OT** *(Information Technology / Operational Technology)* investigations.

## 7.4 Management commands

```kql
.show functions
.show function SeverityRank
```

In **your database**, use **`.create-or-alter`** — safe to re-run without duplicate errors when repeating a lab.

# 8. Hot vs cold data, retention, and caching

ADX stores data in **extents** on blob storage. **Caching** and **retention** policies control how long data stays in fast **hot cache** vs compressed cold storage, and when data **expires** ([retention policy](https://learn.microsoft.com/en-us/azure/data-explorer/kusto/management/retention-policy)).

Lab **7** Q5 runs **`.show`** commands only — production **`.alter` policy** changes require governance.

## 8.1 Hot cache vs cold storage

| Tier | Speed | Utility cyber example |
|------|-------|----------------------|
| **Hot cache** | SSD — sub-second queries | Last 7–14 days — active incident investigation |
| **Cold** (still queryable) | Slower — compressed extents | 90-day–1-year compliance search |
| **Beyond retention** | Data dropped | After NERC-aligned retention period |

At **GB lab scale**, all **3500** Silver rows are hot. At **TB scale**, tuning cache period vs query patterns affects query speed and resource use.

```text
  EXTENT LIFECYCLE (conceptual)

  ingest ──► extent on blob ──► hot cache (fast queries)
                                    │
                                    │ aging / policy
                                    v
                               cold (still queryable, slower)
                                    │
                                    │ retention expires
                                    v
                               dropped
```

## 8.2 Retention policy — what it controls

Retention defines **minimum time data is kept** before eligible for deletion. Scope: database, table, or materialized view.

```kql
.show database policy retention
.show table SecLogsParsed policy retention
```

Utility pattern: **`SecLogsParsed`** longer retention for investigations; **`SecLogsHourly`** Gold may retain longer for trend dashboards with less storage than raw facts.

## 8.3 Caching policy — what it controls

Caching policy defines how long extents stay in **hot cache** on cluster nodes:

```kql
.show table SecLogsParsed policy caching
```

Frequently queried tables (Silver facts, hot Gold MVs) get longer cache windows. Rarely queried archive tables get shorter cache — keeps hot cache focused on active data.

## 8.4 Lab 7 Q5 — review only

```kql
.show database policy retention
.show table SecLogsParsed policy retention
.show table SecLogsParsed policy caching
```

| Command | Purpose |
|---------|---------|
| Database retention | Default for all tables |
| Table retention | Override per table |
| Table caching | Hot cache duration |

Close Day 4 with [labs.md](labs.md): Gold **`SecLogsHourly`** with **`sum(EventCount)` = 3500**, threat intel join, and UDFs on Silver.

**Do not alter** policies on the shared training cluster unless directed in class.

# 9. Day 5 preview

Day 5 shifts from **building** analytics objects to **operating** them at scale on a utility SOC platform.

```text
  DAY 4 (you built)                    DAY 5 (you optimize & investigate)

  SecLogsParsed + ThreatIntelRef       hint.strategy on joins
  SecLogsHourly MV                     ingestion diagnostics
  UDFs in Training folder              RBAC / RLS concepts
                                       capstone: Bronze → Gold drill-down
```

| Topic | Day 5 focus |
|-------|-------------|
| Query optimization | Time filters, join hints (`hint.strategy`), extent scan awareness |
| Ingestion diagnostics | `.show ingestion failures`, latency patterns |
| Security | RBAC roles, row-level security — hands-on in [Day 5 Lab 5](../day-05/labs.md#lab-5--security-rbac-and-rls-demo) |
| MV vs on-demand | When **`SecLogsHourly`** beats ad-hoc `summarize` |
| Capstone | End-to-end investigation across Bronze → Gold |

**Prerequisite for Day 5:** Your database retains **`SecLogsParsed` (3500)**, **`ThreatIntelRef` (8)**, and **`SecLogsHourly`** with **`sum(EventCount)` = 3500**.

**Next:** [Day 05 — Performance, Security, Operations & Capstone](../day-05/README.md)
