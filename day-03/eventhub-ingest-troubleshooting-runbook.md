# Event Hub → ADX — E2E troubleshooting runbook

**Purpose:** Step-by-step checklist to verify one Event Hub message lands correctly in `SecLogsRaw`, and to fix **null/blank** rows.

**Live validation:** `adx-training-tcs` / `LogsDB_atin` — **2026-06-18** (maintainer account). Mapping and ingest path verified; Portal data connection and Event Hub send require appropriate RBAC in your tenant.

**Related:** [labs.md](labs.md) Lab 2 · [02-eventhub-connection.kql](queries/02-eventhub-connection.kql) · [02-verify-eventhub-mapping.kql](queries/02-verify-eventhub-mapping.kql) · [02-debug-eventhub-ingest.kql](queries/02-debug-eventhub-ingest.kql)

---

## End-to-end flow (one record)

```text
  [A] KQL prerequisites (Web UI)     [B] Portal data connection     [C] Send 1 JSON line     [D] Verify Bronze
  streaming policy + mapping    →    MULTIJSON + mapping name   →    to sec-events       →    SecLogsRaw row
  dataexplorer.azure.com             portal.azure.com                 Cloud Shell / tooling      dataexplorer.azure.com
```

**Order:** A → B (**Running**) → C → wait 30–60 s → D.

---

## Step A — Prerequisites on dataexplorer.azure.com

Database: **your** `LogsDB_<id>`.

| Step | Action | Pass criteria | Tested 2026-06-18 |
|------|--------|---------------|-------------------|
| A1 | Run [02-create-bronze-table.kql](../day-02/queries/02-create-bronze-table.kql) if `SecLogsRaw` missing | `.show tables` lists `SecLogsRaw` | PASS |
| A2 | Run [00-enable-streaming-ingest.kql](queries/00-enable-streaming-ingest.kql) | `IsEnabled: true` on streaming policy | PASS |
| A3 | Run **Step 1 only** in [02-eventhub-connection.kql](queries/02-eventhub-connection.kql) | `.show table SecLogsRaw ingestion mappings` includes **`SecLogsRaw_EventHubMapping`** | PASS |

```kql
.show table SecLogsRaw ingestion mappings
| project Name, Kind
```

Expected: **`SecLogsRaw_EventHubMapping`** with `Kind` = `Json`.

---

## Step A* — Validate mapping only (no Event Hub)

Use [02-verify-eventhub-mapping.kql](queries/02-verify-eventhub-mapping.kql) (Steps 1–3). Step 3 deletes the test row so Bronze counts stay at **2500** until class sample data arrives.

**Live test:** PASS on `LogsDB_atin` (2026-06-18).

**If Step 2 fails:** fix Step A3 mapping KQL — do not proceed to Portal until inline ingest passes.

---

## Step B — Portal data connection

