# SPEC-009 — Implementation Plan

**Version:** 0.1  
**Status:** Draft  
**Author:** Aslan  
**Depends on:** SPEC-001 through SPEC-008  
**Project:** Selene  

---

## 1. Purpose

This spec defines the ordered sequence of tasks to build Selene from
scratch. Each task has explicit prerequisites, a spec reference, and
a done condition. Complete tasks in order unless marked as parallelizable.

This is the backlog. When you sit down to build, start at the first
incomplete task.

---

## 2. Critical Path

```
P0 (pre-work)
    │
    ▼
T01 selene-iam stack
    │
    ▼
T02 selene-networking stack
    │
    ├──────────────────────────────────┐
    ▼                                  │ (parallel)
T03 selene-opensearch stack         T04 Golden AMI bake
    │                                  │
    ▼                                  │ T05 Ansible roles
T06 Set /selene/opensearch_endpoint    │     (parallel with T03-T05)
    │                                  │
    └──────────────┬───────────────────┘
                   ▼
             T07 selene-ec2 stack
                   │
                   ▼
             T08 Bucket policy amendment
                   │
                   ▼
             T09 End-to-end verification
```

T04 (AMI bake), T05 (Ansible), and T03 (OpenSearch) can all run in
parallel after T02 completes. T07 (ec2 stack) is blocked until all
three are done and T06 (SSM) is set.

---

## 3. Pre-Work

### P0 — Environment Preparation
**Prerequisites:** None  
**Spec refs:** RESULTS.md, SPEC-008 Section 5  

- [ ] **P0.1** Push selene repo to `github.com/SecOpsHub/selene`
  ```bash
  cd selene
  git init
  git remote add origin https://github.com/SecOpsHub/selene.git
  git add .
  git commit -m "feat: initial project structure, specs, and documentation"
  git push -u origin main
  ```

- [ ] **P0.2** Set static SSM parameters (these do not depend on any stack)
  ```bash
  aws ssm put-parameter \
    --name /selene/cloudtrail_bucket \
    --value "logs.infillion.com" \
    --type String

  aws ssm put-parameter \
    --name /selene/cloudtrail_prefix \
    --value "AWSLogs/o-z70v8p3t14/" \
    --type String
  ```

- [ ] **P0.3** Verify public subnet route tables have an IGW route
  ```bash
  # Check route table for subnet-06e367114ba47947a (ALB subnet 1)
  aws ec2 describe-route-tables \
    --filters "Name=association.subnet-id,Values=subnet-06e367114ba47947a" \
    --query 'RouteTables[*].Routes[?GatewayId!=`local`]'
  ```
  Done when: output shows a route with `DestinationCidrBlock: 0.0.0.0/0`
  and a `GatewayId` starting with `igw-`.

- [ ] **P0.4** Confirm AWS CLI is configured with management account credentials
  ```bash
  aws sts get-caller-identity
  # Expected: Account: 757548139022
  ```

**P0 done when:** Repo is on GitHub, 2 SSM parameters exist, IGW route
confirmed, correct AWS identity confirmed.

---

## 4. Stack Tasks

### T01 — selene-iam Stack
**Prerequisites:** P0 complete  
**Spec refs:** SPEC-005, SPEC-008 Section 4.1  
**File to create:** `infra/iam.yml`  
**Complexity:** Low — IAM only, no VPC dependencies  

**What this template creates:**
- IAM role: `selene-wazuh-instance-role`
- IAM instance profile: `selene-wazuh-instance-profile`
- Inline policy: CloudTrail S3 read (scoped to org prefix)
- Inline policy: SSM parameter read (scoped to `/selene/*`)
- Inline policy: OpenSearch write (scoped to `selene-findings` domain)
- Managed policy attachment: `AmazonSSMManagedInstanceCore`

**Stack parameters:**
- `CloudTrailBucket` = `logs.infillion.com`
- `CloudTrailPrefix` = `AWSLogs/o-z70v8p3t14/`
- `OpenSearchDomainName` = `selene-findings`

