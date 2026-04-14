# SPEC-007 — CloudTrail S3 Log Integration

**Version:** 0.1  
**Status:** Draft  
**Depends on:** SPEC-005  

---

## 1. Overview

Wazuh ingests CloudTrail logs from S3 using its native `aws-s3` wodle
(module). The wodle polls the S3 bucket at a configured interval,
downloads new log files, parses the JSON events, and passes them through
the Wazuh ruleset to generate alerts. No agents are required on member
accounts.

---

## 2. S3 Bucket and Trail

**CloudTrail trail:** `full-org-events`
**S3 bucket:** `logs.infillion.com`
**Organization ID:** `o-z70v8p3t14`
**Region:** `us-east-1` (multi-region trail — logs from all regions land here)

> Note: A second trail (`cloudtrail-from-cf`) exists pointing to a
> Presidio-managed bucket. This is a legacy/vendor trail. Selene
> reads only from `logs.infillion.com`.

**IMPORTANT — Org-level path structure:**
This is an organization-level CloudTrail trail. The S3 path includes
the AWS Organization ID as an intermediate prefix between `AWSLogs/`
and the account ID. This is different from a standard per-account trail.

```
s3://logs.infillion.com/
└── AWSLogs/
    └── o-z70v8p3t14/              ← Organization ID (not account ID)
        └── {account-id}/
            ├── CloudTrail/
            │   └── {region}/{year}/{month}/{day}/
            │       └── {account-id}_CloudTrail_{region}_{timestamp}_{hash}.json.gz
            ├── CloudTrail-Digest/
            └── CloudTrail-Insight/
```

All ~60 member accounts confirmed present under the org prefix.
All AWS regions confirmed per account (16 regions active).

**Note on management account logs:** The management account (757548139022)
also has logs directly under `AWSLogs/757548139022/` without the org prefix.
Selene reads from the org prefix only — `AWSLogs/o-z70v8p3t14/`.

---

## 3. Wazuh aws-s3 Wodle Configuration

This is configured via the `ossec.conf.j2` template (SPEC-006).
Key parameters:

| Parameter | Value | Rationale |
|---|---|---|
| `bucket` | `logs.infillion.com` | CloudTrail bucket |
| `path` | `AWSLogs/o-z70v8p3t14/` | Org-level prefix — captures all 60 accounts |
| `type` | `cloudtrail` | Tells Wazuh to parse CloudTrail JSON format |
| `only_logs_after` | Deploy date | Avoids re-processing history on first run |
| `interval` | `5m` | Balance between alert latency and S3 API cost |
| `run_on_start` | `yes` | Process immediately on Wazuh start |

**Why `AWSLogs/o-z70v8p3t14/` and not `AWSLogs/`:**
The org-level trail stores logs under the Organization ID prefix, not
directly under account IDs. Using `AWSLogs/` would cause Wazuh to also
try to process the management account's direct logs under
`AWSLogs/757548139022/` which uses a different (non-org) path structure.
The org prefix scopes ingestion cleanly to all member accounts.

---

## 4. First-Run Behavior

`only_logs_after` is set to the deployment date to prevent Wazuh from
attempting to process 1 year of existing CloudTrail logs on first start.

Processing 1 year of backlogged CloudTrail logs for 60 accounts would:
- Take days to complete
- Generate excessive alerts for already-resolved events
- Incur significant S3 API costs

After the initial deployment date is set, Wazuh processes only new logs
going forward.

---

## 5. Processing State (Known Limitation SL-001)

Wazuh tracks which S3 files have been processed in a local SQLite
database:

```
/var/ossec/wodles/aws/aws.db
```

This file lives on the EC2 local disk and is lost when the EC2 is
terminated. On replacement:

- Wazuh does not know which files were already processed
- It re-processes files from the last ~5 minutes before termination
- This generates duplicate alerts for that window

**This is acceptable for POC.** The duplicate window is small and
duplicate alerts are a minor operational annoyance, not a data loss event.

**Future resolution (Phase 6):** Mount EFS at
`/var/ossec/wodles/aws/` so the database survives EC2 replacement.

---

## 6. Alert Volume Estimate

Based on typical CloudTrail volume for a 60-account org:

| Source | Est. events/day |
|---|---|
| Console logins (all accounts) | ~500 |
| API calls (all accounts) | ~200,000 |
| After Wazuh filtering (not all trigger alerts) | ~5,000 alerts/day |

OpenSearch index size estimate: ~100 MB/day compressed.
90-day retention: ~9 GB. Well within the 100 GB EBS volume.

---

## 7. Log Parsing

Wazuh's built-in CloudTrail decoder handles the standard log format.
Custom decoders are not required for the POC.

CloudTrail-specific Wazuh rule IDs to be aware of:

| Rule ID Range | Description |
|---|---|
| 80200–80299 | CloudTrail authentication and authorization |
| 80300–80399 | CloudTrail IAM changes |
| 80400–80499 | CloudTrail network changes |

Custom rules in `local_rules.xml` extend these base rules.

---

## 8. Acceptance Criteria

| ID | Criterion |
|---|---|
| AC1 | CloudTrail events from at least 3 member accounts appear in Wazuh alerts within 10 minutes of log delivery |
| AC2 | Each alert contains the correct source account ID, event name, and source IP |
| AC3 | No S3 access errors in `/var/ossec/logs/ossec.log` |
| AC4 | `only_logs_after` prevents re-processing of historical logs on first start |
| AC5 | Wazuh alert rate is within expected range (not zero, not flooding) |
| AC6 | Duplicate alerts after EC2 replacement are limited to ~5 minute window |
