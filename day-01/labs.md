# Day 01 — Labs

**Theme:** ADX Fundamentals & KQL Essentials

**Database:** Each student creates and uses **their own database** on the shared cluster `adx-training-tcs`. Naming convention: **`LogsDB_<your-id>`** (example: `LogsDB_u01`). Use the suffix assigned in class.

**Permissions:** Your account has **cluster-level** access to run `.create database`. Work only in **your** database for all labs.

**Theory:** [README.md](README.md)

---

## Working in the Query tab

1. Open [Azure Data Explorer](https://dataexplorer.azure.com/) and sign in with your **training account**.
2. Select **your** `LogsDB_<id>` in the database dropdown.
3. Open the `.kql` file for the lab in `queries/`.
4. Run **one block at a time** with **Shift+Enter**.
5. Compare your results to the **Example result** table for that lab.

---

## Troubleshooting

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| `.show cluster` works but **`.show database`** or **`.show tables`** fails | Database **not selected** in the Web UI toolbar / left pane | Expand **`adx-training-tcs`** → click **your** `LogsDB_<id>` → confirm the toolbar shows the same name → run again |
| `Database … was not found` or `NetDefaultDB` | Connected to cluster only — no database context | Create your database (Lab 1 step 6) and **select it** in the dropdown |
| `.create database` fails — already exists | Name taken | Pick a different suffix |
| `Forbidden` / `not authorized` on `.create database` | Missing cluster permission | Report to class — cluster role required |
| `.show databases` does not list your database | Create step not run or wrong name in filter | Re-run **`00-create-your-database.kql`** and verify with `.show databases` |

---

## Expected outcomes

| After lab | Check |
|-----------|--------|
| Lab 1 | Your `LogsDB_<id>` appears in `.show databases` |
| Lab 3 | `PracticeSecurityEvents \| count` = **2000** |
| Lab 4 Q1 | AuthFailure = **400** |
| Lab 4 Q2 | High + Critical = **800** |
| Lab 5 Q1 | FirewallDeny = **500** |
| Lab 5 Q3/Q4 | Timechart renders |
| Lab 7 S1 | Brute-force IP list = **31** rows |
| Lab 7 S3 | Bar chart by Facility renders (**5** facilities) |
| Lab 7 S7 | Dual-signal hosts = **2** rows |
| Lab 7 S10 | Substation-A timeline = **48** ordered rows |

---

# Lab 1 — Connect to cluster and create your database

## Objective

Connect to ADX Web UI, explore the shared cluster, **create your personal database**, and confirm database context — the standard workflow (**create → ingest → query → visualize**).

## Tasks

1. Open [Azure Data Explorer Web UI](https://dataexplorer.azure.com/) and sign in with the **training account** (Entra ID — not personal Outlook).
   * **Tip:** Use your browser's **Inprivate / Incognito** window for sign-in. If you see the wrong account, a stale session, or cluster connection errors, close the window and try again in a fresh Incognito session.
2. If prompted, **Add connection** → paste cluster URI from class materials → confirm trust prompt.
3. Open the **Query** tab (default for this course).
4. Open **`queries/01-show-cluster-and-database.kql`** → run **`.show cluster`** and **`.show databases`** (one command at a time, **Shift+Enter**).
5. Open **`queries/00-create-your-database.kql`**.
6. Replace **`YOUR_SUFFIX`** with your assigned id (example: `u01`, `atin`, `smith`) in **every** place it appears.
7. Run **`.create database LogsDB_<your-id>`** → run the verification **`.show databases`** filter.
8. In the **left connection pane**, expand **`adx-training-tcs`** → select **`LogsDB_<your-id>`** — toolbar must show the same database.
9. Run **`.show database`** and **`.show tables`** from the same file (tables empty until Lab 2).

## Example result

| Command | You should see |
|---------|----------------|
| `.show cluster` | Cluster URI, status **Running**, engine version |
| `.show databases` | Your new **`LogsDB_<id>`** plus other student databases |
| `.create database` | Success — database created |
| `.show database` | Policy metadata for **your** selected database |
| `.show tables` | Empty list — no permission error |

## Success criteria

* Your database **`LogsDB_<id>`** exists and is selected in the Web UI.
* No permission-denied errors on `.create database`, `.show database`, or `.show tables`.

---

# Lab 2 — Create practice table

## Objective

Create table **`PracticeSecurityEvents`** in the **Query tab** — your first **table** object in the ADX hierarchy (cluster → database → **table** → rows/extents).

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Open **`queries/02-create-practice-table.kql`**.
3. Run `.create table PracticeSecurityEvents (...)`.
4. Run `.show table PracticeSecurityEvents cslschema`.

> If table already exists, skip or `.drop table PracticeSecurityEvents` in **your** DB only.

## Example result

Eight columns: `Timestamp`, `EventType`, `SourceIP`, `DestinationHost`, `UserPrincipal`, `Severity`, `Message`, `Facility`.

These types match how **Silver** security tables are modeled later (`datetime` + `string` dimensions). Bronze uses `dynamic` for raw JSON; Day 3 **update policy** parses into typed Silver columns.

## Success criteria

* `PracticeSecurityEvents` appears in `.show tables`.

---

# Lab 3 — Seed practice data

## Objective

Load **2000** synthetic utility cyber events using a **management command** (`.set-or-replace`), then verify with **`count`** and **`countif`**.

## Tasks

1. Open **`queries/03-seed-practice-data.kql`**.
2. Run the full **`.set-or-replace`** block once (2000 rows).
3. Run verification queries at file bottom.

## Example result

| Query | Value |
|-------|-------|
| `PracticeSecurityEvents \| count` | **2000** |
| `dcount(EventType)` | **8** |
| AuthFailure count | **400** |
| FirewallDeny count | **500** |

## Success criteria

* Matches table above.

---

# Lab 4 — Filters and projections

## Objective

Apply core KQL **filter** and **shape** operators: `where`, `extend`, `case`, `project`.

## Tasks

1. Database = **your database** (example: **`LogsDB_u01`**).
2. Open **`queries/04-filters-project-extend.kql`**.
3. Run **Q1** (AuthFailure) → **Q4** in order — one block at a time.

## Example result

| Query | Rows |
|-------|------|
| Q1 AuthFailure | **400** |
| Q2 High/Critical | **800** |
| Q3 | `SeverityRank` 1–4 visible |
| Q4 | Only projected columns |

## Success criteria

* Row counts match table above.

---

# Lab 5 — Aggregations and time charts

## Objective

Use **`summarize`**, **`bin(Timestamp, …)`**, and **`render timechart`** — the standard SOC pattern for volume-over-time analysis.

## Tasks

1. Open **`queries/05-summarize-timechart.kql`**.
2. Run Q1–Q4. For charts, click **Chart** in Results pane after Q3 or Q4.

## Example result

| Query | Result |
|-------|--------|
| Q1 | FirewallDeny count = **500** (highest) |
| Q3/Q4 | Line chart with time on X-axis |

## Success criteria

* Chart renders without query error.

---

# Lab 6 — Extract and management commands

## Objective

Parse fields with **`extract`**, rank with **`top`**, and inspect metadata with **`.show table`**.

## Tasks

1. Open **`queries/06-parse-and-management.kql`**.
2. Run Q1–Q5.

## Example result

| Query | Result |
|-------|--------|
| Q1 | `UserDomain` = `utility.com` |
| Q5 count | **2000** |

## Success criteria

* Schema matches Lab 2; count unchanged.

---

# Lab 7 — Scenario-based SOC investigations

## Objective

Apply Day 1 KQL to **realistic utility cyber scenarios** — brute-force patterns, after-hours activity, VPN balance, dual-signal hosts, and incident timelines. Budget **~2 hours** for this lab (10 scenarios × discussion).

## Tasks

1. Confirm **`PracticeSecurityEvents`** has **2000** rows (Lab 3).
2. Open **`queries/07-scenario-investigations.kql`**.
3. Run **Scenario 1** through **Scenario 10** — **one block at a time**.
4. After each scenario, note: *What would you tell the SOC lead?*
5. For **Scenario 3**, switch Results pane to **Chart** after the query runs.

## Scenarios covered

| # | Theme | Key operators |
|---|--------|---------------|
| 1 | Brute-force on SCADA gateway | `summarize`, `where`, `order` |
| 2 | After-hours activity | `where`, `extend`, `hourofday` |
| 3 | Facility risk ranking | `summarize`, `render barchart` |
| 4 | Privilege escalation + auth failures | `let`, `in`, correlation |
| 5 | VPN session imbalance | `countif`, `extend` |
| 6 | Firewall deny by subnet | `extract`, `top` |
| 7 | Dual-signal destination hosts | `countif`, multi-condition |
| 8 | Config change audit | `project`, timeline |
| 9 | Event-type × severity matrix | `summarize` pivot-style |
| 10 | Substation-A incident narrative | `between`, ordered timeline |

## Success criteria

* All 10 scenarios run without syntax errors.
* You can explain at least **three** findings in plain language (example: top facility, suspicious IP, after-hours event type).

---

## Day 1 time guide (8-hour session)

| Block | Duration | Content |
|-------|----------|---------|
| Theory | ~4 h | [README.md](README.md) — ADX model, KQL basics, use cases |
| Labs 1–3 | ~1 h | Connect, create DB, table, seed data |
| Labs 4–6 | ~1 h | Filters, summarize, charts, extract |
| Lab 7 | ~2 h | Scenario investigations (this file) |