**Stack exports (exact names — see SPEC-008):**
- `selene-InstanceRoleArn`
- `selene-InstanceProfileArn`

**Deploy command:**
```bash
aws cloudformation deploy \
  --template-file infra/iam.yml \
  --stack-name selene-iam \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    CloudTrailBucket=logs.infillion.com \
    CloudTrailPrefix="AWSLogs/o-z70v8p3t14/" \
    OpenSearchDomainName=selene-findings
```

**Done when:**
- Stack status: `CREATE_COMPLETE`
- Both exports visible in CloudFormation console
- `aws iam get-role --role-name selene-wazuh-instance-role` returns the role
- Verify no wildcard `*` actions in any policy (AC6 from SPEC-005)

---

### T02 — selene-networking Stack
**Prerequisites:** T01 complete  
**Spec refs:** SPEC-002, SPEC-008 Section 4.2  
**File to create:** `infra/networking.yml`  
**Complexity:** Medium — ALB, multiple SGs, listener rules, target group  

**What this template creates:**
- Security group: `selene-alb-sg`
- Security group: `selene-ec2-sg`
- Security group: `selene-opensearch-sg`
- Separate `AWS::EC2::SecurityGroupIngress` resources for inter-SG rules
  (avoids CloudFormation circular dependency — see SPEC-008 Section 7)
- ALB: `selene-alb` (internet-facing, 2 public subnets)
- ALB listener: port 80 → redirect to 443
- ALB listener: port 443 → forward to target group
- Target group: HTTPS, port 443, health check path `/`

**Stack parameters:**
- `VpcId` = `vpc-06cdf666adc9f698d`
- `AlbSubnet1` = `subnet-06e367114ba47947a`
- `AlbSubnet2` = `subnet-0a2291ca1fe4900c0`
- `Ec2Subnet` = `subnet-0934cf17ca2678038`
- `AllowedCidr` = Your IP /32

**Stack exports (exact names — see SPEC-008):**
- `selene-AlbDnsName`
- `selene-AlbTargetGroupArn`
- `selene-Ec2SecurityGroupId`
- `selene-OpensearchSecurityGroupId`
- `selene-VpcId`

**Deploy command:**
```bash
aws cloudformation deploy \
  --template-file infra/networking.yml \
  --stack-name selene-networking \
  --parameter-overrides \
    VpcId=vpc-06cdf666adc9f698d \
    AlbSubnet1=subnet-06e367114ba47947a \
    AlbSubnet2=subnet-0a2291ca1fe4900c0 \
    Ec2Subnet=subnet-0934cf17ca2678038 \
    AllowedCidr=<your-ip>/32
```

**Done when:**
- Stack status: `CREATE_COMPLETE`
- All five exports visible
- ALB DNS name in outputs — note it down
- ALB health check shows no healthy targets yet (expected — EC2 not deployed)
- Verify: port 443 from your IP returns connection (even if 503 — ALB is up)
- Verify: port 443 from a different IP returns timeout

---

### T03 — selene-opensearch Stack
**Prerequisites:** T02 complete  
**Spec refs:** SPEC-004, SPEC-008 Section 4.3  
**File to create:** `infra/opensearch.yml`  
**Complexity:** Medium — OpenSearch takes 15-20 min to provision  

**What this template creates:**
- OpenSearch domain: `selene-findings`
- Engine: OpenSearch 2.x (latest)
- Instance: `t3.medium.search` × 1
- Storage: 100 GB gp3, encrypted at rest
- VPC placement: `subnet-0934cf17ca2678038`
- Security group: imported from selene-networking
- Fine-grained access control: enabled, IAM master user (instance role)
- HTTPS enforced, no public endpoint

**Stack imports (from preceding stacks):**
- `selene-OpensearchSecurityGroupId` (from selene-networking)
- `selene-VpcId` (from selene-networking)
- `selene-InstanceRoleArn` (from selene-iam)

**Stack parameters:**
- `OpenSearchSubnet` = `subnet-0934cf17ca2678038`
- `EbsVolumeSize` = `100`

