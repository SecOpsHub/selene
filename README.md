# Selene

Self-hosted SIEM for the Infillion AWS Organization, built on
[Wazuh](https://wazuh.com/) with a local OpenSearch indexer.

Selene ingests org-wide CloudTrail logs from 91 AWS accounts,
generates security findings, and provides a team-accessible dashboard —
replacing expensive third-party SIEM tooling at a fraction of the cost.
All infrastructure is CloudFormation. All server configuration is Ansible.
Findings are stored on a persistent EBS volume that survives EC2 replacement.

**Status:** POC — running  
**Monthly cost target:** ≤ $350/mo  
**RTO:** ≤ 10 minutes (ASG + Golden AMI)

---

## Architecture

```
CloudTrail logs (all 91 accounts)
        │
        ▼
S3 Bucket (logs.infillion.com) ── 1-year retention
        │
        ▼ polls every 5 min via aws-s3 wodle
Wazuh EC2  (t3.xlarge, private subnet)
- wazuh-manager: processes CloudTrail logs, applies rules, writes alerts
- wazuh-indexer: local OpenSearch (port 9200) — stores findings on EBS
- wazuh-dashboard: reads from wazuh-indexer, serves UI on port 443
- selene-shipper: Python service that ships alerts to wazuh-indexer
        │
        ▼ EBS volume (200GB gp3, persistent)
/var/lib/wazuh-indexer  ← findings survive EC2 replacement

Access: Your IP → ALB (HTTPS 443) → Wazuh Dashboard
```

> **Note on Amazon OpenSearch Service:** The selene-opensearch CloudFormation
> stack was deployed but is not used. The Wazuh dashboard requires local
> wazuh-indexer on port 9200. Amazon OpenSearch Service does not expose the
> _nodes API required by the dashboard. The stack will be deleted.

Full architecture spec: [docs/architecture/SPEC-001-architecture.md](docs/architecture/SPEC-001-architecture.md)

---

## Repository Structure

```
selene/
├── docs/
│   ├── architecture/          # SPEC-001, SPEC-008, SPEC-009
│   ├── components/            # SPEC-002 through SPEC-007
│   ├── decisions/             # Architecture Decision Records (ADRs)
│   ├── runbooks/              # Operational procedures
│   └── discovery/             # AWS environment discovery scripts + results
├── infra/                     # CloudFormation templates (one per component)
├── ansible/
│   ├── site.yml               # Master playbook (single-file, no roles)
│   ├── inventory/
│   ├── files/
│   │   ├── selene-shipper.py      # Alert shipping service (replaces filebeat)
│   │   └── selene-shipper.service # systemd unit
│   └── templates/
│       ├── opensearch_dashboards.yml.j2
│       └── filebeat.yml.j2        # Kept for reference (filebeat disabled)
└── wazuh/
    ├── rules/                 # Custom detection rules (XML)
    ├── suppressions/          # Alert suppressions
    └── templates/
        └── ossec.conf.j2      # Wazuh manager config template
```

---

## Prerequisites

- AWS CLI configured with management account credentials
- Access to SecOpsHub/selene on GitHub
- A Golden AMI already baked (see docs/runbooks/golden-ami-bake.md)
- SSM parameters pre-populated (see Deployment below)

---

## Deployment

### 1. Set SSM Parameters
```bash
aws ssm put-parameter --name /selene/cloudtrail_bucket \
  --value "logs.infillion.com" --type String

aws ssm put-parameter --name /selene/cloudtrail_org_id \
  --value "o-z70v8p3t14" --type String

# Format must be YYYY-MMM-DD (e.g. 2026-Apr-21), not YYYY-MM-DD
aws ssm put-parameter --name /selene/only_logs_after \
  --value "2026-Apr-21" --type String

aws ssm put-parameter --name /selene/wazuh_indexer_admin_password \
  --value "<password from wazuh-passwords.txt>" --type SecureString
```

### 2. Deploy Stacks (in dependency order)
```bash
aws cloudformation deploy --template-file infra/iam.yml \
  --stack-name selene-iam --capabilities CAPABILITY_NAMED_IAM

aws cloudformation deploy --template-file infra/networking.yml \
  --stack-name selene-networking

# selene-opensearch: deployed but not used — skip or delete
# aws cloudformation delete-stack --stack-name selene-opensearch

aws cloudformation deploy --template-file infra/ec2-asg.yml \
  --stack-name selene-ec2
```

### 3. Run Ansible
```bash
sudo ansible-playbook /opt/selene/ansible/site.yml \
  --inventory /opt/selene/ansible/inventory/localhost \
  --extra-vars "opensearch_endpoint=unused \
                cloudtrail_bucket=$(aws ssm get-parameter --name /selene/cloudtrail_bucket --query Parameter.Value --output text) \
                cloudtrail_org_id=$(aws ssm get-parameter --name /selene/cloudtrail_org_id --query Parameter.Value --output text) \
                only_logs_after=$(aws ssm get-parameter --name /selene/only_logs_after --query Parameter.Value --output text)"
```

### 4. Verify
- Get ALB DNS from selene-networking stack Outputs
- Navigate to https://<alb-dns> — Wazuh dashboard appears within 10 min
- Check: sudo journalctl -u selene-shipper | grep Shipped | tail -5

---

## Alert Ingestion Pipeline

```
wazuh-manager
    │ writes JSON alerts
    ▼
/var/ossec/logs/alerts/alerts.json
    │ tailed every 5 seconds
    ▼
selene-shipper.py (Python, replicates official pipeline.json transforms)
    │   @timestamp  ← timestamp
    │   data.aws.accountId  ← data.aws.aws_account_id
    │   data.aws.region     ← data.aws.awsRegion
    │   GeoLocation  ← geoip lookup on sourceIPAddress (GeoLite2-City.mmdb)
    ▼
wazuh-indexer (local OpenSearch port 9200, data on 200GB EBS)
    │ read by
    ▼
wazuh-dashboard (port 443) ← ALB ← team browser
```

### Why selene-shipper instead of filebeat?
filebeat 7.10.2 (bundled with Wazuh) crashes on AL2023 kernel 6.1 with
pthread_create: Operation not permitted. selene-shipper is a Python
replacement that replicates all official Wazuh filebeat pipeline.json
field transformations. This is a permanent architectural decision, not
a temporary workaround.

---

## Configuration

### Adding a Detection Rule
1. Edit wazuh/rules/local_rules.xml
2. Commit and push to main
3. On EC2: sudo git -C /opt/selene pull && sudo ansible-playbook ...

### SSM Parameters

| Parameter | Type | Description |
|---|---|---|
| /selene/cloudtrail_bucket | String | CloudTrail S3 bucket |
| /selene/cloudtrail_org_id | String | AWS Organization ID |
| /selene/only_logs_after | String | Ingestion start date (YYYY-MMM-DD) |
| /selene/wazuh_indexer_admin_password | SecureString | Local indexer admin password |
| /selene/opensearch_endpoint | String | Amazon OpenSearch endpoint (unused) |

---

## Runbooks

- [Golden AMI Bake](docs/runbooks/golden-ami-bake.md)
- [Disaster Recovery](docs/runbooks/disaster-recovery.md)

---

## Specs

| Spec | Description |
|---|---|
| SPEC-001 | System architecture |
| SPEC-002 | Networking, ALB, security groups |
| SPEC-003 | EC2, ASG, Launch Template, Golden AMI |
| SPEC-004 | Amazon OpenSearch Service (deployed but not used — pending deletion) |
| SPEC-005 | IAM roles and policies |
| SPEC-006 | Ansible playbook structure |
| SPEC-007 | CloudTrail S3 integration |
| SPEC-008 | Interface contracts |
| SPEC-009 | Implementation plan |

---

## Known Limitations

**SL-001** — Duplicate alerts on EC2 replacement (S3 cursor lost). Future: EFS mount.
**SL-002** — Self-signed TLS / ALB DNS name instead of selene.infillion.com. Future: Route 53 Phase 2.
**SL-005** — filebeat 7.10.2 incompatible with AL2023 kernel 6.1. Resolution: selene-shipper (permanent).
**SL-006** — EBS reattach on ASG replacement not automated. Future: UserData reattach logic.

---

## Roadmap

| Phase | Description | Status |
|---|---|---|
| POC | CloudTrail ingestion, dashboard, local indexer, EBS persistence | Running |
| Phase 2 | DNS + ACM cert + EBS reattach automation | Planned |
| Phase 3 | Okta SAML + team VPN CIDR | Planned |
| Phase 4 | SSM Session Manager only, remove port 22 | Planned |
| Production | All checklist items complete | Planned |
| Phase 5 | SQS-based ingestion | Planned |
| Phase 6 | EFS for Wazuh state | Planned |
