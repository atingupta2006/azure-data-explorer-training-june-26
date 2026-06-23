# Day 05 — Scenario-based KQL assignments

**Purpose:** Practice Day 5 skills beyond the guided labs — query optimization, `hint.strategy`, MV vs on-demand, RBAC/RLS demo, monitoring, and capstone investigation patterns.

**Database:** Your workspace `LogsDB_<id>` on cluster `adx-training-tcs` (same as labs). Select **your** database in the Query tab before each assignment.

**Prerequisite:** Full pipeline from Days 2–4 plus [Day 5 labs](labs.md) (or at minimum the [pipeline gate](labs.md#pipeline-gate-before-lab-1)). Assignments that use `RlsDemoEvents` require [Lab 5](labs.md#lab-5--security-rbac-and-rls-demo).

**How to use**

1. Read the **scenario** (utility cyber SOC / platform operations context).
2. Write KQL in the ADX Query tab — do not copy from lab files until you have tried yourself.
3. Compare your results to **Self-check** after you have tried the query yourself.

**Answer keys** are provided by your trainer (not in this repository).

**Locked reference counts (lab profile)**

| Object / metric | Expected |
|-----------------|----------|
| `SecLogsParsed` | **3500** |
| `ThreatIntelRef` | **8** |
| `SecLogsHourly` sum(`EventCount`) | **3500** |
| `RlsDemoEvents` | **10** |
| `AuthFailure` (Silver) | **700** |
| IOC join (SourceIP) enriched rows | **~409** (≥ **300**) |
| scada-gw `AuthFailure` | ≥ **1** (many in course data) |
| BruteForceTarget IP `10.20.1.44` on scada-gw | ≥ **1** |

Sample data window: **`2026-06-11`** through **`2026-06-13`**.

---

## Easy (10) — Optimization, Gold read, operations basics

*Skills: time filter, `project`, Gold MV read, parity check, `.show`, RLS demo. **After pipeline gate** unless noted.*

### E1 — Shift-start auth failure slice

**Scenario:** Tier-1 opens the morning queue. Use a **time-bounded** scan (production pattern) before filtering event type.

**Task:** Count **`AuthFailure`** rows where `Timestamp > datetime(2026-06-11)`.

**Self-check:** **700**.


---

### E2 — Narrow columns before join

**Scenario:** Enrichment job must avoid carrying wide Silver rows into the join operator.

**Task:** Filter time, **`project`** only join keys and labels, **inner join** to `ThreatIntelRef` on `SourceIP`. Return **row count** of enriched matches.

**Self-check:** **~409** (same order of magnitude as Day 4 Lab 2 Q3).


---

### E3 — Dashboard peak hour *(after Lab 4)*

**Scenario:** Executive dashboard reads **Gold** instead of rescanning Silver. Find the single busiest **hour + facility + event type** bucket.

**Task:** Query `SecLogsHourly`, `top 1` by `EventCount` descending.

**Self-check:** One row with positive `EventCount` and populated `HourBucket`.


---

### E4 — Silver vs Gold parity *(after Lab 4)*

**Scenario:** Platform team verifies the materialized view still matches Silver totals after a long week of labs.

**Task:** Use `let` + `toscalar` to `print` on-demand total, MV total, and **`TotalsMatch`**.

**Self-check:** Both totals **3500**; **`TotalsMatch` = true**.


---

### E5 — RLS demo table size *(after Lab 5)*

**Scenario:** After completing Lab 5 (including **Q4c disable**), confirm the demo table row count.

**Task:** Count rows in **`RlsDemoEvents`**.

**Self-check:** **10** (not **4** — RLS must be disabled).


---

### E6 — Demo events by facility *(after Lab 5)*

**Scenario:** Security architect wants to see how the **10** demo rows split across OT facilities.

**Task:** Summarize count by `Facility`; order by facility name.

**Self-check:** Substation-A, Substation-B, and SCADA-Gateway only; sums to **10**.


---

### E7 — Access review starter *(after Lab 5)*

**Scenario:** Quarterly access review begins with **who has permissions** on the student database.

**Task:** Run **`.show database principals`**.

**Self-check:** Result grid lists principals; no permission error.


---

### E8 — Extent awareness *(after Lab 2)*

**Scenario:** Capacity planning asks for **extent count and row count** on Silver without scanning facts.

**Task:** **`.show tables details`** filtered to `SecLogsParsed`; project `TableName`, `TotalExtents`, `TotalRowCount`.

**Self-check:** `TotalRowCount` = **3500**; small extent count at lab scale.


---

### E9 — June window row count

**Scenario:** Analyst confirms how many events fall in the **post–June 11** investigation window used in Day 5 lab files.

**Task:** Count `SecLogsParsed` where `Timestamp > datetime(2026-06-11)`.

**Self-check:** **3500** (all course sample rows fall in this window).


---

### E10 — Known brute-force source

**Scenario:** Threat intel lists **`10.20.1.44`** as **`BruteForceTarget`**. Count Silver events from that IP (any event type).

**Task:** Filter `SourceIP == "10.20.1.44"`; count.

**Self-check:** **≥ 1** (many auth events in batch JSON).


---

## Medium (10) — Hints, Gold drill-down, capstone preview

*Skills: `hint.strategy=shuffle`, on-demand vs Gold, monitoring `.show`, scada gateway filters. Complete the listed lab first.*

### M1 — Shuffle join enrichment *(after Lab 3)*

**Scenario:** Production join policy requires **`hint.strategy=shuffle`** on large fact-to-dimension enrichment.

**Task:** Time-filter Silver, project key columns, **shuffle inner join** to `ThreatIntelRef` on `SourceIP`. Project investigation columns; order by time.

**Self-check:** Rows with `ThreatCategory` populated; no syntax errors.


---

### M2 — High-severity IOC matches *(after Lab 3)*

**Scenario:** SOC lead wants **`ThreatCategory`** counts for **High/Critical** severity events only, using shuffle join.

**Task:** Time filter → shuffle join → filter severity → summarize by `ThreatCategory`.

**Self-check:** Multiple categories possible; all rows High or Critical severity.


---

### M3 — On-demand hourly auth failures *(after Lab 4)*

**Scenario:** Ad-hoc investigation needs **live** hourly auth failure buckets — not Gold MV.

**Task:** Time filter, filter `AuthFailure`, `summarize` by `bin(Timestamp, 1h)` and `Facility`.

**Self-check:** Multiple hour/facility rows; totals across buckets align with auth failure volume.


---

### M4 — Substation-A demo slice *(after Lab 5)*

**Scenario:** RLS policy discussion: show only rows **your** `UserPrincipalName` is allowed to see (same logic as the Lab 5 RLS function).

**Task:** Join `RlsUserScope` to `RlsDemoEvents` on facility match for **your** UPN, or filter `Facility` to the value in your scope row.

**Self-check:** **4** rows if `AllowedFacility == "Substation-A"`; **3** for Substation-B or SCADA-Gateway.


---

### M5 — Gold OT auth KPIs *(after Lab 4)*

**Scenario:** Substation operations manager uses **`SecLogsHourly`** for **`AuthFailure`** at **`Substation-A`**.

**Task:** Query Gold with facility and event type filters; project hourly counts and `HighSeverityCount`.

**Self-check:** **≥ 1** hourly row; matches capstone Step 4 pattern.


---

### M6 — SCADA gateway brute-force evidence *(after Lab 1)*

**Scenario:** Incident ticket: **`10.20.1.44`** failed auth against **`scada-gw.utility.local`**.

**Task:** Filter `DestinationHost`, `EventType`, and `SourceIP`; project evidence columns.

**Self-check:** **≥ 1** row; `Severity` typically High.


---

### M7 — Materialized view health *(after Lab 6)*

**Scenario:** Morning ops check: is **`SecLogsHourly`** healthy?

**Task:** **`.show materialized-views`** filtered to `SecLogsHourly`; project `Name`, `SourceTable`, `IsHealthy`, `LastRunResult`.

**Self-check:** `IsHealthy` = **true** after Day 4 Lab 7.


---

### M8 — VPN auth failure severity mix

**Scenario:** Corporate VPN team wants **`AuthFailure`** counts **by severity** at **`Corporate-VPN`**, time-bounded.

**Task:** Apply June 11 time filter, facility filter, summarize by `Severity`.

**Self-check:** Only `AuthFailure` at Corporate-VPN; no Low-only bulk if filtered to High/Critical elsewhere.


---

### M9 — Gold high-severity rollup

**Scenario:** Risk dashboard sums **`HighSeverityCount`** from Gold by facility (no Silver rescan).

**Task:** Query `SecLogsHourly`, summarize `sum(HighSeverityCount)` by `Facility`, order descending.

**Self-check:** All facilities with High/Critical in Silver appear; positive totals.


---

### M10 — SCADA gateway auth volume *(after Lab 7 preview)*

**Scenario:** Count all **`AuthFailure`** events targeting the SCADA gateway host before opening the full capstone.

**Task:** Filter `DestinationHost == "scada-gw.utility.local"` and `EventType == "AuthFailure"`; count.

**Self-check:** **≥ 1** (typically dozens from batch + Event Hub).


---

## Complex (10) — Multi-step operations and capstone

*Skills: bounded shuffle joins, Gold/Silver reconciliation, executive `print`, pipeline diagnostics. **After Labs 1–7** unless noted.*

### C1 — Bounded brute-force hunt *(after Lab 3)*

**Scenario:** Incident confined to **`2026-06-11`**: list **`BruteForceTarget`** IOC matches with shuffle join and early time filter.

**Task:** Filter to June 11, project, shuffle join filtered dimension, project investigation columns.

**Self-check:** Rows include **`10.20.1.44`**; all `ThreatCategory == "BruteForceTarget"`.


---

### C2 — Gold vs Silver bucket audit *(after Lab 4)*

**Scenario:** Auditor validates one **`Substation-A`** **`AuthFailure`** hour: Gold `EventCount` must equal Silver row count in that hour.

**Task:** Pick top Gold bucket for that facility/type; compare to Silver count in same hour (use `let` + `toscalar`).

**Self-check:** `GoldEventCount` = `SilverCount` for the chosen bucket.


---

### C3 — Capstone threat enrichment *(after Lab 7)*

**Scenario:** Full ticket workflow: **`AuthFailure`** on **`scada-gw.utility.local`** enriched with threat intel using **`hint.strategy=shuffle`**.

**Task:** Filter Silver, shuffle join to `ThreatIntelRef`, project timestamp, IP, category, hint, message.

**Self-check:** **≥ 1** row with **`ThreatCategory`** (e.g. **BruteForceTarget** on **10.20.1.44**).


---

### C4 — Operations dashboard *(after Labs 4–5)*

**Scenario:** Single **`print`** for NOC wallboard: Silver total, Gold total, RLS demo size, scada threat-enriched auth failure count.

**Task:** One query with four labeled metrics using `toscalar` and shuffle join for scada matches.

**Self-check:**

| Metric | Expected |
|--------|----------|
| SilverTotal | **3500** |
| GoldTotal | **3500** |
| RlsDemoRows | **10** |
| ScadaThreatMatches | **≥ 1** |


---

### C5 — SCADA impact by ingest path

**Scenario:** Determine whether gateway attacks arrive via **batch** or **streaming** paths.

**Task:** Filter `DestinationHost == "scada-gw.utility.local"`; summarize total events, auth failures, and High/Critical counts **by `SourceSystem`**.

**Self-check:** Multiple `SourceSystem` values (e.g. Batch-JSON, EventHub).


---

### C6 — Optimization habit check

**Scenario:** Teach the **filter-first** habit: compare full-table row count vs time- and type-bounded auth failure count.

**Task:** One `print` with **`FullTableRows`** and **`AuthFailureAfterJun11`**.

**Self-check:** Full table **3500**; auth failures **700**.


---

### C7 — Top facilities for auth failures (Gold)

**Scenario:** Leadership wants the **top three facilities** by total **`AuthFailure`** volume from Gold — no Silver scan.

**Task:** Filter Gold by `EventType`, summarize `sum(EventCount)` by `Facility`, `top 3`.

**Self-check:** Three facilities; Corporate-VPN or substations typically rank high.


---

### C8 — Production enrichment pattern

**Scenario:** Combine **time filter**, **`project`**, **`hint.strategy=shuffle`**, and severity filters for a manager report.

**Task:** June 11–13 window, project keys, shuffle join High/Critical IOC hints, filter Silver severity High/Critical, summarize by category and facility.

**Self-check:** Subset of ~409 IOC rows; no Low/Medium-only severity in output.


---

### C9 — Pipeline storage footprint *(after Lab 2)*

**Scenario:** Compare **extent and row counts** across Bronze, Silver, and Gold for capacity review.

**Task:** **`.show tables details`** for `SecLogsRaw`, `SecLogsParsed`, `SecLogsHourly`; order by table name.

**Self-check:** Silver **3500** rows; Gold sum of row counts in details may differ (aggregated buckets) — compare `SecLogsParsed` **3500** vs Gold **`sum(EventCount)`** separately.


---

### C10 — End-of-course executive brief *(capstone)*

**Scenario:** Close the week with one query: Silver total, Gold total, parity flag, shuffle-enriched IOC count, scada gateway auth failure count.

**Task:** Single **`print`** with five labeled metrics.

**Self-check:**

| Metric | Expected |
|--------|----------|
| SilverTotal | **3500** |
| GoldTotal | **3500** |
| TotalsMatch | **true** |
| IocEnrichedShuffle | **~409** |
| ScadaGatewayAuthFailures | **≥ 1** |


---

## Assignment map vs Day 5 labs

| Lab | Unlocks assignments |
|-----|---------------------|
| Pipeline gate | All (baseline) |
| Lab 1 | E1–E2, E9–E10, M6, M8, C6 |
| Lab 2 | E8, C9 |
| Lab 3 | M1–M2, C1, C8, C10 (IOC part) |
| Lab 4 | E3–E4, M3, M5, M9, C2, C7, C10 (Gold part) |
| Lab 5 | E5–E7, M4, C4 (RlsDemo part) |
| Lab 6 | M7 |
| Lab 7 | M10, C3, C5, C10 (scada part) |