**Site:** [portal.azure.com](https://portal.azure.com) → **Azure Data Explorer clusters** → **`adx-training-tcs`** → **Databases** → **your DB** → **Data ingestion** or **Data connections** → **+ Add Data Connection** → **Event Hub**.

| Setting | Required value |
|---------|----------------|
| Event Hub namespace | `eh-adx-tcs` |
| Event Hub | `sec-events` |
| Consumer group | **+ Create new** (unique per student; not `$Default`) |
| Table | `SecLogsRaw` |
| Data format | **MULTIJSON** |
| Mapping rule name | **`SecLogsRaw_EventHubMapping`** (exact) |
| Managed identity | **System-assigned** |
| Event system properties | **None** |

Wait until status = **Running**.

**Maintainer note:** Creating connections via `az kusto data-connection event-hub create` requires `Microsoft.Kusto/clusters/databases/dataConnections/write`. Students use **Portal** in class.

---

## Step C — Send one test message to Event Hub

**Sample line** (first line of `data/streaming/sec-events-sample.json`):

```json
{"EventType":"AuthFailure","SourceIP":"10.20.8.1","DestinationHost":"vpn.utility.local","UserPrincipal":"field@utility.com","Severity":"High","Message":"Streaming auth failure","Facility":"Corporate-VPN","Timestamp":"2026-06-11T09:00:00Z"}
```

### Option 1 — Portal (one message)

Event Hubs → **`eh-adx-tcs`** → **`sec-events`** → **Send events** → paste one line → **Send**.

### Option 2 — Cloud Shell (one message)

Requires permission to send to the hub.

```bash
az eventhubs eventhub send \
  --resource-group rg-adx-training-tcs \
  --namespace-name eh-adx-tcs \
  --name sec-events \
  --body '{"EventType":"AuthFailure","SourceIP":"10.20.8.1","DestinationHost":"vpn.utility.local","UserPrincipal":"field@utility.com","Severity":"High","Message":"Streaming auth failure","Facility":"Corporate-VPN","Timestamp":"2026-06-11T09:00:00Z"}'
```

If `az eventhubs eventhub send` is unavailable in your CLI version, use **Option 3** or Portal.

### Option 3 — Course CLI (full 500 or custom one-line file)

From `GH/tools` with venv, `az login`, and `.env` configured:

```bash
adx-tools adx-send-streaming eventhub
```

Uses `az eventhubs namespace authorization-rule keys list` with **`--authorization-rule-name RootManageSharedAccessKey`**.

**Important:** Send **after** Step B is **Running**. Events sent before the connection exists are not replayed for your consumer group.

---

## Step D — Verify on dataexplorer.azure.com

Wait **30–60 seconds**, then run [02-debug-eventhub-ingest.kql](queries/02-debug-eventhub-ingest.kql) or:

```kql
SecLogsRaw
| where RecordFormat == "EventHub"
| order by IngestionTime desc
| take 5
| project IngestionTime, SourceFile, RecordFormat,
          EventType = RawPayload.EventType,
          SourceIP = RawPayload.SourceIP

.show ingestion failures
| where Table == "SecLogsRaw"
| order by FailedOn desc
| take 5
```

**Pass:** New row with `SourceFile` = `sec-events`, `RecordFormat` = `EventHub`, `RawPayload.EventType` populated.

---

## Failure modes (proven on cluster)

### 1. Null / blank row — **no mapping on connection** (most common)

**Symptom:** Row count increases; `IngestionTime`, `SourceFile`, `RecordFormat` empty; `RawPayload` empty.

**Reproduced 2026-06-18** with:

```kql
.ingest inline into table SecLogsRaw with (format='multijson') <|
{"EventType":"AuthFailure",...,"Timestamp":"2026-06-11T09:00:02Z"}
```

Result: `IngestionTime` = null, `SourceFile` = `""`, `RecordFormat` = `""`.

**Fix:** Portal connection must use **`SecLogsRaw_EventHubMapping`** and **MULTIJSON**. Delete and recreate connection if the wizard used identity mapping.

---

### 2. Data present but wrong lineage — **wrong mapping name**

**Symptom:** Rows ingest; `RecordFormat` = `JSON`, `SourceFile` = `sec-app-logs.json` instead of `EventHub` / `sec-events`.

**Reproduced 2026-06-18** using `SecLogsRaw_JsonMapping` on streaming payload.

**Fix:** Event Hub connection → **`SecLogsRaw_EventHubMapping`** only.

---

### 3. Correct mapping — **inline / simulated ingest works**

**Reproduced 2026-06-18:** Step A* passes → mapping KQL is correct; problem is **Portal connection settings** or **hub send timing**.

---

### 4. Row count stays 0 after hub send

| Check | Action |
|-------|--------|
| Connection not **Running** | Wait or fix connection |
| Send before connection | Resend after **Running** |
| Wrong consumer group | Lab 2: use **new** group per student |
| No permission on hub send | Portal **Send events** or class lead send |
| Events in hub but not ADX | Confirm mapping name + MULTIJSON on connection |

---

### 5. `.show ingestion failures` entries

Filter to your database and table:

```kql
.show ingestion failures
| where Database == "LogsDB_<your-id>" and Table == "SecLogsRaw"
| order by FailedOn desc
```

Read **`Details`** — common codes: mapping not found, format errors.

---

## Quick decision tree

```text
  Inline ingest (Step A*) passes?
    NO  → Re-run 02-eventhub-connection.kql Step 1
    YES → Portal connection uses SecLogsRaw_EventHubMapping + MULTIJSON?
            NO  → Fix / recreate connection (Step B)
            YES → Sent event AFTER Running?
                    NO  → Resend (Step C)
                    YES → Wait 60s; check .show ingestion failures
```

---

## Maintainer automation log

| Step | Result | Notes |
|------|--------|-------|
| SecLogsRaw + streaming + mapping | PASS | `LogsDB_atin` |
| `.ingest inline` + correct mapping | PASS | EventType AuthFailure, SourceFile sec-events |
| `.ingest inline` without mapping | PASS (shows bug) | All lineage fields blank — matches student report |
| `.ingest inline` + JsonMapping | PASS (wrong lineage) | RecordFormat JSON, not EventHub |
| `az kusto data-connection event-hub create` | BLOCKED | Needs dataConnections/write RBAC |
| `az eventhubs ... listKeys` | BLOCKED | Needs listKeys on namespace (class lead / send tooling account) |

JSON report: `GH/tools/reports/e2e-eventhub-single-record.json`

---

## Fix checklist (student)

1. Run Step A* inline ingest — must pass.
2. Fix Portal connection (Step B table).
3. Resend one message (Step C).
4. Verify (Step D).
5. If still blank, delete connection, recreate, resend.
6. Ask class lead to confirm hub IAM for cluster managed identity (**Azure Event Hubs Data Receiver** on `eh-adx-tcs`).
