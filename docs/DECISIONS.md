# Decisions Log

Running log of decisions made during the Selene project.
For formal architecture decisions, see `docs/decisions/ADR-*.md`.
This file captures smaller, day-to-day decisions that don't
warrant a full ADR but are worth recording.

---

## 2025 — Project Kickoff

**POC designed for production promotion**
The POC is not throwaway. The core architecture (stateless EC2, external
OpenSearch, Git-controlled config, CloudFormation) is production-grade
from day one. What changes at promotion time is the operational layer:
TLS cert, DNS, Okta auth, port 22 removed. See ADR-005 and
docs/PRODUCTION-CHECKLIST.md.

**No QA environment**
Selene is read-only — it cannot write to any monitored infrastructure.
Blast radius of any failure is bounded to its own components (alerts,
dashboard). Git + Ansible idempotency + CloudFormation rollback are the
change safety mechanisms. See ADR-004.


Chosen for the moon goddess concept — illuminating what happens in
the cloud. Short, pronounceable, no collision with existing AWS or
security product names.

**Wazuh all-in-one on a single EC2**
Distributed Wazuh (separate manager/indexer/dashboard nodes) is not
justified for 60-account CloudTrail volume. Single all-in-one on
t3.xlarge is simpler and sufficient. Revisit if alert volume grows
beyond ~500k/day.

**t3.xlarge for EC2**
Wazuh all-in-one needs minimum 8 GB RAM; 16 GB (t3.xlarge) gives
comfortable headroom for the indexer bridge and dashboard. t3.large
(8 GB) is at the limit and risks OOM under load.

**t3.medium.search for OpenSearch**
Single node, 100 GB gp3. Sufficient for 60-account CloudTrail at
estimated ~100 MB/day compressed. Upgrade path: t3.large.search or
add a second node for HA.

**ALB in front of Wazuh dashboard**
EC2 in private subnet, no public IP. ALB is the only entry point.
This is better security posture than putting EC2 directly in public
subnet even though it's more components to manage.

**Personal IP /32 for POC access**
Simplest possible access control for POC. Expand to team VPN CIDR
when other team members need access.

**Port 22 open to personal IP for now**
Pragmatic choice for active development. Replace with SSM Session
Manager in Phase 4 once POC is validated.

**CloudFormation only — no CDK, no Terraform**
Infillion's existing infrastructure is CloudFormation. Keeping
consistency reduces operational complexity. CDK adds a compilation
step; Terraform requires state management. Pure YAML CFN is the
simplest choice for this stack size.

**Four separate CloudFormation stacks**
iam → networking → opensearch → ec2
Separation allows individual stack updates without touching others.
IAM and networking change rarely; ec2 stack changes with every AMI
update. Stack outputs/imports are the contract between them.

**IMDSv2 required on EC2**
Security best practice. IMDSv1 disabled. No code in this project
requires IMDSv1 — the AWS CLI and Ansible AWS modules all support
IMDSv2.


## 2026-04-21 — POC Deployment Day

**91 accounts in org (not 60)**
Discovery showed 91 accounts under o-z70v8p3t14, not ~60 as originally
estimated. 19 are zero-activity reservation accounts (EC2 reserved
instance purchases with no workloads). These are harmless — the wodle
skips them in seconds. All specs updated from ~60 to 91.

**filebeat 7.10.2 incompatible with AL2023 kernel 6.1 — permanent replacement**
filebeat crashes with pthread_create: Operation not permitted due to
seccomp restrictions in AL2023 kernel 6.1. No configuration fix is
possible — this is a binary incompatibility with the Go 1.14 runtime.
selene-shipper.py (Python) permanently replaces filebeat. It replicates
all official Wazuh filebeat pipeline.json field transformations including
GeoIP lookups using the GeoLite2-City.mmdb bundled with wazuh-indexer.
This is logged as SL-005.

**Amazon OpenSearch Service not used — wazuh-indexer is local**
The Wazuh dashboard (Node.js) requires local OpenSearch on port 9200.
Amazon OpenSearch Service rejects the dashboard connection because:
1. The _nodes API is restricted (required by dashboard for version check)
2. OpenSearch 2.11 vs dashboard 2.19.4 version mismatch
3. The geoip ingest processor is not available in Amazon OpenSearch Service
Decision: wazuh-indexer runs locally. selene-opensearch CloudFormation
stack to be deleted (~$60/mo savings). ADR-001 is superseded.

**EBS volume for wazuh-indexer data persistence**
200GB gp3 EBS volume (vol-0b37de9c1bfd8afdd) mounted at
/var/lib/wazuh-indexer. Survives EC2 termination. UUID in /etc/fstab.
Reattachment to ASG replacement instances is not yet automated (SL-006).

**selene-shipper field normalizations match official pipeline.json**
The official Wazuh filebeat pipeline.json (github.com/wazuh/wazuh) defines
these transforms which selene-shipper replicates exactly:
- @timestamp ← timestamp (ISO8601)
- data.aws.accountId ← data.aws.aws_account_id
- data.aws.region ← data.aws.awsRegion
- GeoLocation ← geoip on data.srcip, data.aws.sourceIPAddress,
  data.aws.client_ip, data.win.eventdata.ipAddress,
  data.aws.service.action.networkConnectionAction.remoteIpDetails.ipAddressV4,
  data.aws.httpRequest.clientIp, data.gcp.jsonPayload.sourceIP,
  data.office365.ClientIP

**ossec.conf bucket name tag must be <name> not <n>**
Wazuh wazuh-modulesd rejects <n> with "No such child tag 'n' of bucket".
The correct XML tag for the bucket name in the aws-s3 wodle is <name>.
This caused repeated wazuh-manager startup failures during deployment.
Fixed in wazuh/templates/ossec.conf.j2.

**only_logs_after date format is YYYY-MMM-DD**
Wazuh aws-s3 wodle rejects numeric month format (2026-04-21).
Correct format is 2026-Apr-21. The SSM parameter /selene/only_logs_after
must use three-letter month abbreviation. SSM parameter updated.

**aws-s3 wodle uses aws_organization_id not path for org CloudTrail**
The <path> parameter causes Wazuh to double-prefix the path
(AWSLogs/o-z70v8p3t14/AWSLogs/). The correct approach for org-level
CloudTrail is the <aws_organization_id> tag which auto-resolves the
correct S3 path structure.

**ISM 90-day retention policy applied to local wazuh-indexer**
Policy selene-90-day-retention created on local wazuh-indexer with
ism_template covering wazuh-alerts-*. Applied manually to existing
indices. New indices auto-enrolled via ism_template.

**Ansible site.yml is single-file (no roles directory)**
The original SPEC-006 called for separate Ansible roles. During
implementation a flat single-file playbook was used instead. The roles
directory was removed. site.yml is the single source of truth for all
Ansible configuration tasks.

**Dashboard timezone set to UTC**
All alert timestamps are stored in UTC (@timestamp from Wazuh).
Setting the Wazuh dashboard timezone to UTC ensures time-range
filters match the actual data timestamps.

**S3 backlog ingestion rate**
With 91 accounts and only_logs_after set to 12 days prior, the wodle
processes accounts sequentially. At ~1 account per 15-20 minutes for
backlog, full coverage takes several hours. only_logs_after reset to
today (2026-Apr-21) to get all 91 accounts appearing in the dashboard
quickly. Backlog processing abandoned in favor of live coverage.
