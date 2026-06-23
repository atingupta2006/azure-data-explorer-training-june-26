# Course glossary — utility cyber & ADX terms

Short expansions for abbreviations used in Days 1–5. Each day README links here on first use of domain jargon.

**Writing convention:** Student materials use **Full Name (ABBR)** together — e.g. **Network Operations Center (NOC)**, **Security Operations Center (SOC)**, **materialized view (MV)** — not the abbreviation alone.

| Term | Full form / meaning | In this course |
|------|---------------------|----------------|
| **ADX** | **Azure Data Explorer** | Central analytics cluster (`adx-training-tcs`) |
| **OT** | **Operational Technology** | Systems that monitor/control physical processes (substations, grid, SCADA) |
| **OT-adjacent** | **Operational Technology–adjacent** | Logs or assets *near* OT zones — substations, SCADA gateways, IoT sensors — even when the log format looks like IT (JSON, auth events) |
| **IT/OT** | **Information Technology / Operational Technology** | Corporate IT (VPN, firewalls) vs field OT (substations); SOC often correlates both in ADX |
| **SCADA** | **Supervisory Control and Data Acquisition** | Industrial control monitoring; e.g. `scada-gw.utility.local` in capstone data |
| **SOC** | **Security Operations Center** | Central analyst team that **monitors, triages, and investigates** security alerts — runs KQL hunts, reviews dashboards, and handles incidents (e.g. Day 5 capstone ticket) |
| **NOC** | **Network Operations Center** | Central team that monitors **platform and network health** — ADX operators use similar `.show` runbooks (Day 5 §8) |
| **KPI** | **Key Performance Indicator** | Dashboard metric — e.g. hourly AuthFailure counts in `SecLogsHourly` (Day 4–5) |
| **SKU** | **Stock Keeping Unit** *(Azure: cluster **service tier / size**)* | Cluster capacity choice — larger SKU handles more ingest and query load |
| **IOC** | **Indicator of Compromise** | Known-bad IP, hash, or domain in `ThreatIntelRef` (Day 4) |
| **RBAC** | **Role-Based Access Control** | Who may query or manage a database/cluster (Day 5 Lab 5) |
| **RLS** | **Row-Level Security** | Policy that filters which *rows* an analyst sees (Day 5 demo on `RlsDemoEvents`) |
| **MI** | **Managed Identity** | Azure AD identity of the ADX *cluster* for Blob/Event Hub ingest (no password) |
| **MV** | **Materialized View** | Pre-aggregated Gold table (e.g. `SecLogsHourly`) refreshed by the cluster |
| **UDF** | **User-Defined Function** | Reusable KQL function (e.g. `IsOTFacility`, `SeverityRank`) |
| **EH** | **Event Hub** | Azure streaming ingest used on Day 3 |
| **ADLS** | **Azure Data Lake Storage** | Blob storage account for batch `.ingest` (Day 2+) |
| **NDJSON** | **Newline-Delimited JSON** | One JSON object per line |
| **DMZ** | **Demilitarized Zone** | Perimeter network segment (e.g. `DMZ-Firewall` facility) |
| **DR** | **Disaster Recovery** | Restoring analytics after outage or bad change; Bronze on ADLS is replay source (Day 5 §8.3) |
| **GRC** | **Governance, Risk, and Compliance** | Teams that own metadata and compliance evidence |
| **NERC CIP** | **North American Electric Reliability Corporation — Critical Infrastructure Protection** | Mandatory grid cybersecurity standards (North America); architecture must document access, network path, and audit evidence |
| **Private endpoint** | Azure Private Link | Private IP in your VNet for ADX, Blob, or Event Hub — no public URL |
| **VNet** | **Virtual Network** | Private network inside Azure where ADX and storage live |
| **VPN** | **Virtual Private Network** | Encrypted tunnel over the **internet** from corporate/substation to Azure (Day 5 §7.1) |
| **ER** | **Azure ExpressRoute** | **Private dedicated circuit** to Azure — not over the public internet (Day 5 §7.1) |
| **ISAC** | **Information Sharing and Analysis Center** | Threat-intel sharing community; `ThreatIntelRef` simulates feed rows |
| **OT-Production** | *(course tag)* | Environment label for production substation / IoT workloads — not a standard acronym |
| **OTAnomaly** | *(threat category)* | IOC class for suspicious OT sensor or gateway activity in lab data |


**`IsOTFacility(Facility)`** — UDF (Day 4 Lab 6) that returns true for substation and SCADA-gateway facilities; use it to filter **OT-adjacent** events without listing sites manually.
