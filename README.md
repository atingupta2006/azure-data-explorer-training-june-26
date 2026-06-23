# Azure Data Explorer (ADX) — TCS Training

**5 days × 8 hours (40 hours)** — hands-on on shared cluster **`adx-training-tcs`**. Each student works in their own database (example: **`LogsDB_u01`**).

## Student path — start here

| Day | Theme | Theory | Labs |
|-----|--------|--------|------|
| 1 | KQL fundamentals | [day-01/README.md](day-01/README.md) | [day-01/labs.md](day-01/labs.md) |
| 2 | Batch ingest → Bronze | [day-02/README.md](day-02/README.md) | [day-02/labs.md](day-02/labs.md) |
| 3 | Streaming, IoT, Silver | [day-03/README.md](day-03/README.md) | [day-03/labs.md](day-03/labs.md) |
| 4 | Advanced KQL, Gold MV | [day-04/README.md](day-04/README.md) | [day-04/labs.md](day-04/labs.md) |
| 5 | Performance, security, capstone | [day-05/README.md](day-05/README.md) | [day-05/labs.md](day-05/labs.md) |

**How to run labs:** Open `day-NN/queries/*.kql` in [ADX Web UI](https://dataexplorer.azure.com), select **your** database, run **one block at a time** with **Shift+Enter**.

**Abbreviations:** **SOC** *(Security Operations Center)*, OT, RBAC, MI, and other domain terms are defined in **[GLOSSARY.md](GLOSSARY.md)**.

## Week pipeline (locked lab counts)

```text
  Day 1   PracticeSecurityEvents (2000)
  Day 2   SecLogsRaw (2500)
  Day 3   SecLogsParsed (3500)
  Day 4   ThreatIntelRef (8) + SecLogsHourly MV (3500)
  Day 5   Capstone + RlsDemoEvents (10)
```

## Repository layout

| Resource | Purpose |
|----------|---------|
| [day-01/](day-01/) … [day-05/](day-05/) | README, labs, KQL queries |
| [data/](data/) | Sample NDJSON/CSV for batch and streaming labs |

**Trainer materials** (delivery guides, assignment answer keys, lab automation) are **not** in this repository — provided separately in class.

## Prerequisites

- Azure AD account with access to **`adx-training-tcs`** and your workspace database (example **`LogsDB_u01`**)
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) for Day 2+ `.ingest`
- Complete each day in **your** database before starting the next
