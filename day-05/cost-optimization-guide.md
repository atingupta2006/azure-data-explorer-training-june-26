# Azure Data Explorer — Cost Optimization Guide (Utility Cyber SOC)

**Purpose:** A dedicated, self-contained hands-on guide for **cost optimization** on your training cluster. Every concept includes **explanations**, **examples**, and **KQL you run yourself** in **your workspace database** on `adx-training-tcs` (example: **`LogsDB_u01`**).

**Audience:** Utility cyber analysts and platform operators moving from lab scale (**3500** Silver rows) to production **TB-scale** estates.

**Time:** Plan **90–120 minutes** to complete all parts and exercises.

---

## How to use this guide

1. Open [dataexplorer.azure.com](https://dataexplorer.azure.com) → cluster **`adx-training-tcs`** → **your** database.
2. Work through **Parts 1–10** in order — run **one KQL block at a time** with **Shift+Enter**.
3. Compare results to **Expected** tables after every step.
4. Complete **Part 9 exercises** and **Part 10 statistics comparison**; use **Appendix C** monthly checklist.

**Do not** assume other course files — everything you need is here.

---

## Lab worksheet

| Variable | Your value (example) |
|----------|----------------------|
| Cluster URI | `https://adx-training-tcs.centralindia.kusto.windows.net` |
| Database | `LogsDB_u01` |
| Today's baseline Silver rows | *(fill after gate)* |
| Today's Gold sum | *(fill after gate)* |

---

## Pipeline gate (run first)

| Object | Expected count |
|--------|----------------|
| `SecLogsParsed` | **3500** |
| `ThreatIntelRef` | **8** |
| `SecLogsHourly` sum(`EventCount`) | **3500** |
| `SecLogsRaw` | **3500** |
| AuthFailure on Silver | **700** |
| Distinct `SourceSystem` | **4** |

```kql
print
    Silver = toscalar(SecLogsParsed | count),
    ThreatIntel = toscalar(ThreatIntelRef | count),
    Gold = toscalar(SecLogsHourly | summarize sum(EventCount)),
    Bronze = toscalar(SecLogsRaw | count),
    AuthFailures = toscalar(SecLogsParsed | where EventType == "AuthFailure" | count),
    SourceSystems = toscalar(SecLogsParsed | summarize dcount(SourceSystem)),
    Ready = (
        toscalar(SecLogsParsed | count) == 3500
        and toscalar(ThreatIntelRef | count) == 8
        and toscalar(SecLogsHourly | summarize sum(EventCount)) == 3500
    )
```

**Expected:** `Silver = 3500`, `ThreatIntel = 8`, `Gold = 3500`, `Bronze = 3500`, `AuthFailures = 700`, `SourceSystems = 4`, `Ready = true`.

If `Ready = false`, stop — rebuild the Days 2–4 pipeline before continuing. Cost tuning on broken data teaches the wrong lessons.

---

# Part 1 — How ADX cost works (concepts)

## 1.1 The billing model in plain language

ADX cost is **not** “per row returned.” It is mostly:

| Pillar | What you pay for | Analogy |
|--------|------------------|---------|
| **Compute (cluster)** | Query CPU, ingest processing, MV refresh | SOC analysts + engines running investigations |
| **Storage** | Compressed extents on underlying blob | Warehouse shelf space for years of logs |
| **Hot cache (RAM/SSD)** | Keeping extents fast to read | Keeping last week's evidence on the desk, not in the archive room |

Microsoft publishes [pricing cost drivers](https://learn.microsoft.com/en-us/azure/data-explorer/pricing-cost-drivers). The habits in this guide target those drivers directly.

## 1.2 The extent model — why time filters save money

ADX stores each table as **extents** (compressed micro-batches). Queries **skip** extents when predicates align with partitioning and ingestion time.

```text
  SecLogsParsed at TB scale (conceptual)

  ┌─────────┬─────────┬─────────┬─────────┬─────────┐
  │ extent  │ extent  │ extent  │ extent  │ extent  │ ...
  │ Jun 01  │ Jun 08  │ Jun 15  │ Jun 22  │ Jun 29  │
  └─────────┴─────────┴─────────┴─────────┴─────────┘
       ✗           ✗           ✓           ✓           ✓
                 skipped by:  where Timestamp > datetime(2026-06-14)
```

| Query shape | Extents touched | Cost at lab (3500 rows) | Cost at TB scale |
|-------------|-----------------|-------------------------|------------------|
| No time filter | **All** | Same (tiny table) | **Very high** |
| `where Timestamp > ago(7d)` | **Subset** | Same (tiny table) | **Much lower** |
| Read `SecLogsHourly` MV | **Pre-aggregated** | Same | **Lowest for KPIs** |

**Key insight:** At **3500** rows, expensive and cheap queries feel identical. You are learning **muscle memory** for production.

## 1.3 Cost stack — five levers

```text
  COST STACK (utility SOC)

  1. INGEST     Many tiny files → many extents → ingest + query metadata cost
  2. QUERY      No time filter → scan all history every time
  3. STORAGE    Long retention everywhere → bigger blob bill
  4. CACHE      Everything hot forever → RAM pressure → bigger SKU
  5. GOLD       No MV → every dashboard re-summarizes Silver
```

**Core principle:** **Scan less · retain wisely · pre-aggregate repeat KPIs · batch ingest · monitor extents.**

## 1.4 Worked example — imaginary TB-scale bill

*Numbers are illustrative — not your training cluster invoice.*

| Scenario | Monthly query pattern | Relative cost |
|----------|----------------------|---------------|
| **A — Optimized** | Dashboards on Gold MV; analysts use `ago(7d)` on Silver | **1×** (baseline) |
| **B — Mixed** | 5 dashboards on Silver; 3 on Gold | **~3–5×** |
| **C — Unbounded** | 20 analysts run full-table joins during incident | **~10–50×** spike |

Your lab pipeline is scenario **A** at miniature scale. Parts 3 and 8 show the KQL difference between B and C.

---

# Part 2 — Managing ingestion costs

## 2.1 Concepts

| Concept | Definition | Cost impact |
|---------|------------|-------------|
| **Extent** | Compressed chunk on storage | More extents = more metadata + slower scans |
| **Batch ingest** | `.ingest` from Blob/ADLS | Fewer, larger files = fewer extents |
| **Streaming ingest** | Event Hub / IoT connection | Low latency; risk of **micro-extents** if messages are tiny |
| **Ingestion mapping** | JSON/CSV field map | Wrong mapping → failures → retries + gaps |
| **Merge** | Platform combines small extents | Many small ingests → merge pressure |

**Course pipeline ingest totals**

| Path | Rows in `SecLogsRaw` | `SourceSystem` / format |
|------|----------------------|-------------------------|
| Batch JSON | **1500** | `Batch-JSON` / JSON |
| Batch CSV | **1000** | `Batch-CSV` / CSV |
| Event Hub | **500** | `EventHub` |
| IoT Hub | **500** | `IoT-Hub` |
| **Total Bronze** | **3500** | **4** paths |

### Step 2.1 — Ingestion failures (first check when rows are missing)

```kql
.show ingestion failures
```

**How to read output**

| Column (typical) | Meaning | Cost/ops impact |
|------------------|---------|-----------------|
| `Table` | Target table | Which pipeline stage broke |
| `IngestionSource` | Blob URI or connection | Auth vs path vs format |
| `FailureKind` / `Details` | Mapping, 403, schema | Retry labor + delayed SOC visibility |
| `FailedOn` | Timestamp | Correlate with deploy/rotation |

**Expected:** Empty or **historical** rows only.

**Example interpretation:** `403 Forbidden` on blob URI → cluster **managed identity** lost **Storage Blob Data Reader** — fix RBAC, not KQL.

### Step 2.2 — Ingestion mappings

```kql
.show table SecLogsRaw ingestion mappings
```

**Expected:** At least **`SecLogsRaw_JsonMapping`** (and CSV-related mappings on staging if used).

Missing mapping → every automated ingest fails → operators re-run manually → **people cost**.

### Step 2.3 — Extent and row inventory

```kql
.show tables details
| where TableName in ("SecLogsRaw", "SecLogsParsed", "SecLogsHourly")
| project TableName, TotalExtents, TotalRowCount, TotalOriginalSize, HotExtents
| order by TableName asc
```

**Expected row counts**

| TableName | TotalRowCount |
|-----------|---------------|
| `SecLogsRaw` | **3500** |
| `SecLogsParsed` | **3500** |
| `SecLogsHourly` | MV row count ≠ 3500 (aggregated buckets) |

**Production signal:** `TotalExtents` grows faster than `TotalRowCount` → **extent explosion** → consider larger batch files or ingest batching policy.

### Step 2.4 — Batch vs streaming split (cost profile)

```kql
SecLogsParsed
| extend IngestionMode = case(
    SourceSystem in ("Batch-JSON", "Batch-CSV"), "Batch",
    SourceSystem in ("EventHub", "IoT-Hub"), "Streaming",
    "Other"
)
| summarize RowCount = count() by IngestionMode
| order by IngestionMode asc
```

**Expected**

| IngestionMode | RowCount |
|---------------|----------|
| Batch | **2500** |
| Streaming | **1000** |

```kql
SecLogsRaw
| summarize RowCount = count() by RecordFormat
| order by RecordFormat asc
```

**Expected:** JSON **1500**, CSV **1000**, EventHub **500**, IoT **500** (format labels may vary by mapping).

**Cost takeaway:** Batch **2500** rows likely arrived in **fewer, larger** landing files. Streaming **1000** rows arrived as **many small** messages — acceptable for SOC latency; expensive if you stream data that could be daily batch.

### Step 2.5 — Gold integrity (ingest → Silver → Gold)

```kql
SecLogsHourly
| summarize GoldEventCount = sum(EventCount)
```

**Expected:** `GoldEventCount = 3500`.

If Gold ≠ Silver, dashboards may **re-scan Silver** to “fix” numbers — hidden query cost.

### Step 2.6 — Recent ingest operations

```kql
.show operations
| where Operation == "DataIngestion"
| top 10 by StartedOn desc
| project StartedOn, Operation, State, Duration
```

**Use when:** Duplicate nightly jobs, surprise backfill, or “who ingested after the change window?”

### Step 2.7 — Ingestion recommendations with examples

| Anti-pattern | Example | Better pattern |
|--------------|---------|----------------|
| Micro-files | 1 JSON line per blob every second | Aggregate to **100 MB** hourly files |
| Daily full re-ingest | Same 90-day file appended daily | Partition by `ingest_date` + idempotent keys |
| Ignore failures | `.show ingestion failures` never reviewed | Daily alert + runbook |
| Stream everything | Archive-tier firewall CSV via Event Hub | **Batch** archive, **stream** active SOC feeds |
| Wrong format | `format=json` on NDJSON multiline file | `format=multijson` + correct mapping |

```text
  UTILITY EXAMPLE — substation export

  BAD:  500 devices × 1 KB file/minute  → 720,000 extents/day
  GOOD: Hourly aggregator → 24 files/day → merge-friendly extents
```

---

# Part 3 — Managing query costs

## 3.1 Query cost rules (memorize these)

1. **Time filter first** — `where Timestamp > ago(7d)` or bounded `between`
2. **Filter on indexed columns** — `EventType`, `Facility` after time
3. **Project early** — drop `Message`, `RawPayload` before `join`
4. **Gold for repeating KPIs** — `SecLogsHourly` for dashboards
5. **Silver for hunts** — drill-down with tight filters
6. **`hint.strategy=shuffle`** — large fact ⋈ small dimension at TB scale

## 3.2 Step 3.1 — Good pattern: time + filter + summarize

```kql
SecLogsParsed
| where Timestamp > datetime(2026-06-11)
| where EventType == "AuthFailure"
| summarize FailureCount = count() by Facility
| order by FailureCount desc
```

Verify the total:

```kql
SecLogsParsed
| where Timestamp > datetime(2026-06-11)
| where EventType == "AuthFailure"
| summarize TotalAuthFailures = count()
```

**Expected:** `TotalAuthFailures = 700` (course-wide AuthFailure count on Silver).

**Why it matters:** In production, `where Timestamp > ago(7d)` might return **50,000** rows instead of **billions** scanned.

## 3.3 Step 3.2 — Anti-pattern: filter after join (bad at scale)

**BAD — join before time filter on fact table:**

```kql
// DO NOT use this pattern on TB-scale SecLogsParsed
SecLogsParsed
| join kind=inner (
    ThreatIntelRef | where MatchType == "SourceIP"
) on $left.SourceIP == $right.MatchKey
| where Timestamp > datetime(2026-06-11)
| summarize c = count()
```

**GOOD — time filter and project first:**

```kql
SecLogsParsed
| where Timestamp > datetime(2026-06-11)
| project Timestamp, SourceIP, EventType, Facility
| join kind=inner (
    ThreatIntelRef
    | where MatchType == "SourceIP"
    | project MatchKey, ThreatCategory
) on $left.SourceIP == $right.MatchKey
| summarize EnrichedEvents = count() by ThreatCategory
```

**Expected:** Enriched matches **≥ 300** (lab profile ~**409** total SourceIP IOC hits).

## 3.4 Step 3.3 — Project before join (column cost)

Wide rows cost more through operators. Compare column counts:

```kql
SecLogsParsed
| getschema
| count
```

Then project only what you need:

```kql
SecLogsParsed
| where Timestamp > datetime(2026-06-11)
| project Timestamp, SourceIP, EventType, Facility, Severity
| join hint.strategy=shuffle kind=inner (
    ThreatIntelRef
    | where MatchType == "SourceIP"
    | project MatchKey, ThreatCategory, SeverityHint
) on $left.SourceIP == $right.MatchKey
| summarize MatchCount = count() by ThreatCategory
```

**Why:** `ThreatIntelRef` has **8** rows. `SecLogsParsed` has **3500** in lab — **billions** in production. Carrying `Message`, `UserPrincipal`, `DestinationHost` through the join multiplies bytes shuffled.

## 3.5 Step 3.4 — Expensive vs cheaper (same KPI)

**Expensive — full Silver scan (dashboard every 5 minutes):**

```kql
SecLogsParsed
| summarize EventCount = count() by Facility, EventType
```

**Cheaper — Gold MV (same executive intent):**

```kql
SecLogsHourly
| summarize TotalEvents = sum(EventCount) by Facility, EventType
```

**Expected:** Both paths sum to **3500** total events across all facility/event buckets.

**Parity check:**

```kql
print
    SilverRows = toscalar(SecLogsParsed | count),
    GoldEventCount = toscalar(SecLogsHourly | summarize sum(EventCount)),
    Match = (toscalar(SecLogsParsed | count) == toscalar(SecLogsHourly | summarize sum(EventCount)))
```

**Expected:** `SilverRows = 3500`, `GoldEventCount = 3500`, `Match = true`.

## 3.6 Step 3.5 — On-demand vs MV (when each is worth the cost)

**On-demand Silver summarize** (flexible, higher scan cost):

```kql
SecLogsParsed
| where Timestamp > datetime(2026-06-11)
| summarize
    EventCount = count(),
    HighSeverityCount = countif(Severity in ("High", "Critical"))
  by HourBucket = bin(Timestamp, 1h), Facility, EventType
| order by HourBucket asc
```

**Gold MV read** (fixed grain, lower repeated cost):

```kql
SecLogsHourly
| where HourBucket > datetime(2026-06-11)
| order by HourBucket asc, Facility asc
```

| Use on-demand when | Use Gold MV when |
|--------------------|------------------|
| One-off investigation | Dashboard refreshed hourly |
| New `summarize` grain needed | Grain is stable (hour × facility × event type) |
| Analyst notebook | Executive / NOC wallboard |

**MV storage cost** exists — but **one** MV refresh beats **fifty** analysts re-summarizing Silver.

## 3.7 Step 3.6 — Cost-efficient capstone path (SCADA gateway)

Investigation ticket: auth failures on **`scada-gw.utility.local`**.

**Efficient Step 2 — filter early on Silver:**

```kql
SecLogsParsed
| where EventType == "AuthFailure"
| where DestinationHost == "scada-gw.utility.local"
| project Timestamp, SourceIP, Facility, Severity, Message, SourceSystem
| order by Timestamp asc
```

**Efficient Step 3 — join only the gateway slice:**

```kql
SecLogsParsed
| where DestinationHost == "scada-gw.utility.local"
| where EventType == "AuthFailure"
| join hint.strategy=shuffle kind=inner (
    ThreatIntelRef
    | where MatchType == "SourceIP"
    | project MatchKey, ThreatCategory, SeverityHint
) on $left.SourceIP == $right.MatchKey
| project Timestamp, SourceIP, ThreatCategory, SeverityHint, Message
```

**Efficient Step 4 — Gold for hourly brief (not Silver rescan):**

```kql
SecLogsHourly
| where Facility == "Substation-A"
| where EventType == "AuthFailure"
| project HourBucket, EventCount, HighSeverityCount
| order by HourBucket asc
```

**Expected:** ≥ **1** row in each step. Step 4 proves **why Day 4 built the MV** — shift handoff reads Gold, not a new `summarize` on full Silver.

## 3.8 Anti-pattern catalog (quick reference)

| # | Anti-pattern | Symptom | Fix |
|---|--------------|---------|-----|
| 1 | No time filter | High `Duration` in `.show commands` | `where Timestamp > ago(7d)` |
| 2 | `join` before `where` on facts | Memory / shuffle pressure | Filter facts first |
| 3 | `summarize` without filter | Full table aggregation | Time-bound first |
| 4 | Dashboard on Silver | Same query every 5 min | `SecLogsHourly` |
| 5 | `take 1000000` “to be safe” | Truncation / limits | Filter + `take` |
| 6 | `union *` across huge DB | Query complexity limit | Explicit table list |
| 7 | Select all columns through pipeline | Wide row shuffle | `project` early |

---

# Part 4 — Retention optimization

## 4.1 Concepts

**Retention policy** = minimum time data is **kept** before eligible for deletion.

| Scope | Show command |
|-------|--------------|
| Database default | `.show database policy retention` |
| Table override | `.show table SecLogsParsed policy retention` |
| Materialized view | `.show table SecLogsHourly policy retention` |

**Retention ≠ backup.** Retention drops data from ADX. **Bronze on ADLS** remains your replay source for compliance.

## 4.2 Step 4.1 — Read retention policies (do not alter on shared training DB)

```kql
.show database policy retention
```

```kql
.show table SecLogsParsed policy retention
```

```kql
.show table SecLogsRaw policy retention
```

**Example policy shape (illustrative JSON):**

```json
{
  "SoftDeletePeriod": "P365D",
  "Recoverability": "Enabled"
}
```

| Field | Meaning |
|-------|---------|
| `SoftDeletePeriod` | Data kept at least this long before purge eligible |
| `Recoverability` | Whether soft-delete recovery is enabled |

## 4.3 Tiering strategy for utility cyber

| Table | Typical retention | Why | Cost |
|-------|-------------------|-----|------|
| `SecLogsRaw` (Bronze) | **Long** (years) | NERC CIP replay, re-ingest | Storage ↑ |
| `SecLogsParsed` (Silver) | **Medium** (90d–1y) | Active hunts | Balance |
| `SecLogsHourly` (Gold) | **Long** | Small rows, trends | Cheap per row |
| `ThreatIntelRef` | **Short** (7–30d) | Feed refresh | Minimal |

```text
  COMPLIANCE QUESTION MAP

  "Prove raw logs existed"     → Bronze + ADLS (outlives hot cluster)
  "Investigate last 90 days"   → Silver retention ≥ 90d
  "5-year auth-failure trend"  → Gold MV retention ≥ 5y
```

## 4.4 Example policy commands (awareness — instructor approval in class)

```kql
// Silver — investigation window
// .alter table SecLogsParsed policy retention softdelete = 365d

// Gold — long trend line
// .alter table SecLogsHourly policy retention softdelete = 1825d

// Bronze — align with ADLS canonical copy, not longer than legal need
// .alter table SecLogsRaw policy retention softdelete = 2555d
```

## 4.5 Retention decision worksheet

| Question | If YES | Action |
|----------|--------|--------|
| Is ADLS canonical for Bronze? | Silver can be **shorter** | Lower Silver retention |
| Do executives use 3-year charts? | Extend **Gold** not Silver | MV retention ↑ |
| Is duplicate data in SIEM + ADX? | Shorter ADX copy | Align with SOC playbook |
| Legal hold on incident? | **Do not** shorten until cleared | Exception process |

---

# Part 5 — Caching optimization

## 5.1 Concepts

Extents live on blob (**cold**). **Caching policy** controls how long they stay in the cluster **hot cache** (fast SSD/RAM).

| Tier | Latency | Cost |
|------|---------|------|
| **Hot** | Milliseconds | Cluster RAM / SKU |
| **Cold** | Seconds–minutes | Cheaper blob; still queryable |

**Retention** = whether data exists. **Caching** = how fast reads are.

## 5.2 Step 5.1 — Show caching policy

```kql
.show table SecLogsParsed policy caching
```

**Example shape:**

```json
{
  "Hot": { "HotDuration": "P7D" }
}
```

`P7D` = 7 days hot after ingest (ISO 8601 duration).

## 5.3 Step 5.2 — Hot vs total extents (hot ratio)

```kql
.show tables details
| where TableName in ("SecLogsRaw", "SecLogsParsed", "SecLogsHourly")
| extend HotRatio = round(100.0 * HotExtents / TotalExtents, 1)
| project TableName, TotalExtents, HotExtents, HotRatio, TotalOriginalSize, HotOriginalSize
```

**How to read**

| HotRatio (lab) | HotRatio (production) | Meaning |
|----------------|-------------------------|---------|
| ~100% | 10–30% on old tables | Most data cold — normal |
| ~100% | <5% on **heavily queried** table | Queries hit cold storage — slow + I/O cost |
| N/A | Sudden drop | Cache policy change or cluster resize |

**Lab note:** At **3500** rows, all extents are often hot — ratio is not meaningful until scale.

## 5.4 Caching recommendations

| Scenario | Policy direction |
|----------|------------------|
| Active incident week | Extend hot on `SecLogsParsed` (e.g. 14d) |
| Archive-only Bronze | **Short** hot — queries rare |
| Executive dashboard | Prefer **Gold MV** — fewer cold Silver scans |
| Predictable morning reports | Warm cache via scheduled light query (advanced) |

```kql
// Example only — do not run on shared training DB without approval
// .alter table SecLogsParsed policy caching hot = 14d
```

---

# Part 6 — Scaling optimization

## 6.1 When to scale the cluster vs tune queries

| Signal | Scale cluster? | Tune queries first? |
|--------|----------------|---------------------|
| One analyst, one slow query | No | **Yes** — missing time filter |
| Ten analysts, all slow | Maybe | **Yes** — check `.show commands` |
| Ingest queue lag growing | **Yes** (ingest capacity) | Batch larger files |
| MV `IsHealthy = false` | Fix MV | **Yes** — unhealthy MV → Silver fallback |
| Extent count 10× in a month | Tune ingest | **Yes** — before SKU jump |

**Rule:** Cheapest scale-up is **scanning less data**. SKU upgrades are **step functions** in cost.

## 6.2 Step 6.1 — Cluster and database context

```kql
.show cluster
```

```kql
.show database
```

Training cluster: **`adx-training-tcs`**. Production: dedicated SKU per region/workload.

## 6.3 Step 6.2 — Materialized view health (cost signal)

```kql
.show materialized-views
| where Name == "SecLogsHourly"
| project Name, SourceTable, IsHealthy, LastRun, LastRunResult
```

**Expected:** `IsHealthy = true`, `LastRunResult = Success`.

**Cost story when unhealthy:**

```text
  MV unhealthy
       → Dashboard queries Silver directly
       → 50× full summarize per day
       → Query cost spike + analyst complaints
       → Fix MV before scaling SKU
```

## 6.4 Growth drivers (utility cyber)

| Driver | Example | Cost lever |
|--------|---------|------------|
| New substations | +500 IoT devices | Streaming policy + batch where possible |
| 7-year retention | NERC evidence | Bronze on ADLS + shorter hot cache |
| Incident surge | 10 concurrent analysts | Gold MVs + standard time windows |
| Per-facility dashboards | 20 MVs | Consolidate grains; avoid MV sprawl |

## 6.5 Scaling patterns (awareness)

| Pattern | Use |
|---------|-----|
| **Scale up SKU** | More RAM for cache + CPU |
| **Scale out** | More nodes for parallelism |
| **Follower cluster** | Read-only queries in second region |
| **Batch ingest off-peak** | Separate ingest from query peaks |

---

# Part 7 — Cost monitoring runbook

## 7.1 Fifteen-minute operator sequence

Run **one block at a time** — same order operators use before major incidents.

**Block 1 — Context**

```kql
.show cluster
```

```kql
.show database
```

**Block 2 — Ingest health**

```kql
.show ingestion failures
```

```kql
.show operations
| where Operation == "DataIngestion"
| top 10 by StartedOn desc
| project StartedOn, State, Duration
```

**Block 3 — Capacity**

```kql
.show tables details
| where TableName in ("SecLogsRaw", "SecLogsParsed", "SecLogsHourly", "ThreatIntelRef")
| project TableName, TotalExtents, TotalRowCount, TotalOriginalSize, HotExtents
```

**Block 4 — Gold trust**

```kql
.show materialized-views
| project Name, SourceTable, IsHealthy, LastRunResult
```

**Block 5 — Query audit**

```kql
.show commands
| where CommandType == "Query"
| top 10 by StartedOn desc
| project StartedOn, User, Duration, State, TotalCpu
```

**Block 6 — Count sanity**

```kql
print
    Silver = toscalar(SecLogsParsed | count),
    Gold = toscalar(SecLogsHourly | summarize sum(EventCount)),
    ThreatIntel = toscalar(ThreatIntelRef | count)
```

**Expected:** Silver **3500**, Gold **3500**, ThreatIntel **8**.

## 7.2 Symptom → diagnostic map

| Symptom | First command | Likely cost cause | Next action |
|---------|---------------|-------------------|-------------|
| Storage bill jumped | `.show tables details` | Retention ↑ or extent explosion | Review ingest file sizes |
| ADX slow | `.show commands` | Full scans | Find user + add time filter |
| Gold dashboard flat | `.show materialized-views` | MV unhealthy | Repair MV (Day 4 pattern) |
| Missing rows | `.show ingestion failures` | Mapping / MI auth | Fix ingest path |
| Duplicate rows | `.show operations` + counts | Re-ingest same blob | Idempotent pipeline design |
| High `TotalCpu` on one query | `.show commands` | Unbounded join | Rewrite query (Part 3) |

## 7.3 Interpreting `.show commands` output

| Field | High value suggests |
|-------|---------------------|
| `Duration` | Long scan or heavy join |
| `TotalCpu` | Expensive distributed work |
| `User` | Who to coach on query patterns |
| `State` | `Failed` vs `Completed` — failed retries also cost |

**Example follow-up** for expensive query:

```kql
.show commands
| where CommandType == "Query"
| top 5 by TotalCpu desc
| project StartedOn, User, Duration, TotalCpu, CommandText
```

Review `CommandText` for missing `where Timestamp` clauses.

## 7.4 Monitoring cadence

| Cadence | Checks |
|---------|--------|
| **Daily** | Ingestion failures; MV `IsHealthy` |
| **Weekly** | Extent growth; top 10 CPU queries |
| **Monthly** | Retention vs compliance; SKU utilization |
| **Post-incident** | Query audit — unbounded scans during surge? |

## 7.5 Azure Monitor (awareness)

Production teams export ADX metrics to **Azure Monitor** / **Log Analytics**:

| Metric area | Alert example |
|-------------|---------------|
| Ingestion latency | Queue depth > threshold |
| Query duration | P95 > 30s |
| CPU | Sustained > 80% |
| MV health | `IsHealthy = false` |

Training cluster: Portal metrics are read-only awareness — **`.show` commands** are your lab equivalent.

---

# Part 8 — Operational efficiency (medallion + teams)

## 8.1 Medallion cost efficiency

```text
  Bronze SecLogsRaw (3500)
       │  update policy (automatic — no extra ADF step)
       v
  Silver SecLogsParsed (3500)  ◄── time-filtered hunts
       │  materialized view refresh
       v
  Gold SecLogsHourly (3500 sum)  ◄── dashboards + shift handoff
```

| Layer | Efficiency rule | Course proof |
|-------|-----------------|--------------|
| **Bronze** | Land once; large batches; ADLS replay | **3500** rows, 4 formats |
| **Silver** | Typed columns; bounded queries | AuthFailure **700** |
| **Gold** | Repeat KPIs only | `sum(EventCount) = 3500` |
| **Dimension** | Tiny join side | `ThreatIntelRef` **8** rows |

## 8.2 Multi-team patterns

| Pattern | Cost benefit |
|---------|--------------|
| **Shared Gold MVs** | One refresh → many dashboards |
| **Standard windows** | `ago(24h)`, `ago(7d)` — predictable scan size |
| **Facility in query** | Matches OT/IT boundaries without duplicate tables |
| **RLS on shared DB** | One copy of data — not per-team databases |

## 8.3 Batch vs streaming (design choice)

| Mode | Course rows | When to choose |
|------|-------------|----------------|
| Batch | **2500** | Compliance archives, nightly exports, CloudTrail S3 |
| Streaming | **1000** | Auth failures, VPN, OT anomalies |

**Hybrid rule:** Stream what the SOC needs in **minutes**; batch what auditors need for **years**.

## 8.4 ADF + cost (orchestration layer)

Azure Data Factory adds **orchestration cost** but reduces **operational mistakes**:

| ADF cost | ADX cost saved |
|----------|----------------|
| Pipeline runs | Fewer failed manual `.ingest` retries |
| Copy activities | Larger staged files → fewer extents |
| Retry policies | Faster recovery from landing failures |

Orchestration is not free — **idempotent** pipelines prevent duplicate `.ingest` append cost.

---

# Part 9 — Hands-on exercises

Complete all five. Write results in your lab worksheet.

### Exercise 1 — Prove AuthFailure count efficiently

Write a query that returns **700** total AuthFailures using a **time filter** and **one** `summarize`.

**Starter:**

```kql
SecLogsParsed
| where Timestamp > datetime(2026-06-11)
| where EventType == "AuthFailure"
| summarize Total = count()
```

**Pass:** `Total = 700`.

---

### Exercise 2 — Batch vs streaming cost profile

Run the Part 2 batch/streaming queries. Answer in one sentence: *Which mode has higher operational extent risk in production and why?*

**Pass:** Streaming — micro-messages create more extents unless batched.

---

### Exercise 3 — Silver vs Gold parity

Run Part 3 Step 3.5 parity check.

**Pass:** `Match = true` and both totals **3500**.

---

### Exercise 4 — Operator triage

Assume: *“Substation-A dashboard shows zero since 09:00.”*  
Run Blocks 2–4 from Part 7.1 in order. List which block you would check first and why.

**Model answer:** Block 2 (ingest failures) — data may never have landed; then Block 4 (MV health) — Gold may be stale.

---

### Exercise 5 — Rewrite an expensive query

**Expensive:**

```kql
SecLogsParsed
| summarize Events = count() by bin(Timestamp, 1h), Facility
```

**Your task:** Rewrite to use **Gold** for the same hourly-by-facility grain.

**Solution:**

```kql
SecLogsHourly
| summarize Events = sum(EventCount) by HourBucket, Facility
```

**Pass:** Results align on total event count (**3500**).

---

# Part 10 — Before/after query statistics

At lab scale (**3500** rows), **Duration** and **CPU** differences between good and bad queries are often **tiny** (milliseconds). You still run this part to learn **where to look** in production when one query costs 100× another.

## 10.1 Where statistics appear in the Web UI

After you run any query in [dataexplorer.azure.com](https://dataexplorer.azure.com):

1. Results pane → **Statistics** tab (next to Results / Chart).
2. Note typical fields:

| Statistic | Meaning |
|-----------|---------|
| **Elapsed time** | Wall-clock time you waited |
| **CPU time** | Compute spent across cluster nodes |
| **Memory peak** | High-water mark during operators |
| **Total rows / data scanned** | How much data operators touched |

```text
  AFTER RUNNING A QUERY

  [ Results ] [ Chart ] [ Statistics ]  ◄── click here
                              │
                              ├── Elapsed time (ms)
                              ├── CPU time
                              └── Memory / scan info
```

**Production habit:** Screenshot or log Statistics when filing a “slow query” ticket — operators use the same numbers in `.show commands`.

## 10.2 Step 10.1 — Run the expensive query (baseline)

Run **alone** (Shift+Enter):

```kql
// EXPENSIVE PATTERN — full Silver summarize (no time filter)
SecLogsParsed
| summarize EventCount = count() by Facility, EventType
| order by EventCount desc
```

1. Open **Statistics** tab — note **Elapsed time** and **CPU time**.
2. Confirm result still sums to **3500** events:

```kql
SecLogsParsed
| summarize Total = count()
```

**Expected:** `Total = 3500`.

## 10.3 Step 10.2 — Run the cheaper query (same KPI intent)

Run **alone**:

```kql
// CHEAPER PATTERN — pre-aggregated Gold MV
SecLogsHourly
| summarize TotalEvents = sum(EventCount) by Facility, EventType
| order by TotalEvents desc
```

1. Open **Statistics** again — compare to Step 10.1.
2. Verify totals:

```kql
SecLogsHourly
| summarize GoldTotal = sum(EventCount)
```

**Expected:** `GoldTotal = 3500`.

**Lab note:** At 3500 rows, both queries may show similar milliseconds. The **pattern** matters at TB scale — Gold avoids rescanning Silver fact extents on every dashboard refresh.

## 10.4 Step 10.3 — Compare with `.show commands` (audit trail)

After running Steps 10.1 and 10.2, run:

```kql
.show commands
| where CommandType == "Query"
| where StartedOn > ago(30m)
| where CommandText has "SecLogsParsed" or CommandText has "SecLogsHourly"
| project StartedOn, Duration, TotalCpu, MemoryPeak, State, CommandText
| order by StartedOn desc
| take 10
```

**How to read**

| Column | Use |
|--------|-----|
| `Duration` | End-to-end query time |
| `TotalCpu` | Best column to sort “expensive” vs “cheap” at scale |
| `MemoryPeak` | Large joins / wide `project` mistakes |
| `CommandText` | Match which pattern you ran |

**Production:** Sort by `TotalCpu` weekly — coach authors of top queries (Part 7.3).

## 10.5 Step 10.4 — Broader query log with `.show queries`

```kql
.show queries
| where StartedOn > ago(30m)
| project StartedOn, Duration, CpuTime, MemoryPeak, RowCount, Text
| order by StartedOn desc
| take 20
```

| Column | Meaning |
|--------|---------|
| `CpuTime` | CPU consumed (similar role to `TotalCpu` in commands) |
| `RowCount` | Rows returned to client |
| `Text` | Query body — search for missing `where Timestamp` |

**Quiet cluster:** Few rows returned is OK — commands still prove the audit path works.

## 10.6 Step 10.5 — Paired comparison (time filter effect)

Run **two queries back-to-back**, then re-run Step 10.3.

**Query A — bounded (good):**

```kql
SecLogsParsed
| where Timestamp > datetime(2026-06-11)
| where EventType == "AuthFailure"
| summarize FailureCount = count() by Facility
```

**Query B — unbounded summarize (bad at TB scale):**

```kql
SecLogsParsed
| where EventType == "AuthFailure"
| summarize FailureCount = count() by Facility
```

At lab scale both return the same **FailureCount** totals (sum **700**). In production, Query B scans **all retention history**; Query A scans **one window**.

Verify both sum to 700:

```kql
SecLogsParsed
| where EventType == "AuthFailure"
| summarize Total = count()
```

**Expected:** `Total = 700`.

## 10.7 Step 10.6 — Join order comparison (statistics exercise)

**Worse pattern — join before filter:**

```kql
SecLogsParsed
| join kind=inner (
    ThreatIntelRef | where MatchType == "SourceIP"
) on $left.SourceIP == $right.MatchKey
| where Timestamp > datetime(2026-06-11)
| summarize Enriched = count()
```

**Better pattern — filter and project first:**

```kql
SecLogsParsed
| where Timestamp > datetime(2026-06-11)
| project SourceIP
| join kind=inner (
    ThreatIntelRef | where MatchType == "SourceIP" | project MatchKey
) on $left.SourceIP == $right.MatchKey
| summarize Enriched = count()
```

Run Step 10.3 again — locate both in `CommandText`. **Expected:** similar `Enriched` count (~**409**); at TB scale the “better” pattern typically shows lower `TotalCpu`.

## 10.8 Recording template (for your worksheet)

| Run | Query label | Elapsed (UI) | CPU (UI) | Duration (.show commands) | TotalCpu (.show commands) |
|-----|-------------|--------------|----------|----------------------------|---------------------------|
| 1 | Silver full summarize | | | | |
| 2 | Gold MV summarize | | | | |
| 3 | AuthFailure bounded | | | | |
| 4 | AuthFailure unbounded | | | | |
| 5 | Join-after-filter (bad) | | | | |
| 6 | Filter-before-join (good) | | | | |

## 10.9 Exercise 6 — Statistics literacy

1. Run the **expensive** Silver summarize from Step 10.1.
2. Run `.show commands` filtered to your last 15 minutes.
3. Answer: **Which column** best identifies expensive queries in a production audit — `Duration` or `TotalCpu`?

**Pass:** **TotalCpu** — distributed work can have high CPU even when wall-clock Duration looks acceptable.

---

# Appendix A — Quick reference (all commands)

```kql
// Gate
print Ready = (toscalar(SecLogsParsed | count) == 3500)

// Ingestion
.show ingestion failures
.show table SecLogsRaw ingestion mappings
.show operations | where Operation == "DataIngestion" | top 10 by StartedOn desc

// Capacity
.show tables details
.show cluster
.show database

// Policies (read-only)
.show database policy retention
.show table SecLogsParsed policy retention
.show table SecLogsParsed policy caching

// MV health
.show materialized-views

// Query audit
.show commands | where CommandType == "Query" | top 10 by TotalCpu desc
.show queries | where StartedOn > ago(1h) | project StartedOn, Duration, CpuTime, Text

// Efficient hunt
SecLogsParsed
| where Timestamp > ago(7d)
| where EventType == "AuthFailure"
| summarize count() by Facility

// Efficient dashboard
SecLogsHourly
| summarize sum(EventCount) by Facility, EventType
```

---

# Appendix B — Scenario walkthrough: incident surge

**Situation:** Substation outage — **10 analysts** query ADX for **4 hours**.

| Analyst | Query habit | Cost impact |
|---------|-------------|-------------|
| **A** | `SecLogsHourly` + `ago(4h)` filter on drill-down | **Low** |
| **B** | Full Silver `summarize` every 10 min | **High** |
| **C** | No time filter; `join` ThreatIntelRef first | **Very high** |

**Platform operator actions during surge:**

1. Confirm MV healthy (Part 6.3).
2. Post **standard query templates** with time filters in Teams.
3. Monitor `.show commands` for top CPU (Part 7.3).
4. **Do not** scale SKU until query patterns are reviewed.

```text
  SURGE TIMELINE

  T+0   Incident declared — analysts open ADX
  T+15m Operator checks MV + failures (Part 7.1)
  T+60m Review top 5 CPU queries — coach unbounded scans
  T+4h  Post-incident: retention + query audit notes
```

---

# Appendix C — Monthly cost review checklist

| # | Review item | Command / action |
|---|-------------|------------------|
| 1 | Pipeline counts stable | Gate query |
| 2 | No chronic ingest failures | `.show ingestion failures` |
| 3 | Extent growth vs row growth | `.show tables details` |
| 4 | MV healthy | `.show materialized-views` |
| 5 | Top 10 expensive queries | `.show commands` by `TotalCpu` |
| 6 | Retention still matches compliance | `.show table ... policy retention` |
| 7 | Cache policy still matches hunt patterns | `.show table ... policy caching` |
| 8 | Dashboards on Gold not Silver | Architecture review |
| 9 | Batch paths use large enough files | Ingest ops review |
| 10 | Duplicate ingest / ADF idempotency | `.show operations` |

---

# Appendix D — Efficiency checklist (from this guide)

| # | Recommendation | Part |
|---|----------------|------|
| 1 | Gate pipeline (**3500** / **8** / Gold **3500**) | Gate |
| 2 | Monitor ingestion failures | 2.2 |
| 3 | Track batch vs streaming split | 2.4 |
| 4 | Track extent growth | 2.3 |
| 5 | Time-filter every investigation | 3.2 |
| 6 | Project before join | 3.3 |
| 7 | Dashboards on Gold MV | 3.5 |
| 8 | Silver/Gold parity | 3.5 |
| 9 | Review retention policies | 4 |
| 10 | Review caching + hot ratio | 5.3 |
| 11 | MV health before incidents | 6.3 |
| 12 | Weekly query CPU audit | 7.3 |
| 13 | Batch ingest over micro-files | 2.7 |
| 14 | Capstone path uses Gold for KPIs | 3.7 |
| 15 | Complete Part 9 exercises | 9 |
| 16 | Compare query Statistics + `.show commands` | 10 |

---

## Summary

Cost optimization on Azure Data Explorer is a **discipline**, not a slider:

1. **Ingest** fewer, larger, cleaner batches — monitor failures and extents.
2. **Query** less per request — time, project, Gold for repeat KPIs.
3. **Retain** by table tier — Bronze long, Silver medium, Gold trends cheap.
4. **Cache** hot data on purpose — measure `HotExtents` / `TotalExtents`.
5. **Scale** after tuning — unhealthy MVs and unbounded scans masquerade as SKU problems.
6. **Monitor** with Part 7 runbook — daily failures, weekly CPU, monthly policies.
7. **Measure** query cost with Part 10 — Web UI Statistics and `.show commands` / `.show queries`.
8. **Operate** with shared Gold KPIs and standard investigation windows.

You practiced every pattern on the **utility cyber pipeline** at lab scale. The same commands and habits apply when your estate reaches **terabytes per day**.
