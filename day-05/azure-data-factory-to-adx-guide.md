# Azure Data Factory → Azure Data Explorer — Hands-On Runbook

**Purpose:** Follow this runbook **step by step** in the Azure Portal to build a working ADF pipeline that lands utility cyber logs in **ADX Bronze** (`SecLogsRaw`). Every command, setting, and verification is included here — you do not need other course files open while you work.

**Time:** Plan **2–3 hours** for first-time completion (including RBAC propagation waits).

**Cluster:** `adx-training-tcs` · **Region:** Central India · **Resource group:** `rg-adx-training-tcs`

---

## Lab worksheet — fill in before you start

Copy this table and replace placeholders with **your** values. Use the same values in every Portal field and KQL command below.

| Variable | Your value (example) | Where used |
|----------|----------------------|------------|
| **Subscription** | *(your Azure subscription)* | Portal top bar |
| **Resource group** | `rg-adx-training-tcs` | ADF, storage, ADX |
| **Storage account** | `stadxtcs2026tcs` | Blob paths, linked service |
| **ADX cluster URI** | `https://adx-training-tcs.centralindia.kusto.windows.net` | ADX linked service |
| **ADX database** | `LogsDB_u01` | Replace `u01` with **your** suffix |
| **ADF factory name** | `adf-adx-tcs-u01` | Must be **globally unique** |
| **Student suffix** | `u01` | Naming convention |

**Blob paths used in this lab**

| Path | Role |
|------|------|
| `training-data/adf-landing/` | Simulated **source** landing zone (you stage files here) |
| `training-data/adf-staging/` | ADF **Copy** sink — files ADF moves before ingest |
| `training-data/bronze/` | Course canonical Bronze path (reference only) |

**Locked row counts (verify against these)**

| After step | Table / filter | Expected count |
|------------|----------------|----------------|
| JSON ingest only | `SecLogsRaw` where `RecordFormat == "JSON"` | **1500** |
| CSV promoted | `SecLogsRaw` where `RecordFormat == "CSV"` | **1000** |
| Batch total | `SecLogsRaw` (batch portion only) | **2500** |

> **Re-run warning:** `.ingest` and `.append` **add rows**. If you already ingested batch data in earlier labs, counts will be **higher** than 2500. This runbook includes a **baseline count** step so you can confirm ADF added the expected **delta** (+1500 JSON, +1000 CSV).

---

## What you will build

```text
  ADF PIPELINE: PL_Bronze_Batch_Ingest

  ┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
  │ adf-landing/    │     │ adf-staging/     │     │ ADX (your LogsDB)       │
  │ sec-app-logs    │────►│ (Copy activity)  │────►│ .ingest → SecLogsRaw    │
  │ sec-web-logs    │     │ same filenames   │     │   JSON 1500             │
  └─────────────────┘     └──────────────────┘     │ CSV via SecLogsCsvStg   │
                                                    │   → SecLogsCsvToBronze  │
                                                    │   → SecLogsRaw +1000    │
                                                    └─────────────────────────┘
```

**Activities in order**

| # | Activity name | Type | Purpose |
|---|---------------|------|---------|
| 1 | `Copy_JSON_Landing_to_Staging` | Copy | Move JSON to staging path |
| 2 | `ADX_Ingest_JSON` | Azure Data Explorer command | `.ingest` JSON → `SecLogsRaw` |
| 3 | `Wait_After_JSON_Ingest` | Wait | 45 seconds for queued ingest |
| 4 | `ADX_Verify_JSON_1500` | Azure Data Explorer command | Count JSON rows (delta check) |
| 5 | `Copy_CSV_Landing_to_Staging` | Copy | Move CSV to staging path |
| 6 | `ADX_Ingest_CSV_Staging` | Azure Data Explorer command | `.ingest` → `SecLogsCsvStg` |
| 7 | `Wait_After_CSV_Ingest` | Wait | 45 seconds |
| 8 | `ADX_Promote_CSV_Bronze` | Azure Data Explorer command | `.append` via `SecLogsCsvToBronze()` |
| 9 | `Wait_After_CSV_Promote` | Wait | 30 seconds |
| 10 | `ADX_Verify_Batch_Total` | Azure Data Explorer command | Print batch totals |

