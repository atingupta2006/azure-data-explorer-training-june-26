# Day 01 — ADX Fundamentals & KQL Essentials

## Learning objectives

* Navigate ADX Web UI, **create your database**, and select it in the dropdown (example: **`LogsDB_u01`**)
* Explain cluster → database → table → extents at a high level
* Write foundational KQL: filter, project, extend, summarize, bin, render

**Hands-on:** [labs.md](labs.md) · [queries/](queries/)

---

## Shared cluster — your own database

This course uses one **shared ADX cluster** (`adx-training-tcs`). **Each student creates a separate database** on that cluster in **Lab 1** — for example **`LogsDB_u01`**, **`LogsDB_smith`**. Use the suffix assigned in class. You need **cluster-level permission** to run `.create database`.

All pipeline tables (`SecLogsRaw`, `SecLogsParsed`, `SecLogsHourly`) live **in your database only**. You create the database, create tables, run ingest, and query independently — you do not share tables with other students.

Always verify the **database dropdown** in ADX Web UI shows **your database** before running queries or `.create` commands. Labs and query files use **`LogsDB_u01`** or **`LogsDB_YOUR_SUFFIX`** as examples; substitute **your** name everywhere.

### Why separate databases on one cluster?

| Question | Answer |
|----------|--------|
| **Is it feasible?** | Yes. ADX clusters routinely host **many databases** (hundreds or more). Each database is an isolated namespace for tables, functions, and policies. |
| **Operational benefit** | Students run `.create`, `.ingest`, and streaming labs **in parallel** without overwriting each other's tables. Each student can be limited to **their own database only**. |

**What “multi-tenant” means (simple):** One **cluster** is like one **building** with shared power and HVAC (compute). Each **database** is a **separate office** with its own key — your tables stay in your office; you cannot change someone else's. That layout is called **multi-tenant**: many tenants (students/teams), one shared platform (cluster).

**Shared resources:** Training files are staged in shared storage; hub connections are configured on the training cluster. Tables and policies you create in labs live in **your database** only.

---

# 1. What is Azure Data Explorer?

**Azure Data Explorer (ADX)** is a fully managed, high-performance **big data analytics platform** from Microsoft. It is built to **collect, store, and analyze large volumes of diverse data in near real time** — logs from applications and firewalls, telemetry from agents, IoT device events, clickstreams, and more — and turn those streams into **interactive insights** using **KQL (Kusto Query Language)**.

Microsoft describes ADX as an **end-to-end solution** for **ingestion, query, visualization, and management** of analytics data. You do not assemble a separate query engine, storage layer, and indexing pipeline yourself; ADX provides the cluster, the Kusto engine, automatic indexing, and the Web UI in one service.

In **energy and utility cyber security**, ADX fits scenarios where a SOC or security engineering team must **search and correlate** high-volume signals quickly: authentication failures on SCADA gateways, VPN sessions for field technicians, firewall denies at the DMZ, configuration changes at substations, and IoT anomalies that may warrant investigation alongside traditional log sources.

## 1.1 Core idea — analytics over append-only streams

ADX is optimized for data that **arrives continuously**, is **time-stamped**, and is **rarely updated row-by-row**. Security and operational logs are the canonical example: each event is appended; analysts filter, aggregate, and pivot over time ranges.

```text
  Typical ADX workload (conceptual)

  Producers                    ADX platform                    Consumers
  ---------                    ------------                    ---------
  Apps, firewalls, VPN,   -->  Ingest (batch or stream)  -->  Analysts (KQL in Web UI)
  IoT, agents, SIEM feeds      Store in tables (extents)       Dashboards (Power BI, Grafana)
                               Auto-index by time              Automation (SDK / REST)
                               Query with KQL                  Alerts (downstream systems)
```

ADX is **not** a general-purpose relational database for OLTP. It does not replace Azure SQL for transactional applications. It **excels** when the question is: *“What happened across millions of events in the last 24 hours?”* — not *“Update customer record #48291.”*

## 1.2 The three Vs — why ADX exists

