# Day 02 — Labs

**Theme:** Batch Ingestion & Bronze Layer

**Database:** Same as Day 1 — **your database** on the shared cluster `adx-training-tcs` (example: **`LogsDB_u01`**).

**Theory:** [README.md](README.md)

---

## Working in the Query tab

1. Select **your** `LogsDB_<id>` in the database dropdown.
2. Open the `.kql` file for the lab in `queries/`.
3. Run **one block at a time** with **Shift+Enter**.
4. Compare your results to the **Example result** table for that lab.

For Lab 2, record the **storage account name** from class materials (example: `stadxtcs2026tcs`) — you will use it in Labs 4–5.

## Troubleshooting

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| `.ingest` fails with authorization / 403 | Missing `;managed_identity=system` on URI | Keep the suffix from the lab file; confirm storage account name |
| Ingest accepted but count = 0 | Queued ingest still processing | Wait 30–60 seconds; rerun `count` |
| Mapping error on ingest | Mapping not created first | Run Lab 4 mapping before Lab 4 ingest; Lab 5 mapping before Lab 5 ingest |
| CSV count 0 after Lab 5 | `.append SecLogsRaw` step skipped | Re-run full `06-ingest-csv-batch.kql` from staging ingest through append |
| Total Bronze &gt; **2500** | Duplicate `.ingest` | Drop `SecLogsRaw` in **your** database and re-run Labs 3–6 |

---

## Expected outcomes

| After lab | Check |
|-----------|--------|
| Lab 4 | JSON rows = **1500** |
| Lab 5 | CSV rows = **1000** |
| Lab 6 Q1 | Total Bronze = **2500** |
| Lab 6 Q2 | **2** `SourceFile` values — **1500** JSON + **1000** CSV |

---

# Lab 1 — Ingestion concepts in ADX

## Objective

Explore **ingestion metadata** commands before creating Bronze — understand how ADX surfaces tables, failures, and retention policies.

## Tasks

1. Open ADX Web UI — **your database** selected (example: **`LogsDB_u01`**).
2. Open **`queries/01-ingestion-commands.kql`**.
3. Run **each command block separately** (Shift+Enter per block).
4. Record baseline state:
   * Does **`SecLogsRaw`** exist yet? (expected: **no** until Lab 3)
   * Does **`PracticeSecurityEvents`** still show from Day 1? (may exist — that is OK)
5. Read Results for **`.show ingestion failures`** — empty is normal before any `.ingest`.

## Example result

| Command | You should see |
|---------|----------------|
| `.show tables` | `PracticeSecurityEvents` and/or empty; **`SecLogsRaw` after Lab 3 only** |
| `.show ingestion failures` | Empty grid or historical failures (no error running command) |
| `.show database policy retention` | Retention policy JSON for your database |

## Success criteria

* All three commands run without permission errors.
* You can explain the difference between **`.set-or-replace`** (Day 1) and **`.ingest`** (Day 2).

---

# Lab 2 — Batch vs streaming (discussion + setup)

## Objective

Contrast **batch** (Day 2 files in Blob/ADLS) with **continuous streaming** (Day 3 Event Hub / IoT Hub), and record the **storage account** and blob paths needed for Labs 4–5.

## Tasks

1. With the class, walk through [README.md](README.md) Section **2.1–2.2** (batch vs streaming axes, one-time batch ingest) and **§3.4** (managed identity).
2. In your notes, record:

   | Field | Your value |
   |-------|------------|
   | Storage account (`<storage-account>`) | _________________ |
   | Cluster URI | `https://adx-training-tcs.centralindia.kusto.windows.net` |
   | Database | Your assigned name (e.g. `LogsDB_u01`) |

3. Confirm staged blob paths (class storage account):

   | File | Path | Rows | Lab |
   |------|------|------|-----|
   | App logs (JSON) | `training-data/bronze/sec-app-logs.json` | 1500 | Lab 4 |
   | Web logs (CSV export) | `training-data/bronze/sec-web-logs.csv` | 1000 | Lab 5 |