---

# Phase 0 — Prerequisites (ADX Query tab)

**Where:** [dataexplorer.azure.com](https://dataexplorer.azure.com) → select cluster **`adx-training-tcs`** → select **your** database (example `LogsDB_u01`).

Run each block with **Shift+Enter** (one block at a time).

### Step 0.1 — Confirm pipeline objects exist

```kql
.show tables
| where TableName in ("SecLogsRaw", "SecLogsCsvStg", "SecLogsParsed")
| project TableName
```

**Pass:** All three table names appear. If any are missing, create them using the blocks in **Appendix A** before continuing.

### Step 0.2 — Confirm ingestion mappings exist

```kql
.show table SecLogsRaw ingestion mappings
```

**Pass:** Mapping named **`SecLogsRaw_JsonMapping`** is listed.

```kql
.show table SecLogsCsvStg ingestion mappings
```

**Pass:** Mapping named **`SecLogsCsvStg_CsvMapping`** is listed.

### Step 0.3 — Confirm promote function exists

```kql
.show function SecLogsCsvToBronze
```

**Pass:** Function body references `SecLogsCsvStg` and packs columns into `RawPayload`.

### Step 0.4 — Record baseline counts (for delta verification)

```kql
let jsonBefore = toscalar(SecLogsRaw | where RecordFormat == "JSON" | count);
let csvBefore = toscalar(SecLogsRaw | where RecordFormat == "CSV" | count);
let totalBefore = toscalar(SecLogsRaw | count);
print JsonBefore = jsonBefore, CsvBefore = csvBefore, TotalBefore = totalBefore
```

**Write down** `JsonBefore`, `CsvBefore`, and `TotalBefore`. After the ADF pipeline succeeds you expect:

- `JsonAfter = JsonBefore + 1500`
- `CsvAfter = CsvBefore + 1000`
- `TotalAfter = TotalBefore + 2500`

### Step 0.5 — Confirm cluster managed identity can read Blob (manual ingest smoke test)

Replace `<storage-account>` with your storage account name.

```kql
.ingest into table SecLogsRaw (
    h'https://<storage-account>.blob.core.windows.net/training-data/bronze/sec-app-logs.json;managed_identity=system'
)
with (format='multijson', ingestionMappingReference='SecLogsRaw_JsonMapping')
```

Wait 30 seconds, then:

```kql
SecLogsRaw | where RecordFormat == "JSON" | count
```

**Pass:** Count increased by **1500** from your Step 0.4 baseline. If this fails with **403**, ask your instructor to grant the **ADX cluster managed identity** **Storage Blob Data Reader** on the storage account before using ADF.

> **Optional:** Skip Step 0.5 if you are confident in cluster MI permissions and want ADF to be the first ingest path. If Step 0.5 succeeds, **re-run Step 0.4** to refresh baselines before the ADF pipeline test.

---

# Phase 1 — Create Azure Data Factory

### Step 1.1 — Open the creation wizard

1. Sign in to [https://portal.azure.com](https://portal.azure.com).
2. Search **Azure Data Factory** → **Create**.
3. **Basics** tab:

| Field | Value |
|-------|-------|
| Subscription | Your subscription |
| Resource group | `rg-adx-training-tcs` |
| Region | **Central India** (same region as ADX) |
| Name | `adf-adx-tcs-<suffix>` — globally unique (example: `adf-adx-tcs-u01`) |
| Version | **V2** |

4. **Git configuration:** Select **Configure Git later** (fastest for lab).
5. **Networking:** Public network access **Enabled** (training default).
6. **Review + create** → **Create**.
7. Wait until deployment completes → **Go to resource**.

### Step 1.2 — Open ADF Studio

1. On the factory overview blade, click **Open Azure Data Factory Studio**.
2. You should see the ADF home page with **Create pipeline**, **Ingest**, **Monitor**.

**Checkpoint:** Factory name appears top-left in Studio.

---

# Phase 2 — Managed identities and RBAC

ADF and ADX each use a **managed identity** (MI) — an Azure AD identity with no password. ADF’s MI must be allowed to **run commands** on your ADX database. The **ADX cluster** MI must read Blob files referenced in `.ingest` URIs (`;managed_identity=system`).

### Step 2.1 — Enable system-assigned MI on ADF

1. Azure Portal → your **Data Factory** resource (not Studio).
2. **Settings** → **Identity**.
3. **System assigned** → Status **On** → **Save** → confirm.
4. Copy the **Object (principal) ID** — label it `ADF-MI-Principal-ID`.

### Step 2.2 — Grant ADF MI permission on ADX database

**Option A — Query tab (if you have cluster admin)**

1. Open [dataexplorer.azure.com](https://dataexplorer.azure.com) → your database.
2. Run (replace principal ID):

```kql
.add database YOUR_DB_NAME admins ('aadapp=ADF-MI-Principal-ID-HERE') 'ADF pipeline managed identity'
```

Replace `YOUR_DB_NAME` with `LogsDB_u01` (your database name).  
For **Ingestor-only** (least privilege in production):

```kql
.add database YOUR_DB_NAME ingestors ('aadapp=ADF-MI-Principal-ID-HERE') 'ADF pipeline ingestor'
```

**Option B — Azure Portal**

1. ADX cluster → **Permissions** → your database → **Add**.
2. Principal: search your ADF factory name → role **Admin** (training) or **Ingestor** (production pattern).

**Wait 2–5 minutes** for Entra ID propagation.

### Step 2.3 — Grant ADF MI read access to storage (for Copy activity)

1. Portal → **Storage account** (`stadxtcs2026tcs` or yours).
2. **Access control (IAM)** → **Add role assignment**.
3. Role: **Storage Blob Data Contributor** (Copy read+write) or **Reader** if sink is elsewhere.
4. Members: **Managed identity** → **Data Factory** → select your factory.
5. **Review + assign**.

### Step 2.4 — Verify ADX cluster MI has Blob read (for `.ingest` URI)

The `.ingest` commands use **`;managed_identity=system`** — that is the **cluster’s** identity, not ADF’s.

1. Portal → **ADX cluster** `adx-training-tcs` → **Identity** → note cluster principal ID.
2. Storage account → **IAM** → confirm cluster MI has **Storage Blob Data Reader** (or Contributor).

**Checkpoint table**

| Identity | Needs | On resource |
|----------|-------|-------------|
| ADF system MI | Database **Admin** or **Ingestor** | ADX database |
| ADF system MI | **Storage Blob Data Contributor** | Storage account |
| ADX cluster MI | **Storage Blob Data Reader** | Storage account |

---

# Phase 3 — Stage source files in Blob (landing zone)

ADF Copy needs a **source** file. Simulate an on-prem drop by placing course samples in `adf-landing/`.

### Step 3.1 — Upload files via Storage Browser

1. Portal → **Storage account** → **Storage browser**.
2. **Blob containers** → `training-data` (create container if missing).
3. Create folder **`adf-landing`** (if not present).
4. Upload from your course clone (or instructor share):

| Local file | Upload to blob path |
|------------|---------------------|
| `data/bronze/sec-app-logs.json` | `training-data/adf-landing/sec-app-logs.json` |
| `data/bronze/sec-web-logs.csv` | `training-data/adf-landing/sec-web-logs.csv` |

5. Create empty folder **`adf-staging`** (ADF Copy will write here).

### Step 3.2 — Verify blobs exist

Storage Browser → confirm:

```text
training-data/adf-landing/sec-app-logs.json
training-data/adf-landing/sec-web-logs.csv
```

**Pass:** Both files show non-zero size.

---

# Phase 4 — Create linked services (ADF Studio)

Open **Azure Data Factory Studio** → **Manage** (toolbox icon) → **Linked services** → **+ New**.

### Step 4.1 — Linked service `LS_ADLS_Blob`

1. Search **Azure Blob Storage** → **Continue**.
2. Settings:

| Field | Value |
|-------|-------|
| Name | `LS_ADLS_Blob` |
| Connect via | **Azure environment** |
| Azure subscription | Your subscription |
| Storage account | Your storage account (`stadxtcs2026tcs`) |
| Authentication type | **Managed identity** |
| Managed identity | **AutoResolveIntegrationRuntime** (system-assigned factory MI) |

3. **Test connection** → **Create**.

**If test fails:** Return to Phase 2 Step 2.3 (Blob Data Contributor for ADF MI).

### Step 4.2 — Linked service `LS_ADX_Kusto`

1. **+ New** → search **Azure Data Explorer (Kusto)** → **Continue**.
2. Settings:

| Field | Value |
|-------|-------|
| Name | `LS_ADX_Kusto` |
| Connect via | **Azure environment** |
| Azure subscription | Your subscription |
| Cluster URL | `https://adx-training-tcs.centralindia.kusto.windows.net` |
| Database | `LogsDB_u01` (your database) |
| Authentication | **Managed identity** |
| Managed identity | Factory system-assigned MI |

3. **Test connection** → **Create**.

**If test fails:** Return to Phase 2 Step 2.2 (database Admin/Ingestor for ADF MI). Wait 5 minutes and retry.

**Checkpoint:** **Manage** → **Linked services** lists `LS_ADLS_Blob` and `LS_ADX_Kusto` with green status.

---

# Phase 5 — Create datasets

**Manage** → **Datasets** → **+ New**.

### Step 5.1 — `DS_Landing_Json` (Copy source)

| Field | Value |
|-------|-------|
| Type | **Binary** |
| Name | `DS_Landing_Json` |
| Linked service | `LS_ADLS_Blob` |
| File path | Container `training-data`, directory `adf-landing`, file `sec-app-logs.json` |

### Step 5.2 — `DS_Staging_Json` (Copy sink)

| Field | Value |
|-------|-------|
| Type | **Binary** |
| Name | `DS_Staging_Json` |
| Linked service | `LS_ADLS_Blob` |
| File path | Container `training-data`, directory `adf-staging`, file `sec-app-logs.json` |

### Step 5.3 — `DS_Landing_Csv`

| Field | Value |
|-------|-------|
| Type | **Binary** |
| Name | `DS_Landing_Csv` |
| Linked service | `LS_ADLS_Blob` |
| File path | `training-data` / `adf-landing` / `sec-web-logs.csv` |

### Step 5.4 — `DS_Staging_Csv`

| Field | Value |
|-------|-------|
| Type | **Binary** |
| Name | `DS_Staging_Csv` |
| Linked service | `LS_ADLS_Blob` |
| File path | `training-data` / `adf-staging` / `sec-web-logs.csv` |

**Checkpoint:** Four datasets under **Manage** → **Datasets**.

---

# Phase 6 — Build pipeline `PL_Bronze_Batch_Ingest`

**Author** → **Pipelines** → **+** → **Pipeline**.

1. Rename pipeline to **`PL_Bronze_Batch_Ingest`** (top name field).
2. **Settings** → **Parameters** → **+ New** (optional but recommended):

| Parameter name | Type | Default |
|----------------|------|---------|
| `storageAccount` | String | `stadxtcs2026tcs` |
| `jsonFileName` | String | `sec-app-logs.json` |
| `csvFileName` | String | `sec-web-logs.csv` |

---

## Activity 1 — `Copy_JSON_Landing_to_Staging`

1. **Activities** → drag **Copy data** onto canvas.
2. Name: **`Copy_JSON_Landing_to_Staging`**.

**Source tab**

| Field | Value |
|-------|-------|
| Source dataset | `DS_Landing_Json` |

**Sink tab**

| Field | Value |
|-------|-------|
| Sink dataset | `DS_Staging_Json` |
| Copy behavior | **Preserve hierarchy** |

**Settings tab**

| Field | Value |
|-------|-------|
| Enable staging | Off (files are small) |
| Fault tolerance | Skip if you want strict fail-fast (default) |

---

## Activity 2 — `ADX_Ingest_JSON`

1. Drag **Azure Data Explorer command** onto canvas.
2. Name: **`ADX_Ingest_JSON`**.
3. Connect green arrow from **Copy_JSON** → **ADX_Ingest_JSON** (on success).

**Settings**

| Field | Value |
|-------|-------|
| Linked service | `LS_ADX_Kusto` |
| Command | See below |

**Command text** (replace storage account if different):

```kql
.ingest into table SecLogsRaw (
    h'https://stadxtcs2026tcs.blob.core.windows.net/training-data/adf-staging/sec-app-logs.json;managed_identity=system'
)
with (format='multijson', ingestionMappingReference='SecLogsRaw_JsonMapping')
```

**Parameterized version** (if you added pipeline parameters):

```text
@concat(
  '.ingest into table SecLogsRaw (h''https://',
  pipeline().parameters.storageAccount,
  '.blob.core.windows.net/training-data/adf-staging/',
  pipeline().parameters.jsonFileName,
  ';managed_identity=system'') with (format=''multijson'', ingestionMappingReference=''SecLogsRaw_JsonMapping'')'
)
```

| Field | Value |
|-------|-------|
| Command timeout | `00:10:00` |

---

## Activity 3 — `Wait_After_JSON_Ingest`

1. Drag **Wait** activity.
2. Name: **`Wait_After_JSON_Ingest`**.
3. Connect from **ADX_Ingest_JSON** → **Wait**.
4. **Wait time:** `45` seconds.

Queued ingest is asynchronous — do not skip this wait on first run.

---

## Activity 4 — `ADX_Verify_JSON_1500`

1. Drag **Azure Data Explorer command**.
2. Name: **`ADX_Verify_JSON_1500`**.
3. Connect from **Wait** → **Verify**.

| Field | Value |
|-------|-------|
| Linked service | `LS_ADX_Kusto` |
| Command type | **Query** (if available) or **Control command** with query |

**Query:**

```kql
SecLogsRaw
| where RecordFormat == "JSON"
| count
```

**Note:** ADF may display the scalar result in activity output. Compare to **JsonBefore + 1500** from Phase 0.

---

## Activity 5 — `Copy_CSV_Landing_to_Staging`

Same pattern as Activity 1:

| Field | Value |
|-------|-------|
| Source | `DS_Landing_Csv` |
| Sink | `DS_Staging_Csv` |

Connect from **ADX_Verify_JSON_1500** → **Copy_CSV** (sequential batch path).

---

## Activity 6 — `ADX_Ingest_CSV_Staging`

| Field | Value |
|-------|-------|
| Name | `ADX_Ingest_CSV_Staging` |
| Linked service | `LS_ADX_Kusto` |

**Command:**

```kql
.ingest into table SecLogsCsvStg (
    h'https://stadxtcs2026tcs.blob.core.windows.net/training-data/adf-staging/sec-web-logs.csv;managed_identity=system'
)
with (format='csv', ingestionMappingReference='SecLogsCsvStg_CsvMapping', ignoreFirstRecord=true)
```

**Critical:** Mapping name is **`SecLogsCsvStg_CsvMapping`** (not `SecLogsCsvMapping`). **`ignoreFirstRecord=true`** skips the CSV header row.

---

## Activity 7 — `Wait_After_CSV_Ingest`

**Wait time:** `45` seconds.

---

## Activity 8 — `ADX_Promote_CSV_Bronze`

CSV rows land in **staging** first. Promote to Bronze with the course function:

**Command:**

```kql
.append SecLogsRaw <| SecLogsCsvToBronze()
```

This matches the manual lab pattern: typed CSV columns → dynamic `RawPayload` with `RecordFormat = 'CSV'`.

---

## Activity 9 — `Wait_After_CSV_Promote`

**Wait time:** `30` seconds.

---

## Activity 10 — `ADX_Verify_Batch_Total`

**Query:**

```kql
print
    JsonRows = toscalar(SecLogsRaw | where RecordFormat == "JSON" | count),
    CsvRows = toscalar(SecLogsRaw | where RecordFormat == "CSV" | count),
    TotalRows = toscalar(SecLogsRaw | count)
```

Compare to Phase 0 baselines + **1500** / **1000** / **2500**.

### Step 6.1 — Validate pipeline canvas

```text
  Copy_JSON → ADX_Ingest_JSON → Wait → ADX_Verify_JSON
       → Copy_CSV → ADX_Ingest_CSV → Wait → ADX_Promote → Wait → ADX_Verify_Total
```

1. **Validate** (toolbar) → fix any errors.
2. **Publish all** (toolbar) → confirm.

**Checkpoint:** Pipeline published without validation errors.

---

# Phase 7 — Test run and monitor

### Step 7.1 — Debug run

1. Open **`PL_Bronze_Batch_Ingest`**.
2. Click **Debug** (triggers one-off run with debug settings).
3. Open **Output** tab → click each activity → review **input/output**.

| Activity | Healthy signal |
|----------|----------------|
| `Copy_JSON_*` | `rowsCopied` > 0 |
| `ADX_Ingest_JSON` | Status Succeeded; no permission error |
| `ADX_Verify_JSON_1500` | Count increased by 1500 |
| `Copy_CSV_*` | `rowsCopied` > 0 |
| `ADX_Ingest_CSV_Staging` | Succeeded |
| `ADX_Promote_CSV_Bronze` | Succeeded |
| `ADX_Verify_Batch_Total` | Json/Csv/Total match expected |

### Step 7.2 — ADF Monitor

1. **Monitor** → **Pipeline runs**.
2. Click the latest run → **Activity runs** → open failed activity **if any**.
3. Read **Error** message — map to **Phase 9 troubleshooting**.

### Step 7.3 — ADX verification (Query tab)

Run as one block:

```kql
print
    JsonRows = toscalar(SecLogsRaw | where RecordFormat == "JSON" | count),
    CsvRows = toscalar(SecLogsRaw | where RecordFormat == "CSV" | count),
    TotalRows = toscalar(SecLogsRaw | count),
    StagingRows = toscalar(SecLogsCsvStg | count)
```

```kql
.show ingestion failures
| where Table in ("SecLogsRaw", "SecLogsCsvStg")
| order by StartedOn desc
| take 5
```

**Pass:**

- No new failures (or failures predating your run).
- JSON and CSV counts match your baseline + 1500 / + 1000.

### Step 7.4 — Confirm Silver update policy still works (optional)

If your database already had Day 3 update policy:

```kql
SecLogsParsed | count
```

Silver may be **3500 + delta** if policy applied to new Bronze rows. For ADF-only batch test on a fresh database, Silver follows Bronze promotion automatically.

---

# Phase 8 — Schedule trigger (optional)

### Step 8.1 — Create schedule

1. **Author** → **Triggers** → **+ New**.
2. Type: **Schedule**.
3. Name: `TR_Nightly_Bronze_Ingest`.
4. Start date/time: tomorrow 01:00 UTC (example).
5. Recurrence: **Every 1 Day**.
6. Associate pipeline: **`PL_Bronze_Batch_Ingest`**.
7. **Publish all**.

### Step 8.2 — Production guardrails before scheduling

| Guardrail | Why |
|-----------|-----|
| Parameterize blob paths with **date folder** | Avoid overwriting same staging file |
| Add **If Condition** on file existence | Skip empty nights |
| Alert on **failure** in Azure Monitor | SOC data gap detection |
| Document **idempotency** | `.ingest` appends — nightly reruns duplicate unless you partition by date or use replace policy |

---

# Phase 9 — Troubleshooting runbook

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Copy activity **403** | ADF MI lacks Blob RBAC | Phase 2 Step 2.3 — **Storage Blob Data Contributor** |
| ADX command **403** / unauthorized | ADF MI not on database | Phase 2 Step 2.2 — **Admin** or **Ingestor**; wait 5 min |
| `.ingest` **403** on blob URI | **Cluster** MI lacks Blob read | Phase 2 Step 2.4 — cluster MI **Blob Data Reader** |
| Ingest succeeds, **0 rows** | Wrong `format` or mapping name | JSON: `multijson` + `SecLogsRaw_JsonMapping`; CSV: `SecLogsCsvStg_CsvMapping` |
| CSV all rows shifted / null | Header not skipped | Add `ignoreFirstRecord=true` |
| CSV in staging, Bronze CSV **0** | Promote step missing | Run Activity 8: `.append SecLogsRaw <| SecLogsCsvToBronze()` |
| Verify count too low | Wait too short | Increase Wait activities to 60–90 s |
| Verify count too high | Pipeline rerun | Expected — `.ingest` appends; record baselines |
| Linked service test fails | Wrong database name | Match **your** `LogsDB_<suffix>` exactly |
| `SecLogsCsvToBronze` not found | Function not created | Appendix A Step A.3 |
| Mapping not found | Typo in mapping reference | `.show table SecLogsRaw ingestion mappings` |

### Diagnostic commands (Query tab)

```kql
.show ingestion failures
```

```kql
.show operations
| where Operation == "DataIngestion"
| top 10 by StartedOn desc
```

```kql
.show table SecLogsRaw ingestion mappings
```

```kql
.show table SecLogsCsvStg ingestion mappings
```

```kql
SecLogsCsvStg | take 5
```

---

# Phase 10 — Success criteria checklist

Print and mark each item when complete.

| # | Criterion | Done? |
|---|-----------|-------|
| 1 | ADF factory created in `rg-adx-training-tcs` | ☐ |
| 2 | System-assigned MI enabled on ADF | ☐ |
| 3 | ADF MI has ADX database **Admin** or **Ingestor** | ☐ |
| 4 | ADF MI has **Storage Blob Data Contributor** | ☐ |
| 5 | ADX cluster MI has **Storage Blob Data Reader** on storage | ☐ |
| 6 | Landing blobs uploaded to `adf-landing/` | ☐ |
| 7 | Linked services `LS_ADLS_Blob` + `LS_ADX_Kusto` test OK | ☐ |
| 8 | Four datasets created | ☐ |
| 9 | Pipeline `PL_Bronze_Batch_Ingest` published | ☐ |
| 10 | Debug run — all activities **Succeeded** | ☐ |
| 11 | JSON rows increased by **1500** vs baseline | ☐ |
| 12 | CSV rows increased by **1000** vs baseline | ☐ |
| 13 | `.show ingestion failures` — no new errors | ☐ |
| 14 | Can explain **Copy → .ingest → wait → verify** pattern | ☐ |

---

# Appendix A — Create ADX objects (if Phase 0 failed)

Run in **your** database if tables/mappings are missing.

### A.1 — Bronze table

```kql
.create table SecLogsRaw (
    IngestionTime: datetime,
    SourceFile: string,
    RecordFormat: string,
    RawPayload: dynamic
)
```

### A.2 — JSON mapping

```kql
.create-or-alter table SecLogsRaw ingestion json mapping 'SecLogsRaw_JsonMapping' '[{"column":"IngestionTime","properties":{"path":"$.Timestamp"}},{"column":"SourceFile","properties":{"ConstValue":"sec-app-logs.json"}},{"column":"RecordFormat","properties":{"ConstValue":"JSON"}},{"column":"RawPayload","properties":{"path":"$"}}]'
```

### A.3 — CSV staging table, mapping, promote function

```kql
.create-merge table SecLogsCsvStg (
    Timestamp: datetime,
    EventType: string,
    SourceIP: string,
    DestinationHost: string,
    UserPrincipal: string,
    Severity: string,
    Message: string,
    Facility: string
)

.create-or-alter table SecLogsCsvStg ingestion csv mapping 'SecLogsCsvStg_CsvMapping' '[{"column":"Timestamp","Properties":{"Ordinal":"0"}},{"column":"EventType","Properties":{"Ordinal":"1"}},{"column":"SourceIP","Properties":{"Ordinal":"2"}},{"column":"DestinationHost","Properties":{"Ordinal":"3"}},{"column":"UserPrincipal","Properties":{"Ordinal":"4"}},{"column":"Severity","Properties":{"Ordinal":"5"}},{"column":"Message","Properties":{"Ordinal":"6"}},{"column":"Facility","Properties":{"Ordinal":"7"}}]'

.create-or-alter function SecLogsCsvToBronze() {
    SecLogsCsvStg
    | extend RawPayload = pack(
        'Timestamp', Timestamp,
        'EventType', EventType,
        'SourceIP', SourceIP,
        'DestinationHost', DestinationHost,
        'UserPrincipal', UserPrincipal,
        'Severity', Severity,
        'Message', Message,
        'Facility', Facility)
    | project IngestionTime = Timestamp, SourceFile = 'sec-web-logs.csv', RecordFormat = 'CSV', RawPayload
}
```

---

# Appendix B — Azure CLI RBAC (alternative to Portal IAM)

Replace placeholders and run in Cloud Shell or local Azure CLI (`az login` first).

```bash
# Variables — set these
SUBSCRIPTION="<your-subscription-id>"
RG="rg-adx-training-tcs"
STORAGE="stadxtcs2026tcs"
ADF_NAME="adf-adx-tcs-u01"
ADX_CLUSTER="adx-training-tcs"

az account set --subscription "$SUBSCRIPTION"

# ADF system-assigned principal ID
ADF_PRINCIPAL=$(az datafactory show -g "$RG" -n "$ADF_NAME" --query identity.principalId -o tsv)
echo "ADF principal: $ADF_PRINCIPAL"

# Storage scope
STORAGE_ID=$(az storage account show -g "$RG" -n "$STORAGE" --query id -o tsv)

# Grant ADF MI Blob Contributor on storage
az role assignment create \
  --assignee "$ADF_PRINCIPAL" \
  --role "Storage Blob Data Contributor" \
  --scope "$STORAGE_ID"

# ADX cluster MI — Blob Reader (for ;managed_identity=system on ingest URI)
CLUSTER_PRINCIPAL=$(az kusto cluster show -g "$RG" -n "$ADX_CLUSTER" --query identity.principalId -o tsv)
az role assignment create \
  --assignee "$CLUSTER_PRINCIPAL" \
  --role "Storage Blob Data Reader" \
  --scope "$STORAGE_ID"
```

Database role for ADF MI is easiest via Query tab `.add database ...` (Phase 2 Step 2.2).

---

# Appendix C — Quick reference — KQL used in pipeline

### JSON ingest (from `adf-staging`)

```kql
.ingest into table SecLogsRaw (
    h'https://<storage-account>.blob.core.windows.net/training-data/adf-staging/sec-app-logs.json;managed_identity=system'
)
with (format='multijson', ingestionMappingReference='SecLogsRaw_JsonMapping')
```

### CSV ingest (staging table)

```kql
.ingest into table SecLogsCsvStg (
    h'https://<storage-account>.blob.core.windows.net/training-data/adf-staging/sec-web-logs.csv;managed_identity=system'
)
with (format='csv', ingestionMappingReference='SecLogsCsvStg_CsvMapping', ignoreFirstRecord=true)
```

### CSV promote to Bronze

```kql
.append SecLogsRaw <| SecLogsCsvToBronze()
```

### Verify

```kql
SecLogsRaw
| summarize Json = countif(RecordFormat == "JSON"), Csv = countif(RecordFormat == "CSV"), Total = count()
```

---

## Summary

| Question | Answer |
|----------|--------|
| **What did you build?** | ADF pipeline: Copy landing → staging → ADX `.ingest` → verify |
| **Which identity reads Blob in `.ingest`?** | **ADX cluster** MI (`;managed_identity=system`) |
| **Which identity runs ADF commands?** | **ADF factory** system-assigned MI |
| **Correct JSON mapping name?** | **`SecLogsRaw_JsonMapping`** |
| **Correct CSV mapping name?** | **`SecLogsCsvStg_CsvMapping`** with `ignoreFirstRecord=true` |
| **How does CSV reach Bronze?** | `SecLogsCsvStg` → `.append SecLogsRaw <| SecLogsCsvToBronze()` |
| **Expected batch delta?** | **+1500** JSON, **+1000** CSV per successful full run |
| **Does ADF replace update policy / Gold MV?** | **No** — ADX handles Silver/Gold after Bronze lands |

Azure Data Factory orchestrates **when** and **from where** files move. Azure Data Explorer controls **how** data is stored and queried. This runbook connects both into the enterprise batch path used in utility cyber log platforms.
