# Day 04 — Labs

**Theme:** Advanced KQL, Data Modeling & Gold Layer

**Database:** Same as Day 1 — **your database** on the shared cluster `adx-training-tcs` (example: **`LogsDB_u01`**).

**Prerequisite:** `SecLogsParsed` = **3500** rows **in your database**; Bronze/Silver pipeline from Days 2–3. If not, complete [Day 3 Lab 5 (update policy + backfill)](../day-03/labs.md#lab-5--update-policy-and-backfill) before Lab 1.

**Theory:** [README.md](README.md) — use the [document map](README.md#document-map) to jump to the section for each lab.

> **Lab order:** Labs 6 (UDF) and 7 (Gold MV) run in a different order than README §6–§7. Follow this file for hands-on steps.

---

## Where you work today

Unlike Day 3, **everything is in the ADX Query tab** — no Portal, no new data connections.

| Task | Site |
|------|------|
| All 7 labs | [dataexplorer.azure.com](https://dataexplorer.azure.com) → select **your** `LogsDB_<id>` |
| Run KQL | Open files in `queries/` → **Shift+Enter** one block at a time |

```text
  Day 3                          Day 4
  Portal + Query tab             Query tab only
  new ingest (EH, IoT)           analyze existing Silver (3500)
  build update policy            model + join + Gold MV
```

---

## Data model for today (read before Lab 1)

Day 4 adds a **star-style model** on top of the Silver table you built on Days 2–3. Full theory with more examples: [README §1](README.md#1-data-modeling--fact-dimension-and-layers).

### Fact vs dimension

| | **Fact table** | **Dimension table** |
|---|----------------|---------------------|
| **What it stores** | Events that **happened** | Lookups that **describe** events |
| **Grain** | One row = one security event | One row = one IOC / pattern / entity |
| **Size in lab** | **`SecLogsParsed`** — **3500** rows | **`ThreatIntelRef`** — **8** rows |
| **How it grows** | Append (ingest + streaming) | Refresh (in lab: you load it once in KQL) |

**Utility cyber fact examples (real world → course):**

| Real-world source | Example event | In course data |
|-------------------|---------------|----------------|
| VPN concentrator | Failed login from remote worker | `AuthFailure` at `Corporate-VPN` |
| DMZ firewall | Blocked scanner traffic | `FirewallDeny` from `203.0.113.50` |
| Substation IoT | Vibration / temperature alert | `SensorAnomaly` at `Substation-D` |

**Dimension in this course:** **`ThreatIntelRef`** — a small watchlist of known-bad **IPs** and **event-type patterns**. Production SOCs also use asset CMDB, facility master, and user directory tables (not built in the lab).

```text
  ONE EVENT (fact)              ONE IOC ROW (dimension)

  Timestamp: 2026-06-11 09:04   MatchKey: 203.0.113.50
  EventType: FirewallDeny       ThreatCategory: ExternalScanner
  SourceIP:  203.0.113.50  ──join──►  SeverityHint: High
  Facility:  DMZ-Firewall
```

### Star schema (course)

The **fact** sits in the **center**. **Dimensions** attach by **`join`**. **Gold** pre-aggregates the fact for dashboards.

```text
                    ┌──────────────────────┐
                    │   ThreatIntelRef     │  DIMENSION (Lab 2)
                    │   8 IOC patterns     │
                    └──────────┬───────────┘
                               │ join
                               v
                       ┌───────────────────┐
                       │  SecLogsParsed    │  FACT — Silver (Lab 1 gate)
                       │  3500 events      │
                       └─────────┬─────────┘
                                 │ materialized view (Lab 7)
                                 v
                       ┌───────────────────┐
                       │  SecLogsHourly    │  GOLD — hourly KPIs
                       └───────────────────┘
```

| Star role | Your table | Lab |
|-----------|------------|-----|
| Fact | `SecLogsParsed` | 1 (verify), 3–5 (KQL) |
| Dimension | `ThreatIntelRef` | 2 (create + join) |
| Gold aggregate | `SecLogsHourly` | 7 (materialized view) |

### IOC and enrichment (Lab 2 preview)

| Term | Meaning |
|------|---------|
| **IOC** | Indicator of Compromise — known-bad IP or attack pattern |
| **Seed** | Load **starter rows** into the new empty table — Lab 2 **Q2** via `.set-or-replace` (8 rows in the query file) |
| **IOC enrichment report** | **Lab 2 Q3 join output** — events plus `ThreatCategory` / `SeverityHint` (not a PDF export) |
| **Where `ThreatIntelRef` comes from (lab)** | **You create it** in Lab 2 Q0–Q2 — `.create table` then seed **8 rows** from inline KQL; not from Blob or Event Hub |
| **Why joins return rows** | Q2 `MatchKey` values (IPs + event types) **match values already in `SecLogsParsed`** from Days 2–3 — typically **~409** rows in Q3 |
| **Production** | ISAC / vendor TI / SOAR → scheduled pipeline → reference table in ADX; events stream separately — [README §1.7 production](README.md#production-where-threat-intel-comes-from) |

```text
  Example: course data already has SourceIP 203.0.113.50 (FirewallDeny)
           Q2 seeds MatchKey 203.0.113.50 → ExternalScanner
           Q3 join connects them → enriched row in your report
```

---

## Working in the Query tab

1. Select **your** `LogsDB_<id>` in the database dropdown.
2. Open the `.kql` file for the lab in `queries/`.
3. Run **one block at a time** with **Shift+Enter**.
4. Compare your results to the **Example result** table for that lab.

**Lab 1 is a gate check** — do not continue if Silver ≠ **3500** or Q3 `Match` = false.

## Troubleshooting

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| Lab 1 Silver ≠ **3500** | Day 3 incomplete | Finish Day 3 Labs 4–5 (update policy + backfill); re-run `01-verify-silver-baseline.kql` |
| Lab 1 Q3 `Match` = false | Bronze/Silver out of sync | Re-run Day 3 Lab 5 Step 2 backfill; confirm `SecLogsRaw` = **3500** |
| Lab 1 AuthFailure ≠ **700** | Partial Silver backfill | Complete Day 3 Lab 5; run Day 3 Lab 7 investigation queries |
| **`ThreatIntelRef` already exists** | Re-running Lab 2 Q1 without Q0 | Run **Q0** (`.drop table … ifexists`) at the top of `02-threatintel-join.kql`, then Q1–Q4 |
| Threat intel join returns 0 | `ThreatIntelRef` not loaded or wrong database | Run Lab 2 Q0–Q2 fully — `.set-or-replace` **8** rows before Q3–Q4 |
| Join Q3 far below **300** | Ref table empty, wrong join key, or stale table | Run [02-verify-threatintel.kql](queries/02-verify-threatintel.kql); `ThreatIntelRef \| count` must be **8** |
| `make-series` error or empty | Wrong time window or no rows in range | Confirm Silver = **3500**; use fixed window in query file (`2026-06-11`–`2026-06-13`) |
| Anomaly Q2 empty | Normal on lab data | **0 rows is OK** — explain why with **3500** events over 48h |
| Window Q3 far below **~182** or **0** | Silver incomplete or `serialize` skipped | Confirm Silver = **3500**; run Q1–Q2 before Q3; see [README §5.5](README.md#55-lab-5-q3--success-then-failure-pattern) |
| UDF not found | Function not created in **your** database | Run Lab 6 Q1 and Q3 **before** invoke queries; check `.show functions` in folder **Training** |
| Gold MV Q2/Q3 empty | MV still building | Wait **45–60s** after Lab 7 Q1; re-run Q2–Q3 or [07-verify-gold.kql](queries/07-verify-gold.kql) |
| Gold `sum(EventCount)` ≠ **3500** | MV incomplete or wrong source table | `.show materialized-views`; drop/recreate MV in **your** DB if needed (see Lab 7 note) |
| `.show` policy permission error | Read-only on shared cluster | Expected in some environments — note output for discussion; do not alter cluster policies |

### Debug Gold materialized view empty or wrong count

**First check — did you wait after create?**

Materialized views with **`backfill=true`** need **30–60 seconds** before first query returns rows. Run Q1, wait, then Q2–Q3.

**Verify MV exists and is healthy** — or run [queries/07-verify-gold.kql](queries/07-verify-gold.kql) Q1–Q4:

```kql
.show materialized-views
SecLogsHourly | take 5
SecLogsHourly | summarize TotalEvents = sum(EventCount)
```

| What you see | Likely cause | Fix |
|--------------|--------------|-----|
| Q2/Q3 return 0 rows immediately after Q1 | Backfill not finished | Wait 45–60s; re-run Q2–Q3 |
| `sum(EventCount)` &lt; **3500** | MV created before Silver complete | Fix Silver (Lab 1); `.drop materialized-view SecLogsHourly ifexists` then re-run Lab 7 Q1 |
| MV not listed | Q1 failed or wrong database | Confirm **your** `LogsDB_<id>` selected; re-run Q1 |
| MV already exists from prior attempt | Stale definition | In **your** database only: `.drop materialized-view SecLogsHourly ifexists` then Q1 |

**Re-run Lab 2 safely:** The query file starts with `.drop table ThreatIntelRef ifexists` (Q0). Run the full file from Q0, or drop manually then Q1–Q4.

---

## Expected outcomes

```text
  AFTER ALL 7 LABS — objects in YOUR database

  SecLogsParsed ──────── fact (3500 rows, unchanged from Day 3)
         │
         ├──join──► ThreatIntelRef (8 rows, you created Lab 2)
         │
         └──MV───► SecLogsHourly (Gold, sum EventCount = 3500)

  Functions: SeverityRank, IsOTFacility (folder Training, Lab 6)
```

| After lab | Check |
|-----------|--------|
| Lab 1 | Silver = **3500**; Bronze = Silver; AuthFailure = **700**; `dcount(SourceSystem)` = **4** |
| Lab 2 | ThreatIntelRef = **8**; Q3 ≥ **300** enriched rows |
| Lab 3 Q2 | make-series ≥ **1** EventType series |
| Lab 4 Q1 | `baseline`, `score`, `anomalies` columns present |
| Lab 4 Q2 | **0 or 1** anomaly rows (empty OK) |
| Lab 5 Q1–Q2 | `EventSeqInFacility`, `PrevEventType` populated |
| Lab 5 Q3 | **~182** auth pattern rows (varies slightly; **0+** if data differs) |
| Lab 6 | `SeverityRank`, `IsOTFacility` in `.show functions` |
| Lab 7 Q3 | `sum(EventCount)` on SecLogsHourly = **3500**; verify Q4 `Match` = **true** |

---

# Lab 1 — Verify Silver baseline

## Objective

Confirm typed Silver **fact** data from Day 3 before creating dimension and Gold objects. Review [Data model for today](#data-model-for-today-read-before-lab-1) (fact vs dimension, star schema) and [README §1.3–§1.4](README.md#13-fact-table-vs-dimension-table) for full theory.

```text
  Lab 1 gate — must pass before Lab 2

  SecLogsParsed = 3500?  ──no──► finish Day 3 backfill
         │
        yes
         v
  Bronze = Silver?  AuthFailure = 700?  ──► continue to Lab 2
```

## Tasks

1. Select **your database** (example: **`LogsDB_u01`**).
2. Open **`queries/01-verify-silver-baseline.kql`**.
3. Run all blocks **Q1–Q6** — total count, `SourceSystem` breakdown, Bronze/Silver parity, AuthFailure, source-system count, `EventType` summary.

> **Q6** is a sanity check (event-type distribution) — not a hard gate, but run it before Lab 2.

> Run **Q3** (`print` with `Match`) as **one block** — do not split the `print` statement.

## Example result

| Check | Value |
|-------|-------|
| Total Silver rows (Q1) | **3500** |
| `SourceSystem` breakdown (Q2) | Batch-CSV **1000**, Batch-JSON **1500**, EventHub **500**, IoT-Hub **500** |
| Q3 `Match` | **true** (Bronze = Silver = **3500**) |
| AuthFailure (Q4) | **700** |
| `SourceSystemCount` (Q5) | **4** |
| `SecLogsRaw \| count` (optional) | **3500** (unchanged from Day 3) |

## Success criteria

* Matches table above. Do not continue if Silver ≠ **3500** or Q3 `Match` = false.

---

# Lab 2 — Reference data and joins

## Objective

Create the **dimension** table **`ThreatIntelRef`** (**8** synthetic IOC rows) in **your database**, then **`join`** it to the Silver **fact** table to produce an **IOC enrichment report**.

This is the **dimension spoke** on the [star schema](#star-schema-course) above — you are both creating the watchlist and using it to enrich events.

> **IOC** = Indicator of Compromise. **`ThreatIntelRef`** is **seeded** (loaded) from **inline KQL** in `02-threatintel-join.kql` (Q0–Q2), not ingested from external files. **Seed** = put the first 8 rows into the new table; those `MatchKey` values match IPs/event types already in your Silver data so Q3 returns enriched rows. Full explanation: [README §1.7](README.md#17-dimension--reference--threatintelref-lab-2) · [What seed means](README.md#what-seed-means) · [Production TI](README.md#production-where-threat-intel-comes-from).

## Tasks

```text
  Lab 2 run order (two files — do not skip verify)

  02-threatintel-join.kql     Q0 drop → Q1 create → Q2 seed (8 rows)
           │
           v
  02-verify-threatintel.kql   Q1 count=8 → Q2 keys → Q3 sample
           │
           v
  02-threatintel-join.kql     Q3 row-level join → Q4 summary
```

> **Management commands** (`.drop`, `.create`, `.set-or-replace`) run in the **Query tab** like any other KQL — select the full block and **Shift+Enter**. They change database schema, not query results only.

> **`kind=leftouter`** keeps all **3500** Silver rows; only matching keys get `ThreatCategory`. **`inner`** would drop non-matching events — wrong for SOC enrichment reports. Theory: [README §2.4](README.md#24-join-flavors-leftouter-vs-inner).

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Open **`queries/02-threatintel-join.kql`**.
3. Run **Q0–Q2** (drop if re-run → create ref table → **seed** **8** rows into the empty table).
4. Open **`queries/02-verify-threatintel.kql`** and run **Q1–Q3** — confirm row count and sample keys before joins.
5. Return to **`02-threatintel-join.kql`** and run **Q3–Q4**.
6. Review Q3 — threat categories on matching SourceIPs (typically **~409** rows; minimum ≥ **300**).
7. Review Q4 — counts by `ThreatCategory` and `EventType`.

> Q0 (`.drop table ThreatIntelRef ifexists`) is harmless on first run and prevents “table already exists” on re-run.

> Use `kind=leftouter` to keep all Silver rows; `where isnotempty(ThreatCategory)` shows matches only.

```text
  Q3 — row-level (SourceIP)          Q4 — summary (EventType)

  ~409 enriched events               3 rows: 800 / 700 / 200
  "show me flagged events"           "count by threat category"
```

## Example result

| Check | Value |
|-------|-------|
| `ThreatIntelRef \| count` | **8** |
| Q3 enriched rows | **~409** (minimum ≥ **300**) with non-empty `ThreatCategory` |
| Q4 sample rows | `PerimeterBlock` / FirewallDeny **800**; `CredentialAttack` / AuthFailure **700**; `PrivilegeAbuse` / PrivilegeEscalation **200** |
| Sample category (Q3) | `ExternalScanner`, `VPNAbuse`, `BruteForceTarget` on matching SourceIPs |

## Success criteria

* Matches table above.

---

# Lab 3 — Time-series analysis

## Objective

Build hourly aggregates with **`bin()`** and time-series vectors with **`make-series`**.

```text
  Q1 summarize + bin     tabular rows (chart-friendly)
  Q2 make-series         dynamic arrays (anomaly / ML functions)
  Q3 filtered series     AuthFailure only (700 events → hourly array)
```

Theory: [README §3](README.md#3-time-series-analysis).

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Open **`queries/03-time-series.kql`**.
3. Run **Q1–Q3** in order.

> Sample data uses a fixed window **`2026-06-11`** to **`2026-06-13`** — matches the course ingest timestamps in `SecLogsParsed`.

4. Optional: add `| render timechart` to a Q1-style summarize and open **Chart** tab:

```kql
SecLogsParsed
| where Timestamp between (datetime(2026-06-11) .. datetime(2026-06-13))
| summarize EventCount = count() by EventType, HourBucket = bin(Timestamp, 1h)
| render timechart
```

## Example result

| Query | Result |
|-------|--------|
| Q1 | Hourly buckets by `EventType` |
| Q2 | ≥ **1** `EventType` with **`dynamic`** `EventCount` array |
| Q3 | Single AuthFailure series (**700** events bucketed) |

## Success criteria

* Q1 and Q2 complete without error; Q2 shows at least one series.

---

# Lab 4 — Anomaly detection

## Objective

Apply **`series_decompose_anomalies`** on hourly event-count series from **`make-series`**.

```text
  make-series ──► EventCount[] ──► series_decompose_anomalies
                                        │
                                        v
                              baseline[], score[], anomalies[]
                              Q2: mv-expand → rows where anomalies == 1
                              (often 0 rows on lab data — still a pass)
```

Theory: [README §4](README.md#4-anomaly-detection).

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Open **`queries/04-anomaly-detection.kql`**.
3. Run **Q1** — select the **entire block** including `let series = ...` **and** the second `series | extend ...` line (one Shift+Enter). Confirm `baseline`, `score`, `anomalies` columns (dynamic arrays).

> **Q1** filters **`FirewallDeny`** only; **Q2** uses **all event types** — that contrast is intentional (narrow series for decomposition vs broad anomaly pass).

4. Run **Q2** — uses **`mv-expand`** to turn array columns into rows; list hours where `anomalies == 1` (may be **empty** on lab data).
5. In discussion: explain why sparse flags are **expected** with **3500** rows.

## Example result

| Column | Meaning |
|--------|---------|
| `baseline` | Expected hourly level |
| `score` | Deviation strength |
| `anomalies` | **`1`** = flagged hour |
| Q2 row count | **0** typical (empty result is OK — no error) |

## Success criteria

* Q1 completes with `baseline`, `score`, `anomalies` columns.
* You can explain what `anomalies == 1` means in plain language.

---

# Lab 5 — Window functions

## Objective

Use **`serialize`**, **`row_number`**, and **`prev`** for ordered event-sequence analysis.

```text
  Why serialize? (without it, prev() sees wrong rows)

  Parallel partitions          serialize → single ordered stream
  [row3][row1][row2]    →      row1 → row2 → row3
                                      prev() works here
```

```text
  order by  ──►  serialize  ──►  row_number(restart) / prev()
       │              │                  │
  define sequence  lock order     compare to prior row / restart per Facility
```

**Lab 5 Q1** uses **`row_number(1, prev(Facility) != Facility)`** so the counter **restarts at 1** for each facility (not a global 1…3500 index).

**Lab 5 Q3** finds AuthSuccess → AuthFailure at the same Facility (~**182** rows). Theory: [README §5](README.md#5-window-functions).

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Open **`queries/05-window-functions.kql`**.
3. Run **Q1–Q3** in order.

## Example result

| Query | Result |
|-------|--------|
| Q1 | `EventSeqInFacility` **restarts at 1** per `Facility` (filter one facility to see 1, 2, 3…) |
| Q2 | `PrevEventType` and `MinutesSincePrev` on most rows |
| Q3 | **~182** rows — AuthFailure where previous event was AuthSuccess at same Facility |

## Success criteria

* Q1 and Q2 show expected window columns.
* Q3 returns auth success→failure pairs (typically **~182** rows on lab data).
* You can explain the **`serialize`** requirement.

---

> **Bridge to Lab 6:** Lab 5 showed **per-row** patterns. Lab 6 **packages reusable logic** (`SeverityRank`, `IsOTFacility`) before Lab 7 builds the **Gold** aggregate — so dashboard queries stay readable.

# Lab 6 — User-defined functions

## Objective

Create and use KQL functions **`SeverityRank`** and **`IsOTFacility`** for reusable logic.

```text
  .create-or-alter function  ──►  stored in YOUR database (folder Training)
                                         │
  query: extend Rank = SeverityRank(...) ◄┘
```

Theory: [README §7](README.md#7-user-defined-functions-udfs).

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Open **`queries/06-create-udf.kql`**.
3. Run blocks in order — **Q1** create `SeverityRank` → **Q1b** `.show functions` → **Q2** query → **Q3** create `IsOTFacility` (**select the entire Q3 block**, create line + `{ ... }` body) → **Q3b** query.

> Each **`.create-or-alter function`** block includes its `{ ... }` body — run the **whole block** with Shift+Enter, not just the first line.

## Example result

| Check | Result |
|-------|--------|
| `.show functions` | **`SeverityRank`**, **`IsOTFacility`** in folder **`Training`** |
| Q2 | High/Critical-ranked rows summarized by Facility, EventType |
| Q3 | OT-adjacent *(Operational Technology–adjacent: substation / SCADA)* facility event counts |

## Success criteria

* Functions listed; Q2 returns High/Critical-ranked rows.

---

# Lab 7 — Gold materialized view and policies

## Objective

Create **`SecLogsHourly`** — the **Gold** table in the star schema — as a materialized view on the Silver fact. After Lab 7, your model is: fact (`SecLogsParsed`) + dimension (`ThreatIntelRef`) + Gold (`SecLogsHourly`).

> Gold answers dashboard questions (*“how many auth failures per hour at each facility?”*) without re-scanning all **3500** Silver rows every time.

```text
  Lab 7 timeline

  Q1  ONE block: drop + create MV + .show materialized-views
           │
           └──► wait 30–60 s (MV backfill — .show runs before data is ready)
                    │
                    v
  Q2–Q4  query Gold (re-run if zero rows)
           │
           v
  07-verify-gold.kql   sum(EventCount)=3500, Match=true  (second file — same checks, cleaner gate)
           │
           v
  Q5     .show retention / caching (read-only)
```

> **Why two verify files?** `07-gold-materialized-view.kql` creates and explores Gold; **`07-verify-gold.kql`** is the **checkpoint gate** (parity print) — same pattern as Day 5 Lab 4 verify file.

Theory: [README §6](README.md#6-materialized-views--gold-seclogshourly) · [§8 policies](README.md#8-hot-vs-cold-data-retention-and-caching).

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Open **`queries/07-gold-materialized-view.kql`**.
3. Run **Q1** as **one block** (`.drop` + `.create` + `.show materialized-views`); wait **30–60 seconds** after Q1 completes before querying Gold.
4. Run **Q2–Q4** — re-run Q2–Q3 if first pass shows zero rows. **Q4** (top facilities dashboard) is exploratory — confirms Gold is queryable.
5. Run **`queries/07-verify-gold.kql`** Q1–Q4 — confirm `TotalEvents` = **3500** and Q4 `Match` = **true**.
6. Return to **`07-gold-materialized-view.kql`** and run **Q5** — `.show` retention and caching (read-only).

> Q1 drops any prior `SecLogsHourly` in **your** database, then creates the MV — same `bin(Timestamp, 1h)` logic as Lab 3 Q1.

## Example result

| Check | Value |
|-------|-------|
| `.show materialized-views` | `SecLogsHourly` listed |
| Q3 `sum(EventCount)` | **3500** |
| `07-verify-gold.kql` Q4 `Match` | **true** |
| Q5 policies | Commands run without permission error |

## Success criteria

* Matches table above.

---

## Optional practice

After finishing all labs, work through **[assignments.md](assignments.md)** — scenario-based KQL tasks with **Self-check** expected values. Answer keys are provided in class (not in this repository).

---

## Next — Day 5

Continue to **[Day 5 — Performance, Security & Capstone](../day-05/labs.md)**. Prerequisite: Lab 7 Gold MV with `sum(EventCount)` = **3500**.

Optional practice above can also be used as **Day 5 warm-up** before starting [Day 5 labs](../day-05/labs.md).

---
