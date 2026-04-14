# SPEC-001 — Selene SIEM Architecture Specification

**Version:** 0.1  
**Status:** Draft  
**Author:** Aslan  
**Created:** 2025  
**Project:** Selene  

---

## 1. Problem Statement

Infillion operates a ~60-account AWS Organization and currently relies on
expensive third-party SIEM tooling for security event visibility. CloudTrail
logs from all accounts are already centralized in the management account S3
bucket. The goal is to deploy a self-hosted, open-source SIEM (Wazuh) that
ingests those logs, generates findings, and provides a dashboard for the
security team — at a fraction of the cost and with full control over
detection rules.

---

## 2. Goals

| ID | Goal |
|---|---|
| G1 | Ingest org-wide CloudTrail logs from the existing management account S3 bucket into Wazuh |
| G2 | Provide a web-accessible Wazuh dashboard for the security team |
| G3 | Store findings in a durable, managed backend (Amazon OpenSearch Service) that survives EC2 failure |
| G4 | Achieve automatic EC2 recovery with RTO ≤ 10 minutes via ASG + Golden AMI |
| G5 | Codify all server configuration as Ansible; all infrastructure as CloudFormation |
| G6 | Maintain 1 year of raw CloudTrail log retention (SOC 2 compliance) |
| G7 | Maintain 90 days of Wazuh findings retention in OpenSearch |
| G8 | Enable custom rule management and alert suppression, version-controlled in Git |

---

## 3. Out of Scope (this phase only)

These are operational requirements for production that are intentionally
deferred from the POC phase. They are not optional — they are required
before Selene can be considered production-ready. See ADR-005 and
`docs/PRODUCTION-CHECKLIST.md` for the full promotion gate criteria.

| ID | Deferred Item | Planned Phase |
|---|---|---|
| NG1 | SSM-only access — port 22 allowed during active development | Phase 4 |
| NG2 | Custom DNS name (`selene.infillion.com`) + ACM TLS cert | Phase 2 |
| NG3 | Okta SAML integration for dashboard auth | Phase 3 |
| NG4 | Multi-node Wazuh cluster — single all-in-one sufficient for current volume | Revisit at scale |
| NG5 | Ingestion beyond CloudTrail S3 — agents, VPC flow logs, GuardDuty | Future phases |
| NG6 | Multi-AZ OpenSearch — single node acceptable for POC | Phase 2 |

**Note on environment strategy:** There is no QA or staging environment.
Selene is a read-only observation tool with no write access to monitored
infrastructure. See ADR-004 for the full rationale.

---

## 4. Constraints

| ID | Constraint |
|---|---|
| C1 | Must deploy into the existing production VPC: `vpc-06cdf666adc9f698d` |
| C2 | Must use CloudFormation exclusively — no CDK, no Terraform |
| C3 | OpenSearch domain must be VPC-only — no public endpoint |
| C4 | CloudTrail S3 bucket already exists and must not be modified structurally |
| C5 | Monthly infrastructure cost target: ≤ $350/mo total |
| C6 | All Wazuh configuration, rules, and suppressions must be stored in Git |

---

## 5. Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                  Management Account VPC                       │
│                  vpc-06cdf666adc9f698d                        │
│                                                               │
│  ┌──────────────────┐        ┌──────────────────────────┐    │
│  │       ALB        │──────▶ │     Wazuh EC2 (AiO)      │    │
│  │  (public subnet) │  443   │     t3.xlarge             │    │
│  │  ports 80, 443   │        │     private subnet        │    │
│  └──────────────────┘        │     - Manager             │    │
│           ▲                  │     - Dashboard           │    │
│           │                  │     - Indexer (bridge)    │    │
│    Your IP /32               └──────────┬───────────────┘    │
│                                         │ HTTPS 443           │
│                              ┌──────────▼───────────────┐    │
│                              │  Amazon OpenSearch Svc    │    │
│                              │  t3.medium.search × 1     │    │
│                              │  100 GB gp3               │    │
│                              │  VPC endpoint only        │    │
│                              │  90-day ISM policy        │    │
│                              └──────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
         │
         │ S3 GetObject + ListBucket (IAM role, same account)
         ▼