**Stack exports:**
- `selene-OpenSearchEndpoint`
- `selene-OpenSearchArn`
- `selene-OpenSearchDomainName`

**Deploy command:**
```bash
aws cloudformation deploy \
  --template-file infra/opensearch.yml \
  --stack-name selene-opensearch \
  --parameter-overrides \
    OpenSearchSubnet=subnet-0934cf17ca2678038 \
    EbsVolumeSize=100
```

**⚠️ OpenSearch takes 15-20 minutes to provision.** This is normal.
Watch status with:
```bash
watch -n 30 "aws opensearch describe-domain \
  --domain-name selene-findings \
  --query 'DomainStatus.Processing'"
# Done when: false
```

**Done when:**
- Stack status: `CREATE_COMPLETE`
- Domain processing: `false`
- Domain endpoint visible in stack outputs
- Proceed immediately to T06

---

### T06 — Set OpenSearch SSM Parameter
**Prerequisites:** T03 complete  
**Spec refs:** SPEC-008 Section 5  
**Complexity:** Trivial — one CLI command  

```bash
ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name selene-opensearch \
  --query 'Stacks[0].Outputs[?OutputKey==`OpenSearchEndpoint`].OutputValue' \
  --output text)

aws ssm put-parameter \
  --name /selene/opensearch_endpoint \
  --value "$ENDPOINT" \
  --type String

echo "Set: $ENDPOINT"
```

**Done when:** All three SSM parameters exist:
```bash
aws ssm get-parameters-by-path --path /selene/ \
  --query 'Parameters[*].{Name:Name,Value:Value}'
# Expected: 3 parameters — bucket, prefix, opensearch_endpoint
```

---

## 5. Parallel Track: Golden AMI

*Can start after T02 is complete. Must finish before T07.*

### T04 — Golden AMI Bake
**Prerequisites:** T02 complete (need a subnet to launch the bake instance)  
**Spec refs:** SPEC-003 Section 2, runbooks/golden-ami-bake.md  
**Complexity:** Medium — follow the runbook exactly  

Follow `docs/runbooks/golden-ami-bake.md` step by step.

**Key checkpoints:**
- [ ] Wazuh all-in-one install completes without errors
- [ ] All Wazuh services stop cleanly after install
- [ ] `ls /var/ossec/etc/ossec.conf` returns no such file (removed)
- [ ] Ansible, git, aws CLI all present
- [ ] AMI created with name `selene-wazuh-YYYYMMDD`
- [ ] Bake instance terminated

**Record the AMI ID here:** `ami-` (fill in after bake)

**Done when:** AMI status is `available`:
```bash
aws ec2 describe-images \
  --owners self \
  --filters "Name=name,Values=selene-wazuh-*" \
  --query 'Images[*].{ImageId:ImageId,Name:Name,State:State}'
```

---

## 6. Parallel Track: Ansible Roles

*Can start any time. Must be committed to GitHub before T07.*

### T05 — Implement Ansible Roles
**Prerequisites:** SPEC-006, SPEC-007, SPEC-008 Section 6 understood  
**Spec refs:** SPEC-006, SPEC-007, SPEC-008  
**Files to complete:** All role `tasks/main.yml` files + `ossec.conf.j2`  
**Complexity:** High — most of the configuration logic lives here  

Complete in this order (each role depends on the previous working):

#### T05.1 — wazuh_services role
Simplest role. Ensures services are in the correct state.

Tasks:
- Enable and start `wazuh-indexer`
- Enable and start `wazuh-manager`
- Enable and start `wazuh-dashboard`
- Handler: restart services in correct order when notified

Done when: `ansible-playbook site.yml` on a running Wazuh instance
starts all three services.

#### T05.2 — wazuh_config role + ossec.conf.j2 template
The most critical role. Renders the full `ossec.conf` from template.

`ossec.conf.j2` must include:
- `<wodle name="aws-s3">` block with:
  - `bucket`: `{{ cloudtrail_bucket }}`
  - `path`: `{{ cloudtrail_prefix }}`
  - `type`: `cloudtrail`
  - `only_logs_after`: deploy date (set at bake time or passed as variable)
  - `interval`: `5m`
  - `run_on_start`: `yes`
