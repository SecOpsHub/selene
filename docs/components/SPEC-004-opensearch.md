# SPEC-004 — Amazon OpenSearch Service Domain

**Version:** 0.1  
**Status:** Draft  
**Depends on:** SPEC-002  
**CloudFormation stack:** `selene-opensearch`

---

## 1. Overview

Amazon OpenSearch Service is the durable findings store for Selene.
It is intentionally separate from the EC2 instance so that findings
survive EC2 termination and replacement. This is the primary mechanism
for meeting G3 (durable findings) and enabling G4 (stateless recovery).

---

## 2. Domain Configuration

| Property | Value |
|---|---|
| Engine | OpenSearch 2.x (latest available at deploy time) |
| Instance type | `t3.medium.search` |
| Instance count | 1 |
| Storage type | EBS gp3 |
| Storage size | 100 GB |
| Multi-AZ | No (POC; Phase 2 adds second node) |
| Endpoint | VPC-only (no public endpoint) |
| Subnet | Private subnet (same as EC2; from RESULTS.md) |
| Security group | `selene-opensearch-sg` (SPEC-002) |
| Encryption at rest | Yes (AWS managed key) |
| Encryption in transit | Yes (HTTPS enforced, HTTP rejected) |
| Fine-grained access control | Enabled |
| Master user | IAM-based (EC2 instance role; SPEC-005) |
| Automated snapshots | Daily (AWS managed, 14-day retention) |

---

## 3. Index Structure

Wazuh writes alerts to time-based indices using this pattern:

```
wazuh-alerts-4.x-YYYY.MM.DD
```

One index per day. At 90-day retention with ~50k CloudTrail events/day,
this is approximately 4.5M documents. Well within `t3.medium.search`
capacity on 100 GB storage.

---

## 4. Index State Management (ISM) Policy

An ISM policy is applied to all `wazuh-alerts-*` indices to enforce
the 90-day findings retention requirement (G7).

Policy name: `selene-90-day-retention`

```
State: hot
  - min_index_age: 90d → transition to delete

State: delete
  - Action: delete index
```

This policy is applied automatically to all `wazuh-alerts-*` indices
via an index template.

---

## 5. Access Control

Fine-grained access control uses IAM authentication. The Wazuh EC2
instance role (SPEC-005) is mapped to the OpenSearch `all_access` role
in the internal user database. No username/password is used.

The OpenSearch domain has no public endpoint. It is only reachable:
- From within the VPC on port 443
- By principals whose IAM role is mapped in fine-grained access control

---

## 6. SSM Parameter

The OpenSearch VPC endpoint is stored in SSM Parameter Store so the
EC2 UserData can retrieve it without hardcoding:

| Parameter | Description |
|---|---|
| `/selene/opensearch_endpoint` | VPC endpoint hostname for the domain |

This value is set once after the OpenSearch domain is created and does
not change unless the domain is recreated.

---

## 7. Cost Estimate

| Item | Monthly Cost |
|---|---|
| `t3.medium.search` instance | ~$50 |
| 100 GB gp3 EBS | ~$10 |
| **Total** | **~$60/mo** |

---

## 8. CloudFormation Stack Outputs

| Export Name | Value | Consumed By |
|---|---|---|
| `selene-OpenSearchEndpoint` | VPC endpoint hostname | Stored in SSM; used by EC2 UserData |
| `selene-OpenSearchArn` | Domain ARN | selene-iam stack (IAM policy resource) |
| `selene-OpenSearchDomainName` | Domain name | Documentation |

---

## 9. Acceptance Criteria

| ID | Criterion |
|---|---|
| AC1 | Domain is reachable from EC2 on port 443 |
| AC2 | Domain returns 403 from any host outside the VPC |
| AC3 | `wazuh-alerts-*` indices appear after Wazuh connects |
| AC4 | ISM policy `selene-90-day-retention` is active on `wazuh-alerts-*` |
| AC5 | HTTPS is enforced (HTTP connections rejected) |
| AC6 | EC2 instance role can write to indices without username/password |
| AC7 | Terminating EC2 does not affect indices in OpenSearch |
