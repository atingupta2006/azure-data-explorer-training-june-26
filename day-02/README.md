# Day 02 — Batch Ingestion & Bronze Layer

## Learning objectives

* Ingest batch files from Blob into **`SecLogsRaw`** with mappings
* Create JSON and CSV ingestion mappings for Bronze
* Verify Bronze with locked counts (**2500** rows)
* Contrast batch Blob ingest vs continuous streaming

**Prerequisite:** Day 1 — Web UI navigation, **your database**, basic KQL on `PracticeSecurityEvents`.

**Hands-on:** [labs.md](labs.md) | **Queries:** [queries/](queries/) | **Sample files:** [data/README.md](../data/README.md) | **Regenerate data:** [producer/README.md](../producer/README.md)

---


# 1. Ingestion concepts and pipelines

**Ingestion** is how data enters ADX tables so it becomes **queryable with KQL**. Microsoft defines ingestion as loading data into a cluster table with validation, format conversion, schema matching, indexing, encoding, and compression — then data is available for query ([ingestion overview](https://learn.microsoft.com/en-us/azure/data-explorer/ingest-data-overview)).

Day 1 used **`.set-or-replace`** to seed 2000 rows into `PracticeSecurityEvents` — a **direct management command** suitable for teaching. Day 2 onward uses **production-style ingestion**: files in **Azure Blob/ADLS** and (Day 3) **continuous connections** from Event Hub and IoT Hub into **`SecLogsRaw` (Bronze)**.

## 1.1 Ingestion vs query — two paths through ADX

```text
  INGESTION PATH (writes)              QUERY PATH (reads — Day 1 skill)
  -----------------------              -----------------------------

  Blob / stream source                 Analyst in Web UI
         |                                    |
         v                                    v
  Data management service              Kusto engine
  (batch, map, validate)               (filter, summarize, chart)
         |                                    |
         v                                    v
  New EXTENTS in table  <--- same --->  Read EXTENTS + cache
         |
         v
  SecLogsRaw (Bronze)
```

| Path | You trigger | Result |
|------|-------------|--------|
| **Ingestion** | `.ingest`, data connection, `.set-or-replace` | New or replaced data in table |
| **Query** | `SecLogsRaw \| count` | Read-only result set |

Ingestion is **not instant OLTP** — after `.ingest`, wait briefly (seconds for lab files; minutes for large batches) before verification counts.

## 1.2 One-time vs continuous ingestion

Microsoft divides ingestion into two strategic modes ([ingestion overview](https://learn.microsoft.com/en-us/azure/data-explorer/ingest-data-overview)):

| Mode | When to use | Course example |
|------|-------------|----------------|
| **One-time** | Historical load, backfill, prototype | Day 2 `.ingest` of staged JSON/NDJSON files |
| **Continuous** | Live monitoring, SOC streaming | Day 3 Event Hub + IoT Hub connections |

```text
  ONE-TIME (Day 2)                    CONTINUOUS (Day 3)

  sec-app-logs.json  ──► .ingest       Event Hub ──► data connection ──► SecLogsRaw
  (1500 rows, once)         once              (500 events per lab stream)
```

Utility cyber examples:

* **One-time:** Re-ingest 90 days of archived firewall CSV from ADLS after a schema fix.
* **Continuous:** Live authentication failure stream for near-real-time correlation.

## 1.3 Queued vs streaming ingestion (engine behavior)

Inside continuous ingestion, ADX uses two internal paths ([ingestion overview](https://learn.microsoft.com/en-us/azure/data-explorer/ingest-data-overview)):

| Engine mode | Throughput | Latency | Typical use |
|-------------|------------|---------|-------------|
| **Queued ingestion** | High — batches merged into optimized extents | Typically seconds–minutes | `.ingest` from Blob (Microsoft default recommendation) |
| **Streaming ingestion** | Micro-batches; row store first | Near real-time (seconds) | Event Hub / IoT — requires **streaming policy** on `SecLogsRaw` |

```text
  QUEUED (typical batch)                 STREAMING (continuous sources)

  .ingest / large batch                  Event Hub / IoT message
         |                                      |
         v                                      v
  Ingestion queue                        Row store (fast)
         |                                      |
         v                                      v
  Column extents                         Column extents
  (compressed, indexed)                  (same end state)
```

Microsoft recommends **queued ingestion** for most high-volume scenarios. **Streaming** fits low-latency monitoring when enabled on the table.

Default queued batching (platform): up to **5 minutes**, **1000 items**, or **~1 GB** per batch — merged for efficient queries. Lab files are tiny, so you see results almost immediately.

## 1.4 Direct ingestion management commands

Microsoft lists **direct ingestion** commands for exploration and prototyping — not for high-volume production ([ingestion overview](https://learn.microsoft.com/en-us/azure/data-explorer/ingest-data-overview)):

| Command | What it does | Lab usage |
|---------|--------------|-----------|
| **`.ingest into table`** | Read from **external storage** (Blob URI) | **Labs 4–5** |
| **`.set` / `.set-or-replace` / `.append`** | Data from **inline query** or datatable | Optional streaming simulation in later labs |
| **`.ingest inline`** | Data embedded in command text | Not used in labs |

Batch ingest from Blob uses **`.ingest into table`** with **`;managed_identity=system`** on the URI — the cluster reads storage with its own identity (RBAC is configured once on the training storage account). You never paste storage account keys into KQL.

## 1.7 What happens after ingest (extents)

Ingestion creates or appends **extents** (compressed columnar shards) in `SecLogsRaw`. You do not manage extents manually. Verification uses KQL:

```kql
SecLogsRaw | count                              // total rows
SecLogsRaw | where RecordFormat == "JSON" | count // JSON batch only
.show ingestion failures                          // rows that failed
```

**Re-running `.ingest`** on the same file may **append duplicates** — production pipelines use idempotent patterns; labs assume **single run** unless you drop the table and start again.

# 2. Batch vs streaming ingestion

Section 1 introduced **one-time vs continuous** and **queued vs streaming** engine paths. This section explains those concepts and how they apply to **Blob batch files** (today's labs) versus **continuous Event Hub / IoT feeds** (covered when you reach streaming ingestion).

## 2.1 Two axes — do not confuse them

Students often mix up **when data arrives** (batch file vs live stream) with **how ADX ingests it** (queued vs streaming engine). Keep both axes in mind:

```text
  AXIS 1 — SOURCE PATTERN (business)          AXIS 2 — ADX ENGINE (platform)

  One-time file (.ingest)                     Queued ingestion (default, high throughput)
  Continuous Event Hub feed                   Streaming ingestion (low latency, needs policy)
```

| Term in conversation | Usually means |
|----------------------|-------------|
| **Batch ingestion** | Discrete **files** in Blob/ADLS + `.ingest` or Event Grid trigger |
| **Streaming ingestion** | **Continuous** messages + optional **streaming policy** on table |
| **Queued** (engine) | ADX batches incoming work (up to ~5 min / 1000 items / ~1 GB) |
| **Streaming** (engine) | Micro-batches → row store → column extents (seconds latency) |

Microsoft recommends **queued ingestion** for most high-volume scenarios ([ingestion overview](https://learn.microsoft.com/en-us/azure/data-explorer/ingest-data-overview)). Continuous sources can use queued or streaming engine paths depending on table policy.

## 2.2 One-time batch ingestion

**One-time ingestion** fits historical transfer, backfill, missing data, and prototyping ([Microsoft — one-time ingestion](https://learn.microsoft.com/en-us/azure/data-explorer/ingest-data-overview#one-time-data-ingestion)).

**Batch** in utility cyber suits:

* Large files landed on a schedule (hourly, nightly)
* Reprocessing historical archives from a data lake
* Initial backfill before enabling streaming
* Corrected files re-landed after a mapping fix

```text
  Security ops batch path (labs)

  App logs (JSON)  ──►  ADLS bronze/  ──►  .ingest + JsonMapping  ──►  SecLogsRaw
  Firewall (CSV)   ──►  ADLS bronze/  ──►  .ingest + CsvMapping   ──►  SecLogsCsvStg ──► SecLogsRaw
```

You run batch ingest from:

* **Query tab** — **`.ingest into table`** (this course)
* **Web UI Get data** — upload or pick from storage (optional UI path)
* **Production** — Azure Data Factory, Event Grid on blob create, SDKs (awareness only)

Training files are staged under `training-data/bronze/` in the class storage account. Lab 2 lists the account name ([labs.md](labs.md)).

### Batch characteristics (Microsoft)

| Property | Labs | Production batch |
|----------|------|------------------|
| Trigger | Manual `.ingest` | Schedule, blob event, ADF pipeline |
| File size | KB | Up to connector limits (`.ingest` via queued path: **6 GB** per command) |
| Idempotency | Re-run may duplicate rows | Partition keys, ingestion time, dedup logic |
| Failure visibility | `.show ingestion failures` | Alerts, retry up to **48 hours** (direct ingest) |

# 3. Blob Storage and ADLS Gen2 sources

**Azure Blob Storage** and **Azure Data Lake Storage Gen2 (ADLS Gen2)** are the primary **batch** landing zones for this course. Security teams land appliance exports and application logs in a **data lake**; ADX reads files with **`.ingest into table`** using a **blob URI** and the cluster's **managed identity**.

Section 2 chose **batch vs streaming**. This section covers **where batch files live**, **how URIs work**, and **how the cluster authenticates** — prerequisites for Labs 4–5.

## 3.1 Blob vs ADLS Gen2 — what students need to know

| Feature | Azure Blob Storage | ADLS Gen2 |
|---------|-------------------|-----------|
| Core service | Object storage (containers + blobs) | Blob storage **plus** hierarchical namespace |
| Path model | Flat container/blob | Directory-like folders (`bronze/`, `silver/`) |
| Typical use | Simple file drops, backups | Enterprise **data lakes**, analytics zones |
| ADX ingest URI | `https://...blob.core.windows.net/...` | `abfss://...@...dfs.core.windows.net/...` |
| This course | **Primary** — all lab `.ingest` examples | Same files; alternate URI style (awareness) |

```text
  UTILITY DATA LAKE (conceptual)

  storage account: stadxtcs2026tcs
  |
  +-- container: training-data
        |
        +-- bronze/          <-- Day 2 batch files (raw security logs)
        +-- silver/          (future staging)
        +-- reference/       (Day 4 threat intel — awareness)
```

Utility cyber pattern: **Bronze zone** in the lake holds immutable raw logs; ADX **`SecLogsRaw`** mirrors that landing for query. Silver/Gold transformations happen inside ADX (Day 3+), not by overwriting lake files.

## 3.2 Training storage layout

Staged training files map from the GitHub repo to ADLS:

| Repo path | Staged ADLS path | Rows | Lab |
|-----------|------------------|------|-----|
| `data/bronze/sec-app-logs.json` | `training-data/bronze/sec-app-logs.json` | **1500** | Lab 4 |
| `data/bronze/sec-web-logs.csv` | `training-data/bronze/sec-web-logs.csv` | **1000** | Lab 5 ingest |
| `data/bronze/sec-web-logs.ndjson` | `training-data/bronze/sec-web-logs.ndjson` | **1000** | Same rows as CSV (reference copy) |

See [data/README.md](../data/README.md) for field schema and AuthFailure counts across the week.

```text
  REPO (GitHub)              ADLS (training storage)        ADX (your database)

  data/bronze/*.json   ──►   training-data/bronze/    ──►   .ingest → SecLogsRaw
  (sample files)             (staged in storage)              (you run in labs)
```

**Lab 5 ingest:** Students ingest **`sec-web-logs.csv`** (**1000** data rows + header) with **`format='csv'`** into staging table **`SecLogsCsvStg`**, then promote to **`SecLogsRaw`** with **`RecordFormat = CSV`**. The **`sec-web-logs.ndjson`** file in storage is a reference copy of the same rows.

## 3.3 URI patterns — Blob HTTPS vs ADLS abfss

Replace **`<storage-account>`** with the value from Lab 2 (class example: **`stadxtcs2026tcs`**).

### Blob HTTPS (used in all lab query files)

```text
https://<storage-account>.blob.core.windows.net/<container>/<path/to/file>
```

Examples:

```text
https://<storage-account>.blob.core.windows.net/training-data/bronze/sec-app-logs.json
https://<storage-account>.blob.core.windows.net/training-data/bronze/sec-web-logs.csv
```

### ADLS Gen2 abfss (equivalent — awareness)

When the storage account has hierarchical namespace enabled:

```text
abfss://<container>@<storage-account>.dfs.core.windows.net/<path/to/file>
```

Example:

```text
abfss://training-data@<storage-account>.dfs.core.windows.net/bronze/sec-app-logs.json
```

Both forms point at the **same blob**. Labs use **HTTPS Blob** URIs for consistency.

### URI anatomy

```text
  https://stadxtcs2026tcs.blob.core.windows.net/training-data/bronze/sec-app-logs.json;managed_identity=system
  |       |                  |                    |            |      |                    |
  scheme  account            blob endpoint        container    folder file                 auth suffix
```

| Part | Training value |
|------|----------------|
| Storage account | `stadxtcs2026tcs` |
| Container | `training-data` |
| Folder | `bronze/` |
| Auth suffix | **`;managed_identity=system`** (required in labs) |

## 3.4 Cluster access — managed identity (no storage keys)

When you run **`.ingest into table`**, ADX must **read a file from Azure Storage** (Blob or ADLS). That read happens **as the cluster**, not as your personal user account in the browser. The cluster needs permission on the storage account — without it, ingest fails even if you can see the file in the Azure Portal.

### Why not paste a storage key in KQL?

In older patterns, applications stored **storage account keys** or long-lived **SAS tokens** in scripts. That is risky: keys appear in query history, chat logs, and screenshots. This course uses **managed identity** instead — the cluster authenticates to Azure Storage using an Azure AD identity that is **built into the cluster resource**, with **no secret in your lab file**.

### What is managed identity (plain terms)?

Think of the ADX cluster as a **service account** in Azure Active Directory (Entra ID):

```text
  You (analyst)                         ADX cluster (service)
  -------------                         ---------------------

  Signed in to Web UI                   Has its own identity in Entra ID
  Run .ingest in Query tab    ──►       Cluster identity calls Storage API
  You do NOT pass a password            Storage checks RBAC: "Is this cluster allowed to read?"
```

The cluster’s **system-assigned managed identity** is created automatically with the cluster. That identity is granted **Storage Blob Data Reader** on the training storage account before labs. Every `.ingest` command uses the same cluster identity to read shared training files.

### What `;managed_identity=system` means on the URI

Blob URIs in lab queries end with an **ingestion property suffix** (after a semicolon):

```text
  .../bronze/sec-app-logs.json;managed_identity=system
                                ^^^^^^^^^^^^^^^^^^^^^^^^^
                                Tell ADX: authenticate to Storage as the
                                cluster's system-assigned managed identity
```

| Piece | Meaning |
|-------|---------|
| **`;`** | Separates blob path from ingestion/auth properties |
| **`managed_identity=system`** | Use the cluster’s **system-assigned** identity (not a user account, not a key) |
| **Alternative (not used in labs)** | `;managed_identity=<user-assigned identity resource id>` for a dedicated identity per workload |

If you **omit** the suffix, ADX may try other auth modes or fail — **always include `;managed_identity=system`** on training blob URIs.

### End-to-end flow

```text
  1. You run .ingest (Query tab, your database selected)
           |
           v
  2. ADX data management service parses URI + mapping name
           |
           v
  3. Cluster managed identity → Azure Storage: GET blob bytes
           |                    (RBAC: Storage Blob Data Reader)
           v
  4. Parse multijson → apply SecLogsRaw_JsonMapping → write extents
           |
           v
  5. Rows appear in SecLogsRaw (after short queued delay)
```

### Your responsibility vs platform setup

| Who | Responsibility |
|-----|----------------|
| **Platform (before labs)** | Cluster identity enabled; **Storage Blob Data Reader** on `training-data` container; files under `bronze/` |
| **You (in labs)** | Replace **`<storage-account>`** with the name from Lab 2; **keep** `;managed_identity=system`; select **your** database |
| **Never** | Put storage account keys, SAS with write access, or secrets in KQL files or GitHub |

### When ingest fails — what to check

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| Authorization / 403 on storage | Cluster identity lacks Blob Data Reader | Report in class — RBAC fix on storage |
| Blob not found | Wrong account name or path typo | Compare URI to Lab 2 table |
| Ingest accepted but count = 0 | Queued processing not finished | Wait 30–60 seconds; rerun `count` |
| Mapping error | Mapping not created before `.ingest` | Run Lab **4** mapping query file first ([queries/03-create-json-mapping.kql](queries/03-create-json-mapping.kql)) |

Managed identity is the same pattern used for **Event Hub** and **IoT Hub** data connections in streaming labs — the cluster identity is granted **Azure Event Hubs Data Receiver** (or equivalent) instead of storage RBAC.

## 3.5 `.ingest from storage` — command shape

### What is `SecLogsRaw_JsonMapping`?

A blob file is just **bytes** (JSON lines). Your Bronze table **`SecLogsRaw`** has **four columns** with specific types. An **ingestion mapping** is the **named rule set** that tells ADX how to fill those columns from each parsed JSON line.

**`SecLogsRaw_JsonMapping`** is the mapping you create in **Lab 4** ([queries/03-create-json-mapping.kql](queries/03-create-json-mapping.kql)). You reference it by name at ingest time:

```kql
with (format='multijson', ingestionMappingReference='SecLogsRaw_JsonMapping')
```

Think of it as a **translation table** from file shape → table shape:

```text
  One line in sec-app-logs.json          SecLogsRaw_JsonMapping              Row in SecLogsRaw
  -----------------------------          ------------------------              ----------------

  {                                      $.Timestamp  ──────────────►  IngestionTime (datetime)
    "Timestamp": "2026-06-11T09:09:01Z",  ConstValue   ──────────────►  SourceFile = sec-app-logs.json
    "EventType": "AuthFailure",           ConstValue   ──────────────►  RecordFormat = JSON
    "SourceIP": "10.20.1.44",             $ (whole object) ───────────►  RawPayload (dynamic JSON)
    ...
  }
```

| Mapping name | Used for | Created in |
|--------------|----------|------------|
| **`SecLogsRaw_JsonMapping`** | App log NDJSON (`sec-app-logs.json`) | Lab **4** (create mapping + ingest) |
| **`SecLogsCsvStg_CsvMapping`** | Firewall CSV (`sec-web-logs.csv`) | Lab **5** (staging table + ingest) |

**Why not map `EventType` and `SourceIP` directly to Bronze columns?** Bronze is the **raw landing zone** — one `dynamic` **`RawPayload`** holds the full event. Typed columns (`EventType`, `SourceIP`, …) are extracted later in **Silver** via update policy. The mapping only needs to set **lineage** (`SourceFile`, `RecordFormat`) plus **`IngestionTime`** and **`RawPayload`**.

Line-by-line detail: [§5.4](#54-seclogsraw-jsonmapping-lab-4-line-by-line).

Microsoft **direct ingestion from storage** uses **`.ingest into table`** ([ingestion overview — direct commands](https://learn.microsoft.com/en-us/azure/data-explorer/ingest-data-overview#direct-ingestion-with-management-commands)):

```kql
.ingest into table SecLogsRaw
(
    h'https://<storage-account>.blob.core.windows.net/training-data/bronze/sec-app-logs.json;managed_identity=system'
)
with (format='multijson', ingestionMappingReference='SecLogsRaw_JsonMapping')
```

| Clause | Lab 4 | Lab 5 |
|--------|-------|-------|
| Table | `SecLogsRaw` | `SecLogsCsvStg` (then `.append` → `SecLogsRaw`) |
| URI file | `sec-app-logs.json` | `sec-web-logs.csv` |
| `format` | `multijson` | `csv` |
| Mapping | `SecLogsRaw_JsonMapping` | `SecLogsCsvStg_CsvMapping` |
| Expected rows | **1500** | **1000** |

The command returns when ingest is **accepted**; queued processing writes extents. Wait **30–60 seconds**, then verify with `count`.

### Ingestion properties on the URI

Properties can appear in the `with (...)` clause or after **`;`** on the URI ([data ingestion properties](https://learn.microsoft.com/en-us/kusto/ingestion-properties?view=microsoft-fabric)). Labs use the `with` clause for `format` and `ingestionMappingReference`; auth uses **`;managed_identity=system`** on the URI string.

## 3.8 Verify storage path before ingest

After Lab 2, confirm your notes match the checkpoint table:

| Check | Expected |
|-------|----------|
| Storage account | Matches `<storage-account>` in queries |
| Container | `training-data` |
| JSON blob | `bronze/sec-app-logs.json` exists (**1500** NDJSON lines) |
| CSV blob | `bronze/sec-web-logs.csv` exists (**1000** data rows + header) |
| URI suffix | `;managed_identity=system` on every `.ingest` |
| Database | Your database selected (example: `LogsDB_u01`) |

Optional peek after Lab 4 (not required):

```kql
SecLogsRaw
| where RecordFormat == "JSON"
| take 1
| project SourceFile, RecordFormat, RawPayload
```

# 4. Data formats

**Format** tells ADX **how to parse bytes** in a blob (JSON lines, CSV rows, Parquet columns). **Mapping** (Section 5) tells ADX **which parsed fields land in which table columns**. Both are required for successful Bronze ingest.

```text
  Blob file  ──►  format='multijson'  ──►  parsed records  ──►  mapping  ──►  SecLogsRaw columns
                  (Section 4)                                  (Section 5)
```

Microsoft supports many [ingestion data formats](https://learn.microsoft.com/en-us/azure/data-explorer/ingestion-supported-formats). Day 2 hands-on uses **NDJSON** for Lab 4 and **native CSV** for Lab 5.

## 4.1 Supported formats — course vs production

| Format | Extension | Day 2 | `format` value (typical) | Utility cyber source |
|--------|-----------|-------|--------------------------|----------------------|
| **NDJSON / multiline JSON** | `.json`, `.ndjson` | **Lab 4 ingest** | `multijson` | App middleware, API gateways, SIEM JSON export |
| **CSV** | `.csv` | **Lab 5 ingest** | `csv` | Firewall, proxy, VPN appliance export |
| **TSV** | `.tsv` | Mention | `tsv` | Legacy mainframe-style exports |
| **JSON array** | `.json` | Not in labs | `json` | Single API response dump |
| **AVRO** | `.avro` | Mention | `avro` | Kafka / Schema Registry pipelines |
| **Parquet** | `.parquet` | Mention | `parquet` | Analytics lake, compliance archive |
| **ORC** | `.orc` | Mention | `orc` | Hadoop-era lake files |

Day 3 streaming (Event Hub / IoT Hub) also carries **JSON** payloads — same field names as batch files.

## 4.2 NDJSON — newline-delimited JSON (Lab 4 file)

Each **line** is one complete JSON object. No wrapping array. This is the most common **application log** shape in cloud-native systems. The file’s **first** line may be a different event type; the example below is a real **AuthFailure** row from `sec-app-logs.json` (also used for Day 4 ThreatIntel **`BruteForceTarget`** enrichment).

```json
{"Timestamp":"2026-06-11T09:09:01Z","EventType":"AuthFailure","SourceIP":"10.20.1.44","DestinationHost":"scada-gw.utility.local","UserPrincipal":"operator@utility.com","Severity":"High","Message":"Failed login after 3 attempts","Facility":"Substation-A"}
```

File: `data/bronze/sec-app-logs.json` — **1500** NDJSON lines → **1500** Bronze rows after Lab 4.

### NDJSON vs other JSON layouts

| Layout | File shape | ADX `format` | Course |
|--------|------------|--------------|--------|
| **NDJSON** (one object per line) | `{...}\n{...}\n` | **`multijson`** | **Lab 4** |
| **JSON array** | `[{...},{...}]` | `json` | Not used in labs |
| **Single JSON object** | `{...}` | `json` | One row only |

```text
  NDJSON (multijson)              JSON array (json)

  { row1 }                        [
  { row2 }                          { row1 },
  { row3 }                          { row2 }
                                    ]
```

**Rule for Day 2:** If each line is its own `{...}` object, use **`format='multijson'`**.

## 4.3 CSV — appliance export shape (Lab 5)

Firewall and proxy appliances often export **CSV** with a header row:

```text
Timestamp,EventType,SourceIP,DestinationHost,UserPrincipal,Severity,Message,Facility
2026-06-11T10:00:01Z,AuthFailure,10.20.3.55,scada-gw.utility.local,tech@utility.com,Medium,Account locked,Substation-B
```

File: `data/bronze/sec-web-logs.csv` — **1000 data rows** + header.

### Lab 5 flow — staging then Bronze

ADX cannot map a native CSV row directly into a single **`dynamic`** column on `SecLogsRaw`. Lab 5 uses a **staging table** with typed columns, then **`pack()`** into `RawPayload`:

```text
  sec-web-logs.csv  ──►  SecLogsCsvStg  ──►  SecLogsCsvToBronze()  ──►  SecLogsRaw
  format='csv'          CSV mapping         pack() + lineage cols       RecordFormat=CSV
```

| Step | Object | Role |
|------|--------|------|
| 1 | `SecLogsCsvStg` | Typed columns matching CSV header |
| 2 | `SecLogsCsvStg_CsvMapping` | Ordinal mapping (`0`–`7`) |
| 3 | `.ingest` with `ignoreFirstRecord=true` | Skip header row |
| 4 | `SecLogsCsvToBronze()` + `.append` | Build `RawPayload` dynamic, set lineage |

Lab 5 ingest command ([queries/06-ingest-csv-batch.kql](queries/06-ingest-csv-batch.kql)):

```kql
.ingest into table SecLogsCsvStg
(
    h'https://<storage-account>.blob.core.windows.net/training-data/bronze/sec-web-logs.csv;managed_identity=system'
)
with (format='csv', ingestionMappingReference='SecLogsCsvStg_CsvMapping', ignoreFirstRecord=true)

.append SecLogsRaw <| SecLogsCsvToBronze()
```

**Do not** ingest `sec-web-logs.csv` with `format='multijson'` — that causes parse failures.

## 4.4 The `format` property in `.ingest`

Specify format in the **`with (...)`** clause ([ingestion properties](https://learn.microsoft.com/en-us/kusto/ingestion-properties?view=microsoft-fabric)):

```kql
.ingest into table SecLogsRaw
(
    h'https://<storage-account>.blob.core.windows.net/training-data/bronze/sec-app-logs.json;managed_identity=system'
)
with (format='multijson', ingestionMappingReference='SecLogsRaw_JsonMapping')
```

| Lab | File | `format` | Why |
|-----|------|----------|-----|
| **4** | `sec-app-logs.json` | `multijson` | **1500** NDJSON lines |
| **5** | `sec-web-logs.csv` | `csv` | **1000** CSV data rows (+ header skipped) |

Wrong format → parse errors → check **`.show ingestion failures`**.

## 4.5 Shared field schema (all course files)

All bronze and streaming sample files share the same logical schema ([data/README.md](../data/README.md)):

| Field | Type (logical) | Example |
|-------|----------------|---------|
| `Timestamp` | datetime string (ISO 8601) | `2026-06-11T09:09:01Z` |
| `EventType` | string | `AuthFailure`, `FirewallDeny`, `VPNLogin` |
| `SourceIP` | string | `10.20.1.44` |
| `DestinationHost` | string | `scada-gw.utility.local` |
| `UserPrincipal` | string | `operator@utility.com` (may be empty) |
| `Severity` | string | `Low`, `Medium`, `High`, `Critical` |
| `Message` | string | Human-readable detail |
| `Facility` | string | `Substation-A`, `DMZ-Firewall`, `Corporate-VPN` |

In **Bronze**, the full object lives in **`RawPayload` (dynamic)** — not as typed top-level columns. **Silver** (Day 3) extracts typed fields via update policy.

```text
  File row (JSON or CSV→JSON)          Bronze SecLogsRaw
  ---------------------------          -----------------

  Timestamp, EventType, ...     ──►    IngestionTime  ← $.Timestamp (mapping)
                                       SourceFile     ← ConstValue
                                       RecordFormat   ← ConstValue
                                       RawPayload     ← entire object ($)
```

## 4.6 Event types in Day 2 batch files

Locked counts at course scale ([data/README.md](../data/README.md#event-type-reference-authfailure--700-in-silver-after-day-3)):

| EventType | JSON file (Lab 4) | CSV file (Lab 5) |
|-----------|-------------------|------------------|
| AuthFailure | 300 | 200 |
| AuthSuccess | 200 | 100 |
| FirewallDeny | 400 | 200 |
| FirewallAllow | 200 | 100 |
| VPNLogin | 200 | 100 |
| VPNLogout | 0 | 100 |
| PrivilegeEscalation | 100 | 100 |
| ConfigChange | 100 | 100 |

After Day 3 streaming, **AuthFailure total in Silver = 700** (300 JSON + 200 CSV + 200 Event Hub).

# 5. Ingestion mappings

An **ingestion mapping** binds **source fields** (after format parsing) to **destination table columns**. It is the contract that prevents ingest failures and wrong-type landing ([ingestion mappings](https://learn.microsoft.com/en-us/kusto/management/mappings?view=microsoft-fabric)).

Without a mapping matching your Bronze schema, ADX cannot populate `IngestionTime`, `SourceFile`, `RecordFormat`, and `RawPayload` correctly.

```text
  Parsed record from multijson          JSON mapping              SecLogsRaw
  -----------------------------         -------------             ----------

  { "Timestamp": "...",                 $.Timestamp      ──►  IngestionTime
    "EventType": "AuthFailure",         ConstValue       ──►  SourceFile
    "SourceIP": "...",                  ConstValue       ──►  RecordFormat
    ... }                                $               ──►  RawPayload (dynamic)
```

## 5.1 Mapping types in ADX

| Mapping kind | Used when source is | Day 2 |
|--------------|---------------------|-------|
| **JSON mapping** | JSON / NDJSON / `multijson` | **Lab 4** |
| **CSV mapping** | Native `format='csv'` files | **Lab 5** (on `SecLogsCsvStg`) |
| **Avro mapping** | Avro files | Mention (Kafka) |
| **Parquet mapping** | Parquet files | Mention (lake) |

Lab 4 uses a **JSON mapping** on `SecLogsRaw`. Lab 5 uses a **CSV mapping** on staging table `SecLogsCsvStg`, then promotes rows with **`RecordFormat = CSV`** via `SecLogsCsvToBronze()`.

## 5.2 Create and inspect mappings

Mappings are **database entities** attached to a table:

```kql
.create-or-alter table SecLogsRaw ingestion json mapping 'SecLogsRaw_JsonMapping' '[{"column":"IngestionTime","properties":{"path":"$.Timestamp"}},{"column":"SourceFile","properties":{"ConstValue":"sec-app-logs.json"}},{"column":"RecordFormat","properties":{"ConstValue":"JSON"}},{"column":"RawPayload","properties":{"path":"$"}}]'
```

List mappings on the table:

```kql
.show table SecLogsRaw ingestion mappings
```

| Command | Purpose |
|---------|---------|
| `.create-or-alter ... ingestion json mapping` | Create or update mapping (idempotent) |
| `.show table SecLogsRaw ingestion mappings` | Verify mapping exists before `.ingest` |
| `.drop table SecLogsRaw ingestion json mapping 'Name'` | Remove mapping (lab reset only) |

Run mapping commands **before** `.ingest` — Labs 4 and 5 order: `03` → `04`, `05` → `06`.

## 5.3 JSON mapping elements

Each mapping entry maps one **table column**:

| Property | Meaning | Lab 4 example |
|----------|---------|---------------|
| **`path`** | JSONPath to source field | `"$.Timestamp"` → `IngestionTime` |
| **`path": "$"`** | Entire parsed object | Full event → `RawPayload` |
| **`ConstValue`** | Fixed string per mapping | `"sec-app-logs.json"` → `SourceFile` |
| **`transform`** | Optional conversion | Not used in Day 2 labs |

```text
  One NDJSON line                         Mapping rules                    Bronze row
  ----------------                        -------------                    ----------

  {                                       $.Timestamp        →  IngestionTime = 2026-06-11T09:09:01Z
    "Timestamp": "2026-06-11T09:09:01Z",  ConstValue         →  SourceFile    = sec-app-logs.json
    "EventType": "AuthFailure",            ConstValue         →  RecordFormat  = JSON
    "SourceIP": "10.20.1.44",              $                  →  RawPayload    = { whole object }
    ...
  }
```

**Why store the whole object in `RawPayload`?** Bronze lands raw data with minimal transform. **Silver** parses `EventType`, `SourceIP`, etc. into typed columns via **update policy**.

## 5.4 `SecLogsRaw_JsonMapping` — Lab 4 (line by line)

**Recap:** The mapping is a **saved object** on your database, attached to table `SecLogsRaw`. Its name **`SecLogsRaw_JsonMapping`** is what you pass in `ingestionMappingReference`. Lab **4** **creates** it and **uses** it during `.ingest`.

Query file: [queries/03-create-json-mapping.kql](queries/03-create-json-mapping.kql)

| Column | Mapping | Source |
|--------|---------|--------|
| `IngestionTime` | `path: $.Timestamp` | Event timestamp from JSON line |
| `SourceFile` | `ConstValue: sec-app-logs.json` | Logical file name (constant for this mapping) |
| `RecordFormat` | `ConstValue: JSON` | Marks batch as application JSON |
| `RawPayload` | `path: $` | Complete JSON object as `dynamic` |

Referenced at ingest time:

```kql
with (format='multijson', ingestionMappingReference='SecLogsRaw_JsonMapping')
```

## 5.5 `SecLogsCsvStg_CsvMapping` — Lab 5 (native CSV)

Query file: [queries/05-create-csv-mapping.kql](queries/05-create-csv-mapping.kql)

CSV mapping uses **ordinals** (0-based column position). Header row is skipped at ingest with **`ignoreFirstRecord=true`**.

| Ordinal | CSV column | Staging column |
|---------|------------|----------------|
| 0 | Timestamp | `Timestamp` |
| 1 | EventType | `EventType` |
| 2 | SourceIP | `SourceIP` |
| 3 | DestinationHost | `DestinationHost` |
| 4 | UserPrincipal | `UserPrincipal` |
| 5 | Severity | `Severity` |
| 6 | Message | `Message` |
| 7 | Facility | `Facility` |

```kql
.create-or-alter table SecLogsCsvStg ingestion csv mapping 'SecLogsCsvStg_CsvMapping' '[
  {"column":"Timestamp","Properties":{"Ordinal":"0"}},
  {"column":"EventType","Properties":{"Ordinal":"1"}},
  ...
]'
```

Function **`SecLogsCsvToBronze()`** packs typed columns into **`RawPayload`** and sets Bronze lineage:

| Bronze column | Source |
|---------------|--------|
| `IngestionTime` | `Timestamp` from staging |
| `SourceFile` | `'sec-web-logs.csv'` |
| `RecordFormat` | `'CSV'` |
| `RawPayload` | `pack(...)` of all event fields |

Ingest uses **`format='csv'`** against **`sec-web-logs.csv`**:

```kql
with (format='csv', ingestionMappingReference='SecLogsCsvStg_CsvMapping', ignoreFirstRecord=true)
```

Verification filters on **`RecordFormat == "CSV"`** on `SecLogsRaw`.

## 5.6 Two formats, one Bronze table

```text
  Lab 4                              Lab 5
  ----                               ----

  SecLogsRaw_JsonMapping             SecLogsCsvStg_CsvMapping
         |                                  |
         v                                  v
  sec-app-logs.json                  sec-web-logs.csv
  format=multijson                   format=csv → SecLogsCsvStg
  RecordFormat = JSON                SecLogsCsvToBronze() → RecordFormat = CSV
  1500 rows                          1000 rows
         \                                  /
          ──────────►  SecLogsRaw  ◄────────
                      2500 rows total
```

Lab 4 lands directly on **`SecLogsRaw`**. Lab 5 lands on **`SecLogsCsvStg`** first, then **`.append`** promotes into the same Bronze table.

## 5.7 Run batch ingest with mapping reference

Full Lab 4 command ([queries/04-ingest-json-batch.kql](queries/04-ingest-json-batch.kql)):

```kql
.ingest into table SecLogsRaw
(
    h'https://<storage-account>.blob.core.windows.net/training-data/bronze/sec-app-logs.json;managed_identity=system'
)
with (format='multijson', ingestionMappingReference='SecLogsRaw_JsonMapping')
```

| `with` property | Required | Role |
|-----------------|----------|------|
| `format` | Yes | Parser (`multijson` for labs) |
| `ingestionMappingReference` | Yes for Bronze | Names mapping on `SecLogsRaw` |
| `ignoreFirstRecord` | CSV native only | Skip header row |
| `tags` | No | Extent tags (advanced) |

Replace `<storage-account>` with Lab 2 value. Keep **`;managed_identity=system`** on the URI ([§3.4](#34-cluster-access-managed-identity-no-storage-keys)).

# 6. Bronze layer — `SecLogsRaw`

**Bronze** is the **raw landing zone** in the medallion pipeline. Table **`SecLogsRaw`** stores every security event with minimal transform: lineage columns plus the full payload in **`dynamic`**. Labs create the table (Lab 3), ingest batch files (Labs 4–5), and verify landing (Lab 6).

## 6.1 Medallion layers — where Bronze fits

| Layer | Table | ADX mechanism | Locked rows (checkpoint) |
|-------|--------|---------------|--------------------------|
| **Bronze** | `SecLogsRaw` | Ingest + mappings | **2500** after batch labs |
| **Silver** | `SecLogsParsed` | Update policy | **3500** (after streaming + backfill) |
| **Gold** | `SecLogsHourly` | Materialized view | `sum(EventCount)` = **3500** |

```text
  Blob batch ──►  SecLogsRaw  ──►  SecLogsParsed  ──►  SecLogsHourly
  (Labs 4–5)       (Bronze)         (Silver)            (Gold)
       │               │                  ▲
       │               │    update policy │
       │               └──────────────────┘
       │
  Event Hub / IoT streams ──► same SecLogsRaw
```

| Question | Bronze answer | Silver answer |
|----------|---------------|---------------|
| What did we receive? | `RawPayload`, `SourceFile` | Typed `EventType`, `SourceIP`, … |
| From which source? | `RecordFormat`, `SourceFile` | `SourceSystem`, parsed fields |
| Ready for SOC dashboards? | Peek only | Full filters, joins, MVs |

Bronze answers: *"What did we receive, from which file, in what shape?"* Silver answers: *"What are the typed security fields for analytics?"*

## 6.2 Bronze vs `PracticeSecurityEvents`

| Aspect | `PracticeSecurityEvents` | Bronze `SecLogsRaw` |
|--------|--------------------------|---------------------|
| Purpose | Learn KQL on typed columns | Land **raw** pipeline data |
| Load method | `.set-or-replace` inline | `.ingest` from Blob + mappings |
| Schema | Typed columns (`EventType`, `SourceIP`, …) | **`RawPayload` dynamic** + lineage |
| Row count | **2000** (locked) | **2500** after batch labs |
| Pipeline role | Standalone practice table | **Start** of Bronze→Silver→Gold |

```text
  PRACTICE TABLE (KQL labs)          PIPELINE (ingest labs)

  PracticeSecurityEvents             SecLogsRaw ──► SecLogsParsed ──► SecLogsHourly
  (typed, 2000 rows)                   (Bronze, dynamic RawPayload)
```

Do not confuse the two tables — pipeline checkpoints use **`SecLogsRaw`**, not `PracticeSecurityEvents`.

## 6.3 Why `RawPayload` is `dynamic`

Utility logs arrive as **JSON lines** and **CSV exports** with the same logical fields but different on-disk shapes. Bronze stores the **entire parsed object** in one column:

* **One table** for JSON and CSV lineage (`RecordFormat` distinguishes them)
* **No schema drift failures** when a new optional field appears in source logs
* **Silver update policy** (Day 3) extracts `EventType`, `SourceIP`, `Facility`, etc. into typed columns once

```text
  Ingest (Day 2)                    Query Bronze (Day 2)              Silver (Day 3)

  NDJSON line  ──►  RawPayload     RawPayload.EventType  ──►  EventType: string
  { EventType,       (dynamic)       (peek with extend)          (typed column)
    SourceIP, ... }
```

KQL on `dynamic` uses dot notation: `RawPayload.EventType`, wrapped in `tostring()` when comparing to strings.

## 6.4 Locked schema — four columns

```text
SecLogsRaw
| Column        | Type     | Purpose |
|---------------|----------|---------|
| IngestionTime | datetime | Event time from source (`$.Timestamp` in mapping) |
| SourceFile    | string   | Logical origin file (`sec-app-logs.json`, `sec-web-logs.csv`) |
| RecordFormat  | string   | `JSON` or `CSV` — export / lineage label |
| RawPayload    | dynamic  | Full event object as ingested |
```

Create with Lab 3 ([queries/02-create-bronze-table.kql](queries/02-create-bronze-table.kql)):

```kql
.create table SecLogsRaw (
    IngestionTime: datetime,
    SourceFile: string,
    RecordFormat: string,
    RawPayload: dynamic
)
```

| Column | Populated by | Example value |
|--------|--------------|---------------|
| `IngestionTime` | Mapping `$.Timestamp` | `2026-06-11T09:09:01Z` |
| `SourceFile` | Mapping `ConstValue` | `sec-app-logs.json` |
| `RecordFormat` | Mapping `ConstValue` | `JSON` |
| `RawPayload` | Mapping `$` | `{ "EventType": "AuthFailure", ... }` |

**Do not add typed security columns to Bronze in this course** — that is Silver's job.

## 6.5 Lab 7 — pipeline checkpoint (discussion)

Close Day 2 with [labs.md](labs.md) **Lab 7**: name **Bronze → Silver → Gold** table names (`SecLogsRaw`, `SecLogsParsed`, `SecLogsHourly`), explain why Bronze uses **`RawPayload`**, and preview Day 3 **update policy** and streaming data connections. Locked Day 3 targets: Bronze **3500**, Silver **3500**, AuthFailure **700**.
