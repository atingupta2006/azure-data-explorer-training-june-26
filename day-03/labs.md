# Day 03 — Labs

**Theme:** Streaming Ingestion, IoT Hub & Silver Layer

**Database:** Same as Day 1 — **your database** on the shared cluster `adx-training-tcs` (example: **`LogsDB_u01`**).

**Prerequisite:** `SecLogsRaw` from Day 2 with **2500** batch rows **in your database**.

**Theory:** [README.md](README.md) · [policies-guide.md](policies-guide.md) (Labs 4–5)

> **Run order:** Labs **1 → 2 → 3 → 8 → 4 → 5 → 9 → 6 → 7**. Labs **8** (Bronze telemetry) and **9** (Silver telemetry) are numbered 8–9 but run **in the middle** of the pipeline — not last.

---

## Where to work (two sites)

Day 3 uses **two different websites**. Do not look for data connections on [dataexplorer.azure.com](https://dataexplorer.azure.com) — create them only in **Azure Portal** on the ADX cluster.

| Task | Site | URL |
|------|------|-----|
| Run KQL (mappings, policies, counts, Silver labs) | **ADX Web UI** | [dataexplorer.azure.com](https://dataexplorer.azure.com) |
| Create **data connections** (Labs 2–3) | **Azure Portal** (ADX cluster → **Databases** → your DB) | [portal.azure.com](https://portal.azure.com) |
| Event Hub / IoT Hub setup (class lead demo) | **Azure Portal** | [portal.azure.com](https://portal.azure.com) |
| Optional: open Query from Portal | Portal → cluster → **Open in Web UI** | Opens dataexplorer.azure.com Query tab |

```text
  dataexplorer.azure.com              portal.azure.com (ADX cluster blade)
  ─────────────────────              ───────────────────────────────────
  Query tab + .kql files        |    Databases → YOUR DB → Data ingestion
  Mappings, policies            |         or Data connections (same area)
  Verify SecLogsRaw counts        |    + Add Data Connection
                                  |    Check status = Running
```

Microsoft docs: [Event Hub connection (Portal)](https://learn.microsoft.com/en-us/azure/data-explorer/create-event-hubs-connection?tabs=portal-adx) · [IoT Hub connection (Portal)](https://learn.microsoft.com/en-us/azure/data-explorer/create-iot-hub-connection?tabs=portal)

---

## Working in the Query tab (dataexplorer.azure.com)

1. Select **your** `LogsDB_<id>` in the database dropdown (toolbar and left pane must match).
2. Open the `.kql` file for the lab in `queries/`.
3. Run **one block at a time** with **Shift+Enter**.
4. Compare your results to the **Example result** table for that lab.

Lab 1 is a gate check — do not continue if Bronze ≠ **2500**.

---

## Troubleshooting

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| Lab 1 Bronze ≠ **2500** | Day 2 ingest incomplete | Finish Day 2 Labs 4–5, then re-run Lab 1 |
| EventHub or IoT count stays **0** | Wrong order, connection not **Running**, or sample data not sent yet | Mapping → Portal connection **Running** → class sends sample → wait 30–60 s → rerun count |
| Wrong consumer group | Lab 2: reused `$Default` or another student's group. Lab 3: created new instead of **`adx`** | See [Before Labs 2–3 — Consumer group](labs.md#consumer-group--what-to-pick-in-the-portal-form) |
| Cannot find data connections on dataexplorer.azure.com | Data connections are only in **Azure Portal** on the ADX cluster | [portal.azure.com](https://portal.azure.com) → **Azure Data Explorer clusters** → **`adx-training-tcs`** → **Databases** → **your** `LogsDB_<id>` → **Data ingestion** or **Data connections** → **+ Add Data Connection** (Lab 2 step 5) |
| Connection status **Failed** | Wrong hub name or permissions | Match the lab table; report in class |
| `SecLogsParsed` count = **0** after Lab 5 Step 1 | Backfill not run | Run Lab 5 **Step 2** (`.set-or-append` block) |
| Silver &lt; Bronze after streaming | Backfill ran before all Bronze rows arrived | Re-run Lab 5 Step 2 after Labs 2–3 complete |
| `.alter ... policy update` fails | Command split across lines | Paste Step 1 as **one** line ([policies-guide.md](policies-guide.md) §5.5) |
| Event Hub rows **inserted but null/blank** | Wrong **mapping** or **data format** on Portal connection; or querying **Silver** before Lab 5 | [eventhub-ingest-troubleshooting-runbook.md](eventhub-ingest-troubleshooting-runbook.md) · [02-debug-eventhub-ingest.kql](queries/02-debug-eventhub-ingest.kql) |

### Debug Event Hub rows null or blank {#debug-event-hub-rows-null-or-blank}

**Full E2E runbook (step-by-step):** [eventhub-ingest-troubleshooting-runbook.md](eventhub-ingest-troubleshooting-runbook.md)

**Quick mapping test** (no Event Hub) — run on dataexplorer.azure.com:

Open [queries/02-verify-eventhub-mapping.kql](queries/02-verify-eventhub-mapping.kql) (Steps 1–3). Step 3 removes the test row so Bronze stays **2500** until class sample data arrives.

Or paste Step 1 only:

```kql
.ingest inline into table SecLogsRaw with (format='multijson', ingestionMappingReference='SecLogsRaw_EventHubMapping') <|
{"EventType":"AuthFailure","SourceIP":"10.20.8.99","DestinationHost":"vpn.utility.local","UserPrincipal":"lab-verify@utility.com","Severity":"High","Message":"ADX Lab 2 mapping verify — safe to delete","Facility":"Corporate-VPN","Timestamp":"2026-06-11T08:59:59Z"}
```

If Step 2 in that file shows `RecordFormat` = `EventHub` and `SourceIP` = `10.20.8.99`, your mapping is correct — fix the **Portal data connection** (MULTIJSON + mapping name).

**Yes — null rows are almost always mapping or data format on the Portal connection**, not Event Hub delivery.

**First check — are you on Bronze?**

`SecLogsRaw` has only **four** columns: `IngestionTime`, `SourceFile`, `RecordFormat`, `RawPayload`. Fields like `EventType` and `SourceIP` live **inside** `RawPayload` until Lab 5 Silver. Query:

```kql
SecLogsRaw
| where RecordFormat == "EventHub"
| take 3
| project IngestionTime, SourceFile, RecordFormat, EventType = RawPayload.EventType, SourceIP = RawPayload.SourceIP
```

**Run diagnostics:** [queries/02-debug-eventhub-ingest.kql](queries/02-debug-eventhub-ingest.kql) (Q1–Q5).

| What you see | Likely cause | Fix |
|--------------|--------------|-----|
| Row count up; `RecordFormat` and `SourceFile` **empty** | Connection not using **`SecLogsRaw_EventHubMapping`** (identity / wrong name / wizard mapping) | Portal → edit or **delete and recreate** connection — see Lab 2 field table |
| `RecordFormat` = `EventHub`, `SourceFile` = `sec-events`, but **`RawPayload` empty** | **Data format** not **MULTIJSON**; or message body is not a JSON object | Connection: **MULTIJSON** + mapping `SecLogsRaw_EventHubMapping`; resend sample after fix |
| `RecordFormat` = `JSON` instead of `EventHub` | Connection used **`SecLogsRaw_JsonMapping`** (Day 2) | Use **`SecLogsRaw_EventHubMapping`** only for Event Hub connection |
| Batch JSON rows OK; Event Hub rows blank | Mapping KQL not run in **your** database before connect | Re-run **Step 1** in `02-eventhub-connection.kql`, then fix connection |
| `.show ingestion failures` has errors | Format/mapping mismatch | Read `Details` column; fix format/mapping; resend |

**Portal connection must match exactly (Lab 2 step 5):**

| Setting | Required value |
|---------|----------------|
| Table | `SecLogsRaw` |
| Data format | **MULTIJSON** (not JSON, CSV, or TXT) |
| Mapping rule name | **`SecLogsRaw_EventHubMapping`** (exact spelling) |
| Event system properties | **None** selected (unless you extend the mapping) |

**Fix workflow**

1. On **dataexplorer.azure.com**: run Step 1 in `02-eventhub-connection.kql` again, then [02-verify-eventhub-mapping.kql](queries/02-verify-eventhub-mapping.kql) Steps 1–2 → mapping must pass before Portal.
2. On **Portal**: open your Event Hub data connection → confirm table, **MULTIJSON**, and mapping name above. If wrong, delete the connection and create a new one (or edit if Portal allows).
3. Wait until connection is **Running**.
4. **Resend** sample events (connection only reads events that arrive **after** it exists): [send reference](#lab-2-reference-send-sec-events-samplejson-event-hub).
5. Wait 30–60 s → run Q1 in `02-debug-eventhub-ingest.kql` → `EventType` should show values like `AuthFailure`, `VPNLogin`.

**Good row example:**

| IngestionTime | SourceFile | RecordFormat | RawPayload.EventType |
|---------------|------------|--------------|----------------------|
| 2026-06-11T09:00:00Z | sec-events | EventHub | AuthFailure |

---

## Expected outcomes

```text
  DAY 3 PIPELINE + TELEMETRY LABS

  Lab 1  Bronze gate (2500)
  Lab 2  Event Hub (+500 → 3000)
  Lab 3  IoT Hub (+500 → 3500)
  Lab 8  Analyze IoT on Bronze ◄── telemetry (deviceId in RawPayload)
  Lab 4  Create SecLogsParsed
  Lab 5  Update policy + backfill (3500 Silver)
  Lab 9  Analyze IoT on Silver ◄── telemetry (SourceSystem = IoT-Hub)
  Lab 6  Kafka / Logstash (discussion)
  Lab 7  Silver investigation
```

| After lab | Check |
|-----------|--------|
| Lab 1 | Bronze = **2500** |
| Lab 2 | Bronze = **3000**; EventHub = **500** |
| Lab 3 | Bronze = **3500**; IoT = **500** |
| Lab 8 | IoT EventType: SensorAnomaly **200**; devices **200/200/100** |
| Lab 4 | `SecLogsParsed` exists; row count **0** |
| Lab 5 | Silver = **3500** |
| Lab 9 | IoT-Hub = **500**; OT substations **400** rows in Q5 |
| Lab 7 Q1 | AuthFailure = **700** |
| Lab 7 Q5 | `dcount(SourceSystem)` = **4** |

---

# Lab 1 — Verify Bronze baseline

## Objective

Confirm **Day 2 batch data** is present in **`SecLogsRaw`** before streaming and Silver labs — gate check for locked counts.

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Open **`queries/01-verify-bronze-baseline.kql`**.
3. Run **both query blocks** separately.
4. Record results — compare to locked values below.
5. If total ≠ **2500**, complete Day 2 Labs 4–5 before Labs 2–7.

## Example result

| Query | Expected |
|-------|----------|
| `SecLogsRaw \| count` | **2500** |
| `RecordFormat == "JSON"` (from summarize) | **1500** — `sec-app-logs.json` |
| `RecordFormat == "CSV"` (from summarize) | **1000** — `sec-web-logs.csv` |

## Success criteria

* Total count = **2500**; JSON **1500** + CSV **1000**.
* You can name the **four Bronze columns** and explain why `RawPayload` is `dynamic`.

---

# Before Labs 2–3

**Day 2:** files in blob storage → you ran **`.ingest`** → rows in `SecLogsRaw`.

**Labs 2–3:** JSON events go to **Event Hub** or **IoT Hub** (Azure services that receive live events). ADX reads those events through a **data connection** you create in **Azure Portal** (not on dataexplorer.azure.com).

The class lead sets up Event Hub and IoT Hub in Azure Portal (steps below) and sends the sample data. **You** run mapping KQL on **dataexplorer.azure.com**, create the data connection in **Azure Portal**, then verify counts back in the Web UI.

```text
  Lab 2:  sample JSON  →  Event Hub (sec-events)   →  ADX data connection (Portal)  →  SecLogsRaw (Web UI queries)
  Lab 3:  sample JSON  →  IoT Hub (iot-adx-tcs)    →  ADX data connection (Portal)  →  SecLogsRaw (Web UI queries)
```

| Who | What | Where |
|-----|------|-------|
| Class lead | Create hubs, grant ADX access, send **500** sample messages when your connection is **Running** | **Azure Portal** |
| You | Streaming policy, mapping KQL, verify counts | **dataexplorer.azure.com** |
| You | **Data connection** (Labs 2–3) | **Azure Portal** → **`adx-training-tcs`** → **Databases** → your DB → **Data ingestion** or **Data connections** |

**Order:** mapping → connection **Running** → raise your hand → class sends sample → wait 30–60 s → verify.

### Consumer group — what to pick in the Portal form

A **consumer group** is a named reader slot on the hub. ADX uses it to read messages for **your** data connection. Labs 2 and 3 differ:

| Lab | Hub | What you do in the ADX connection form |
|-----|-----|----------------------------------------|
| **Lab 2** (Event Hub) | `sec-events` | **Create a new group** for yourself — Portal adds it on the hub when you save. Do **not** pick `$Default` or another student's group. |
| **Lab 3** (IoT Hub) | `iot-adx-tcs` | **Select existing `adx`** — class lead created it on **Built-in endpoints → Events**. Do **not** create a new group. |

## Event Hub — class lead creates (before Lab 2)

Watch this demo in Portal, or read the steps. In class the resources usually already exist.

1. [Azure Portal](https://portal.azure.com) → **Create a resource** → **Event Hubs**.
2. Resource group **`rg-adx-training-tcs`**. Namespace name **`eh-adx-tcs`**. Same region as ADX. Pricing tier **Standard** → **Create**.
3. Open namespace **`eh-adx-tcs`** → **Event Hubs** → **+ Event Hub** → name **`sec-events`** → **Create**.
4. Namespace → **Access control (IAM)** → **Add role assignment** → role **Azure Event Hubs Data Receiver** → member **`adx-training-tcs`** (managed identity) → **Save**.
5. **Azure Data Explorer clusters** → **`adx-training-tcs`** → **Configurations** → **Streaming ingestion** = **On**.
6. **Optional demo — send one test event** (class lead; shows how events enter Event Hub before the full **500**-line send):

   1. Portal → **Event Hubs** → namespace **`eh-adx-tcs`** → open hub **`sec-events`**.
   2. Open **Send events** (under **Features** or the hub toolbar — wording varies by Portal version).
   3. Open `data/streaming/sec-events-sample.json` in the repo. Copy **one full line** only (one JSON object). Example first line:

   ```json
   {"EventType":"AuthFailure","SourceIP":"10.20.8.1","DestinationHost":"vpn.utility.local","UserPrincipal":"field@utility.com","Severity":"High","Message":"Streaming auth failure","Facility":"Corporate-VPN","Timestamp":"2026-06-11T09:00:00Z"}
   ```

   4. Paste into the **Event** / **Message** box. Set **Content type** to `application/json` if the form asks for it.
   5. Click **Send** (or **Send events**).
   6. After a student ADX data connection is **Running**, one row can appear in `SecLogsRaw` with `RecordFormat == "EventHub"`. The lab checkpoint is **500** rows after the full sample send (next section).

## IoT Hub — class lead creates (before Lab 3)

1. Portal → **Create a resource** → **IoT Hub** → name **`iot-adx-tcs`**, resource group **`rg-adx-training-tcs`** → **Create**.
2. IoT Hub → **Devices** → **Add device** for **`substation-sensor-01`**, **`substation-sensor-02`**, **`substation-sensor-03`**.
3. **Built-in endpoints** → **Events** → **Consumer groups** → add **`adx`** (Lab 3 ADX form uses this name).
4. No extra IAM step is required for students — the IoT connection form uses the built-in shared access policy **`iothubowner`** (read permission on the hub).
5. **Optional demo — send one test message** (class lead; device-to-cloud, not cloud-to-device):

   1. Portal → **Cloud Shell** (top bar) → **Bash**.
   2. Run (one line from the sample file as `--data`):

   ```bash
   az iot device send-d2c-message --hub-name iot-adx-tcs --device-id substation-sensor-01 --data '{"deviceId":"substation-sensor-01","EventType":"SensorAnomaly","SourceIP":"10.20.9.10","DestinationHost":"iot-gateway.utility.local","UserPrincipal":"","Severity":"High","Message":"Temperature spike near access panel","Facility":"Substation-C","Timestamp":"2026-06-11T09:00:00Z"}'
   ```

   3. Or copy any single line from `data/iot/device-telemetry.json` into the `--data` value.
   4. After a student ADX data connection is **Running** (consumer group **`adx`**), one IoT row may appear. The lab checkpoint is **500** rows after the full sample send (next section).

## Send sample file → hub (in class + reference for later)

### During Labs 2–3 in class

**You do not run the full send in class.** When your ADX data connection is **Running**, raise your hand. The class lead sends all **500** lines, then you wait **30–60 seconds** and run the verify queries in your lab.

| Lab | Sample file (in repo) | Destination |
|-----|------------------------|-------------|
| Lab 2 | `data/streaming/sec-events-sample.json` | Event Hub **`sec-events`** |
| Lab 3 | `data/iot/device-telemetry.json` | IoT Hub **`iot-adx-tcs`** |

Use the steps below **after class** to practice on your own (sandbox subscription, or when you have hub + ADX permissions).

### End-to-end flow (class demonstration)

```text
  Lab 2
  ─────
  sec-events-sample.json     Azure CLI / tooling          Event Hub           ADX data          SecLogsRaw
  (500 JSON lines,           sends each line as one  →    eh-adx-tcs /   →    connection   →    +500 rows
   one object per line)       event to the hub              sec-events          (Portal)          RecordFormat=EventHub

  Lab 3
  ─────
  device-telemetry.json      Azure CLI sends one     →    IoT Hub        →    ADX data          SecLogsRaw
  (500 JSON lines; each       device-to-cloud msg         iot-adx-tcs         connection        +500 rows
   line has deviceId)         per line                                        (Portal)          RecordFormat=IoT
```

**Order that must not change:** mapping KQL → ADX connection **Running** → **then** send file to hub → wait 30–60 s → verify counts.

Messages that arrive **before** your connection exists are not replayed for your consumer group — send again after **Running** if needed.

### Before you send (checklist)

| Check | Lab 2 | Lab 3 |
|-------|-------|-------|
| Hub exists | `eh-adx-tcs` / `sec-events` | `iot-adx-tcs` |
| ADX connection | **Running** on **your** database | **Running** on **your** database |
| Azure sign-in | `az login` (same tenant as hubs) | Same |
| File format | NDJSON — **one JSON object per line** | Same |
| IoT devices | — | `substation-sensor-01`, `-02`, `-03` on the hub |

---

### Lab 2 reference — send `sec-events-sample.json` → Event Hub {#lab-2-reference-send-sec-events-samplejson-event-hub}

**File:** `GH/data/streaming/sec-events-sample.json` (**500** lines)  
**Target:** namespace **`eh-adx-tcs`**, hub **`sec-events`**

#### Option A — Course CLI (full **500** messages; same as class demo)

From a machine with the training repo, Python 3, and [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli):

```bash
cd GH/tools
python -m venv .venv
source .venv/Scripts/activate    # Windows Git Bash; use .venv/bin/activate on Linux/macOS
pip install -e .
az login
```

Copy `GH/tools/.env.example` → `GH/tools/.env` and set at least:

| Variable | Value |
|----------|-------|
| `ADX_EVENTHUB_NAMESPACE` | `eh-adx-tcs` |
| `ADX_EVENTHUB_NAME` | `sec-events` |
| `ADX_RESOURCE_GROUP` | `rg-adx-training-tcs` |

Send:

```bash
adx-tools adx-send-streaming eventhub
```

Success: JSON output includes `"pass": true` and `"messages_sent": 500`.

**What it does:** reads each line from the sample file and sends all lines in one batch to **`sec-events`** using the Event Hub namespace connection string (via `az eventhubs namespace authorization-rule keys list`).

#### Option B — Azure Cloud Shell (full **500**; no local Python venv)

1. [portal.azure.com](https://portal.azure.com) → **Cloud Shell** → **Bash**.
2. Upload `sec-events-sample.json` to Cloud Shell (or clone the training repo).
3. Run:

```bash
RG=rg-adx-training-tcs
NS=eh-adx-tcs
HUB=sec-events
SAMPLE=sec-events-sample.json   # path to your uploaded file

CONN=$(az eventhubs namespace authorization-rule keys list \
  -g "$RG" --namespace-name "$NS" --authorization-rule-name RootManageSharedAccessKey \
  --query primaryConnectionString -o tsv)

pip install azure-eventhub -q

python3 << PY
from azure.eventhub import EventData, EventHubProducerClient
from pathlib import Path

conn = """$CONN"""
hub = "$HUB"
lines = [ln.strip() for ln in Path("$SAMPLE").read_text().splitlines() if ln.strip()]
client = EventHubProducerClient.from_connection_string(conn, eventhub_name=hub)
batch = client.create_batch()
for line in lines:
    batch.add(EventData(line))
with client:
    client.send_batch(batch)
print(f"Sent {len(lines)} events to {hub}")
PY
```

You need **Event Hubs Data Sender** (or equivalent) on the namespace to read the connection string and send.

#### Option C — Portal (one message only — demo)

See **Event Hub — class lead creates** → optional **Send events** above. Use this to see how **one** line enters the hub; do not paste **500** lines manually.

---

### Lab 3 reference — send `device-telemetry.json` → IoT Hub

**File:** `GH/data/iot/device-telemetry.json` (**500** lines)  
**Target:** IoT Hub **`iot-adx-tcs`** (device-to-cloud on built-in **Events** endpoint)

Each line is JSON with a **`deviceId`** field. The sender must use that ID so the message is accepted as from **`substation-sensor-01`**, **`substation-sensor-02`**, or **`substation-sensor-03`**.

#### Option A — Course CLI (full **500** messages; same as class demo)

Same setup as Lab 2 Option A, plus in `.env`:

| Variable | Value |
|----------|-------|
| `ADX_IOT_HUB` | `iot-adx-tcs` |

Send:

```bash
adx-tools adx-send-streaming iot
```

**What it does:** for each file line, runs:

`az iot device send-d2c-message --hub-name iot-adx-tcs --device-id <deviceId from JSON> --data '<line>'`

#### Option B — Azure Cloud Shell (full **500**)

1. Cloud Shell → **Bash**; upload `device-telemetry.json`.
2. Run:

```bash
HUB=iot-adx-tcs
SAMPLE=device-telemetry.json
COUNT=0

while IFS= read -r line || [ -n "$line" ]; do
  [ -z "$line" ] && continue
  device=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['deviceId'])" "$line")
  az iot device send-d2c-message --hub-name "$HUB" --device-id "$device" --data "$line"
  COUNT=$((COUNT + 1))
done < "$SAMPLE"

echo "Sent $COUNT messages to $HUB"
```

You need permission to send device messages (e.g. **IoT Hub Data Contributor** on the hub, or class sandbox role).

#### Option C — Portal / Cloud Shell (one message only — demo)

See **IoT Hub — class lead creates** → optional demo above.

---

### After sending — verify on dataexplorer.azure.com

1. Wait **30–60 seconds**.
2. Run **Step 2** in the lab query file:
   - Lab 2: `queries/02-eventhub-connection.kql` → total **3000**, EventHub **500**
   - Lab 3: `queries/03-iot-hub-connection.kql` → total **3500**, IoT **500**

If counts are **0**, confirm connection **Running** and resend after it was **Running**.

---

# Lab 2 — Event Hub streaming ingest

## Objective

Add **500** rows with `RecordFormat = EventHub`. Bronze total goes from **2500** to **3000**.

## Tasks

**Steps 1–5 — [dataexplorer.azure.com](https://dataexplorer.azure.com) (Query tab)**

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Run `SecLogsRaw | count` — expect **2500**.
3. Open `queries/00-enable-streaming-ingest.kql`. Run both commands (`IsEnabled`: true).
4. Open `queries/02-eventhub-connection.kql`. Run **Step 1 only** (Event Hub mapping).
5. Open `queries/02-verify-eventhub-mapping.kql`. Run **Steps 1–3** in order:
   - Step 1: inline test ingest
   - Wait **~20 seconds**
   - Step 2: confirm `SourceFile` = `sec-events`, `RecordFormat` = `EventHub`, `SourceIP` = `10.20.8.99` (sentinel test row — not in class sample)
   - Step 3: delete the test row (Bronze should return to **2500**)

   **STOP** if Step 2 shows blank/null columns — re-run Step 4 mapping; do not create the Portal connection yet.

**Step 6 — [Azure Portal](https://portal.azure.com)** (data connection — not on dataexplorer.azure.com)

6. Create the Event Hub **data connection** (after Steps 4–5 pass).

   **Portal path**

   - [portal.azure.com](https://portal.azure.com) → **Azure Data Explorer clusters** → **`adx-training-tcs`**
   - **Databases** → **your** `LogsDB_<id>` → **Data ingestion** or **Data connections**
   - **+ Add Data Connection** → **Event Hub**

   ```text
   portal.azure.com → adx-training-tcs → Databases → LogsDB_u01
     → Data ingestion / Data connections → + Add Data Connection → Event Hub
   ```

   **Form fields**

| Field | Value |
|-------|-------|
| Data connection name | `sec-events-to-seclogsraw` |
| Event Hub namespace | `eh-adx-tcs` |
| Event Hub | `sec-events` |
| Table name | `SecLogsRaw` |
| Data format | **MULTIJSON** |
| Mapping rule name | `SecLogsRaw_EventHubMapping` |
| Managed identity | **System-assigned** |

   **Consumer group (Lab 2 only)** — do this in the **same** ADX form; you do **not** open Event Hub separately:

   1. Find **Consumer group**.
   2. Choose **+ Create new** (Portal may say **Create new consumer group**).
   3. If asked for a name, type a unique value (example: `cg-u01`). If Portal fills in a name automatically, keep it.
   4. Do **not** select `$Default` or a group another student is using.

   Click **Create** → wait until status is **Running** (refresh if needed). If **Failed**, check hub names above and report in class.

   > **Mapping rule name** must be **`SecLogsRaw_EventHubMapping`** (not `SecLogsRaw_JsonMapping`, not blank / identity). **Data format** must be **MULTIJSON**. Wrong values produce rows with **null/blank** fields — see [Troubleshooting](#debug-event-hub-rows-null-or-blank).

   > Counts are verified on **dataexplorer.azure.com**, not in Portal.

7. When the connection is **Running**, raise your hand. After the class sends sample data, wait **30–60 seconds**, then run **Step 2** in `queries/02-eventhub-connection.kql`.

## Example result

| Check | Value |
|-------|-------|
| `SecLogsRaw \| count` | **3000** |
| `RecordFormat == "EventHub"` | **500** |
| Sample `SourceFile` | `sec-events` |

## Success criteria

* Total **3000**; EventHub rows **500**.

---

# Lab 3 — IoT Hub ingest

## Objective

Add **500** rows with `RecordFormat = IoT`. Bronze total goes from **3000** to **3500**.

## Tasks

**Steps 1–4 — dataexplorer.azure.com**

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Run `SecLogsRaw | count` — expect **3000**.
3. Open `queries/03-iot-hub-connection.kql`. Run **Step 1 only** (IoT mapping).
4. Open `queries/03-verify-iot-mapping.kql`. Run **Steps 1–3** in order (same pattern as Lab 2 step 5):
   - Step 2 must show `SourceFile` = `iot-device-telemetry`, `RecordFormat` = `IoT`, `deviceId` = `lab-verify-test` (sentinel — not in class sample)
   - Step 3 removes the test row (Bronze should return to **3000**)

   **STOP** if Step 2 shows blank/null columns — re-run Step 3 mapping; do not create the Portal connection yet.

**Step 5 — Azure Portal** (data connection)

5. Create the IoT Hub **data connection** (same Portal path as Lab 2 step 6).

   - [portal.azure.com](https://portal.azure.com) → **Azure Data Explorer clusters** → **`adx-training-tcs`**
   - **Databases** → **your** `LogsDB_<id>` → **Data ingestion** or **Data connections** → **+ Add Data Connection** → **IoT Hub**

| Field | Value |
|-------|-------|
| Data connection name | `iot-to-seclogsraw` |
| IoT Hub | `iot-adx-tcs` |
| Shared access policy | **`iothubowner`** |
| Table name | `SecLogsRaw` |
| Data format | **JSON** |
| Mapping | `SecLogsRaw_IoTMapping` |

   **Consumer group (Lab 3 only):**

   1. Open the **Consumer group** dropdown.
   2. Select **`adx`** (class lead added it under IoT Hub → **Built-in endpoints** → **Events**).
   3. Do **not** choose **Create new**.

   Click **Create** → wait for **Running**.

6. When the connection is **Running**, raise your hand. After the class sends sample data, wait **30–60 seconds**, then run **Step 2** in `queries/03-iot-hub-connection.kql`.

## Example result

| Check | Value |
|-------|-------|
| `SecLogsRaw \| count` | **3500** |
| `RecordFormat == "IoT"` | **500** |
| All four formats present | JSON, CSV, EventHub, IoT |

## Success criteria

* Total **3500**; IoT rows **500**.

> **Next:** [Lab 8 — IoT telemetry on Bronze](#lab-8-iot-telemetry-on-bronze) before creating Silver.

---

# Lab 8 — IoT telemetry on Bronze {#lab-8-iot-telemetry-on-bronze}

## Objective

Analyze **substation device telemetry** on **`SecLogsRaw`** using **`RawPayload`** fields — event types, **`deviceId`**, facilities, and critical **`SensorAnomaly`** alerts.

Theory: [README §3.7](README.md#37-analyzing-iot-telemetry-on-bronze-lab-8).

```text
  Lab 3 landed IoT rows          Lab 8 queries RawPayload

  RecordFormat = IoT      ──►    EventType, deviceId, Facility
  RawPayload (dynamic)            (Silver not required yet)
```

## Tasks

1. Confirm **your database** is selected and `SecLogsRaw | count` = **3500**.
2. Open **`queries/08-iot-telemetry-bronze.kql`**.
3. Run **Q1–Q5** in order.

## Example result

| Query | Expected |
|-------|----------|
| Q1 IoT count | **500** |
| Q2 EventType | `SensorAnomaly` **200**; `DeviceHeartbeat`, `ConfigChange`, `FirewallDeny` **100** each |
| Q3 deviceId | `substation-sensor-01` **200**, `-02` **200**, `-03` **100** |
| Q4 Substation-D Critical anomalies | **10** sample rows ( **100** total; `SourceIP` often **`10.20.9.3`**) |
| Q5 Facility | `Substation-C` **300**, `Substation-D` **100**, `DMZ-Firewall` **100** |

## Success criteria

* Counts match table above.
* You can explain why **`deviceId`** is queried as **`RawPayload.deviceId`** on Bronze.

---

# Lab 4 — Create Silver table

## Objective

Create typed Silver table **`SecLogsParsed`** with the locked nine-column schema.

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Confirm `SecLogsRaw | count` = **3500**.
3. Open **`queries/04-create-silver-table.kql`**.
4. Run `.create-merge table SecLogsParsed` (nine columns including **`SourceSystem`**).
5. Run `.show table SecLogsParsed cslschema` — verify column names and types match [README.md](README.md) Section 6.2.

> **`.create-merge`** is safe to re-run in **your** database. Row count stays **0** until Lab 5.

## Example result

| Check | Value |
|-------|-------|
| Columns | **9** — `Timestamp` through `SourceSystem` |
| Row count after Lab 4 | **0** (backfill is Lab 5) |
| `SourceSystem` type | `string` |

## Success criteria

* `SecLogsParsed` appears in `.show tables`.
* Schema matches the Silver schema in [README.md](README.md).

---

# Lab 5 — Update policy and backfill

## Objective

Enable **update policy** from `SecLogsRaw` → `SecLogsParsed` and **backfill** all existing Bronze rows into Silver.

> Read [policies-guide.md](policies-guide.md) Sections 7 and 12 before this lab.

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Open **`queries/05-update-policy-backfill.kql`**.
3. Run **Step 1** as **one line** — the entire `.alter table SecLogsParsed policy update ...` command (do not split).
4. Run `.show table SecLogsParsed policy update` — confirm `IsEnabled: true`, `Source: SecLogsRaw`.
5. Run **Step 2** — select from `.set-or-append` through the final `project` line.
6. Run `SecLogsParsed | count` — expect **3500**.
7. Run **`queries/06-verify-silver.kql`** Q1–Q4 before Lab 7.

> **Re-run only:** If Silver already has rows and you need to append missing Bronze rows without duplicating, use optional **`queries/05b-idempotent-backfill.kql`** (not in the same session as Step 2).

> Backfill uses the **same KQL** as the policy query. Day 2 batch rows did not auto-forward because they landed before the policy existed.

## Example result

| Check | Value |
|-------|-------|
| `SecLogsParsed \| count` | **3500** |
| `SecLogsRaw \| count` | **3500** (unchanged) |
| Update policy | `IsEnabled: true` |
| SourceSystem values | **4** (`Batch-JSON`, `Batch-CSV`, `EventHub`, `IoT-Hub`) |

## Success criteria

* Silver **3500** = Bronze **3500**.
* Q1–Q4 in `06-verify-silver.kql` match expected results below.

**Silver verification (before Lab 7):** [queries/06-verify-silver.kql](queries/06-verify-silver.kql)

| Query | Expected |
|-------|----------|
| Q1 count | **3500** |
| Q2 SourceSystem | **4** values — `Batch-CSV` **1000**, `Batch-JSON` **1500**, `EventHub` **500**, `IoT-Hub` **500** |
| Q3 Bronze vs Silver | `Match` = **true** |
| Q4 EventType | Summarize completes (e.g. AuthFailure **700**, FirewallDeny, VPNLogin, …) |

> **Next:** [Lab 9 — IoT telemetry on Silver](#lab-9-iot-telemetry-on-silver) before Kafka discussion or Lab 7.

---

# Lab 9 — IoT telemetry on Silver {#lab-9-iot-telemetry-on-silver}

## Objective

Analyze the same **500** IoT messages as typed Silver rows — **`SourceSystem == "IoT-Hub"`** — including OT substation patterns and hourly **`SensorAnomaly`** counts.

Theory: [README §6.10](README.md#610-iot-telemetry-on-silver-lab-9).

```text
  Lab 8 (Bronze)                 Lab 9 (Silver)

  RawPayload.deviceId            SourceSystem = IoT-Hub
  manual extend in query    ──►   EventType, Facility, Severity columns
```

## Tasks

1. Confirm `SecLogsParsed | count` = **3500**.
2. Open **`queries/09-iot-telemetry-silver.kql`**.
3. Run **Q1–Q5** in order.

## Example result

| Query | Expected |
|-------|----------|
| Q1 IoT-Hub count | **500** |
| Q2 EventType | Same mix as Lab 8 Q2 (`SensorAnomaly` **200**, others **100**) |
| Q3 High/Critical | Rows grouped by `Facility`, `EventType` (e.g. **100** SensorAnomaly per substation) |
| Q4 Hourly SensorAnomaly | Bucketed rows; total anomalies = **200** |
| Q5 OT substations | `Substation-C` + `Substation-D` = **400** events summed across EventTypes |

## Success criteria

* Q1 = **500**; Q2 matches Lab 8 event-type breakdown.
* You can explain **`SourceSystem == "IoT-Hub"`** vs Bronze **`RecordFormat == "IoT"`**.

---

# Lab 6 — Kafka and Logstash (architecture)

## Objective

Describe how external streaming platforms integrate with ADX in utility enterprises.

## Tasks

1. Review [README.md](README.md) Section **5** (Kafka and Logstash).
2. Sketch **Kafka → Event Hub → ADX** and **Logstash → Blob → ADX** paths on paper.
3. Name **one reason** a utility might keep Kafka on-premises.
4. Name **one reason** to land Logstash output in Blob vs Event Hub.

## Success criteria

* You can explain one architecture path without hands-on Kafka/Logstash config.
* You can state this course uses **Event Hub** and **IoT Hub** for Azure-native streaming.

---

# Lab 7 — Investigate on Silver

## Objective

Run investigation queries on typed **`SecLogsParsed`** data — prove Silver is ready for Day 4 Gold and advanced KQL.

## Tasks

1. Confirm **your database** is selected (example: **`LogsDB_u01`**).
2. Confirm `SecLogsParsed | count` = **3500**.
3. Open **`queries/07-silver-investigation.kql`**.
4. Run **Q1** through **Q5** in order (one block at a time).

## Example result

| Query | Result |
|-------|--------|
| Q1 AuthFailure | **700** (300 Batch-JSON + 200 Batch-CSV + 200 EventHub + 0 IoT-Hub) |
| Q2 by SourceSystem | Batch-JSON **300**, Batch-CSV **200**, EventHub **200** |
| Q3 High/Critical | Grouped by `Facility` |
| Q4 streaming only | Rows from `EventHub` and `IoT-Hub` |
| Q5 `dcount(SourceSystem)` | **4** |

## Success criteria

* Row counts match table above.
* You can explain **`SourceSystem`** vs Bronze **`RecordFormat`**.