4. Cluster **managed identity** reads Blob with **`;managed_identity=system`** on the URI — no storage keys in queries.
5. Note streaming service names for later labs (write down):

   | Service | Training name |
   |---------|---------------|
   | Event Hub namespace | `eh-adx-tcs` |
   | Event Hub | `sec-events` |
   | IoT Hub | `iot-adx-tcs` |
   | IoT consumer group | `adx` |

## Example `.ingest` URI (Lab 4 — do not run yet)

Replace `<storage-account>` with the value from step 2:

```text
https://<storage-account>.blob.core.windows.net/training-data/bronze/sec-app-logs.json;managed_identity=system
```

## Success criteria

* Storage account name recorded for Labs 4–5.
* You can explain **batch file** vs **continuous Event Hub** without conflating them with queued vs streaming **engine**.
* You can name **`;managed_identity=system`** as the cluster auth suffix for Blob reads.

---

# Lab 3 — Create Bronze table

## Objective

Create the Bronze table **`SecLogsRaw`** — empty shell with four columns before mappings and ingest.

## Tasks

1. Confirm database dropdown shows **your database** (example: **`LogsDB_u01`**).
2. Open **`queries/02-create-bronze-table.kql`**.
3. Run the **`.create table`** block only.
4. Run **`.show table SecLogsRaw cslschema`** — confirm four columns.
5. Optional: `SecLogsRaw | count` → expected **0** (no ingest yet).

> If **`SecLogsRaw`** already exists from a prior attempt in **your** database, use **`.create-or-alter table`** or drop the table and re-run from Lab 3 — you are not affecting other students' databases.

## Example result

| Column | Type | Purpose |
|--------|------|---------|
| `IngestionTime` | datetime | Source event timestamp |
| `SourceFile` | string | Origin file name |
| `RecordFormat` | string | `JSON` or `CSV` |
| `RawPayload` | dynamic | Full event object |

## Success criteria