- OpenSearch output block pointing at `{{ opensearch_endpoint }}`
- Standard Wazuh global and alerts config

Tasks:
- Template `ossec.conf.j2` → `/var/ossec/etc/ossec.conf`
- Notify restart handler if file changed (idempotent)

Done when: rendered `ossec.conf` on EC2 contains the correct bucket,
prefix, and OpenSearch endpoint values.

#### T05.3 — wazuh_indexer role
Configures the local Wazuh indexer to forward to external OpenSearch
rather than storing locally.

Tasks:
- Configure `/etc/wazuh-indexer/opensearch.yml` with `{{ opensearch_endpoint }}`
- Set correct auth (IAM-based, no username/password)
- Notify restart handler if config changed

Done when: Wazuh indexer connects to OpenSearch domain without error
(`/var/ossec/logs/ossec.log` shows no connection errors).

#### T05.4 — wazuh_rules role
Deploys custom rules and suppressions from Git.

Tasks:
- Copy `wazuh/rules/local_rules.xml` → `/var/ossec/etc/rules/local_rules.xml`
- Copy `wazuh/suppressions/local_overrides.xml` → `/var/ossec/etc/local_overrides.xml`
- Notify restart handler if either file changed

Done when: `ansible-playbook site.yml` twice in a row — second run
shows zero `changed` tasks (idempotency confirmed).

#### T05.5 — Full playbook smoke test
Run the complete playbook against the baked AMI instance (before ASG):

```bash
# On the EC2 instance (SSH in directly for this test)
cd /opt && git clone https://github.com/SecOpsHub/selene
ansible-playbook /opt/selene/ansible/site.yml \
  --inventory /opt/selene/ansible/inventory/localhost \
  --extra-vars "opensearch_endpoint=<endpoint> \
                cloudtrail_bucket=logs.infillion.com \
                cloudtrail_prefix=AWSLogs/o-z70v8p3t14/"
```

Done when: playbook completes with 0 failures, Wazuh services running,
dashboard reachable on port 443 locally.

---

## 7. Integration: EC2 Stack and Verification

### T07 — selene-ec2 Stack
**Prerequisites:** T03 + T04 + T05 + T06 all complete  
**Spec refs:** SPEC-003, SPEC-008 Section 4.4  
**File to create:** `infra/ec2-asg.yml`  
**Complexity:** Medium  

**What this template creates:**
- Launch Template: `selene-wazuh-lt`
  - AMI: parameter (filled with AMI ID from T04)
  - Instance type: `t3.xlarge`
  - Instance profile: imported from selene-iam
  - Security group: imported from selene-networking
  - Subnet: `subnet-0934cf17ca2678038`
  - No public IP
  - IMDSv2 required
  - UserData: reads 3 SSM params, clones repo, runs Ansible
- ASG: `selene-asg`
  - Desired/Min/Max: 1/1/1
  - Health check: ELB, grace period 600s
  - Target group: imported from selene-networking

**Stack imports:**
- `selene-InstanceProfileArn` (from selene-iam)
- `selene-Ec2SecurityGroupId` (from selene-networking)
- `selene-AlbTargetGroupArn` (from selene-networking)

**Stack parameters:**
- `AmiId` = AMI ID from T04
- `Ec2Subnet` = `subnet-0934cf17ca2678038`
- `InstanceType` = `t3.xlarge`
- `HealthCheckGracePeriod` = `600`

**Deploy command:**
```bash
aws cloudformation deploy \
  --template-file infra/ec2-asg.yml \
  --stack-name selene-ec2 \
  --parameter-overrides \
    AmiId=<ami-id-from-T04> \
    Ec2Subnet=subnet-0934cf17ca2678038 \
    InstanceType=t3.xlarge \
    HealthCheckGracePeriod=600
```

**Watch the boot:**
```bash
# Get instance ID
INSTANCE_ID=$(aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names selene-asg \
  --query 'AutoScalingGroups[0].Instances[0].InstanceId' \
  --output text)

# Tail init log (requires SSM Session Manager or SSH)
aws ssm start-session --target $INSTANCE_ID
sudo tail -f /var/log/selene-init.log
```