Big-data platforms are often described by **velocity**, **variety**, and **volume**. ADX is designed for all three simultaneously:

| Dimension | Meaning | Utility cyber example |
|-----------|---------|------------------------|
| **Velocity** | High rate of incoming events | Thousands of auth and firewall events per minute during an incident |
| **Variety** | Mixed schemas and formats | JSON app logs, CSV exports from legacy appliances, IoT telemetry with extra device fields |
| **Volume** | Large total retained data | Months of centralized logs at GB/day → TB total for compliance |

Microsoft positions ADX for **high velocity, diverse, raw data** where you need **interactive analytics** — aggregation, correlation, and pattern detection — without first building a fully curated data warehouse star schema.

## 1.3 Structured model, flexible payloads

ADX uses a **relational organization**: **cluster → database → table → rows**, with **strongly typed columns** (`datetime`, `string`, `long`, `dynamic`, etc.). That said, semi-structured payloads are first-class: a `dynamic` column can hold JSON from a firewall or application, and KQL parses fields at query time or via **ingestion mappings** (Days 2–3).

Later modules build a **Bronze → Silver → Gold** pipeline (`SecLogsRaw` → `SecLogsParsed` → `SecLogsHourly`). Day 1 uses **`PracticeSecurityEvents`** only so you learn KQL first.

## 1.5 What makes ADX distinctive (platform capabilities)

The following capabilities matter for this course and for production design. You will touch several of them hands-on this week.

