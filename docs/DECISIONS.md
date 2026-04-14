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