**Done when:**
- Stack status: `CREATE_COMPLETE`
- EC2 instance healthy in target group
- ALB returns HTTP 200 on HTTPS from your IP

---

### T08 — Bucket Policy Amendment
**Prerequisites:** T01 complete (role ARN exists)  
**Spec refs:** SPEC-005 Section 3  
**Complexity:** Low — one policy statement added  

Add the Selene read statement to `logs.infillion.com` bucket policy.
The exact JSON is in SPEC-005 Section 3.

**⚠️ This modifies existing infrastructure.** Review the current bucket
policy before making changes. Add the statement — do not replace the
existing policy.

```bash
# View current policy first
aws s3api get-bucket-policy --bucket logs.infillion.com

# Then add the Selene statement via console or CLI
# Use the exact JSON from SPEC-005 Section 3
```

**Done when:**
```bash
# From the EC2 instance:
aws s3 ls s3://logs.infillion.com/AWSLogs/o-z70v8p3t14/ | head -5
# Expected: list of account ID prefixes
```

---

### T09 — End-to-End Verification
**Prerequisites:** T07 + T08 complete  
**Spec refs:** SPEC-001 Section 11 (Acceptance Criteria)  

Work through every acceptance criterion from SPEC-001:

| AC | Criterion | Verified |
|---|---|---|
| AC1 | All four CloudFormation stacks deploy without errors | |
| AC2 | Dashboard reachable via ALB DNS on HTTPS from allowed IP | |
| AC3 | CloudTrail events from ≥3 accounts appear as Wazuh alerts | |
| AC4 | EC2 termination → working dashboard within 10 minutes | |
| AC5 | OpenSearch findings intact after EC2 replacement | |
| AC6 | Custom rule in `local_rules.xml` fires on test event | |
| AC7 | Suppression in `local_overrides.xml` silences noisy event | |
| AC8 | Full rebuild from AMI + Ansible completes unattended | |

**AC3 verification — how to trigger a test event:**
```bash
# Generate a CloudTrail event in any member account
# The simplest: describe EC2 instances (read-only, harmless)
aws ec2 describe-instances --profile <member-account-profile>
# Wait up to 5 minutes, then check Wazuh dashboard for the event
```

**AC6 verification — test a custom rule:**
Add a rule to `wazuh/rules/local_rules.xml` that fires on
`DescribeInstances` events, commit, re-run playbook, trigger the
event, confirm alert appears in dashboard.

**Done when:** All 8 AC items checked. POC is technically complete.
Proceed to management presentation (Gate 0 of PRODUCTION-CHECKLIST.md).

---

## 8. Task Summary Table

| Task | Description | Depends On | Parallel? | Complexity |
|---|---|---|---|---|
| P0 | Environment prep, SSM static params | — | — | Low |
| T01 | selene-iam stack | P0 | No | Low |
| T02 | selene-networking stack | T01 | No | Medium |
| T03 | selene-opensearch stack | T02 | With T04, T05 | Medium |
| T04 | Golden AMI bake | T02 | With T03, T05 | Medium |
| T05 | Ansible roles (4 roles + template) | T02 | With T03, T04 | High |
| T06 | Set opensearch_endpoint SSM param | T03 | No | Trivial |
| T07 | selene-ec2 stack | T03+T04+T05+T06 | No | Medium |
| T08 | Bucket policy amendment | T01 | After T01, before T09 | Low |
| T09 | End-to-end verification | T07+T08 | No | — |

**Estimated total build time:**
- Sequential (one person): 2-3 focused days
- T03 (OpenSearch) adds 15-20 min wait that can be used for T04/T05
- T04 (AMI bake) adds ~45-60 min that can be used for T05

---

## 9. Acceptance Criteria for Phase 4

Phase 4 (this spec) is complete when T09 is done and all AC items
in SPEC-001 Section 11 are verified. The system is then POC-complete
and ready for management presentation.
