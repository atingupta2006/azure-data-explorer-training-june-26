# Day 04 — Scenario-based KQL assignments

**Purpose:** Practice Day 4 skills beyond the guided labs — fact/dimension joins, time-series, anomalies, windows, UDFs, and Gold MV.

**Database:** Your workspace `LogsDB_<id>` on cluster `adx-training-tcs` (same as labs). Select **your** database in the Query tab before each assignment.

**Prerequisite:** [Day 3 Lab 5](../day-03/labs.md#lab-5--update-policy-and-backfill) complete — `SecLogsParsed` = **3500** rows. Complete [Day 4 labs](labs.md) in order before assignments that need `ThreatIntelRef`, UDFs, or `SecLogsHourly`.

**How to use**

1. Read the **scenario** (utility cyber SOC context).
2. Write KQL in the ADX Query tab — do not copy from lab files until you have tried yourself.
3. Compare your results to **Self-check** after you have tried the query yourself.

**Answer keys** are provided by your trainer (not in this repository).

**Locked reference counts (lab profile)**

| Object / metric | Expected |
|-----------------|----------|
| `SecLogsParsed` | **3500** |
| `AuthFailure` | **700** |
| `FirewallDeny` | **800** |
| `SourceSystem` values | **4** |
| `ThreatIntelRef` | **8** |
| IOC join (SourceIP) enriched rows | **~409** (≥ **300**) |
| Auth success→failure pairs (window) | **~182** |
| `SecLogsHourly` sum(`EventCount`) | **3500** |

Sample data window: **`2026-06-11`** through **`2026-06-13`**.

---

## Easy (10) — Silver basics and filters

*Skills: `count`, `where`, `summarize`, `order`, `take`, `dcount`. **After Lab 1** unless noted.*

### E1 — Morning health check

**Scenario:** You start shift on the utility SOC dashboard. Confirm the Silver fact table loaded completely after Day 3 backfill.

**Task:** Write a query that returns the **total row count** of `SecLogsParsed`.

**Self-check:** **3500**.


---

### E2 — Auth failure triage queue

**Scenario:** The identity team asks how many **authentication failures** are in the current dataset before they open a ticket.

**Task:** Count rows where `EventType == "AuthFailure"`.

**Self-check:** **700**.


---

### E3 — Event catalog

**Scenario:** A new analyst needs a list of **distinct event types** and how many times each appears.

**Task:** Summarize `count()` by `EventType`; sort by count descending.

**Self-check:** Includes `AuthFailure`, `FirewallDeny`, `VPNLogin`, `SensorAnomaly`, etc.; totals sum to **3500**.


---

### E4 — DMZ firewall slice

**Scenario:** Perimeter team wants all events where **`Facility == "DMZ-Firewall"`**.

**Task:** Return `Timestamp`, `EventType`, `SourceIP`, `Severity`, `Message` for that facility; order by time.

**Self-check:** Hundreds of rows (mostly `FirewallDeny`).


---

### E5 — Ingest lineage

**Scenario:** Prove all **four** ingest paths (batch JSON, batch CSV, Event Hub, IoT) are represented in Silver.

**Task:** Summarize row count by `SourceSystem`.

**Self-check:** **4** systems — Batch-JSON **1500**, Batch-CSV **1000**, EventHub **500**, IoT-Hub **500**.


---

### E6 — Top facilities by volume

**Scenario:** Management asks which **five facilities** generated the most security events.

**Task:** `summarize` count by `Facility`, `top 5` by count.

**Self-check:** DMZ-Firewall and Corporate-VPN typically rank high.


---

### E7 — High-severity filter

**Scenario:** Tier-1 only wants **`High`** or **`Critical`** severity events in the lab window.

**Task:** Filter `SecLogsParsed` where `Severity in ("High", "Critical")` and `Timestamp` between `datetime(2026-06-11)` and `datetime(2026-06-13)`.

**Self-check:** Thousands of rows; no `Low`/`Medium` in result.


---

### E8 — Threat intel watchlist size *(after Lab 2)*

**Scenario:** After seeding the dimension table, verify the IOC reference loaded correctly.

**Task:** Return row count of `ThreatIntelRef`.

**Self-check:** **8**.


---

### E9 — Substation IoT stream *(after Lab 1)*

**Scenario:** OT engineer asks how many events came from **IoT Hub** telemetry (not batch or VPN stream).

**Task:** Count rows where `SourceSystem == "IoT-Hub"`.

**Self-check:** **500**.


---

### E10 — First hourly bucket *(intro to `bin()`)*

**Scenario:** Control room wants **hourly** event volume for **`FirewallDeny`** only.

**Task:** Use `bin(Timestamp, 1h)` and `summarize count()` by hour; order by hour.

**Self-check:** Multiple hour buckets; total counts across buckets = **800** for `FirewallDeny`.


---

## Medium (10) — Joins, time-series, windows, UDFs

*Skills: `join`, `make-series`, `serialize`, UDFs, Gold queries. Complete the listed lab first.*

### M1 — External scanner IOC hits *(after Lab 2)*

**Scenario:** Threat intel flagged IP **`203.0.113.50`** as **`ExternalScanner`**. List matching Silver events with threat context.

**Task:** Join `SecLogsParsed` to `ThreatIntelRef` on `SourceIP` (filter dimension to `MatchType == "SourceIP"`). Keep rows where `ThreatCategory == "ExternalScanner"`. Project time, IP, facility, category, hint.

**Self-check:** Many rows; all `SourceIP` = `203.0.113.50`.


---

### M2 — Credential attack summary *(after Lab 2)*

**Scenario:** Use the **event-type** IOC row (`AuthFailure` → `CredentialAttack`) to summarize how many auth failures are tagged.

**Task:** Join on `EventType` (filter `MatchType == "EventType"`). Summarize count by `ThreatCategory` and `EventType`.

**Self-check:** One row — `CredentialAttack` / `AuthFailure` / **700**.


---

### M3 — VPN auth failures by facility

**Scenario:** Corporate VPN team wants **`AuthFailure`** counts **per facility** to find hot spots.

**Task:** Filter `EventType == "AuthFailure"`, summarize by `Facility`, order descending.

**Self-check:** **700** rows total across facilities; `Corporate-VPN` is a major share.


---

### M4 — Hourly auth failure series *(after Lab 3)*

**Scenario:** Build a time-series for **`AuthFailure`** counts per hour for anomaly tooling later.

**Task:** Use `make-series` with `default=0`, window `2026-06-11` to `2026-06-13`, step `1h`.

**Self-check:** One series; dynamic array length matches hour range; sum of array ≈ **700**.


---

### M5 — Event sequence number at substation *(after Lab 5)*

**Scenario:** For **`Substation-A`**, assign a **sequence number** to each event in time order for timeline reconstruction.

**Task:** Filter facility, `order by Timestamp`, `serialize`, `extend Seq = row_number()`, project key columns.

**Self-check:** `Seq` starts at 1 and increments; no duplicate sequence in same facility block.


---

### M6 — Gap since previous event *(after Lab 5)*

**Scenario:** Analysts suspect **long gaps** between events may indicate sensor outage.

**Task:** Order all events by `Timestamp`, `serialize`, compute **`MinutesSincePrev`** with `datetime_diff` and `prev(Timestamp)`. Show rows where gap **> 30** minutes.

**Self-check:** Some rows with large gaps (lab data has regular timestamps — gaps may be sparse).


---

### M7 — High/Critical ranked events *(after Lab 6)*

**Scenario:** Use the **`SeverityRank`** UDF to list only **High** and **Critical** events (`Rank >= 3`).

**Task:** `extend Rank = SeverityRank(Severity)`, filter, summarize count by `Facility` and `EventType`.

**Self-check:** No Low/Medium-only rows; counts align with severity filter.


---

### M8 — OT facility dashboard *(after Lab 6)*

**Scenario:** **NERC CIP** *(grid cybersecurity standard — Critical Infrastructure Protection)* review needs event counts only from **OT-adjacent** *(Operational Technology–adjacent: substation / SCADA)* facilities.

**Task:** Use **`IsOTFacility(Facility)`** in a `where` clause; summarize by `Facility` and `EventType`.

**Self-check:** Only substations A–D and `SCADA-Gateway`; no `Corporate-VPN` rows.


---

### M9 — Gold hourly top bucket *(after Lab 7)*

**Scenario:** Dashboard team uses **`SecLogsHourly`** instead of scanning Silver. Find the **single hour + facility + event type** with the highest `EventCount`.

**Task:** Query `SecLogsHourly`, order by `EventCount` desc, `take 1`.

**Self-check:** One row with positive `EventCount` and `HourBucket` populated.


---

### M10 — Perimeter block volume *(after Lab 2)*

**Scenario:** Summarize all events tagged **`PerimeterBlock`** from the event-type IOC join.

**Task:** Join on `EventType`, filter `ThreatCategory == "PerimeterBlock"`, count rows.

**Self-check:** **800** (all `FirewallDeny` rows in lab data).


---

## Complex (10) — Multi-step investigations

*Skills: combine join + time filter, windows + filter, Gold drill-down, bounded joins. **After Labs 1–7** unless noted.*

### C1 — Bounded IOC hunt

**Scenario:** During incident **`2026-06-11`**, find all **SourceIP IOC matches** with **`Critical`** or **`High`** hints only — production pattern: filter time **before** join.

**Task:** Filter `SecLogsParsed` to June 11, join to IP dimension, filter severity hint, project investigation columns.

**Self-check:** Subset of ~409 total IOC rows; all have non-empty `ThreatCategory`.


---

### C2 — OT anomaly + threat intel *(after Lab 2)*

**Scenario:** **`10.20.9.3`** is flagged **`OTAnomaly`** in threat intel. List **`SensorAnomaly`** events from **`IoT-Hub`** with that source IP enriched.

**Task:** Filter Silver for IoT sensor anomalies and IP; join to `ThreatIntelRef`; require match.

**Self-check:** Rows at **`Substation-D`** with `ThreatCategory == "OTAnomaly"`.


---

### C3 — Auth failure hourly chart data *(after Lab 3)*

**Scenario:** Prepare data for a **timechart**: hourly **`AuthFailure`** count **by facility** (top 3 facilities only).

**Task:** Filter auth failures, summarize by `bin(Timestamp, 1h)` and `Facility`, keep top facilities by total volume, order for charting.

**Self-check:** Multiple rows; optional `| render timechart` in UI.


---

### C4 — Firewall deny anomaly pass *(after Lab 4)*

**Scenario:** Run **`series_decompose_anomalies`** on hourly **`FirewallDeny`** counts and list any flagged hours.

**Task:** `make-series` → decompose → `mv-expand` → `where anomalies == 1`.

**Self-check:** **0 or 1** rows acceptable on lab data; query must run without error.


---

### C5 — Success-then-failure credential pattern *(after Lab 5)*

**Scenario:** Hunt **session abuse**: **`AuthSuccess`** immediately followed by **`AuthFailure`** at the **same facility** (same pattern as Lab 5 Q3).

**Task:** `order by Facility, Timestamp`, `serialize`, `prev()`, filter pattern, project evidence columns.

**Self-check:** **~182** rows typical.


---

### C6 — Gold vs Silver hour reconciliation *(after Lab 7)*

**Scenario:** Auditor picks **`Corporate-VPN`** + **`AuthFailure`** and compares **one hour bucket** between Gold and Silver.

**Task:** From `SecLogsHourly`, read `EventCount` for one `HourBucket`; from `SecLogsParsed`, count rows in same hour/facility/type; values should match.

**Self-check:** Counts equal for the chosen bucket.


---

### C7 — Inner join IOC hit list only

**Scenario:** SOC manager wants **only** events with a confirmed IOC match — no null categories (production **`inner`** join pattern).

**Task:** `join kind=inner` on `SourceIP` to IP dimension; no `isnotempty` filter needed.

**Self-check:** Row count ≤ **409**; every row has `ThreatCategory`.


---

### C8 — OT High/Critical with rank and facility *(after Lab 6)*

**Scenario:** Combine **`IsOTFacility`**, **`SeverityRank >= 3`**, and summarize **`HighSeverityCount`**-style metric on Silver (preview of Gold logic).

**Task:** Filter OT facilities, rank severity, summarize count by `Facility` where rank ≥ 3.

**Self-check:** Substations and SCADA only; Critical/High events only.


---

### C9 — Streaming vs batch auth failures

**Scenario:** Compare **`AuthFailure`** counts: **batch** (`Batch-JSON` + `Batch-CSV`) vs **streaming** (`EventHub` + `IoT-Hub`).

**Task:** Single query with `case()` or conditional summarize producing two buckets.

**Self-check:** Batch **500** (300+200), streaming **200** (200+0 IoT), total **700**.


---

### C10 — End-to-end mini investigation *(capstone)*

**Scenario:** **Executive brief:** (1) Total Silver events, (2) IOC-enriched event count (SourceIP join), (3) top facility from Gold, (4) count of OT **`SensorAnomaly`** events. Deliver as **one query** using **`print`** or nested subqueries / `let` statements.

**Task:** Write a single KQL script with **four labeled outputs** (four queries in one file is OK if `print` is awkward).

**Self-check:**


| Metric | Expected |
|--------|----------|
| Total Silver | **3500** |
| IOC enriched (SourceIP) | **~409** |
| Gold total events | **3500** |
| IoT SensorAnomaly | **200** |

---

## Assignment map vs Day 4 labs

| Lab | Unlocks assignments |
|-----|---------------------|
| Lab 1 | E1–E7, E9–E10 |
| Lab 2 | E8, M1–M2, M10, C1–C2, C7, C10 (partial) |
| Lab 3 | M4, C3 |
| Lab 4 | C4 |
| Lab 5 | M5–M6, C5 |
| Lab 6 | M7–M8, C8 |
| Lab 7 | M9, C6, C10 (Gold part) |