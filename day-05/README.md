# Day 05 — Performance, Security, Operations & Capstone

## Learning objectives

* Apply query optimization and join hints at lab scale
* Review RBAC, RLS concepts, and monitoring commands
* Compare materialized view vs on-demand aggregates
* Complete end-to-end capstone investigation

**Prerequisite:** Days 2–4 pipeline in **your database** — `SecLogsRaw`, `SecLogsParsed` (**3500** rows), `ThreatIntelRef` (**8**), `SecLogsHourly` (Gold MV; `sum(EventCount)` = **3500**). Run [pipeline gate](labs.md#pipeline-gate-before-lab-1) (`queries/00-verify-pipeline-baseline.kql`) before Lab 1.

**Hands-on:** [labs.md](labs.md) | **Queries:** [queries/](queries/) | **Practice:** [assignments.md](assignments.md) | **Cost optimization:** [cost-optimization-guide.md](cost-optimization-guide.md) | **ADF → ADX:** [azure-data-factory-to-adx-guide.md](azure-data-factory-to-adx-guide.md) | **Data:** [data/README.md](../data/README.md) | **Terms:** [GLOSSARY.md](../GLOSSARY.md)

### Document map

| Section | Topic | Labs |
|---------|--------|------|
| [At a glance](#day-5-at-a-glance) | 7-lab arc, pipeline gate, capstone | All |
| — | [Azure Data Factory → ADX runbook](azure-data-factory-to-adx-guide.md) — hands-on Portal lab (ADF + Copy + `.ingest` + verify) | Optional (**2–3 h**) |
| — | [Cost optimization guide](cost-optimization-guide.md) — ingest, query, retention, cache, MV, exercises | Optional (**90–120 min**) |
| Gate | Pipeline verify (3500 + 8 + Gold) | [00-verify-pipeline-baseline.kql](queries/00-verify-pipeline-baseline.kql) |
| [1](#1-query-optimization) | Time filters, project, bounded joins | Lab 1 |
| [2](#2-ingestion-and-shard-tuning) | Extents, ingestion diagnostics | Lab 2 |
| [3](#3-hintstrategy) | `hint.strategy=shuffle` | Lab 3 |
| [4](#4-materialized-views-vs-on-demand-queries) | Silver vs Gold parity | Lab 4 (+ [verify](queries/04-verify-mv-parity.kql)) |
| [5](#5-capacity-planning-and-scaling) | TB-scale awareness | Lab 2, 6 |
| [6](#6-authentication-rbac-and-row-level-security) | Principals, RLS demo | Lab 5 (+ [verify](queries/05-verify-rlsdemo.kql)) |
| [7](#7-network-cross-tenant-and-auditing) | VPN, ER, private endpoints, NERC CIP, auditing | Read after Lab 5 (class discussion) |
| [8](#8-monitoring-and-disaster-recovery) | `.show` diagnostics, cost, disaster recovery (DR) | Lab 6 |
| [9](#9-capstone-scenario--utility-cyber-investigation) | End-to-end investigation | Lab 7 (+ [verify](queries/07-verify-capstone.kql)) |
| — | [Scenario assignments](assignments.md) (30 KQL tasks + answers) | After labs |

### Day 5 at a glance {#day-5-at-a-glance}

**Where you work:** [dataexplorer.azure.com](https://dataexplorer.azure.com) Query tab only — same as Day 4. You **optimize, secure, and operate** the pipeline you built on Days 2–4; you do not ingest new batch files today.

```text
  YOUR DAY (labs.md order)

  Gate   Verify pipeline ([00-verify](queries/00-verify-pipeline-baseline.kql)) ──► Ready = true
           │
           v
  Labs 1–3  Query efficiency + hint.strategy
           │
           v
  Lab 4     MV vs on-demand ──► TotalsMatch = true (3500 = 3500)
           │
           v
  Lab 5     RBAC + RlsDemoEvents (10 rows) — RLS on demo table only
           │
           v
  Lab 6     Monitoring `.show` commands
           │
           v
  Lab 7     Capstone: scada-gw AuthFailure → threat intel → Gold KPIs

  END STATE: same pipeline objects + RlsDemoEvents (10) for security discussion
```

---


# 1. Query optimization {#query-optimization}

Days 1–4 taught **correct** KQL. Day 5 teaches **efficient** KQL for **terabyte-scale** utility log platforms. At lab scale (**3500** Silver rows) every query feels instant — the habits below matter when `SecLogsParsed` holds billions of rows and many analysts query during an incident.

Query cost tracks **data scanned** (extents read), not just rows returned ([query limits](https://learn.microsoft.com/en-us/azure/data-explorer/kusto/concepts/query-limits)). The goal: **touch fewer extents, carry fewer columns, prefer Gold for repeated KPIs**.

## 1.1 What Day 5 adds to the week

```text
  BUILT (Days 1–4)                    DAY 5 (today)

  Pipeline Bronze → Gold              Optimize queries at TB scale
  join, time-series, MV               Ingestion diagnostics
                                      hint.strategy, security, capstone
```

| Focus | Question answered |
|-------|-------------------|
| **§1–§3** | How do I scan less data per query? |
| **§4–§5** | When is a Gold MV worth the extra storage and refresh overhead? |
| **§6–§7** | Who can see which rows? How is the platform secured and audited? |
| **§8** | How do I monitor health, cost, and recovery? | Lab 6 (includes recent query commands) |
| **§9** | Can I investigate end-to-end under pressure? |

## 1.2 The scan model — extents and time

ADX stores table data in **extents** (compressed micro-batches). Queries skip extents when filters align with **time partitioning** and **ingestion time** ([extents overview](https://learn.microsoft.com/en-us/azure/data-explorer/kusto/management/extents-overview)).

```text
  TB-scale SecLogsParsed
  ┌────────┬────────┬────────┬────────┐
  │ extent │ extent │ extent │ extent │  ... thousands
  │ Jun 10 │ Jun 11 │ Jun 12 │ Jun 13 │
  └────────┴────────┴────────┴────────┘
       ▲
       │  where Timestamp > ago(7d)  →  skip older extents
```

| Pattern | Effect at scale |
|---------|-----------------|
| **`where Timestamp > ago(7d)`** | Primary way to limit data scanned in SOC investigations |
| **`where Timestamp between (datetime(2026-06-11) .. datetime(2026-06-13))`** | Lab KQL files — fixed window for June 2026 sample data |
| **`where EventType == "..."`** | Secondary filter after time |
| **`project` early** | Less column data through join/summarize |
| **Query Gold MV** | Pre-aggregated — fewer rows than Silver |

## 1.3 Core optimization patterns

| Pattern | Why | Lab |
|---------|-----|-----|
| Time-bound facts | Reduces extents scanned | Lab 1 Q1 |
| **`project` before `join`** | Smaller left side in hash join | Lab 1 Q2 |
| Filter dimension (`MatchType`) | Tiny right side | Day 4 §2 |
| **`summarize` on Gold** | Dashboard KPIs without Silver rescan | Lab 4 |
| Avoid `union *` on huge DB | Query complexity limits | Awareness |

### Good — time + filter + summarize (Lab 1 Q1)

```kql
SecLogsParsed
| where Timestamp > datetime(2026-06-11)   // lab files: sample data mid-June 2026; production often uses ago(7d)
| where EventType == "AuthFailure"
| summarize FailureCount = count() by Facility
| order by FailureCount desc
```

Answers: *which facilities had auth failures in the last week?* — bounded scan even when the table holds years of history.

### Good — project before join (Lab 1 Q2)

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

Carries only columns needed for enrichment — not `Message`, `UserPrincipal`, etc.

## 1.4 Anti-patterns at TB scale

| Anti-pattern | Risk |
|--------------|------|
| Full-table join without time filter | Scans entire fact history |
| `join` before `where` on facts | Larger hash tables |
| `take 1000000` without filter | Result truncation / memory pressure |
| Repeated Silver `summarize` for same dashboard | Wasted compute — use Gold MV |
| Select `*` / all columns through pipeline | Wide rows in join operators |

```text
  BAD (TB scale)                         GOOD (this course)

  SecLogsParsed                          SecLogsParsed
  | join ThreatIntelRef                  | where Timestamp > datetime(2026-06-11)
  | summarize ...                        | project key columns
                                         | join ThreatIntelRef
                                         | summarize ...
```

Lab 1 Q3 is a **pattern reminder** — at **3500** rows, bounded vs unbounded performs the same; the habit matters for production.

# 2. Ingestion and shard tuning

Query performance depends on **how data landed**. **Ingestion tuning** affects extent count, merge behavior, failed batches, and downstream query parallelism ([ingestion overview](https://learn.microsoft.com/en-us/azure/data-explorer/ingest-data-overview)).

Day 5 Lab 2 uses **diagnostic commands** — not re-ingesting data — to build operational awareness.

## 2.1 Extents — the storage unit behind ingest and query

| Concept | Meaning |
|---------|---------|
| **Extent** | Compressed blob chunk holding table rows |
| **Many small extents** | Often from streaming or tiny batch files — more metadata overhead |
| **Fewer large extents** | Typical of well-sized `.ingest` batches — better scan efficiency |
| **Failed ingest** | Row never lands — visible in `.show ingestion failures` |
| **Merge (platform)** | ADX combines small extents over time — operators watch extent count in Lab 2 |

```text
  INGEST (Days 2–3)                    QUERY (Day 5)

  .ingest / data connection  ──►  extents in SecLogsRaw
  update policy              ──►  extents in SecLogsParsed
  MV refresh                 ──►  extents in SecLogsHourly
                                          │
                                          ▼
                          time filter skips extents outside window
```

## 2.2 Ingestion levers (production)

| Lever | Purpose | Where used |
|-------|---------|-----------------|
| **Batch size** | Larger blobs → fewer extents | Day 2 `.ingest` |
| **Streaming batching** | Latency vs extent churn | Day 3 streaming policy |
| **Mapping correctness** | Prevents format failures | Day 2 mappings |
| **Merge policy** | Combines small extents | Platform-managed — awareness only |

Utility surge: substation export dumps **10 GB** nightly — operators prefer **few large** `.ingest` jobs over millions of tiny files.

## 2.3 Diagnostic commands — Lab 2

File: [queries/02-ingestion-tuning.kql](queries/02-ingestion-tuning.kql).

```kql
.show ingestion failures

.show table SecLogsRaw ingestion mappings

.show table SecLogsRaw details

.show tables details
| where TableName in ("SecLogsRaw", "SecLogsParsed", "SecLogsHourly")
| project TableName, TotalExtents, TotalRowCount
| order by TableName asc
```

| Command | What it tells you |
|---------|-------------------|
| **`.show ingestion failures`** | Mapping errors, auth failures, bad URIs |
| **`.show table ... ingestion mappings`** | Active JSON/CSV mappings on Bronze |
| **`.show table ... details`** | Extent count, row count, size for one table |
| **`.show tables details`** | Compare extent counts across pipeline tables |

**Lab expectation:** failures table empty or shows **historical** class issues; pipeline tables listed with small extent counts.

# 3. hint.strategy

Distributed joins on large fact tables can **shuffle** or **broadcast** data across cluster nodes. KQL **`hint.strategy`** gives the optimizer explicit guidance ([join operator — hints](https://learn.microsoft.com/en-us/kusto/query/join-operator#join-hints)).

Day 4 introduced joins without hints (lab data too small). Day 5 Lab 3 adds **`hint.strategy=shuffle`** for the **`SecLogsParsed` ⋈ `ThreatIntelRef`** pattern at scale.

## 3.1 Why hints exist

| Join side | Course table | Production scale |
|-----------|--------------|------------------|
| **Left (fact)** | `SecLogsParsed` **3500** rows | Billions of rows |
| **Right (dimension)** | `ThreatIntelRef` **8** rows | Thousands of IOCs — still small |

When the **fact is large** and neither side fits in memory for broadcast, **shuffle** partitions both sides by join key across nodes.

```text
  hint.strategy=shuffle

  Node A: subset of SourceIPs  ──┐
  Node B: subset of SourceIPs  ──┼── join locally
  Node C: subset of SourceIPs  ──┘
```

## 3.2 shuffle vs broadcast (awareness)

| Hint | When Microsoft might use it |
|------|----------------------------|
| **`hint.strategy=broadcast`** | Right table small enough to copy to all nodes |
| **`hint.strategy=shuffle`** | Both sides large — partition by join key |
| **(default / auto)** | Optimizer chooses based on statistics |

Wrong hints waste CPU or cause memory pressure ([query limits — HashJoin](https://learn.microsoft.com/en-us/azure/data-explorer/kusto/concepts/query-limits#limit-on-memory-consumed-by-query-operators)). **Validate in production** with query statistics — not guesswork.

Hint strategies are covered in the advanced KQL module (join performance section).

## 3.3 Lab 3 queries

File: [queries/03-hint-strategy.kql](queries/03-hint-strategy.kql).

### Q1 — shuffle join with projection

```kql
SecLogsParsed
| where Timestamp > datetime(2026-06-11)
| project Timestamp, SourceIP, EventType, Facility, Severity
| join hint.strategy=shuffle kind=inner (
    ThreatIntelRef
    | where MatchType == "SourceIP"
    | project MatchKey, ThreatCategory, SeverityHint
) on $left.SourceIP == $right.MatchKey
| project Timestamp, EventType, SourceIP, ThreatCategory, SeverityHint, Facility
| order by Timestamp asc
```

### Q2 — shuffle + severity filter + summarize

```kql
SecLogsParsed
| where Timestamp > datetime(2026-06-11)
| join hint.strategy=shuffle kind=inner (
    ThreatIntelRef | where MatchType == "SourceIP"
    | project MatchKey, ThreatCategory
) on $left.SourceIP == $right.MatchKey
| where Severity in ("High", "Critical")
| summarize MatchCount = count() by ThreatCategory
```

**Still filter time first** — hint does not replace §1 patterns.

# 4. Materialized views vs on-demand queries

Day 4 Lab 7 created **`SecLogsHourly`** as a **materialized view** on Silver. Day 5 Lab 4 proves **equivalence** — on-demand `summarize` on **`SecLogsParsed`** and querying the Gold MV should align on totals ([materialized views overview](https://learn.microsoft.com/en-us/azure/data-explorer/kusto/management/materialized-views/materialized-view-overview)).

## 4.1 Two ways to get hourly counts

| Approach | Query target | When to use |
|----------|--------------|-------------|
| **On-demand** | `SecLogsParsed` + live `summarize` | Ad-hoc investigation, one-off cuts |
| **Materialized view** | `SecLogsHourly` | Repeated dashboard KPIs, manager views |

```text
  ON-DEMAND (Lab 4 Q1)              GOLD MV (Lab 4 Q2)

  Every refresh scans Silver        Query reads pre-aggregated buckets
  Flexible group-by                 Fixed MV definition (Day 4 Lab 7)
  Higher compute at TB scale        Background refresh + extra storage
```

```text
  MATERIALIZED VIEW LIFECYCLE

  SecLogsParsed (Silver facts)
         │
         │  MV definition: summarize by HourBucket, Facility, EventType
         v
  SecLogsHourly  ◄── periodic refresh (cluster merges new Silver extents)
         │
         └── Dashboard / manager queries read MV, not full Silver rescan
```

Lab 4 **Q3** proves **`sum(EventCount)`** on the MV equals **`count()`** on Silver (**3500** = **3500**) — the MV is logically equivalent, not a different dataset.

## 4.2 Lab 4 queries

File: [queries/04-mv-vs-ondemand.kql](queries/04-mv-vs-ondemand.kql).

**Q1 — on-demand Silver summarize:**

```kql
SecLogsParsed
| where Timestamp > datetime(2026-06-11)
| summarize
    EventCount = count(),
    HighSeverityCount = countif(Severity in ("High", "Critical"))
  by HourBucket = bin(Timestamp, 1h), Facility, EventType
```

**Q2 — Gold MV read:**

```kql
SecLogsHourly
| where HourBucket > datetime(2026-06-11)
| order by HourBucket asc, Facility asc
```

**Q3 — locked parity check:**

```kql
let onDemandTotal = toscalar(SecLogsParsed | summarize Total = count());
let mvTotal = toscalar(SecLogsHourly | summarize Total = sum(EventCount));
print OnDemandTotal = onDemandTotal, MaterializedViewTotal = mvTotal,
      TotalsMatch = (onDemandTotal == mvTotal)
```

| Check | Expected |
|-------|----------|
| **`TotalsMatch`** | **`true`** |
| Both totals | **3500** |

Same aggregation logic as Day 4 Lab 7 Gold MV — Day 4 ran the same summarize ad-hoc before creating `SecLogsHourly`.

## 4.3 On-demand vs Gold MV — trade-offs for SOC dashboards

| Factor | On-demand | Gold MV |
|--------|-----------|---------|
| **Storage** | Silver only | Silver + MV extents |
| **Repeated queries** | High — rescans facts each time | Low — reads pre-aggregated buckets |
| **Flexibility** | Change `summarize` anytime | Alter MV definition |
| **Best for** | Analyst notebooks | Executive hourly auth-failure dashboard |

Hybrid: analysts use **Silver** for drill-down; managers use **`SecLogsHourly`** for facility heatmaps.

# 5. Capacity planning and scaling

Training runs on **`adx-training-tcs`** — a shared cluster where students sign in with **cluster-level administrator access** (all databases on the cluster). Each learner still works in **their workspace database** (`LogsDB_<id>`) so Days 2–5 pipeline objects stay in one place; elevated access is for learning management commands, not because every analyst queries every database in production.

Production utility platforms plan **GB/day → TB/day** growth — operators tune cluster SKU, ingest throughput, retention, cache, and disaster recovery as volume grows ([choose cluster SKU](https://learn.microsoft.com/en-us/azure/data-explorer/manage-cluster-choose-sku)).

## 5.1 Growth drivers in utility cyber

| Driver | Example | ADX impact |
|--------|---------|------------|
| New substations online | +500 devices | More IoT/streaming extents |
| Longer retention | 7y compliance | More cold storage; cache policy matters |
| Concurrent analysts | Incident surge | Query concurrency + SKU |
| Gold MV count | Many dashboards | MV refresh CPU + storage |

## 5.2 Metrics that predict pain

Lab 2 **`.show tables details`** (`TotalExtents`, `TotalRowCount`) and Lab 6 monitoring preview what operators watch before scaling SKU or retention.

| Signal | Warning sign |
|--------|--------------|
| Extent count rising fast | Many small ingests — batch larger |
| MV refresh lag | `IsHealthy` false or stale Gold |
| Hot cache miss | Repeated Silver scans for same dashboard |

## 5.3 Lab vs production scale

| | **This course** | **Production utility** |
|---|-----------------|------------------------|
| Silver rows | **3500** | Billions |
| Cluster | Shared training SKU | Dedicated per region |
| Sign-in access | **Cluster admin** (all databases) | Least privilege — Viewer/User on shared DBs |
| Where you run labs | **Your workspace DB** (`LogsDB_<id>`) | Often **one shared prod database** + **RLS** (§6.3) |

Day 5 optimization patterns (§1–§3) exist because production cannot afford full-table scans — even when analysts share one database, time filters and Gold MVs keep query cost predictable.

## 5.4 Lab connection

Lab 2 extent summary and Lab 6 monitoring commands preview the metrics operators use for capacity decisions — no sizing exercise in class.

---

# 6. Authentication, RBAC, and row-level security

Day 5 **Lab 5** is hands-on security — you register **your Entra ID `UserPrincipalName`** in **`RlsUserScope`**, seed **`RlsDemoEvents`** (**10** rows across three facilities), **implement per-user RLS**, observe filtering (**10 → 4** or **3** by facility), then **disable** the policy.

Every query passes through three gates:

| Gate | Question | Mechanism |
|------|----------|-----------|
| **Authentication** | Who signed in? | Microsoft Entra ID |
| **RBAC** | May this identity use this database / run this command? | Cluster or database role |
| **RLS** (optional) | Which **rows** appear in query results? | Table policy |

```text
  SECURITY LAYERS

  Analyst sign-in (Entra ID)
         │
         v
  RBAC — cluster or database role (.show database principals)
         │
         v
  Query table (e.g. SecLogsParsed, RlsDemoEvents)
         │
         v
  RLS filter (optional) — hide rows by Facility, region, etc.
         │
         v
  Result set visible to this analyst
```

Microsoft reference: [RBAC](https://learn.microsoft.com/en-us/azure/data-explorer/kusto/management/access-control/role-based-access-control) · [RLS policy](https://learn.microsoft.com/en-us/azure/data-explorer/kusto/management/row-level-security-policy)

## 6.1 Authentication — human analysts vs cluster services

Two different identities appear in the course pipeline — do not confuse them.

| Identity | Used by | Purpose in course |
|----------|---------|-------------------|
| **Entra ID user** | You in Web UI | Run KQL, management commands, view results |
| **Cluster managed identity (MI)** | ADX cluster service | Read Blob URIs, Event Hub — Days 2–3 ingest |

**MI** = **Managed Identity** — an Azure AD identity for the **cluster itself** (no username/password). Storage and Event Hub grant RBAC to this identity so `.ingest` and data connections work without embedding keys in KQL.

```text
  HUMAN PATH                         SERVICE PATH (Days 2–3)

  Analyst ──Entra ID──► ADX Query     ADX cluster ──MI (Managed Identity)──► Blob / Event Hub
  tab                   engine               │
                        │                    └── .ingest / data connection
                        └── your KQL never contains storage keys
```

**Utility example:** a Tier-2 analyst signs in with **Entra ID** to hunt auth failures. Overnight **batch ingest** from ADLS runs under the **cluster MI** — the blob URI uses `;managed_identity=system` (Day 2), not a shared storage password.

Lab 5 does not change authentication — it assumes you are already signed in. Focus: **who is authorized on the database** (§6.2) and **how RLS would narrow rows** in production (§6.3).

## 6.2 RBAC — cluster and database roles

**RBAC** (role-based access control) assigns permissions at **cluster** scope (all databases) or **database** scope (one `LogsDB_<id>`).

Lab 5 — run in Query tab with **your workspace database** selected:

```kql
.show database principals
```

| Scope | Role (examples) | Typical capability |
|-------|-----------------|-------------------|
| **Cluster** | All-databases **Admin** | Create/drop databases, cluster policies |
| **Database** | **Admin** | Tables, functions, policies, ingest in that DB |
| **Database** | **User** | Ingest + query |
| **Database** | **Viewer** | Read only |

### This course — cluster administrator access

Your training sign-in has **cluster-level administrator access** on **`adx-training-tcs`**. You can:

* Open and manage **any database** on the cluster
* Run `.create`, `.alter`, `.drop`, and policy commands without a separate escalation ticket

**Lab convention:** still work in **your workspace database** (`LogsDB_<id>`) for Days 2–5 objects. Pipeline checkpoints (**3500** Silver, **8** threat intel, Gold **3500**) live there. Cluster admin is for **learning**; mixing lab tables across databases makes verification harder.

```text
  TRAINING CLUSTER (adx-training-tcs)

  Your sign-in (cluster admin)
         │
         ├── LogsDB_u01   ← Student A — full Week 2–5 pipeline
         ├── LogsDB_u02   ← Student B
         ├── LogsDB_u03   ← …
         └── LogsDB_atin  ← Maintainer / trainer workspace

  Dropdown rule: select YOUR LogsDB_<id> before every lab block
```

### Production contrast — least privilege

| Role | Typical ADX access | Utility example |
|------|-------------------|-----------------|
| **Security Operations Center (SOC) analyst** | Viewer or User on **shared prod DB** | Tier-2 analyst queries auth failures — no `.drop table` |
| **Platform engineer** | Cluster or database Admin | Create tables, fix ingest mappings |
| **Auditor** | Viewer + export to SIEM | Read-only compliance review |

Production rarely gives analysts **cluster admin**. Instead, **RLS** (§6.3) restricts rows when many teams share one **`SecLogsParsed`**.

## 6.3 Row-level security — facility-scoped rows

**RLS** filters rows **after** RBAC allows table access. RBAC answers *“May I query this table?”* RLS answers *“Which rows appear?”*

**Utility scenario:** a **Substation-A** analyst may query `SecLogsParsed`, but RLS returns only rows where **`Facility == "Substation-A"`**. A **corporate SOC lead** with a broader policy might see all facilities in the same table.

Inspect policy (read-only in Lab 5 **Q2**):

```kql
.show table SecLogsParsed policy row_level_security
```

**Per-user RLS** in Lab 5 **Q3c–Q4c** (on **`RlsDemoEvents` only**):

**Step 1 — Register your login** (`Q3d` uses `current_principal_details()["UserPrincipalName"]` automatically):

```kql
.set-or-replace RlsUserScope <|
print UserPrincipalName = tostring(current_principal_details()["UserPrincipalName"]), AllowedFacility = "Substation-A"
```

Change **`AllowedFacility`** to `"Substation-B"` or `"SCADA-Gateway"` and re-run **Q3d** to see a different row count under RLS.

**Step 2 — RLS function** looks up **your** UPN in `RlsUserScope` and filters events:

```kql
.create-or-alter function with () RlsDemoUserFacilityScope() {
    let MyUpn = tostring(current_principal_details()["UserPrincipalName"]);
    let Allowed = toscalar(
        RlsUserScope
        | where UserPrincipalName == MyUpn
        | project AllowedFacility
    );
    RlsDemoEvents
    | where Facility == Allowed
}

.alter table RlsDemoEvents policy row_level_security enable "RlsDemoUserFacilityScope"
```

While enabled, **`RlsDemoEvents | count`** shows **4** (Substation-A), **3** (Substation-B), or **3** (SCADA-Gateway) — only **your** mapped facility. RLS applies to every principal, including cluster admin; the policy uses **your signed-in UPN**, not a shared static filter.

**Always disable** before verify and later labs:

```kql
.alter table RlsDemoEvents policy row_level_security disable "RlsDemoUserFacilityScope"
```

### Why labs use `RlsDemoEvents` — not `SecLogsParsed`

| Table | RLS in labs? | Reason |
|-------|--------------|--------|
| **`SecLogsParsed`** | **No** | RLS hides rows → breaks Days 2–4 counts (**3500**, joins, Gold parity) |
| **`RlsUserScope`** | **Yes (Lab 5)** | **1** row per student — your **`UserPrincipalName`** → **`AllowedFacility`** |
| **`RlsDemoEvents`** | **Yes (Lab 5)** | **10** seeded rows (**4**/**3**/**3**) — safe sandbox; disable RLS before leaving lab |

Lab 5 flow ([queries/05-security-rbac-rls.kql](queries/05-security-rbac-rls.kql)):

```text
  Q0  drop RlsDemoEvents (clean start)
  Q1  .show database principals
  Q2  .show RLS on SecLogsParsed (read — do not alter)
  Q3a create RlsDemoEvents
  Q3b seed 10 rows (4+3+3 facilities)
  Q3c create RlsUserScope
  Q3d register YOUR UserPrincipalName → AllowedFacility
  Q6  before RLS — count = 10; scope row = 1
  Q4a create RlsDemoUserFacilityScope function
  Q4b enable on RlsDemoEvents
  Q7  with RLS — count = 4 or 3 (your facility)
  Q5  .show RLS policy (IsEnabled = true)
  Q4c disable RLS
  Q8  after disable — count = 10
```

Verify file: [05-verify-rlsdemo.kql](queries/05-verify-rlsdemo.kql) — expect **10** rows from **OT-adjacent** *(Operational Technology–adjacent: substation / SCADA)* facilities.

```text
  RBAC vs RLS (remember for exam / design discussions)

  "Can I run this query?"     →  RBAC role on database
  "Why do I see 40 not 3500?" →  RLS may be filtering (not used on SecLogsParsed in labs)
```

## 6.4 Lab 5 connection and success criteria

| Task | File | Expected |
|------|------|----------|
| Principals review | `05-security-rbac-rls.kql` Q1 | Lists roles without permission error |
| RLS inspection | Q2, Q5 | Read policies — SecLogsParsed empty or unchanged |
| Demo table + per-user RLS | Q3a–Q8, verify | **`RlsDemoEvents` = 10** after Q4c; **4** or **3** while RLS enabled |
| Verify | [05-verify-rlsdemo.kql](queries/05-verify-rlsdemo.kql) | Count **10** |

**Do not** enable RLS on **`SecLogsParsed`**. Capstone (§9) and all prior labs assume the full **3500** Silver rows are visible.

---

# 7. Network, cross-tenant, and auditing

**Read-only architecture section** — no Azure Portal steps today. You already practiced **who** can access data (§6 RBAC/RLS). Section 7 answers **how** traffic should reach ADX in a regulated utility and **what evidence** you keep when auditors or incident responders ask questions.

Day 5 **Lab 5 Q1** (`.show database principals`) is your only hands-on touchpoint here. **Day 6** covers **VPN** and **ER** in depth for hybrid log shipping; today you learn the vocabulary so those labs make sense.

## 7.0 Three questions compliance teams ask

| Question | Section | What it means in plain language |
|----------|---------|--------------------------------|
| **Who** may query OT-related logs? | §6 (RBAC + RLS) | Role on the database + optional row filter by `Facility` |
| **How** does traffic reach ADX? | §7.1 (network paths) | Analysts and ingest should not cross the public internet for sensitive telemetry |
| **Where** is proof retained? | §7.3 (auditing) | Sign-in logs, query history, management commands, Bronze copies |

```text
  COMPLIANCE STACK (utility reference architecture)

  Layer 1 — ACCESS     Entra ID sign-in → RBAC → optional RLS (§6)
  Layer 2 — NETWORK    Corporate network → VPN or ER → VNet → Private Link → ADX
  Layer 3 — EVIDENCE   Activity Log + ADX audit + Bronze retention (§7.3)
```

## 7.1 Network paths — VPN, ER, and private endpoints

Utility cyber teams often require that **query**, **ingest**, and **management** traffic to Azure stays on **controlled paths** — especially when **`SecLogsParsed`** includes **OT-adjacent** substation or SCADA-related events.

### How analysts and ingest reach Azure (terms)

| Term | Full name | What it is | Typical utility use |
|------|-----------|------------|---------------------|
| **VPN** | **Virtual Private Network** | Encrypted tunnel over the **public internet** between corporate HQ and Azure | Quick pilot; analysts or small forwarders connect from office/substation |
| **ER** | **Azure ExpressRoute** | **Private dedicated link** (telco/MPLS) from your datacenter to Azure — traffic does **not** ride the public internet | Production **Security Operations Center (SOC)**; steady volume from regulated sites |
| **VNet** | **Virtual Network** | Private IP network inside Azure | ADX and storage sit here |
| **Private endpoint / Private Link** | Azure Private Link service | Gives ADX, Blob, or Event Hub a **private IP inside your VNet** so clients never use the cluster’s public URL | Target state for analyst Web UI and `.ingest` |

**VPN vs ER (remember for design discussions):**

| | **VPN** | **ER (ExpressRoute)** |
|---|---------|------------------------|
| Path | Internet + encryption | Private carrier / MPLS circuit |
| Setup | Fast, lower cost | Slower to provision, higher cost |
| Best for | Pilots, remote sites, DR tests | Primary SOC path, large regulated utilities |
| Day 6 | Discussed for hybrid **log shipping** | Preferred for steady OT-adjacent ingest |

```text
  PATH A — VPN (encrypted over internet)

  Analyst laptop ──VPN tunnel──► Corporate firewall ──► Azure VNet ──► ADX Query tab

  PATH B — ExpressRoute (private circuit)

  Utility WAN / MPLS ──ExpressRoute──► Azure edge ──► VNet ──► ADX / Blob / Event Hub

  INSIDE THE VNET — Private endpoint (both paths end here)

  VNet ── Private Link ──► ADX cluster
                      └──► Blob (Day 2 .ingest)
                      └──► Event Hub (Day 3 streaming)
```

| Resource | Why private link matters | Course touchpoint |
|----------|--------------------------|-------------------|
| **ADX cluster** | Analyst KQL and API calls stay on private IP | Web UI at [dataexplorer.azure.com](https://dataexplorer.azure.com) uses public URL in **training**; production uses private endpoint |
| **Storage account** | Batch ingest URIs not exposed publicly | Day 2 `.ingest` + `;managed_identity=system` |
| **Event Hub** | Streaming agents connect without public broker | Day 3 data connection |

> **Training vs production:** this course uses the **public ADX endpoint** for simplicity. In a **NERC CIP**–aligned design, architects document **VPN or ER** to the VNet **plus** private endpoints — reference architecture sketches cover that path; you do **not** configure it in Day 5 labs.

### NERC CIP — what it means here (awareness only)

**NERC CIP** = **North American Electric Reliability Corporation — Critical Infrastructure Protection** — mandatory cybersecurity standards for bulk electric grid operators in North America. You are **not** implementing CIP controls in this lab; you learn how ADX fits the **evidence** auditors expect.

| CIP-style question | Where your architecture doc answers it | Day 5 / course link |
|--------------------|----------------------------------------|---------------------|
| Who can view substation-related logs? | RBAC roles + optional RLS by `Facility` | §6 · Lab 5 Q1 `.show database principals` |
| How is analyst access protected in transit? | VPN or ER to VNet; private endpoint to ADX | §7.1 (this section) |
| Can you prove who ran a destructive command? | Entra sign-in + ADX management audit | §7.3 |
| Can you recover raw logs after a mistake? | Bronze / ADLS retention + re-ingest | Day 2 · §8.3 |

**Sector guidance (broader than NERC):** any regulated utility (water, gas, nuclear-adjacent) asks the same three layers — **access**, **network path**, **audit trail**. Your Day 6 hybrid deliverable checklist items **7–8** capture this for the full multi-cloud diagram.

## 7.2 Cross-cluster and cross-database queries

Utilities grow through **mergers**, **regional DR** *(Disaster Recovery)*, and **multi-cloud** footprints (Day 6). ADX lets one KQL script read more than one database or cluster:

| Pattern | Syntax idea | When used |
|---------|-------------|-----------|
| **Another database, same cluster** | `database('OtherDb').Table` | Shared dimension in prod DB |
| **Remote cluster** | `cluster('uri').database('db').Table` | Federated hunt across regions |

```text
  THIS COURSE (one cluster)           ENTERPRISE (federated)

  adx-training-tcs                    cluster(India).SecLogsParsed
       │                              cluster(DR-US).SecLogsParsed
       ├── LogsDB_u01 ─ your labs            │
       └── LogsDB_u02                        └── union / join in one KQL script
```

Example federated shape (awareness — not a Day 5 lab step):

```kql
cluster('https://adx-dr.centralindia.kusto.windows.net').database('ProdLogs').SecLogsParsed
| where Timestamp > ago(1d)
| union (
    SecLogsParsed
    | where Timestamp > ago(1d)
)
| summarize EventCount = count() by Facility
```

**Training note:** cluster admin lets you **see** all databases on `adx-training-tcs`; capstone and checkpoints still run in **your workspace DB** only.

## 7.3 Auditing — prove who did what, when

**RBAC** tells you who *may* access a database today. **Auditing** tells you who *did* run queries, change policies, or drop tables yesterday — required for **NERC CIP** evidence and general SOC investigations.

| Audit source | What it records | Utility example |
|--------------|-----------------|-----------------|
| **Entra ID sign-in logs** | User login time, IP, MFA result | Was `analyst@utility.com` active during the incident window? |
| **Azure Activity Log** | Azure resource changes (SKU, RBAC assignment) | Who granted cluster Admin to a contractor? |
| **ADX query audit** (`.show commands`) | KQL text, duration, caller | Did someone export all `SecLogsParsed` rows? |
| **ADX management audit** | `.create`, `.alter`, `.drop`, policy changes | Who ran `.drop table SecLogsParsed`? |
| **Bronze / ADLS retention** (Day 2) | Raw payloads kept N days | Re-ingest after bad update policy; regulatory hold |

```text
  INCIDENT: "SecLogsParsed row count dropped overnight"

  Step 1  Entra ID sign-in logs     Who was logged in at T0?
  Step 2  ADX management audit      Which command altered or dropped data?
  Step 3  .show database principals Did RBAC change? (Lab 5 Q1)
  Step 4  Bronze on ADLS            Can we re-ingest from Day 2 blob paths? (§8.3)
```

Lab 5 **Q1** is the **access review** starting point — list principals and roles before an audit meeting. Production teams export ADX audit to **Log Analytics**, **Microsoft Sentinel**, or a long-term compliance archive.

## 7.4 What to remember (exam / design discussions)

| Topic | Remember this |
|-------|----------------|
| **VPN** | Encrypted tunnel over internet — fast to start; variable quality |
| **ER** | Private dedicated link to Azure — preferred for production utility SOC |
| **Private endpoint** | ADX/Blob/EH private IP inside VNet — traffic never uses public cluster URL |
| **Cross-cluster** | `cluster('uri').database('db').Table` — post-merger / multi-region hunts |
| **Auditing** | Sign-in + query/management audit + Bronze retention = evidence chain |
| **NERC CIP (awareness)** | Document **who** (§6), **how** (§7.1), **proof** (§7.3) — not configured in Day 5 labs |

**Lab connection:** discuss §7 after **Lab 5** (while RBAC is fresh) or during the **Lab 6** break before monitoring queries. Full hybrid paths are drawn on **Day 6** Labs **5 + 9** (AWS design Labs **7–8**).

---

# 8. Monitoring and disaster recovery

**Operators and platform engineers** keep the pipeline healthy; **Security Operations Center (SOC) analysts** consume the data. Section 8 teaches the **read-only `.show` commands** Day 5 **Lab 6** runs before the capstone — the same checks a utility **Network Operations Center (NOC)** or ADX platform team uses when dashboards look wrong, row counts drop, or ingest stops.

You do **not** change cluster settings today. You learn **what to look at** and **what a healthy lab pipeline looks like** so Lab 7 capstone numbers are trustworthy.

> **Abbreviations in this section:** We write **Full Name (ABBR)** — e.g. **Network Operations Center (NOC)**, **materialized view (MV)**, **disaster recovery (DR)**. See [GLOSSARY.md](../GLOSSARY.md).

## 8.0 Two roles — analyst vs operator

| Role | Primary job | Day 5 touchpoint |
|------|-------------|------------------|
| **Security Operations Center (SOC) analyst** | Hunt threats, run KQL investigations | Labs 1–5, 7 capstone |
| **Platform / Network Operations Center (NOC) operator** | Keep ingest, materialized view (MV) refresh, and cluster health OK | **Lab 6** `.show` diagnostics |

```text
  WHEN THINGS LOOK WRONG

  Security Operations Center (SOC) analyst says: "Dashboard shows zero AuthFailures since 09:00"
       │
       v
  Operator checks (Lab 6 order):
       1 .show ingestion failures     — did batch/stream ingest fail?
       2 .show tables details         — did SecLogsParsed row count drop?
       3 .show materialized-views     — is SecLogsHourly stale?
       4 .show commands               — is someone running expensive queries?
```

**Four questions Lab 6 answers:**

| # | Question | Command | Healthy in *this course* |
|---|----------|---------|--------------------------|
| 1 | Is ingest failing? | `.show ingestion failures` | Empty or old historical rows only |
| 2 | Are tables the right size? | `.show tables details` | `SecLogsParsed` **3500** rows; modest extent count |
| 3 | Is Gold materialized view (MV) healthy? | `.show materialized-views` | `SecLogsHourly` **`IsHealthy = true`** |
| 4 | Are queries expensive? | `.show commands` | Recent queries complete; no runaway duration |

Microsoft reference: [Monitor Azure Data Explorer](https://learn.microsoft.com/en-us/azure/data-explorer/monitor-data-explorer)

## 8.1 Monitoring commands — Lab 6 walkthrough

File: [queries/06-monitoring-diagnostics.kql](queries/06-monitoring-diagnostics.kql) — run **one block at a time** (Shift+Enter).

### Block 1–2 — Cluster and database context

```kql
.show cluster
.show database
```

| Command | What you learn | Utility example |
|---------|----------------|-----------------|
| **`.show cluster`** | Cluster URI, version, **SKU (service tier / size)** awareness | Confirm you are on **`adx-training-tcs`**, not a **disaster recovery (DR)** follower |
| **`.show database`** | Database name, retention hints | Confirm **`LogsDB_<id>`** is selected — same convention as §6 |

**Lab note:** output may include fields you cannot change (shared training cluster). Read-only is fine — the goal is knowing these commands exist for production runbooks.

### Block 3 — Ingestion failures (most important for “missing rows”)

```kql
.show ingestion failures
```

Shows **why** a `.ingest` or streaming connection rejected data — mapping errors, auth failures, bad blob URI, format mismatch.

| Column (typical) | Meaning |
|------------------|---------|
| `Table` | Target table (e.g. `SecLogsRaw`) |
| `IngestionSource` | Blob URI or connection id |
| `FailureKind` / `Details` | Mapping error, auth, schema |
| `FailedOn` | When it failed |

**Healthy (lab):** **no new rows** after your successful Day 2–3 ingest.

**Production example:** After a storage key rotation, failures show **403 Forbidden** on blob URI — fix **Managed Identity (MI)** and **Role-Based Access Control (RBAC)** (§6.1) or storage role assignment, then re-run `.ingest`.

**Course scenario:** If Lab 7 capstone Step 2 returns **zero** gateway rows, an operator checks here *before* the analyst rewrites KQL — the data may never have landed.

### Block 4 — Recent ingest operations

```kql
.show operations
| where Operation == "DataIngestion"
| top 10 by StartedOn desc
```

Answers: *“Did anything ingest recently, and did it succeed?”* Complements failures — operations can **succeed** while row counts still look wrong (wrong table, wrong DB).

**Utility example:** Nightly firewall CSV job should show a **DataIngestion** operation every 24h. A gap after a holiday weekend triggers a check of the upstream scheduler, not just ADX.

### Block 5 — Table size and extents (capacity + sanity check)

```kql
.show tables details
| where TableName in ("SecLogsRaw", "SecLogsParsed", "SecLogsHourly", "ThreatIntelRef")
| project TableName, TotalExtents, TotalOriginalSize, HotExtents, HotOriginalSize
```

| Column | Plain language | What to check in lab |
|--------|----------------|----------------------|
| `TotalRowCount` *(if shown)* / separate count query | Rows in table | `SecLogsParsed` = **3500**; `ThreatIntelRef` = **8** |
| `TotalExtents` | Number of storage chunks | Small in lab; **explosion** in prod = too many tiny ingests |
| `HotExtents` | Extents in RAM cache | Higher = faster repeat queries for recent data |
| `TotalOriginalSize` | Disk footprint | Grows with retention; drives cost (§8.2) |

```text
  HOT vs COLD (from .show tables details)

  HotExtents   ──► in RAM cache — fast for today's Security Operations Center (SOC) shift queries
  TotalExtents ──► all stored extents — hot + cold

  Example: HotExtents << TotalExtents
           → repeated full-table scans hit cold storage (slow + costly)
           Fix: time filter (§1), query Gold materialized view (MV) (§4), or cache policy
```

**Worked example — row count sanity check** (run after Block 5):

```kql
SecLogsParsed | count          // expect 3500
ThreatIntelRef | count         // expect 8
SecLogsHourly | summarize sum(EventCount)  // expect 3500
```

If counts differ, use the [pipeline gate](labs.md#pipeline-gate-before-lab-1) — Lab 6 confirms **health**, the gate confirms **checkpoints**.

### Block 6 — Materialized view (MV) health (Gold dashboard trust)

```kql
.show materialized-views
| project Name, SourceTable, IsHealthy, LastRunResult
```

**`SecLogsHourly`** (Day 4 Lab 7) must show:

| Field | Healthy value | If unhealthy |
|-------|---------------|--------------|
| `IsHealthy` | **`true`** | Gold dashboard **key performance indicators (KPIs)** may be stale or wrong |
| `LastRunResult` | **Success** | Investigate materialized view (MV) definition or source table issues |
| `SourceTable` | `SecLogsParsed` | Confirms materialized view (MV) still tied to Silver |

**Utility example:** Control-room dashboard reads **`SecLogsHourly`**. If `IsHealthy = false` after a Silver schema change, operators refresh or recreate the materialized view (MV) **before** executives see flat lines during an active incident.

**Lab 7 link:** Capstone Step 4 reads Gold — run Block 6 **before** Step 4 so you trust the hourly buckets.

### Block 7 (Q5) — Recent query commands (performance awareness)

```kql
.show commands
| where CommandType == "Query"
| top 10 by StartedOn desc
| project StartedOn, User, Duration, State
```

Shows **who** ran **what**, how long it took, and whether it completed — ties to §7.3 auditing.

| Pattern | Likely cause | Fix (Day 5 theme) |
|---------|--------------|-------------------|
| **Duration** very high, same user repeating | Full Silver scan, no time filter | Add `where Timestamp > ago(7d)` (Lab 1) |
| **Duration** high on join queries | Large fact + dimension join | `project` before join (Lab 1); `hint.strategy=shuffle` (Lab 3) |
| Dashboard query every 5 min on Silver | Wrong layer for **key performance indicators (KPIs)** | Read **`SecLogsHourly`** materialized view (MV) instead (Lab 4) |

**Quiet training cluster:** Q5 may return **few or no rows** — that is OK. The command still runs without permission error.

### Ops response loop (symptom → command → action)

```text
  Symptom                         Command                      Next step
  ─────────────────────────────────────────────────────────────────────────────
  "Missing rows since midnight"   .show ingestion failures     Mapping / Managed Identity (MI) / re-ingest
  "SecLogsParsed count wrong"     .show tables details + count  Pipeline gate; Day 2–3 replay
  "Gold dashboard flat"           .show materialized-views       Wait backfill; fix materialized view (MV) (Day 4 Lab 7)
  "ADX slow this morning"         .show commands                 Time filter; use Gold materialized view (MV)
  "Storage bill jumped"           .show tables details           Retention policy; larger batches (§5)
  "Who ingested after change?"    .show operations             Correlate with Activity Log (§7.3)
```

## 8.2 Cost optimization — scan less, retain wisely

ADX bills correlate with **data scanned**, **RAM cache**, **materialized view (MV) storage**, and **retention** ([pricing cost drivers](https://learn.microsoft.com/en-us/azure/data-explorer/pricing-cost-drivers)). Day 5 §1–§4 patterns exist partly to control these costs at utility scale.

| Lever | What it controls | Utility trade-off |
|-------|------------------|-------------------|
| **Query time filters** (§1) | Extents scanned per investigation | Shorter window during incident surge = lower cost |
| **Retention policy** | How long Bronze/Silver kept | 7-year **North American Electric Reliability Corporation — Critical Infrastructure Protection (NERC CIP)** evidence vs storage bill |
| **Cache policy** | Which extents stay hot in RAM | Faster hunts on `SecLogsParsed` — costs memory |
| **Gold materialized views (MVs)** (§4) | Pre-aggregate vs re-scan Silver | Extra storage + refresh CPU vs cheaper dashboards |

### Expensive vs cheaper — concrete query shapes

**Expensive (avoid for repeating dashboards):**

```kql
// Scans all Silver extents — fine at 3500 rows, costly at billions
SecLogsParsed
| summarize EventCount = count() by Facility, EventType
```

**Cheaper (same key performance indicator (KPI) intent on Gold):**

```kql
// Reads pre-aggregated materialized view (MV) — Lab 4 parity proved 3500 = 3500
SecLogsHourly
| summarize TotalEvents = sum(EventCount) by Facility, EventType
```

**Cheaper investigation (always filter time first):**

```kql
SecLogsParsed
| where Timestamp > ago(7d)
| where EventType == "AuthFailure"
| summarize Failures = count() by Facility
```

```text
  COST MINDSET (utility Security Operations Center (SOC))

  Expensive pattern     Dashboard polls Silver every 5 min, no time filter, full summarize
  Cheaper pattern       Dashboard reads SecLogsHourly materialized view (MV); analysts drill to Silver on click

  Expensive pattern     10 analysts run identical full-week joins during incident
  Cheaper pattern       Shared Gold materialized view (MV) + bounded time windows + hint.strategy (§3)
```

Training cluster cost is managed for the course — learn the **patterns** for production TB-scale estates.

## 8.3 Disaster recovery — Bronze as evidence and replay source

**Disaster recovery (DR)** = restoring analytics after cluster loss, bad schema change, or regional outage. Azure Data Explorer clusters can be rebuilt; **Bronze on Azure Data Lake Storage (ADLS)** often remains the **canonical copy** of raw logs.

| Disaster recovery (DR) pattern | Role | Course anchor |
|------------|------|---------------|
| **Bronze retention + Azure Data Lake Storage (ADLS)** | Source of truth for re-ingest | Day 2 `.ingest` from `training-data/...` blobs |
| **Follower cluster** | Read-only query in second region | Awareness only — not a lab step |
| **Replay `.ingest`** | Rebuild Silver/Gold after fix | Same mappings as Day 2–3; update policy re-applies |

```text
  REGION A (primary)                    REGION B (disaster recovery (DR) — awareness)

  Ingest ──► SecLogsRaw                 Follower cluster (read-only queries)
       │                                       ▲
       └── Azure Data Lake Storage (ADLS) / Blob (canonical) ─────────────┘
            training-data/...

  FAILURE: analyst accidentally drops Silver policy or cluster service tier (SKU) lost
  RECOVERY (conceptual):
    1. Bronze blobs still on Azure Data Lake Storage (ADLS)  ← Day 2 paths unchanged
    2. Re-create tables / mappings                           ← Day 2 Lab queries
    3. Re-run .ingest into SecLogsRaw                        ← same URIs + Managed Identity (MI)
    4. Re-apply update policy                                 ← Day 3 Lab 5
    5. Refresh SecLogsHourly materialized view (MV)           ← Day 4 Lab 7; wait for IsHealthy
    6. Verify counts (3500 / 8 / Gold 3500)                   ← pipeline gate
```

**Utility example:** A bad update policy wiped **`Severity`** parsing for one day. Bronze **`SecLogsRaw`** still holds **`RawPayload`**. Operators fix the policy, trigger backfill, and **replay from Bronze** — auditors prefer proving raw retention over “we lost the logs.”

**Streaming note:** Day 3 Event Hub / IoT data is harder to replay than batch blobs — production designs keep **offset checkpoints** and **dead-letter** paths. Batch Bronze on Azure Data Lake Storage (ADLS) remains the simplest disaster recovery (DR) story in this course.

Day 2 **Azure Data Lake Storage (ADLS) paths** and Day 3 **streaming** connections are the **recovery inputs**. Lab 6 confirms the pipeline is **healthy now** before you trust capstone Gold (§9).

## 8.4 Lab 6 connection — block-by-block checklist

Run [06-monitoring-diagnostics.kql](queries/06-monitoring-diagnostics.kql) in **your workspace database** before Lab 7.

| Block | Command | Pass criteria |
|-------|---------|---------------|
| 1 | `.show cluster` | Returns cluster metadata (read-only OK) |
| 2 | `.show database` | Shows **your** `LogsDB_<id>` |
| 3 | `.show ingestion failures` | No **new** blocking failures |
| 4 | `.show operations` (ingest) | Recent ops listed or empty on quiet cluster |
| 5 | `.show tables details` | All four pipeline tables listed; counts match gate |
| 6 | `.show materialized-views` | **`SecLogsHourly`**: `IsHealthy = true` |
| 7 | `.show commands` | Runs without permission error |

**Quick verify after Lab 6:**

```kql
SecLogsParsed | count                                    // 3500
.show materialized-views | where Name == "SecLogsHourly"  // IsHealthy = true
```

| Check | Expected before Lab 7 capstone |
|-------|-------------------------------|
| `.show ingestion failures` | No new blocking errors |
| `SecLogsParsed` row count | **3500** |
| `SecLogsHourly` `IsHealthy` | **true** |
| `.show commands` | Runs without permission error |

If Block 6 fails, fix the Gold **materialized view (MV)** (Day 4 Lab 7) **before** capstone Step 4 — see [Debug TotalsMatch](labs.md#debug-totalsmatch-gold-mv).

---

# 9. Capstone scenario — utility cyber investigation

Day 5 **Lab 7** closes the week with a **single Security Operations Center (SOC) ticket** that uses Bronze lineage, Silver filters, threat enrichment, and Gold key performance indicators (KPIs) — the same layers you built on Days 2–4, with Day 5 **`hint.strategy`** and optimization habits applied.

Run the pipeline gate ([00-verify-pipeline-baseline.kql](queries/00-verify-pipeline-baseline.kql)) and Lab 6 monitoring checks before starting — capstone assumes **`SecLogsParsed = 3500`**, **`ThreatIntelRef = 8`**, Gold sum **3500**.

## 9.1 Ticket — OT gateway auth failures

**OT gateway** = field **Operational Technology** gateway (e.g. **SCADA** — *Supervisory Control and Data Acquisition*) that bridges substation systems and corporate networks. **`scada-gw.utility.local`** in course data is an OT-adjacent auth target.

**Security Operations Center (SOC) ticket (utility cyber):** *(work item assigned to the central investigation queue)*

*"Multiple authentication failures reported against **`scada-gw.utility.local`** (SCADA gateway). Identify source IPs, check threat intel, and summarize hourly impact at **`Substation-A`** for the shift handoff."*

**Why this scenario fits the course data:**

* **`scada-gw.utility.local`** appears in Silver **`DestinationHost`** with **`AuthFailure`** events
* Known bad IPs in **`ThreatIntelRef`** overlap **`SourceIP`** on auth failures (Day 4 join pattern)
* **`SecLogsHourly`** already aggregates **`Substation-A`** **`AuthFailure`** by hour (Day 4 Gold MV)

## 9.2 Investigation path — five steps

File: [queries/07-capstone-investigation.kql](queries/07-capstone-investigation.kql) — run **one block at a time**.

```text
  CAPSTONE FLOW

  Step 1  BRONZE     SecLogsRaw — gateway host in RawPayload / lineage
            │
            v
  Step 2  SILVER     SecLogsParsed — AuthFailure + DestinationHost filter
            │
            v
  Step 3  THREAT     join ThreatIntelRef (hint.strategy=shuffle)
            │
            v
  Step 4  GOLD       SecLogsHourly — Substation-A AuthFailure by hour
            │
            v
  Step 5  SUMMARY     count by SourceSystem — executive one-liner
```

| Step | Layer | What you prove | Minimum result |
|------|-------|----------------|----------------|
| **1** | Bronze | Ingest path for gateway events | Rows with gateway-related payload / host |
| **2** | Silver | Auth failures targeting gateway | ≥ **1** `AuthFailure` on `scada-gw.utility.local` |
| **3** | Enrichment | Known-threat overlap | ≥ **1** row with **`ThreatCategory`** |
| **4** | Gold | Hourly OT impact | ≥ **1** **`SecLogsHourly`** row — Substation-A + AuthFailure |
| **5** | Brief | Volume by ingest path | Summarize by **`SourceSystem`** for handoff |

### Step 2 — Silver filter (pattern)

```kql
SecLogsParsed
| where EventType == "AuthFailure"
| where DestinationHost == "scada-gw.utility.local"
| project Timestamp, SourceIP, Facility, Severity, Message
| order by Timestamp asc
```

### Step 3 — threat join (Day 5 style)

Use **`hint.strategy=shuffle`** on the Day 4 join pattern when the fact side is large — same logic as Lab 3, applied to the gateway slice.

### Step 4 — Gold read (not Silver rescan)

```kql
SecLogsHourly
| where Facility == "Substation-A"
| where EventType == "AuthFailure"
| project HourBucket, EventCount, HighSeverityCount
| order by HourBucket asc
```

Prefer **`SecLogsHourly`** for the hourly brief — that is why Day 4 built the MV (§4).

Verify file: [07-verify-capstone.kql](queries/07-verify-capstone.kql) — confirms minimum counts programmatically.

## 9.3 Skills map — which day each step uses

| Capstone step | Days 1–5 skill |
|---------------|----------------|
| Bronze lineage | Day 2 **`RecordFormat`** / Day 3 **`SourceSystem`** |
| Silver typed filter | Day 3 **`SecLogsParsed`** schema |
| Threat join | Day 4 **`ThreatIntelRef`** + Day 5 **`hint.strategy`** |
| Gold hourly KPI | Day 4 **`SecLogsHourly`** MV |
| Time-bounded mindset | Day 5 §1 — filter before join |
| Ops confidence | Day 5 Lab 6 — MV healthy before trusting Step 4 |

## 9.4 Shift handoff — what a good answer includes

A complete capstone brief (2–3 sentences plus numbers):

1. **What happened** — auth failures against `scada-gw.utility.local`
2. **Threat context** — at least one **`ThreatCategory`** from join (e.g. brute-force IP)
3. **OT impact** — **`SecLogsHourly`** peak hour at **`Substation-A`**
4. **Lineage** — which **`SourceSystem`** contributed (batch vs Event Hub vs IoT)

```text
  EXECUTIVE ONE-LINER (template)

  "N AuthFailure events hit scada-gw from IP X (ThreatCategory Y) during hour Z;
   Substation-A hourly Gold shows W events — primary source Batch-JSON / EventHub / …"
```

## 9.5 Full course pipeline (Days 1–5)

```text
  DAY 1   PracticeSecurityEvents (2000)    KQL fundamentals
  DAY 2   SecLogsRaw (2500→3500)            Bronze batch ingest
  DAY 3   SecLogsParsed (3500)              Streaming + update policy → Silver
  DAY 4   ThreatIntelRef (8) + SecLogsHourly  Joins, MV Gold
  DAY 5   RlsDemoEvents (10) + capstone     Secure, operate, investigate

  MEDALLION (end of Day 5):

  SecLogsRaw ──► SecLogsParsed ──► join ThreatIntelRef ──► SecLogsHourly
     Bronze          Silver              enrich               Gold KPIs
                          │
                          └── Capstone: scada-gw AuthFailure path (Lab 7)
```

| Layer | Table | Lab scale | Day built |
|-------|-------|-----------|-----------|
| Practice | `PracticeSecurityEvents` | 2000 | 1 |
| Bronze | `SecLogsRaw` | 3500 | 2–3 |
| Silver | `SecLogsParsed` | 3500 | 3 |
| Dimension | `ThreatIntelRef` | 8 | 4 |
| Gold | `SecLogsHourly` | sum = 3500 | 4 |
| Security demo | `RlsDemoEvents` | 10 | 5 |

After Lab 7, the Days 1–5 pipeline objects remain unchanged except **`RlsDemoEvents`** — Silver **3500** should still verify.
