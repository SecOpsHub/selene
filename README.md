# Selene

Self-hosted SIEM for the Infillion AWS Organization, built on
[Wazuh](https://wazuh.com/) with Amazon OpenSearch Service.

Selene ingests org-wide CloudTrail logs from ~60 AWS accounts,
generates security findings, and provides a team-accessible dashboard —
replacing expensive third-party SIEM tooling at a fraction of the cost.
All infrastructure is CloudFormation. All server configuration is Ansible.
All findings state is external to the EC2 instance.

**Status:** POC — in progress  
**Monthly cost target:** ≤ $350/mo  
**RTO:** ≤ 10 minutes (ASG + Golden AMI)

---

## Architecture

```
CloudTrail logs (all ~60 accounts)
        │
        ▼
S3 Bucket (management account) ── 1-year retention
        │
        ▼ polls every 5 min
Wazuh EC2  (t3.xlarge, private subnet)
- Manager + Dashboard + Indexer bridge
- Stateless: fully configured by Ansible on every boot
- ASG of 1: auto-replaced on failure
        │
        ▼ HTTPS alerts
Amazon OpenSearch Service  (t3.medium.search, VPC-only)
- Findings storage
- 90-day retention (ISM policy)
- Survives EC2 replacement

Access: Your IP → ALB (HTTPS 443) → Wazuh Dashboard
```

Full architecture spec: [docs/architecture/SPEC-001-architecture.md](docs/architecture/SPEC-001-architecture.md)

---

## Repository Structure

```
selene/
├── docs/
│   ├── architecture/          # SPEC-001: system-level design
│   ├── components/            # SPEC-002 through SPEC-007
│   ├── decisions/             # Architecture Decision Records (ADRs)
│   ├── runbooks/              # Operational procedures
│   └── discovery/             # AWS environment discovery scripts + results
├── infra/                     # CloudFormation templates (one per component)
├── ansible/
│   ├── site.yml               # Master playbook
│   ├── inventory/
│   └── roles/
│       ├── wazuh_config/      # Renders ossec.conf from template
│       ├── wazuh_rules/       # Deploys custom detection rules
│       ├── wazuh_indexer/     # Configures OpenSearch connection
│       └── wazuh_services/    # Starts and restarts Wazuh services
└── wazuh/
    ├── rules/                 # Custom detection rules (XML) — source of truth
    ├── suppressions/          # Alert suppressions
    └── templates/             # ossec.conf.j2 Jinja2 template
```

---

## Prerequisites

- AWS CLI configured with management account credentials
- Access to `SecOpsHub/selene` on GitHub
- A Golden AMI already baked (see [docs/runbooks/golden-ami-bake.md](docs/runbooks/golden-ami-bake.md))
- SSM parameters pre-populated (see Deployment below)

---

## Deployment

### 1. Run Discovery (first time only)
```bash
AWS_PROFILE=management bash docs/discovery/discover.sh
# Review output, fill in docs/discovery/RESULTS.md
```

### 2. Set SSM Parameters
```bash
aws ssm put-parameter --name /selene/opensearch_endpoint \
  --value <domain-endpoint> --type String

aws ssm put-parameter --name /selene/cloudtrail_bucket \
  --value <bucket-name> --type String
```

### 3. Deploy Stacks (in dependency order)
```bash
aws cloudformation deploy --template-file infra/iam.yml \
  --stack-name selene-iam --capabilities CAPABILITY_NAMED_IAM

aws cloudformation deploy --template-file infra/networking.yml \
  --stack-name selene-networking

aws cloudformation deploy --template-file infra/opensearch.yml \
  --stack-name selene-opensearch

aws cloudformation deploy --template-file infra/ec2-asg.yml \
  --stack-name selene-ec2
```

### 4. Verify
- Get ALB DNS from selene-networking stack Outputs
- Navigate to `https://<alb-dns>` — Wazuh dashboard should appear within 10 min
- Check `/var/ossec/logs/ossec.log` on EC2 for S3 integration status

---

## Configuration

### Adding a Detection Rule
1. Edit `wazuh/rules/local_rules.xml`
2. Commit and push to `main`
3. Re-run Ansible on the EC2:
   ```bash
   ssh ec2-user@<ec2-ip>
   ansible-playbook /opt/selene/ansible/site.yml
   ```
   *(Future: auto-triggered via SSM or EventBridge)*

### Adding a Suppression
1. Edit `wazuh/suppressions/local_overrides.xml`
2. Commit, push, re-run playbook

### SSM Parameters

| Parameter | Description |
|---|---|
| `/selene/opensearch_endpoint` | OpenSearch VPC domain endpoint |
| `/selene/cloudtrail_bucket` | CloudTrail S3 bucket name |

---

## Runbooks

- [Golden AMI Bake](docs/runbooks/golden-ami-bake.md)
- [Disaster Recovery](docs/runbooks/disaster-recovery.md)

---

## Specs

| Spec | Description |
|---|---|
| [SPEC-001](docs/architecture/SPEC-001-architecture.md) | System architecture |
| [SPEC-002](docs/components/SPEC-002-networking.md) | Networking, ALB, security groups |
| [SPEC-003](docs/components/SPEC-003-ec2-asg.md) | EC2, ASG, Launch Template, Golden AMI |
| [SPEC-004](docs/components/SPEC-004-opensearch.md) | Amazon OpenSearch Service domain |
| [SPEC-005](docs/components/SPEC-005-iam.md) | IAM roles and policies |
| [SPEC-006](docs/components/SPEC-006-ansible.md) | Ansible playbook structure |
| [SPEC-007](docs/components/SPEC-007-cloudtrail.md) | CloudTrail S3 integration |

---

## Architecture Decisions

| ADR | Decision |
|---|---|
| [ADR-001](docs/decisions/ADR-001-opensearch-vs-s3.md) | OpenSearch Service vs S3 for findings storage |
| [ADR-002](docs/decisions/ADR-002-stateless-ec2.md) | Stateless EC2 with Git as source of truth |
| [ADR-003](docs/decisions/ADR-003-polling-vs-sqs.md) | S3 polling vs SQS-based ingestion |
| [ADR-004](docs/decisions/ADR-004-no-qa-environment.md) | No QA environment — read-only safety rationale |
| [ADR-005](docs/decisions/ADR-005-poc-to-production.md) | POC-to-production promotion strategy |

---

## Known Limitations

**SL-001 — Duplicate alerts on EC2 replacement**
Wazuh tracks processed S3 files in a local SQLite database lost on EC2
termination. A replacement instance re-processes ~5 minutes of recent logs,
generating duplicate alerts. Acceptable for POC.
Resolution (future): mount EFS for `/var/ossec/wodles/aws/`.

**SL-002 — Self-signed TLS certificate**
The ALB uses a self-signed certificate for POC. Browser will show a
security warning. Resolution (future): ACM + Route 53 custom domain.

**SL-003 — Single OpenSearch node**
No multi-AZ for the OpenSearch domain in POC. Domain unavailable during
AWS maintenance windows. Resolution (future): 2-node multi-AZ deployment.

---

## Roadmap

Selene is built POC-first with the intent to promote to production.
The architecture is production-grade from day one. Each phase below
removes an operational shortcut. See `docs/PRODUCTION-CHECKLIST.md`
for the full promotion gate.

| Phase | Description | Production Gate? | Status |
|---|---|---|---|
| POC | CloudTrail ingestion, Wazuh dashboard, OpenSearch, ASG recovery | No | 🔄 In progress |
| Phase 2 | DNS (selene.infillion.com) + ACM cert + 2-node OpenSearch | Yes — TLS + HA | ⏳ Planned |
| Phase 3 | Okta SAML dashboard auth + team VPN CIDR access | Yes — auth | ⏳ Planned |
| Phase 4 | SSM Session Manager only — remove port 22 | Yes — access hardening | ⏳ Planned |
| **Production** | All checklist items complete | **Promotion declared** | ⏳ |
| Phase 5 | SQS-based log ingestion (replace polling, lower latency) | No — optimization | ⏳ Planned |
| Phase 6 | EFS for Wazuh state (eliminate duplicate alerts on restart) | No — optimization | ⏳ Planned |