┌──────────────────────────────────────────────────┐
│  CloudTrail S3: logs.infillion.com                │
│  Trail: full-org-events (multi-region)            │
│  All ~60 accounts → AWSLogs/{account-id}/...      │
│  1-year S3 lifecycle policy (raw logs)            │
└──────────────────────────────────────────────────┘

Auto Scaling Group
  desired: 1 │ min: 1 │ max: 1
  └── Launch Template
        └── Golden AMI (selene-wazuh-YYYYMMDD)
              └── UserData → git clone SecOpsHub/selene
                    └── ansible-playbook site.yml
                          └── Wazuh configured, services started
```

---

## 6. Data Flow

1. Member accounts write CloudTrail logs to management account S3 bucket
2. Wazuh EC2 polls S3 via `wodle/aws-s3` module every 5 minutes
3. Wazuh Manager processes log events against ruleset, generates alerts
4. Alerts forwarded to Amazon OpenSearch Service over HTTPS (port 443)
5. Security team accesses Wazuh Dashboard via ALB on port 443
6. ALB security group restricts inbound access to known IP `/32`

---

## 7. Recovery Flow

1. ASG health check detects unhealthy instance (ELB health check)
2. ASG terminates instance and launches replacement from Golden AMI
3. UserData script clones `SecOpsHub/selene` from GitHub
4. Ansible playbook runs: configures Wazuh, points indexer at existing
   OpenSearch endpoint (read from SSM Parameter Store)
5. Wazuh services start; dashboard becomes reachable via ALB
6. All findings intact in OpenSearch — no data loss
7. Total elapsed time: ≤ 10 minutes

---

## 8. State Model

This is the core reliability design. State is intentionally separated:

| State Type | Where Stored | Survives EC2 Loss? |
|---|---|---|
| Raw CloudTrail logs | S3 (existing) | Yes |
| Wazuh findings/alerts | Amazon OpenSearch Service | Yes |
| Wazuh rules | GitHub (`wazuh/rules/`) | Yes |
| Wazuh suppressions | GitHub (`wazuh/suppressions/`) | Yes |
| Wazuh config (ossec.conf) | GitHub (`wazuh/templates/`) | Yes |
| S3 processing cursor (aws.db) | EC2 local disk | **No — SL-001** |
| Wazuh Manager state | EC2 local disk | **No — acceptable** |

The EC2 instance is treated as ephemeral. Nothing critical lives only on it.

---

## 9. Cost Estimate

| Component | Type | Est. Monthly Cost |
|---|---|---|
| Wazuh EC2 | t3.xlarge on-demand | ~$120 |
| Amazon OpenSearch | t3.medium.search × 1 | ~$55 |
| OpenSearch EBS | 100 GB gp3 | ~$10 |
| ALB | per LCU + hourly | ~$20 |
| S3 API calls | polling 5 min interval | ~$5 |
| Data transfer | minimal (VPC internal) | ~$5 |
| **Total** | | **~$215/mo** |

Well within the $350/mo target. EC2 reserved instance (1-year) reduces
EC2 cost to ~$75/mo, bringing total to ~$170/mo if committed.

---

## 10. Environment Values (Discovery Complete)

All environment-specific values resolved. See `docs/discovery/RESULTS.md`.

| Value | Resolved |
|---|---|
| VPC ID | `vpc-06cdf666adc9f698d` (production-vpc, 10.1.0.0/16) |
| ALB subnets | `subnet-06e367114ba47947a` (us-east-1a), `subnet-0a2291ca1fe4900c0` (us-east-1b) |
| EC2 / OpenSearch subnet | `subnet-0934cf17ca2678038` (us-east-1a, private) |
| CloudTrail trail | `full-org-events` (multi-region, org-level) |
| CloudTrail bucket | `logs.infillion.com` |
| CloudTrail S3 prefix | `AWSLogs/o-z70v8p3t14/` (org-level path — includes org ID) |
| Organization ID | `o-z70v8p3t14` |
| Management account ID | `757548139022` |
| Region | `us-east-1` |
| Active regions in logs | 16 (all major AWS regions confirmed) |

---

## 11. Acceptance Criteria

The POC is complete when all of the following are true:

| ID | Criterion |
|---|---|
| AC1 | All four CloudFormation stacks deploy without errors |
| AC2 | Wazuh dashboard is reachable via ALB DNS on HTTPS from allowed IP |
| AC3 | CloudTrail events from at least 3 member accounts appear as Wazuh alerts |
| AC4 | Terminating EC2 manually results in working dashboard within 10 minutes |
| AC5 | OpenSearch findings are intact after EC2 replacement (no data loss) |
| AC6 | A custom detection rule in `local_rules.xml` fires on a test event |
| AC7 | A suppression in `local_overrides.xml` silences a known-noisy event |
| AC8 | Full rebuild from Golden AMI + Ansible completes unattended |

---

## 12. POC-to-Production Path

This POC is designed with the expectation of promotion to production.
The architecture is production-grade from day one. What changes at
promotion is the operational layer, not the design.

**Architecture decisions that are already production-grade:**
- Stateless EC2 with Git as source of truth (ADR-002)
- Durable findings in OpenSearch, separate from EC2 (ADR-001)
- CloudFormation-managed infrastructure
- IAM least privilege with no wildcard actions (SPEC-005)
- IMDSv2 enforced
- No public OpenSearch endpoint

**Operational shortcuts to resolve before promotion:**

| Shortcut | Resolution | Phase |
|---|---|---|
| Self-signed TLS cert (SL-002) | ACM cert + Route 53 DNS | Phase 2 |
| Personal IP /32 only | Team VPN CIDR + Okta SSO | Phase 2/3 |
| Port 22 open | SSM Session Manager | Phase 4 |
| Single OpenSearch node (SL-003) | 2-node multi-AZ | Phase 2 |

See `docs/PRODUCTION-CHECKLIST.md` for the complete gate criteria.

---

## 13. Known Limitations

**SL-001 — Duplicate alerts on EC2 replacement**
Wazuh's S3 integration tracks processed files in a local SQLite database
(`/var/ossec/wodles/aws/aws.db`). This file is lost when the EC2 is
terminated. Upon replacement, Wazuh re-processes ~5 minutes of recent logs,
generating duplicate alerts. This is acceptable for POC.
Resolution: mount EFS for `/var/ossec/wodles/aws/` in a future phase.

**SL-002 — Self-signed TLS certificate**
ALB uses a self-signed certificate during POC. Browsers will show a
security warning. Resolution: ACM + Route 53 in Phase 2.

**SL-003 — Single OpenSearch node, no multi-AZ**
OpenSearch domain has one node in one AZ. Unavailable during AWS
maintenance events for that AZ. Resolution: 2-node multi-AZ in Phase 2.

---

## 14. Related Specs

- [SPEC-008 Interface Contracts](SPEC-008-interface-contracts.md)
- [SPEC-002 Networking](../components/SPEC-002-networking.md)
- [SPEC-003 EC2 / ASG / Golden AMI](../components/SPEC-003-ec2-asg.md)
- [SPEC-004 OpenSearch Service](../components/SPEC-004-opensearch.md)
- [SPEC-005 IAM](../components/SPEC-005-iam.md)
- [SPEC-006 Ansible](../components/SPEC-006-ansible.md)
- [SPEC-007 CloudTrail S3 Integration](../components/SPEC-007-cloudtrail.md)