* `.show tables` includes **`SecLogsRaw`**.
* Schema matches four columns above.
* You can explain Bronze vs Silver ([README §6](README.md#61-medallion-layers--where-bronze-fits)).

---

# Lab 4 — JSON batch ingest from Blob

## Objective

Define a JSON ingestion mapping and **batch-ingest** application security logs from **Azure Blob** into Bronze using **`.ingest into table`** and **managed identity**.

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Open **`queries/03-create-json-mapping.kql`** → run mapping block only (then `.show` block).
3. Open **`queries/04-ingest-json-batch.kql`**.
4. Replace **`<storage-account>`** with the name from Lab 2 (example: `stadxtcs2026tcs`).
5. Verify the blob URI ends with **`;managed_identity=system`** — do not remove it.
6. Run the **`.ingest`** block only; wait **30–60 seconds** (queued ingestion).
7. Run the verification query at the bottom of the file (or):

```kql
SecLogsRaw | where RecordFormat == "JSON" | count
```

> Each NDJSON line becomes one Bronze row. **`path: "$"`** in the mapping stores the full object in `RawPayload`.

## Example URI (after placeholder replace)

```text
https://stadxtcs2026tcs.blob.core.windows.net/training-data/bronze/sec-app-logs.json;managed_identity=system
```

## Example result

| Check | Value |
|-------|-------|
| JSON row count | **1500** |
| `SourceFile` sample | `sec-app-logs.json` |
| `RecordFormat` | `JSON` |

## Success criteria

* JSON row count = **1500**.
* Sample row shows `SourceFile == "sec-app-logs.json"` and `RecordFormat == "JSON"`.
* If ingest fails, run `.show ingestion failures` and check the auth suffix on the URI.

---

# Lab 5 — Native CSV batch ingest from Blob

## Objective

Define a **CSV ingestion mapping** on a staging table, ingest the **firewall appliance CSV export** from Blob, and promote rows into Bronze **`SecLogsRaw`**.

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Open **`queries/05-create-csv-mapping.kql`** → run **all blocks** (staging table, CSV mapping, function, `.show` commands).
3. Open **`queries/06-ingest-csv-batch.kql`**.
4. Replace **`<storage-account>`** with Lab 2 value.
5. Confirm URI points to **`sec-web-logs.csv`** and includes **`;managed_identity=system`**.
6. Run **`.ingest into table SecLogsCsvStg`**; wait **30–60 seconds**.
7. Run `SecLogsCsvStg | count` → expected **1000**.
8. Run **`.append SecLogsRaw <| SecLogsCsvToBronze()`** to promote into Bronze.
9. Verify:

```kql
SecLogsRaw | where RecordFormat == "CSV" | count
```

## Example URI (after placeholder replace)

```text
https://stadxtcs2026tcs.blob.core.windows.net/training-data/bronze/sec-web-logs.csv;managed_identity=system
```

## Example result

| Check | Value |
|-------|-------|
| Staging row count | **1000** |
| Bronze CSV row count | **1000** |
| `SourceFile` sample | `sec-web-logs.csv` |
| AuthFailure in RawPayload | ≥ **200** |
| FirewallDeny in RawPayload | ≥ **200** |

## Success criteria

* Staging count = **1000** and Bronze CSV-labelled count = **1000**.
* Sample row shows `SourceFile == "sec-web-logs.csv"` and `RecordFormat == "CSV"`.
* You can explain **CSV ordinal mapping** on `SecLogsCsvStg` vs **JSON mapping** on `SecLogsRaw` (Lab 4).
* Combined with Lab 4, total Bronze = **2500** (verified in Lab 6).

---

# Lab 6 — Verify Bronze layer

## Objective

Validate **landed raw data** with KQL on **`SecLogsRaw`** — locked counts, lineage, and **`dynamic`** peek patterns.

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Open **`queries/07-verify-bronze.kql`**.
3. Run **Q1** through **Q5** — one block at a time (Shift+Enter).
4. Compare each result to the table below.
5. Optional: run `.show table SecLogsRaw ingestion mappings` — expect **one** JSON mapping (`SecLogsRaw_JsonMapping` from Lab 4). CSV mapping lives on **`SecLogsCsvStg`**.

## Example result

| Query | Expected result |
|-------|-----------------|
| **Q1** total count | **2500** |
| **Q2** by SourceFile | `sec-app-logs.json` / JSON / **1500**; `sec-web-logs.csv` / CSV / **1000** |
| **Q3** peek EventType | Values like `AuthFailure`, `FirewallDeny` inside `RawPayload` |
| **Q4** AuthFailure | JSON **300**, CSV **200** (Day 2 batch total **500**) |
| **Q5** time-bounded | Both formats present; sums to **2500** |

## Success criteria

* All Q1–Q5 match locked counts — do not edit KQL to force a pass.
* You can **`extend`** fields from `RawPayload` and explain why Bronze uses **`dynamic`**.

---

# Lab 7 — Pipeline checkpoint (discussion)

## Objective

Close this module by relating **Bronze `SecLogsRaw`** to **Silver `SecLogsParsed`** and **Gold `SecLogsHourly`**, and explain how **continuous streaming** feeds the same Bronze table.

## Tasks

1. Review Bronze → Silver → Gold ([README.md](README.md) Section **6.1**).
2. In your own words, explain **why Bronze uses `RawPayload` dynamic** instead of typed columns.
3. Name the Day 3 mechanism that fills Silver: **`update policy`**.
4. Name **three typed columns** Silver will expose (examples: `EventType`, `SourceIP`, `SourceSystem`).
5. Compare transports:

   | Day | Source | ADX mechanism |
   |-----|--------|---------------|
   | 2 | Blob / ADLS | **`.ingest into table`** |
   | 3 | Event Hub / IoT Hub | **Data connection** |

6. Sketch (paper or whiteboard) **Kafka → Event Hub → ADX** — architecture only.
7. Confirm Day 3 prep: Day 03 README.
8. Optional verification — Bronze still at locked counts:

```kql
SecLogsRaw | count
SecLogsRaw | summarize count() by RecordFormat
```

## Success criteria

* You can draw **Bronze → Silver → Gold** and name **update policy** for Day 3.
* You can contrast **batch Blob** vs **streaming Event Hub** without confusing them with queued vs streaming **engine**.
* You know the **Day 3 locked targets**: Bronze **3500**, Silver **3500**, AuthFailure **700**.
