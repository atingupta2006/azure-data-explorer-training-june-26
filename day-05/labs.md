# Day 05 — Labs

**Theme:** Performance, Security, Operations & Capstone

**Database:** Same as Day 1 — **your workspace database** on the shared cluster `adx-training-tcs` (example: **`LogsDB_u01`** — substitute your assigned suffix). Training sign-in has **cluster admin**; still select **your** database in the Query tab so pipeline checkpoints stay isolated.

**Prerequisite:** Full pipeline from Days 2–4 **in your workspace database**: `SecLogsRaw`, `SecLogsParsed` (**3500**), `ThreatIntelRef` (**8**), `SecLogsHourly` (Gold MV; `sum(EventCount)` = **3500**). If not, complete [Day 4](../day-04/labs.md) first.

**Theory:** [README.md](README.md) — use the [document map](README.md#document-map) to jump to the section for each lab.

---

## Day 5 at a glance {#day-05-labs-at-a-glance}

**Where you work:** [dataexplorer.azure.com](https://dataexplorer.azure.com) Query tab only — optimize and operate the **existing** Days 2–4 pipeline; no new batch ingest today.

```text
  YOUR DAY (this file, top to bottom)

  Gate (00-verify) ──► Ready = true
           │
           ├── Labs 1–3   Query optimization + hint.strategy
           ├── Lab 4      MV vs on-demand parity (3500 = 3500)
           ├── Lab 5      RBAC + RlsDemoEvents (10) — demo RLS only
           ├── Lab 6      Monitoring `.show` — health before capstone
           └── Lab 7      scada-gw AuthFailure → threat intel → Gold

  END STATE: pipeline unchanged + RlsDemoEvents (10) · Silver still 3500 · ready for Day 6 gate
```

---

## Expected outcomes

```text
  AFTER ALL LABS — objects in YOUR workspace database

  SecLogsParsed (3500) + ThreatIntelRef (8) + SecLogsHourly (3500)
         + RlsDemoEvents (10) + UDFs from Day 4
```

| After step | Check |
|------------|--------|
| Gate | Q4 `Ready` = **true**; Silver **3500**, ThreatIntel **8**, Gold sum **3500** |
| Lab 1 Q1 | AuthFailure totals sum to **700** across facilities |
| Lab 1 Q2 | Enriched summarize by `ThreatCategory` (**~409** matches total) |
| Lab 2 Q4 | `SecLogsParsed` **TotalRowCount** = **3500** |
| Lab 2 Q5 | Gold `sum(EventCount)` = **3500** |
| Lab 3 | `hint.strategy=shuffle` join runs without error |
| Lab 4 Q3 | `TotalsMatch` = **true** (**3500** = **3500**) |
| Lab 4 verify Q4 | `Match` = **true** |
| Lab 5 Q6 | **10** rows before RLS (mixed facilities) |
| Lab 5 Q7 | **4** or **3** rows with RLS (your `AllowedFacility`) |
| Lab 5 Q8 / verify | **10** rows; RLS disabled |
| Lab 6 | `SecLogsHourly` `IsHealthy` = **true**; Block 7 runs without permission error |
| Lab 7 Step 2 | ≥ **1** AuthFailure on `scada-gw.utility.local` |
| Lab 7 Step 3 | ≥ **1** row with `ThreatCategory` (**10.20.1.44** / **BruteForceTarget**) |
| Lab 7 Step 4 | ≥ **1** Gold hourly row for Substation-A AuthFailure |
| Lab 7 verify Q5 | `CapstoneReady` = **true** |

```text
  CAPSTONE DATA PATH (Lab 7)

  SecLogsRaw (Bronze)     scada-gw rows across JSON / CSV / EventHub
         │
         v
  SecLogsParsed (Silver)  AuthFailure on DestinationHost = scada-gw.utility.local
         │
         ├── join ThreatIntelRef ──► 10.20.1.44 → BruteForceTarget
         │
         v
  SecLogsHourly (Gold)    Substation-A AuthFailure hourly buckets
```

---

## Where you work today

Same as Day 4 — **ADX Query tab only**. No Portal, no new ingest connections.

| Task | Site |
|------|------|
| All 7 labs + gate | [dataexplorer.azure.com](https://dataexplorer.azure.com) → select **your** database (example **`LogsDB_u01`**) |
| Run KQL | Open files in `queries/` → **Shift+Enter** one block at a time |

```text
  Day 4                          Day 5
  Query tab only                 Query tab only
  build ThreatIntel + Gold MV    optimize, secure, monitor, capstone
  analyze Silver (3500)          same pipeline — production patterns
```

---

## Objects for today (read before Lab 1)

Day 5 uses **everything you built on Days 2–4**. You add **`RlsDemoEvents`** (**10** rows) in Lab 5 for security discussion only.

| Object | Role | Count / state | Built on |
|--------|------|---------------|----------|
| `SecLogsRaw` | Bronze | **3500** rows | Days 2–3 |
| `SecLogsParsed` | Silver fact | **3500** rows | Day 3 |
| `ThreatIntelRef` | Dimension / IOC | **8** rows | Day 4 Lab 2 |
| `SecLogsHourly` | Gold MV | `sum(EventCount)` = **3500** | Day 4 Lab 7 |
| `SeverityRank`, `IsOTFacility` | UDFs | 2 functions in **Training** | Day 4 Lab 6 |
| `RlsDemoEvents` | Security demo | **10** rows (Lab 5) | Day 5 Lab 5 |

```text
  WEEK PIPELINE (unchanged counts — Day 5 adds RlsDemoEvents only)

  SecLogsRaw (3500) ──update policy──► SecLogsParsed (3500)
                                              │
                         ┌────────────────────┼────────────────────┐
                         │ join               │ MV                 │
                         v                    v                    │
                  ThreatIntelRef (8)    SecLogsHourly (3500)       │
                         │                    │                    │
                         └──── Lab 3/7 capstone enrich ─────────────┘

  Lab 5 adds: RlsDemoEvents (10) — do NOT apply RLS to SecLogsParsed
```

**Capstone anchor (Lab 7):** batch JSON includes **`AuthFailure`** rows on **`scada-gw.utility.local`** from SourceIP **`10.20.1.44`** → joins to **`BruteForceTarget`** in `ThreatIntelRef`. See [data/README.md](../data/README.md#day-5-capstone-scada-gateway).

---

## Pipeline gate (before Lab 1) {#pipeline-gate-before-lab-1}

Run **[queries/00-verify-pipeline-baseline.kql](queries/00-verify-pipeline-baseline.kql)** before Lab 1. **Stop** if Q4 `Ready` = **false**.

```text
  GATE CHECK                         IF FAIL
  SecLogsParsed = 3500               → Day 3 Labs 4–5 (update policy)
  ThreatIntelRef = 8                 → Day 4 Lab 2 Q0–Q2
  sum(SecLogsHourly.EventCount)=3500 → Day 4 Lab 7 (+ wait 30–60 s)
  SecLogsHourly IsHealthy = true     → recreate MV (Day 4 Lab 7 Q1)
```

| Query | Expected |
|-------|----------|
| Q1 Silver count | **3500** |
| Q2 ThreatIntelRef | **8** |
| Q3 Gold sum | **3500** |
| Q4 `Ready` | **true** |
| Q5 MV health | `IsHealthy` = **true** |

**Lab 1 is not a substitute for the gate** — the gate checks ThreatIntelRef and Gold MV, not just Silver.

---

## Lab run order {#lab-run-order}

| Step | File | Theory |
|------|------|--------|
| **Gate** | [00-verify-pipeline-baseline.kql](queries/00-verify-pipeline-baseline.kql) | [README prerequisite](README.md#day-5-at-a-glance) |
| Lab 1 | [01-query-optimization.kql](queries/01-query-optimization.kql) | [§1 Query optimization](README.md#1-query-optimization) |
| Lab 2 | [02-ingestion-tuning.kql](queries/02-ingestion-tuning.kql) | [§2 Ingestion tuning](README.md#2-ingestion-and-shard-tuning) |
| Lab 3 | [03-hint-strategy.kql](queries/03-hint-strategy.kql) | [§3 hint.strategy](README.md#3-hintstrategy) |
| Lab 4 | [04-mv-vs-ondemand.kql](queries/04-mv-vs-ondemand.kql) + [04-verify-mv-parity.kql](queries/04-verify-mv-parity.kql) | [§4 MV vs on-demand](README.md#4-materialized-views-vs-on-demand-queries) |
| Lab 5 | [05-security-rbac-rls.kql](queries/05-security-rbac-rls.kql) + [05-verify-rlsdemo.kql](queries/05-verify-rlsdemo.kql) | [§6 RBAC / RLS](README.md#6-authentication-rbac-and-row-level-security) |
| Lab 6 | [06-monitoring-diagnostics.kql](queries/06-monitoring-diagnostics.kql) | [§8 Monitoring](README.md#8-monitoring-and-disaster-recovery) · capacity [§5](README.md#5-capacity-planning-and-scaling) |
| Lab 7 | [07-capstone-investigation.kql](queries/07-capstone-investigation.kql) + [07-verify-capstone.kql](queries/07-verify-capstone.kql) | [§9 Capstone](README.md#9-capstone-scenario--utility-cyber-investigation) |

> **After Lab 5:** Read [README §7](README.md#7-network-cross-tenant-and-auditing) for network cross-tenant and auditing (class discussion — no lab file).

> **Enterprise batch orchestration (hands-on runbook):** [azure-data-factory-to-adx-guide.md](azure-data-factory-to-adx-guide.md) — full Portal lab: create ADF, RBAC, linked services, datasets, 10-activity pipeline (Copy → `.ingest` → wait → verify), schedule trigger, and troubleshooting. Plan **2–3 hours**. Self-contained — no other day files required.

---

## Working in the Query tab

1. Select **your** database in the dropdown (example **`LogsDB_u01`**).
2. Open the `.kql` file for the lab in `queries/`.
3. Run **one block at a time** with **Shift+Enter**.
4. Compare your results to the **Example result** table for that lab.

**Shift+Enter rule:** In Lab 5, run **Q3a/Q3b**, **Q3c/Q3d**, and **Q4a/Q4b** as **separate** blocks.

**Re-run safety:** Lab 5 Q0 drops `RlsDemoEvents` only — never apply RLS to `SecLogsParsed`.

---

## Troubleshooting

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| Gate Q4 `Ready` = false | Missing Day 4 objects | Run [Day 4 labs](../day-04/labs.md) Labs 2 and 7 |
| Gate Q3 Gold sum ≠ **3500** | MV backfill incomplete | Wait 45–60 s; re-run Q3; see [Debug TotalsMatch](#debug-totalsmatch-gold-mv) |
| Join or MV query times out | Missing time filter | Use patterns from Lab 1 and Lab 3 query files |
| Lab 5 “table already exists” | Re-run without Q0 | Run full `05-security-rbac-rls.kql` from **Q0** |
| Lab 5 Q3b fails after skipping Q3a | Blocks combined or wrong order | Run Q3a alone, then Q3b alone |
| Capstone Step 3 empty | `ThreatIntelRef` missing | Day 4 Lab 2 Q0–Q2 |
| Capstone Step 2 empty | Silver incomplete | Re-run pipeline gate |
| `TotalsMatch` = false | MV stale or Silver ≠ Gold | [Debug TotalsMatch](#debug-totalsmatch-gold-mv) |
| `.show cluster` permission note | Shared training cluster | Read-only output is OK — discuss in Lab 6 |

### Debug TotalsMatch and Gold MV {#debug-totalsmatch-gold-mv}

**First check — did Day 4 MV finish backfill?**

```kql
.show materialized-views
| where Name == "SecLogsHourly"
SecLogsHourly | summarize TotalEvents = sum(EventCount)
```

| What you see | Fix |
|--------------|-----|
| Q3 `TotalsMatch` = false | Confirm Silver = **3500**; run [04-verify-mv-parity.kql](queries/04-verify-mv-parity.kql) |
| Gold sum &lt; **3500** | Wait 45–60 s after Day 4 Lab 7 Q1; re-run |
| MV `IsHealthy` = false | In **your** DB: `.drop materialized-view SecLogsHourly ifexists` → re-run Day 4 Lab 7 Q1 |

### Debug capstone (Lab 7)

| Step empty | Check |
|------------|--------|
| Step 2 | Re-run Step 2 in capstone file — AuthFailures on `scada-gw.utility.local`; count ≥ **1** |
| Step 3 | `ThreatIntelRef` = **8** rows; Step 2 includes SourceIP **10.20.1.44** |
| Step 4 | Gold hourly rows for Substation-A AuthFailure — see Step 4 in capstone file |

Run [07-verify-capstone.kql](queries/07-verify-capstone.kql) after Steps 1–5 — Q5 `CapstoneReady` = **true**.

---

# Lab 1 — Query optimization and joins

## Objective

Apply **time filters**, **column projection**, and **bounded joins** on `SecLogsParsed` — production patterns at lab scale.

Theory: [README §1](README.md#1-query-optimization).

```text
  Lab 1 pattern

  where Timestamp first  →  filter EventType  →  project keys  →  join / summarize
```

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Open **`queries/01-query-optimization.kql`**.
3. Run **Q1–Q3** in order.

## Example result

| Query | Result |
|-------|--------|
| Q1 | AuthFailure counts by `Facility` (700 total) |
| Q2 | Enriched rows by `ThreatCategory` (**~409** IOC matches) |
| Q3 | Pattern print statement (bounded vs unbounded) |

## Success criteria

* Q1 completes; AuthFailure counts sum to **700**.
* Q2 returns threat categories; total enriched matches **~409** (same class as Day 4 join).

---

# Lab 2 — Ingestion tuning and diagnostics

## Objective

Inspect **ingestion failures**, mappings, and **extent** distribution for capacity awareness.

Theory: [README §2](README.md#2-ingestion-and-shard-tuning) · Capacity context: [§5](README.md#5-capacity-planning-and-scaling) (extent metrics you inspect here feed production sizing decisions).

```text
  Lab 2 — read metadata, do not re-ingest (5 blocks)

  Block 1  .show ingestion failures
  Block 2  .show table SecLogsRaw ingestion mappings
  Block 3  .show table SecLogsRaw details
  Block 4  Q4 — .show tables details (pipeline row counts)
  Block 5  Q5 — Gold sum(EventCount) cross-check
```

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Open **`queries/02-ingestion-tuning.kql`**.
3. Run **blocks 1–5 in order** — each `.show` or query block is a separate Shift+Enter (see diagram above).
4. Confirm Q4 `SecLogsParsed` **TotalRowCount = 3500** and Q5 Gold sum = **3500**.

## Example result

| Command | Acceptable result |
|---------|-------------------|
| `.show ingestion failures` | Empty or historical failures |
| Q4 extent summary | `SecLogsRaw`, `SecLogsParsed`, `SecLogsHourly` listed |
| Q4 Silver rows | **3500** |
| Q5 Gold sum | **3500** |

## Success criteria

* Commands run; Silver **3500** and Gold sum **3500** confirmed.

---

# Lab 3 — hint.strategy

## Objective

Use **`hint.strategy=shuffle`** on a fact-to-dimension join — production join optimization.

Theory: [README §3](README.md#3-hintstrategy).

```text
  join hint.strategy=shuffle kind=inner ( ThreatIntelRef ... ) on SourceIP
```

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Open **`queries/03-hint-strategy.kql`**.
3. Run **Q1** and **Q2**, then **Q3** (broadcast vs shuffle awareness).

> **`shuffle`** helps large fact joins on distributed clusters — at lab scale the hint is **syntax practice** for production.

## Example result

| Check | Result |
|-------|--------|
| Q1 | Enriched events with `ThreatCategory` |
| Q2 | Match counts for High/Critical |
| Q3 | Prints broadcast vs shuffle note |
| Errors | None |

## Success criteria

* Q1 returns rows; no join syntax errors.

---

# Lab 4 — Materialized view vs on-demand

## Objective

Compare live Silver **`summarize`** with Gold **`SecLogsHourly`** — verify **`TotalsMatch = true`** (**3500** = **3500**).

Theory: [README §4](README.md#4-materialized-views-vs-on-demand-queries).

```text
  Lab 4 Q1 on-demand Silver     Lab 4 Q2 read Gold MV     Lab 4 Q3 parity print
```

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Open **`queries/04-mv-vs-ondemand.kql`**.
3. Run **Q1–Q3** in order.
4. Open **`queries/04-verify-mv-parity.kql`** and run **Q1–Q4** — Q4 `Match` = **true**.

## Example result

| Check | Value |
|-------|-------|
| Q3 `TotalsMatch` | **`true`** |
| Both totals | **3500** |
| Verify Q4 `Match` | **`true`** |

## Success criteria

* `TotalsMatch` = **true**; verify file Q4 `Match` = **true**.

---

# Lab 5 — Security: RBAC and RLS demo

## Objective

Review **database principals**, implement **RLS** on **`RlsDemoEvents`**, and observe row filtering before disabling the policy.

Theory: [README §6](README.md#6-authentication-rbac-and-row-level-security) · Network/compliance framing: [§7](README.md#7-network-cross-tenant-and-auditing) *(VPN, ER, NERC CIP awareness — discussion after this lab)*.

```text
  Security layers (Lab 5)

  Entra ID sign-in  →  RBAC (cluster / database)  →  per-user RLS on demo table
        │                    │                              │
   who you are          .show principals            RlsUserScope + Q4a/Q4b
   UserPrincipalName    cluster admin in course      Q7: 10 → 4 or 3 (your facility)
```

```text
  Two identities in the course (README §6.1)

  YOU (analyst)     Entra ID sign-in  →  Query tab KQL
  ADX CLUSTER       MI (Managed Identity)  →  Blob / Event Hub ingest (Days 2–3)
                    └── no password in .ingest URI — ;managed_identity=system
```

```text
  Q0 drop  →  Q1 principals  →  Q2 RLS on SecLogsParsed (read-only)
           →  Q3a create events  →  Q3b seed (4+3+3)
           →  Q3c scope table  →  Q3d register YOUR UserPrincipalName
           →  Q6 before RLS (10 rows + your scope row)
           →  Q4a function  →  Q4b enable
           →  Q7 with RLS (4 or 3 rows)  →  Q5 policy  →  Q4c disable  →  Q8 (10 rows)

  NEVER apply RLS to SecLogsParsed
```

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Open **`queries/05-security-rbac-rls.kql`**.
3. Run **Q0–Q8** in order — separate blocks: **Q3a/Q3b**, **Q3c/Q3d**, **Q4a/Q4b**.
4. **Q3d** — registers **your** `UserPrincipalName` from `current_principal_details()` (default facility **Substation-A**). Edit the facility string and re-run **Q3d** only to try **Substation-B** or **SCADA-Gateway**.
5. **Q6** — confirm **10** event rows and **1** scope row for your login.
6. **Q4a–Q4b** — per-user RLS function + enable on **`RlsDemoEvents` only**.
7. **Q7** — count drops to **4** or **3** (matches your `AllowedFacility`). **Q5** shows `IsEnabled = true`.
8. **Q4c** — disable RLS (required). **Q8** — confirm **10** rows return.
9. Open **`queries/05-verify-rlsdemo.kql`** — Q1 = **10**, Q2 facility mix, Q3 `IsEnabled = false`.

> **Do not** enable RLS on `SecLogsParsed` — it breaks Days 2–4 labs for your database.

### Student FAQ — RLS and `RlsDemoEvents`

| Question | Answer |
|----------|--------|
| Why only **10** rows in `RlsDemoEvents`? | **Demo table** for security hands-on — **4** Substation-A + **3** Substation-B + **3** SCADA-Gateway from Silver via `.set-or-replace`. |
| Why does count drop to **4** or **3** after Q4b? | RLS uses **your** `UserPrincipalName` from **`RlsUserScope`** — you only see rows for **your** `AllowedFacility`. Default **Substation-A** = **4** rows. |
| How is my login captured? | **Q3d** calls `current_principal_details()["UserPrincipalName"]` — the same Entra ID you used to sign in to the Query tab. |
| Why run **Q4c disable**? | Restores all **10** rows for verify, assignments, and later days. Always disable before leaving Lab 5. |
| Why not apply RLS to `SecLogsParsed`? | RLS would **hide rows** from your Week 2–4 labs and break checkpoint counts. Use **`RlsDemoEvents` only**. |
| What does **seed** mean here? | Same as Day 4 ThreatIntel — load starter rows into a new table (Q3b). |
| When is RLS used in production? | Shared prod databases — e.g. substation analyst sees only their **Facility** (README §6.3). |
| I have cluster admin — why use one database? | **Convention for labs** — pipeline objects and locked counts live in **your** workspace database (example **`LogsDB_u01`**). Cluster admin lets you run management commands; it does not require querying every database. |
| What is **MI** in the README diagram? | **Managed Identity** — the ADX cluster’s own Azure AD identity used for Blob/Event Hub ingest (Days 2–3). You sign in with **Entra ID**; the cluster uses **MI** for `.ingest` — see [README §6.1](README.md#61-authentication--human-analysts-vs-cluster-services). |
| What is **OT-adjacent**? | **Operational Technology–adjacent** — substation, SCADA, or field IoT logs near the OT zone. See [GLOSSARY.md](../GLOSSARY.md). |
| What is **SOC**? | **Security Operations Center** — the central team that monitors alerts, runs KQL investigations, and handles incidents (e.g. Day 5 capstone ticket). See [GLOSSARY.md](../GLOSSARY.md). |

## Example result

| Check | Value |
|-------|-------|
| Q1 principals `.show` | No permission error |
| Q6 before RLS | **10** rows; **1** `RlsUserScope` row for your UPN |
| Q7 with RLS | **4** or **3** rows (your `AllowedFacility`) |
| Q5 policy | `IsEnabled = true` |
| Q8 after Q4c disable | **10** rows |
| Verify Q1–Q3 | **10** rows; facility mix; RLS **disabled** |

## Success criteria

* Matches table above.

---

# Lab 6 — Monitoring and operations

## Objective

Use **`.show`** management commands to inspect cluster health, ingest status, table size, **materialized view (MV)** health, and recent query activity — the operator checklist before the Lab 7 capstone.

Theory: [README §8](README.md#8-monitoring-and-disaster-recovery) · Pre-capstone checklist: [§8.4](README.md#84-lab-6-connection--block-by-block-checklist)

**Roles:** **Security Operations Center (SOC) analysts** hunt in KQL; **Network Operations Center (NOC) / platform operators** run these `.show` commands when row counts, dashboards, or ingest look wrong. Lab 6 teaches the operator side.

### Pre-flight checklist (before Lab 7)

| Check | Expected before Lab 7 |
|-------|------------------------|
| `.show ingestion failures` | No new blocking errors |
| `SecLogsParsed` row count | **3500** |
| `SecLogsHourly` `IsHealthy` | **true** |
| `.show commands` | Runs without permission error |

### Block guide (matches README §8.1)

| Block | What it answers | Healthy lab signal |
|-------|-----------------|-------------------|
| 1–2 | Which cluster / database am I on? | `adx-training-tcs`, your database (example **`LogsDB_u01`**) |
| 3 | Did ingest fail? | Empty failures table |
| 4 | Did ingest run recently? | Ops listed or quiet cluster |
| 5 | Are table sizes sane? | Four pipeline tables; **3500** Silver |
| 6 | Is Gold **materialized view (MV)** healthy? | `SecLogsHourly` **`IsHealthy = true`** |
| 7 | Any expensive queries? | Command runs; duration reasonable if rows exist |

```text
  Monitoring loop (Lab 6 — symptom → command → action)

  "Dashboard shows zero since 09:00"  →  Block 3 failures, Block 5 counts
  "Gold key performance indicator (KPI) flat"  →  Block 6 materialized-views
  "Azure Data Explorer slow this morning"      →  Block 7 commands → add time filter (Lab 1)
  "Storage / extent count worry"               →  Block 5 details → retention (README §8.2)
```

```text
  Lab 6 — seven blocks (run each separately)

  1 .show cluster          4 .show operations (ingestion)
  2 .show database         5 .show tables details  (+ optional count queries)
  3 .show ingestion failures  6 .show materialized-views
  7 .show commands (recent queries)
```

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Read [README §8.0–§8.1](README.md#80-two-roles--analyst-vs-operator) — analyst vs operator framing.
3. Open **`queries/06-monitoring-diagnostics.kql`**.
4. Run **blocks 1–7 in order** — Shift+Enter each block alone.
5. After Block 5, optionally run the verify counts from [README §8.4](README.md#84-lab-6-connection--block-by-block-checklist).
6. Confirm **`SecLogsHourly`** shows **`IsHealthy = true`** before starting Lab 7.

## Example result

| Block / check | Result |
|---------------|--------|
| 3 ingestion failures | Empty or historical only |
| 5 table details | `SecLogsRaw`, `SecLogsParsed`, `SecLogsHourly`, `ThreatIntelRef` listed |
| 5 Silver count (optional) | **3500** |
| 6 `SecLogsHourly` | `IsHealthy` = **true**, `LastRunResult` = Success |
| 7 query commands | Runs without error (may be empty on quiet cluster) |

## Success criteria

* Block 6 shows healthy Gold **materialized view (MV)**; Block 5 lists pipeline tables.
* You can name **one** command for each symptom: missing rows → failures; stale Gold → materialized-views; slow queries → commands.

### Student FAQ — monitoring

| Question | Answer |
|----------|--------|
| What is **Network Operations Center (NOC)**? | Team that monitors **platform and network health** — similar operator role to Azure Data Explorer platform engineers running `.show` runbooks. |
| What is **Security Operations Center (SOC)**? | Central analyst team that hunts threats and investigates alerts — you act as a SOC analyst in Labs 1–5 and 7. |
| What is **materialized view (MV)**? | Pre-aggregated Gold table (e.g. `SecLogsHourly`) — Block 6 checks **`IsHealthy`**. |
| Why run Lab 6 before capstone? | Capstone Step 4 reads **`SecLogsHourly`** — Block 6 proves the materialized view (MV) is trustworthy. |
| Block 7 returns no rows? | Normal on a quiet shared cluster; success = command runs without permission error. |
| Failures table has old rows? | Historical failures from earlier class attempts may appear — look for **recent** `FailedOn` timestamps. |
| Where is **disaster recovery (DR)** explained? | [README §8.3](README.md#83-disaster-recovery--bronze-as-evidence-and-replay-source) — Bronze on **Azure Data Lake Storage (ADLS)** is the replay source. |

---

# Lab 7 — Capstone investigation

## Objective

End-to-end utility cyber investigation — **Bronze → Silver → threat intel → Gold → summary**.

Theory: [README §9](README.md#9-capstone-scenario--utility-cyber-investigation).

## Scenario

Analyst ticket: *"Multiple authentication failures reported against `scada-gw.utility.local`. Determine sources, threat context, and hourly impact."*

> **Threat intel match:** **`10.20.1.44`** → **`BruteForceTarget`** comes mainly from **Batch-JSON** auth failures on the gateway. Event Hub adds many other SourceIPs on the same host — Step 3 still passes when any row matches `ThreatIntelRef`.

### Capstone flow and `CapstoneReady` (verify Q5)

```text
  Step 1 Bronze lineage  →  Step 2 Silver filter  →  Step 3 TI join (shuffle)
       →  Step 4 Gold KPI  →  Step 5 executive summary
```

Run [07-verify-capstone.kql](queries/07-verify-capstone.kql) Q5 as **one block** after Steps 1–5:

| Check | Condition |
|-------|-----------|
| SCADA AuthFailures | ≥ **1** row on `scada-gw.utility.local` |
| Threat enrichment | ≥ **1** join row (e.g. **10.20.1.44** → **BruteForceTarget**) |
| Gold Substation-A | ≥ **1** AuthFailure hour bucket in `SecLogsHourly` |
| **`CapstoneReady`** | All three conditions **true** |

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Open **`queries/07-capstone-investigation.kql`**.
3. Run **Steps 1–5** in order.
4. Open **`queries/07-verify-capstone.kql`** — Q5 `CapstoneReady` = **true**.
5. Document findings for the debrief:
   * How many **AuthFailure** rows on the gateway?
   * Which **SourceIP** matches threat intel?
   * What does **Gold** show for Substation-A AuthFailure hours?

> **Debrief:** After Lab 7, your class may review investigation findings together.

## Example result

| Step | Minimum result |
|------|----------------|
| Step 1 | Rows for JSON and EventHub `RecordFormat` / `SourceFile` |
| Step 2 | ≥ **1** AuthFailure on `scada-gw.utility.local` |
| Step 3 | ≥ **1** row with **`ThreatCategory`** (**10.20.1.44** / **BruteForceTarget**) |
| Step 4 | ≥ **1** Gold hourly row for Substation-A AuthFailure |
| Step 5 | Multiple **SourceSystem** values (Batch-JSON, EventHub, etc.) |
| Verify Q5 | `CapstoneReady` = **true** |

## Success criteria

* Matches table above; you can narrate **Bronze → Silver → Gold** path.

---

## After the labs — scenario assignments

After finishing all labs, work through **[assignments.md](assignments.md)** — scenario-based KQL tasks with **Self-check** expected values. Answer keys are provided in class (not in this repository).

| Difficulty | Focus |
|------------|--------|
| Easy | Time filters, `project`, Gold read, parity, `.show`, RLS demo |
| Medium | `hint.strategy`, Gold drill-down, MV health, scada gateway |
| Complex | Bounded shuffle joins, Gold/Silver audit, executive `print`, capstone |

---

## Next — course close

You have completed the **5-day Azure ADX pipeline** (Days 1–5). Optional review: [Day 5 README §9.5](README.md#95-full-course-pipeline-days-15) full course diagram.

**Optional deep dives:** [cost-optimization-guide.md](cost-optimization-guide.md) (**90–120 min**) · [azure-data-factory-to-adx-guide.md](azure-data-factory-to-adx-guide.md) (**2–3 h**)

Continue to **[Day 06 — Multi-Cloud & Hybrid Architecture](../day-06/labs.md)** — run the [Day 6 pipeline gate](../day-06/labs.md#lab-run-order) to confirm Silver still **3500** before starting Module 11.