| Capability | What it means for you |
|------------|----------------------|
| **Fast ingest** | Batch (Blob/ADLS) and streaming (Event Hub, IoT Hub) |
| **KQL** | Pipe-oriented query language — primary skill in today's labs |
| **Automatic indexing** | ADX indexes data **by time** at ingest — no manual `CREATE INDEX`; see [§1.5a](#15a-automatic-indexing-by-time-what-that-means) |
| **Update policies** | Transform Bronze → Silver on ingest (covered when you build Silver) |
| **Materialized views** | Precomputed aggregates for dashboards (Gold layer) |
| **Integrations** | Power BI, Grafana, ODBC/JDBC; same KQL ecosystem powers Azure Monitor logs and Defender |

## 1.5a Automatic indexing by time — what that means

In a traditional SQL database you often **create indexes manually** (`CREATE INDEX …`) so lookups stay fast. **ADX does not work that way for log analytics.** When data is ingested, the engine **automatically organizes and indexes it around time** — you do not define index objects in Day 1 labs.

### What happens at ingest

```text
  Events arrive (batch or stream)
           |
           v
  ADX splits table data into EXTENTS (compressed shards)
           |
           +-- Each extent covers a TIME RANGE (among other metadata)
           |
           +-- Column indexes built for fast filters (strings, dynamic JSON, etc.)
           |
           v
  Query engine can SKIP extents outside your time window
```

Think of a **filing cabinet sorted by date**: if you ask for *"events from yesterday only"*, the engine opens the drawers for yesterday — not every drawer since last year.

### Two time columns to know

| Column / function | Meaning | Course example |
|-------------------|---------|----------------|
| **`Timestamp`** (your schema) | **Event time** — when the security event happened | `PracticeSecurityEvents`, later `SecLogsParsed` |
| **`ingestion_time()`** | **Arrival time** — when ADX received the row | Useful for pipeline debugging (Day 2+) |

For investigations, analysts almost always filter on **`Timestamp`** (event time). That matches how SOC questions are phrased: *"Auth failures in the last hour on the SCADA gateway."*

### What you do in KQL (Day 1 habit)

Always **bound queries with a time filter** on datetime columns:

```kql
PracticeSecurityEvents
| where Timestamp > datetime(2026-06-10T08:00:00Z)   // lab data; production: ago(1d) or ago(7d)
| where EventType == "AuthFailure"
| summarize count() by bin(Timestamp, 1h)
```

| Pattern | Purpose |
|---------|---------|
| `where Timestamp > ago(1d)` | Last 24 hours only (production SOC) |
| `where Timestamp between (datetime(2026-06-11) .. datetime(2026-06-13))` | Full lab pipeline window (Bronze/Silver sample data) |
| `where Timestamp between (datetime(2026-06-10) .. datetime(2026-06-12))` | Full lab incident window (**2000** practice rows) |
| `summarize … by bin(Timestamp, 1h)` | Hourly buckets for charts (Lab 5) |

**Without a time filter**, ADX may scan **more extents than necessary**. On lab tables with **2000** rows the query still feels instant. On production tables with **billions** of rows, an unbounded query can time out or run very slowly — Day 5 covers tuning; **Day 1 establishes the habit**.

### "Auto-index" vs manual indexes — summary

| Traditional DB | ADX (this course) |
|----------------|-------------------|
| You design and maintain indexes | Engine indexes **at ingest** |
| Index on chosen columns | **Time** is the primary partition for log tables; string/`dynamic` columns also indexed |
| Full table scan if index missing | **Extent pruning** when time range is narrow |

**Physical detail:** extents, columnar storage, and merge policy are in [§2.6](#26-extents-how-adx-stores-rows-on-disk). **Lab connection:** Lab 5 uses an explicit `datetime(2026-06-10)` window and `bin(Timestamp, …)` — you are exercising time-bounded queries that benefit from automatic time indexing.

---

ADX is not an isolated product. **KQL** and the Kusto engine appear across Microsoft’s observability and security stack:

```text
  Kusto / KQL ecosystem (simplified)

                    +------------------+
                    |  Azure Data      |
                    |  Explorer (ADX)  |  <-- this course (first-class cluster)
                    +--------+---------+
                             |
         +-------------------+-------------------+
         |                   |                   |
         v                   v                   v
  Azure Monitor        Microsoft           Application
  / Log Analytics      Defender            Insights
  (workspace KQL)      (advanced hunting)   (KQL queries)
```

If you already know Log Analytics queries, you already know much of **KQL syntax** — ADX adds full cluster control, custom ingestion pipelines, update policies, and materialized views on **your** data estate.

## 1.7 Official workflow — four steps

Microsoft documents a standard ADX workflow ([overview](https://learn.microsoft.com/en-us/azure/data-explorer/data-explorer-overview)):

```text
  1. CREATE          2. INGEST           3. QUERY            4. VISUALIZE
  -------            -------             ------              -----------

  Cluster +          Load data into      Run KQL in          Charts in Web UI,
  database(s)        tables (batch or    Web UI, SDK,        Power BI, Grafana,
                     streaming)          or REST API         or export results
        |                  |                  |                    |
        v                  v                  v                    v
  LogsDB_u01         (ingest later)      PracticeSecurity    timechart (Lab 5)
  (this course)                          Events (Day 1)
```

**Day 1** emphasizes step **3 (Query)** using a small practice table, plus steps **1 (Create)** via `.create table` and `.show` commands in Lab 1–2. Later modules add **Ingest** into Bronze and Silver, then Gold aggregates. Visualization starts with **`render timechart`** in the Web UI; connector-based dashboards are discussed as production follow-on.

Access is through the **[Azure Data Explorer Web UI](https://dataexplorer.azure.com)** or Azure Portal → cluster → **Open in Web UI**. Programmatic access uses [SDKs and REST](https://learn.microsoft.com/en-us/azure/data-explorer/); this course uses the Web UI only.

**Sign-in tip:** Use an **Incognito / InPrivate** browser window when connecting to the Web UI. Training accounts often conflict with a personal Microsoft account already signed in to the browser. If sign-in fails, the wrong tenant appears, or the cluster will not load, close the window and retry in a **new Incognito session**.

# 2. ADX architecture

ADX is designed for **scale-out log and telemetry analytics**. Understanding its hierarchy — **cluster → database → table → extent** — helps you choose the right scope for commands, policies, and permissions. Microsoft documents ADX as separating **compute** (query and ingest processing) from **durable storage** (Azure Blob), which is why the same platform can scale from **gigabyte lab tables** to **terabyte production estates**.

This section maps directly to **Labs 1–2**: you connect to a **cluster**, select a **database**, run `.show` commands to inspect context, then **create a table** with a typed schema.

## 2.1 Logical hierarchy — four levels

```text
  ADX logical model (what you see in the Web UI)

  +-- Cluster  adx-training-tcs
  |     |
  |     |  compute + engine; shared by all students in this course
  |     |
  |     +-- Database  LogsDB_u01  (Student 1 — own tables & policies)
  |     +-- Database  LogsDB_u02  (Student 2)
  |     +-- Database  LogsDB_u03  (Student 3 …)
  |           |
  |           |  namespace for tables, functions, policies (per student)
  |           |
  |           +-- Table  PracticeSecurityEvents  (Day 1)
  |           |     |
  |           |     +-- Rows  (2000 practice events in labs)
  |           |     |
  |           |     +-- Extents  (compressed shards — created when you ingest)
  |           |
  |           +-- Table  (pipeline tables — created in ingest modules, not Day 1)
  |
  +-- Azure Blob Storage  (durable persistence behind the cluster)
```

| Level | What it is | Course example |
|-------|------------|----------------|
| **Cluster** | Top-level Azure resource; runs the Kusto engine | `adx-training-tcs` |
| **Database** | Container for tables, functions, policies | Your database (e.g. `LogsDB_u01`) |
| **Table** | Typed columns holding rows | `PracticeSecurityEvents` |
| **Extent** | Immutable compressed shard of table data | Created automatically on ingest |

Microsoft notes a cluster can hold **many databases** (up to platform limits), and each database **many tables**. Your **database dropdown** in the Web UI selects which namespace your KQL commands affect.

## 2.3 Cluster — the Kusto engine boundary

An **ADX cluster** is the Azure resource provisioned for this course. It:

* Executes **KQL** and **management commands** (`.create table`, `.show cluster`, policies).
* Runs **ingestion pipelines** that pull from Event Hub, Blob, IoT Hub, etc.
* Hosts **multiple databases** on shared compute.

For this course:

* **Same cluster for everyone:** `adx-training-tcs` — one engine, one Web UI connection.
* **Different database per student:** Student **u01** → **`LogsDB_u01`**, student **smith** → **`LogsDB_smith`**, and so on. **You create your database in Lab 1** with `.create database LogsDB_<your-id>`. Names in lab files are **examples**; use **your** suffix everywhere.

The cluster URI looks like:

`https://adx-training-tcs.centralindia.kusto.windows.net`

**Lab 1 commands:** `.show cluster` returns cluster metadata; `.create database LogsDB_<your-id>` creates your workspace; `.show databases` lists all databases; `.show database` (with **your** database selected) shows policy metadata for **your** workspace.

## 2.4 Database — your workspace and policy boundary

A **database** is a logical container for:

* **Tables** and **materialized views**
* **Functions** (including UDFs — Day 4)
* **Policies**: retention, caching, update policies, merge, streaming ingestion, RLS (later days)

Permissions are granted **per database**. If you are student **u01**, you work in **`LogsDB_u01`** only — you cannot create or drop tables in **`LogsDB_u02`** (another student's workspace).

**Lab 1 command:** `.show databases` lists all databases on the cluster (including other students'); `.show database` (with **your** database selected) shows policy metadata for **your** workspace.

```text
  Scope discipline (avoid the #1 Day 1 mistake)

  WRONG:  Run .create table on cluster default / wrong DB  -->  table in unexpected place
  RIGHT:  Select YOUR database in dropdown, then .create table  -->  table in your workspace
```

## 2.5 Tables — schema, columns, append-only logs

A **table** defines **columns** and **data types**. Day 1 creates:

```kql
.create table PracticeSecurityEvents (
    Timestamp: datetime,
    EventType: string,
    SourceIP: string,
    ...
)
```

| Type | Typical use in security logs |
|------|------------------------------|
| `datetime` | Event time — always filter on this in production |
| `string` | IPs, hostnames, user names, messages |
| `long` / `int` | Counts, ports, status codes |
| `dynamic` | JSON payloads (Bronze `RawPayload` — Day 2+) |
| `bool` | Flags |

Security log tables are **append-only** in practice: new events arrive; analysts query and aggregate rather than updating individual rows. ADX supports data modification patterns (`.set-or-replace`, extent swap), but the **mental model** for SOC data is continuous append.

**Lab 2 commands:** `.create table` defines schema; `.show table PracticeSecurityEvents cslschema` confirms columns.

## 2.6 Extents — how ADX stores rows on disk

When you run `.set` or `.ingest`, you add **rows to a table**. Behind the scenes, ADX groups those rows into **extents** — compressed, immutable **chunks** of storage ([Extents overview](https://learn.microsoft.com/en-us/azure/data-explorer/kusto/management/extents-overview)). You **create tables and load data**; ADX **creates and manages extents for you**.

```text
  What YOU see (logical)              What ADX stores (physical)

  Table: PracticeSecurityEvents       One table, many extents over time

  Row 1   AuthFailure    08:01       +------------------+
  Row 2   FirewallDeny   08:02       | Extent 1         |  rows from ingest batch A
  Row 3   VPNLogin       08:03       | (compressed)     |  (e.g. Day 1 .set seed)
  ...                                 +------------------+
  Row 1999 AuthFailure   11:58       +------------------+
  Row 2000 FirewallDeny  11:59       | Extent 2         |  rows from a later ingest
                                      | (compressed)     |
                                      +------------------+
                                                |
                                                v
                                      Stored on cluster nodes (SSD + cache)
                                      Queries read only extents they need
```

**Analogy:** You write events into a **ledger** (the table). ADX automatically packs pages of that ledger into **bound volumes** (extents) for efficient storage and search. You never run a `.create extent` command — packing happens when data arrives.

Key properties (from Microsoft documentation):

| Property | Meaning |
|----------|---------|
| **Automatic** | Extents appear when you load data (`.set`, `.ingest`, streaming) — no manual step |
| **Immutable** | An extent is not edited in place; updates create new extents |
| **Columnar** | Data arranged by column inside each extent — good compression and analytics |
| **Indexed at ingest** | Time and common filter columns indexed for fast queries ([§1.5a](#15a-automatic-indexing-by-time-what-that-means)) |
| **Distributed** | Extents can sit on different nodes; queries run in parallel |

**When extents are created in this course:**

* Day 1 — `.set-or-replace` into `PracticeSecurityEvents`
* Day 2 — `.ingest into table` for Bronze batch files
* Day 3 — streaming from Event Hub / IoT Hub

**Why analysts care:** Queries scan **relevant extents** — especially those matching your `where Timestamp …` filter ([§1.5a](#15a-automatic-indexing-by-time-what-that-means)). Unbounded queries on huge tables read too many extents and slow down — **always bound `Timestamp`** in production (Day 1 habit; Day 5 tuning).

## 2.9 Ingestion path vs query path

ADX exposes different internal paths for **writes** and **reads**:

```text
  Two paths through the cluster

  INGESTION PATH                         QUERY PATH
  --------------                         ----------

  Blob / Event Hub / IoT                 Web UI / SDK / REST
         |                                      |
         v                                      v
  Data management pipeline               Engine nodes
  (batch, map, validate)                 (plan + execute KQL)
         |                                      |
         v                                      v
  New extents in table                   Read extents (+ cache)
         |                                      |
         +------------ same table --------------+
                    PracticeSecurityEvents  (Day 1)
                    (+ pipeline tables later in the week)
```

| Path | Endpoint role | Day 1 example |
|------|---------------|---------------|
| **Ingestion** | High-throughput writes, mappings, batching | `.set-or-replace` in Lab 3 |
| **Query** | Interactive KQL, `.show` commands | Labs 4–6 filters and charts |

**Latency:** Streaming events are often queryable in **seconds**. Large batch files may take **minutes** depending on size and cluster load. ADX is **not** synchronous OLTP — after ingest, wait briefly before verification counts.

## 2.10 End-to-end data flow (overview)

From later modules onward, batch and streaming sources land in **Bronze**, parse to **Silver**, and aggregate to **Gold** in **your database**. Day 1 stays on **`PracticeSecurityEvents`** only.

## 2.12 Map Day 1 labs to architecture objects

| Lab | Architecture object | Command / action |
|-----|---------------------|------------------|
| 1 | Cluster + **create database** | `.show cluster`, `.create database`, `.show database`, `.show tables` |
| 2 | Table + schema | `.create table`, `.show table … cslschema` |
| 3 | Rows in table (extents created automatically) | `.set-or-replace` |
| 4–6 | Query over table | KQL `where`, `summarize`, `render` |
| 7 | SOC scenario investigations | `let`, `join`, `extract`, `render barchart`, timelines |

# 3. Use cases

Microsoft documents ADX for **log analytics**, **time-series analytics**, **IoT**, and **general-purpose exploratory analytics** ([overview](https://learn.microsoft.com/en-us/azure/data-explorer/data-explorer-overview)). This course covers four use cases:

1. **Log analytics**
2. **Telemetry**
3. **IoT**
4. **Clickstream**

In **energy and utility cyber security**, these are **different signal types** that can land in the same ADX estate — firewall logs, agent heartbeats, substation sensors, and portal activity. Today's labs use **log analytics** on `PracticeSecurityEvents`.

```text
  Four use cases → one analytics platform (conceptual)

  Log analytics ----\
  Telemetry --------+---->  ADX (your database)  ---->  KQL
  IoT --------------|
  Clickstream ------/
```

## 3.1 How the four use cases differ

| Use case | What flows in | Primary question | In these labs |
|----------|---------------|------------------|---------------|
| **Log analytics** | Auth, firewall, VPN, app audit | *Who did what, from where, when?* | **`PracticeSecurityEvents`** — Labs 4–6 |
| **Telemetry** | Health, metrics, agent status | *Is the pipeline healthy?* | Concept only |
| **IoT** | Device/sensor readings | *What did the device report?* | Concept only |
| **Clickstream** | Sequenced user/system actions | *What path led to this action?* | Architecture discussion |

All four share ADX strengths: **time-ordered append**, **schema variety** (`string` + `dynamic` JSON), and **interactive KQL** over raw data without a pre-built star schema.

## 3.2 Log analytics — core of this course

**Log analytics** means searching **event records** that answer security questions: who signed in, what was blocked, what changed, and when.

**Simple example (one row):**

| Timestamp | EventType | SourceIP | UserPrincipal | Message |
|-----------|-----------|----------|---------------|---------|
| 2026-06-10 09:15 | AuthFailure | 10.20.5.12 | operator@utility.com | Failed login after 3 attempts |

An analyst might ask: *“How many `AuthFailure` events came from substation networks in the last hour?”* — that is **log analytics** in ADX: filter by `EventType`, `Timestamp`, and `Facility`, then **count** or **chart**.

ADX ingests thousands or millions of such rows (JSON, CSV, streams) and runs those questions quickly with **KQL**.

```text
  Log analytics in plain terms

  1. Events arrive     -->  2. Land in a table  -->  3. Analyst queries
     (firewall, VPN,          (PracticeSecurityEvents)     (filter, summarize,
      auth, apps)              Day 1 table)                  chart — Labs 4–6)
```

**What you analyze in this course:** authentication success/failure, firewall allow/deny, configuration changes, VPN sessions.

**Day 1 practice:** `PracticeSecurityEvents` uses event type names such as `AuthFailure`, `FirewallDeny`, and `VPNLogin` — the same vocabulary as later security logs in this course.

**Utility example:** Ten failed logins on `scada-gw.utility.local` in five minutes → investigate source IPs and correlate with firewall denies.

Sample files for later ingest are generated by the [Python data producer](../producer/README.md) and stored under [`data/`](../data/).

## 3.3 Other use cases (brief)

**Telemetry** tracks *health* (heartbeats, collector status), not *who logged in*. **IoT** covers field sensors and gateways. **Clickstream** covers sequenced portal or app actions. All can share the same ADX cluster.
