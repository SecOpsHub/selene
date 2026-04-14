# SPEC-003 — EC2, ASG, Launch Template, and Golden AMI

**Version:** 0.1  
**Status:** Draft  
**Depends on:** SPEC-002, SPEC-005  
**CloudFormation stack:** `selene-ec2`

---

## 1. Overview

Wazuh runs as an all-in-one installation on a single EC2 instance.
The instance is ephemeral by design — all configuration comes from Ansible
on boot, all findings state lives in OpenSearch. The ASG ensures automatic
replacement on failure.

---

## 2. Golden AMI

The Golden AMI is a pre-baked snapshot with Wazuh installed but not
configured. Configuration happens at runtime via Ansible. This makes
boot time fast (~5 min) without baking environment-specific values
into the image.

### 2.1 Bake Process (manual)

See full procedure: [docs/runbooks/golden-ami-bake.md](../runbooks/golden-ami-bake.md)

Summary:
1. Launch base Amazon Linux 2023 `t3.xlarge` in prod VPC
2. Install Wazuh all-in-one (manager + indexer + dashboard)
3. Install Ansible, git, aws CLI
4. Stop all Wazuh services (config applied later by Ansible)
5. Remove any environment-specific values from Wazuh config
6. Create AMI: name `selene-wazuh-YYYYMMDD`
7. Terminate bake instance

### 2.2 AMI Naming Convention

```
selene-wazuh-YYYYMMDD
```

When updating the AMI, create a new one with today's date.
Update the Launch Template to point to the new AMI.
Old AMIs are kept for 90 days then deregistered.

### 2.3 Rebake Triggers

Rebake the AMI when:
- A new major Wazuh version is released
- Amazon Linux 2023 security patches require it (monthly cadence)
- A new base dependency (Ansible, git) requires update

---

## 3. Launch Template

| Property | Value |
|---|---|
| AMI | Latest `selene-wazuh-YYYYMMDD` |
| Instance type | `t3.xlarge` (4 vCPU, 16 GB RAM) |
| IAM instance profile | `selene-wazuh-instance-profile` (SPEC-005) |
| Security group | `selene-ec2-sg` (SPEC-002) |
| Subnet | Private subnet (from RESULTS.md) |
| Public IP | No |
| EBS root volume | 50 GB gp3, encrypted |
| Metadata IMDSv2 | Required (IMDSv1 disabled) |

### 3.1 UserData Script

Runs on every instance launch. Pulls config from Git and applies it.

```bash
#!/bin/bash
set -euo pipefail

# Log all output
exec > >(tee /var/log/selene-init.log) 2>&1
echo "Selene init started: $(date)"

# Read configuration from SSM Parameter Store
OPENSEARCH_ENDPOINT=$(aws ssm get-parameter \
  --name /selene/opensearch_endpoint \
  --query Parameter.Value --output text)

CLOUDTRAIL_BUCKET=$(aws ssm get-parameter \
  --name /selene/cloudtrail_bucket \
  --query Parameter.Value --output text)

# Clone the selene repo (latest main)
cd /opt
git clone https://github.com/SecOpsHub/selene
cd selene

# Run the Ansible playbook
ansible-playbook ansible/site.yml \
  --inventory ansible/inventory/localhost \
  --extra-vars "opensearch_endpoint=${OPENSEARCH_ENDPOINT} \
                cloudtrail_bucket=${CLOUDTRAIL_BUCKET}"

echo "Selene init complete: $(date)"
```

---

## 4. Auto Scaling Group

| Property | Value |
|---|---|
| Desired capacity | 1 |
| Minimum capacity | 1 |
| Maximum capacity | 1 |
| Health check type | ELB |
| Health check grace period | 600 seconds |
| Target groups | selene ALB target group (from selene-networking stack) |
| Termination policy | OldestInstance |

The grace period of 600 seconds gives Wazuh time to start before the
ALB health check begins evaluating the instance. Wazuh all-in-one takes
approximately 3-4 minutes to fully start.

---

## 5. Instance Sizing Rationale

`t3.xlarge` (4 vCPU, 16 GB RAM) is chosen because:

- Wazuh all-in-one (manager + OpenSearch indexer + dashboard) recommends
  minimum 8 GB RAM; 16 GB provides comfortable headroom
- The Wazuh indexer is used only as a bridge to forward to external
  OpenSearch — minimal local index storage required
- CloudTrail logs for 60 accounts at typical volume (~50k events/day)
  are well within the capacity of a single t3.xlarge

---

## 6. CloudFormation Stack Outputs

| Export Name | Value |
|---|---|
| `selene-Ec2InstanceId` | Current EC2 instance ID |
| `selene-AsgName` | ASG name (for manual operations) |

---

## 7. Acceptance Criteria

| ID | Criterion |
|---|---|
| AC1 | EC2 instance launches and passes ALB health check within 10 minutes |
| AC2 | Wazuh dashboard is accessible via ALB after launch |
| AC3 | Manually terminating the EC2 results in a replacement within 10 minutes |
| AC4 | Replacement instance has identical Wazuh configuration (rules, config) |
| AC5 | `/var/log/selene-init.log` shows successful Ansible run on new instance |
| AC6 | IMDSv2 is enforced (IMDSv1 returns 401) |
| AC7 | No environment-specific values are baked into the Golden AMI |
