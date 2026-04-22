# SPEC-004 — OpenSearch (Local wazuh-indexer)

**Version:** 0.2
**Status:** Revised — architecture changed during POC deployment
**Depends on:** SPEC-002
**CloudFormation stack:** `selene-opensearch` (deployed but NOT USED — pending deletion)

---

## 1. Architecture Change Summary

The original design called for Amazon OpenSearch Service as the durable
findings store. During POC deployment this was found to be incompatible
with the Wazuh dashboard for three reasons:

1. **_nodes API restricted** — Amazon OpenSearch Service restricts the
   `_nodes` API. The Wazuh dashboard (Node.js) calls this API at startup
   to retrieve version information. Without it, the dashboard cannot connect.

2. **Version mismatch** — Wazuh dashboard 2.19.4 vs Amazon OpenSearch
   2.11.0. The dashboard rejects the connection.

3. **geoip processor unavailable** — The official Wazuh filebeat pipeline
   uses the `geoip` ingest processor which is not available in Amazon
   OpenSearch Service. This caused filebeat to fail on pipeline load.

**Decision:** Use the local `wazuh-indexer` (bundled OpenSearch) as the
findings store. Findings persistence is achieved via a dedicated EBS volume
mounted at `/var/lib/wazuh-indexer`.

---

## 2. Current Architecture

### Local wazuh-indexer

| Property | Value |
|---|---|
| Process | wazuh-indexer (bundled OpenSearch) |
| Port | 9200 (HTTPS, self-signed cert) |
| Data path | /var/lib/wazuh-indexer |
| Storage | EBS vol-0b37de9c1bfd8afdd (200GB gp3) |
| Persistence | EBS survives EC2 termination |
| Cluster name | wazuh-cluster |
| Admin username | admin |
| Admin password | SSM SecureString /selene/wazuh_indexer_admin_password |

### EBS Volume

| Property | Value |
|---|---|
| Volume ID | vol-0b37de9c1bfd8afdd |
| Size | 200 GB gp3 |
| AZ | us-east-1a (same as EC2) |
| Mount point | /var/lib/wazuh-indexer |
| fstab | UUID-based, nofail |
| Encryption | Yes (EBS encryption) |
| Estimated capacity | ~90 days at full 91-account volume |

### Index Structure

```
wazuh-alerts-4.x-YYYY.MM.DD   ← one index per day
wazuh-monitoring-YYYY.WWw      ← Wazuh monitoring stats
wazuh-statistics-YYYY.WWw      ← Wazuh statistics
wazuh-states-*                 ← inventory/state data
```

### ISM Retention Policy

Policy name: `selene-90-day-retention`
Applied to: `wazuh-alerts-*` indices
Action: delete after 90 days

---

## 3. Alert Ingestion (selene-shipper)

The local wazuh-indexer receives alerts from `selene-shipper.py`, a Python
service that replaces filebeat. It tails `/var/ossec/logs/alerts/alerts.json`
and ships documents via the OpenSearch bulk API.

Field normalizations applied (matching official Wazuh pipeline.json):

| Field | Source |
|---|---|
| `@timestamp` | `timestamp` |
| `data.aws.accountId` | `data.aws.aws_account_id` |
| `data.aws.region` | `data.aws.awsRegion` |
| `GeoLocation` | geoip lookup on 8 IP fields via GeoLite2-City.mmdb |

---

## 4. Amazon OpenSearch Service Stack (NOT USED)

The `selene-opensearch` CloudFormation stack was deployed but is not used.

**Pending action:** Delete the stack to stop incurring ~$60/mo in charges:
```bash
aws cloudformation delete-stack --stack-name selene-opensearch
```

The stack created:
- Domain: `selene-findings` (OpenSearch 2.11.0, t3.medium.search)
- VPC endpoint (internal only)
- 100GB gp3 EBS storage

The SSM parameter `/selene/opensearch_endpoint` is kept for reference
but the endpoint is not in use.

---

## 5. Cost Comparison

| Approach | Monthly Cost | Status |
|---|---|---|
| Amazon OpenSearch Service (original plan) | ~$60 | Not used |
| Local wazuh-indexer + 200GB EBS | ~$16 | Current |
| Savings | ~$44/mo | |

---

## 6. Known Limitations

**SL-006 — EBS reattach not automated**
If the ASG launches a replacement EC2, it will not automatically reattach
vol-0b37de9c1bfd8afdd. Data is safe on the EBS volume but inaccessible
until the volume is manually reattached and mounted.

Resolution (Phase 2): Add EBS reattach logic to UserData or a Lambda
triggered by ASG lifecycle hook.

**No HA**
Single-node indexer, single AZ. Acceptable for POC.

---

## 7. Acceptance Criteria (Updated)

| ID | Criterion |
|---|---|
| AC1 | wazuh-indexer is active and healthy (green cluster status) |
| AC2 | EBS volume mounted at /var/lib/wazuh-indexer with UUID in fstab |
| AC3 | wazuh-alerts-* indices appear and grow as CloudTrail events are processed |
| AC4 | ISM policy selene-90-day-retention is active on wazuh-alerts-* |
| AC5 | selene-shipper ships alerts with accountId, region, GeoLocation fields |
| AC6 | Terminating EC2 does not destroy index data (EBS persists) |
| AC7 | selene-opensearch CloudFormation stack deleted |
