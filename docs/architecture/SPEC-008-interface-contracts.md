# SPEC-008 — Interface Contracts

**Version:** 0.1  
**Status:** Draft  
**Author:** Aslan  
**Depends on:** SPEC-001 through SPEC-007  
**Project:** Selene  

---

## 1. Purpose

This spec defines the exact contracts between all Selene components.
It is the authoritative reference for:

- CloudFormation stack outputs and cross-stack imports
- SSM Parameter Store schema
- Ansible variable interface
- Security group reference model
- Fixed naming contracts (domain names, role names, stack names)

Every value defined here is a commitment. If a CloudFormation template
exports `selene-AlbTargetGroupArn`, it must use exactly that name.
If the OpenSearch domain is named `selene-findings`, it must be exactly
that. Downstream components depend on these names being stable.

---

## 2. Fixed Naming Contracts

These names are chosen here and never change. They are not discovered
or generated — they are declared.

**Important: Two different things are called "domain" in this system.**

| Term | Value | What It Is |
|---|---|---|
| OpenSearch "domain" | `selene-findings` | AWS's internal name for the OpenSearch cluster. Not DNS. Not public. Used in ARNs and CLI commands only. |
| Public DNS name | `selene.infillion.com` | The URL the team types in a browser. Route 53 + ACM + ALB. Phase 2. |

These two names have nothing to do with each other. `selene-findings`
never appears in a browser. `selene.infillion.com` never appears in an
IAM policy.

| Resource | Fixed Name | Reason Fixed |
|---|---|---|
| OpenSearch cluster | `selene-findings` | IAM policy ARN hardcodes this; must be declared before OpenSearch deploys |
| Public dashboard URL | `selene.infillion.com` | Confirmed — Route 53 + ACM in Phase 2 |
| IAM role | `selene-wazuh-instance-role` | Bucket policy references this ARN |
| IAM instance profile | `selene-wazuh-instance-profile` | Launch Template references by name |
| CloudFormation stacks | `selene-iam`, `selene-networking`, `selene-opensearch`, `selene-ec2` | Cross-stack import references |
| ASG name | `selene-asg` | Operational runbooks reference this |
| Launch Template name | `selene-wazuh-lt` | AMI update procedure references this |
| ALB name | `selene-alb` | Route 53 alias target in Phase 2 |

---

## 3. CloudFormation Stack Dependency Graph

```
selene-iam
    │ exports: InstanceRoleArn, InstanceProfileArn
    ▼
selene-networking
    │ exports: AlbTargetGroupArn, Ec2SecurityGroupId,
    │          OpensearchSecurityGroupId, AlbDnsName, VpcId
    ▼
selene-opensearch
    │ outputs: OpenSearchEndpoint (→ stored in SSM manually after deploy)
    │          OpenSearchArn, OpenSearchDomainName
    ▼
selene-ec2
    (imports from all three preceding stacks via Fn::ImportValue)
```

**Note on IAM → OpenSearch ordering:**
The IAM stack references the OpenSearch domain by its fixed name
`selene-findings` (see Section 2). The domain does not need to exist
when IAM deploys — the ARN is constructed from the known account ID,
region, and fixed domain name. This avoids a circular dependency.

---

## 4. Stack Outputs and Imports

### 4.1 selene-iam

**Exports (consumed by other stacks):**

| Export Name | Value | Consumed By |
|---|---|---|
| `selene-InstanceRoleArn` | ARN of `selene-wazuh-instance-role` | selene-opensearch (fine-grained access), selene-ec2 |
| `selene-InstanceProfileArn` | ARN of `selene-wazuh-instance-profile` | selene-ec2 Launch Template |

**This stack has no imports** — it is the root of the dependency graph.

**Parameters (inputs at deploy time):**

| Parameter | Default | Description |
|---|---|---|
| `CloudTrailBucket` | `logs.infillion.com` | Used to scope S3 IAM policy |
| `CloudTrailPrefix` | `AWSLogs/o-z70v8p3t14/` | Used to scope S3 resource ARN |
| `OpenSearchDomainName` | `selene-findings` | Used to construct OpenSearch ARN |

---

### 4.2 selene-networking

**Exports (consumed by other stacks):**

| Export Name | Value | Consumed By |
|---|---|---|
| `selene-AlbDnsName` | ALB DNS name | Documentation, RESULTS.md |
| `selene-AlbTargetGroupArn` | Target group ARN | selene-ec2 ASG |
| `selene-Ec2SecurityGroupId` | EC2 SG ID | selene-ec2 Launch Template, selene-opensearch inbound rule |
| `selene-OpensearchSecurityGroupId` | OpenSearch SG ID | selene-opensearch domain config |
| `selene-VpcId` | VPC ID | selene-opensearch domain config |

**This stack has no imports** — all values are hardcoded parameters.

**Parameters (inputs at deploy time):**

| Parameter | Value | Description |
|---|---|---|
| `VpcId` | `vpc-06cdf666adc9f698d` | Existing production VPC |
| `AlbSubnet1` | `subnet-06e367114ba47947a` | Public subnet us-east-1a |
| `AlbSubnet2` | `subnet-0a2291ca1fe4900c0` | Public subnet us-east-1b |
| `Ec2Subnet` | `subnet-0934cf17ca2678038` | Private subnet us-east-1a |
| `AllowedCidr` | Your IP /32 | ALB and SSH inbound allow |

---

### 4.3 selene-opensearch

**Exports:**

| Export Name | Value | Consumed By |
|---|---|---|
| `selene-OpenSearchEndpoint` | VPC endpoint hostname | → Stored manually in SSM after deploy |
| `selene-OpenSearchArn` | Domain ARN | Documentation |
| `selene-OpenSearchDomainName` | `selene-findings` | Documentation |

**Imports (from preceding stacks):**

| Import Name | Source Stack | Used For |
|---|---|---|
| `selene-Ec2SecurityGroupId` | selene-networking | Inbound rule on OpenSearch SG |
| `selene-OpensearchSecurityGroupId` | selene-networking | Domain SG assignment |
| `selene-VpcId` | selene-networking | VPC placement |
| `selene-InstanceRoleArn` | selene-iam | Fine-grained access control master user |

**Parameters (inputs at deploy time):**

| Parameter | Value | Description |
|---|---|---|
| `OpenSearchSubnet` | `subnet-0934cf17ca2678038` | Private subnet for domain |
| `EbsVolumeSize` | `100` | GB of gp3 storage |

**Post-deploy manual step:**
After this stack deploys, retrieve the endpoint and store in SSM:
```bash
ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name selene-opensearch \
  --query 'Stacks[0].Outputs[?OutputKey==`OpenSearchEndpoint`].OutputValue' \
  --output text)

aws ssm put-parameter \
  --name /selene/opensearch_endpoint \
  --value "$ENDPOINT" \
  --type String
```

---

### 4.4 selene-ec2

**No exports** — this is the leaf of the dependency graph.

**Imports (from preceding stacks):**

| Import Name | Source Stack | Used For |
|---|---|---|
| `selene-InstanceProfileArn` | selene-iam | Launch Template IamInstanceProfile |
| `selene-Ec2SecurityGroupId` | selene-networking | Launch Template SecurityGroupIds |
| `selene-AlbTargetGroupArn` | selene-networking | ASG TargetGroupARNs |

**Parameters (inputs at deploy time):**

| Parameter | Description |
|---|---|
| `AmiId` | Golden AMI ID (`selene-wazuh-YYYYMMDD`) — updated on each AMI bake |
| `Ec2Subnet` | `subnet-0934cf17ca2678038` — private subnet for instance |
| `InstanceType` | `t3.xlarge` |
| `HealthCheckGracePeriod` | `600` — seconds before ALB health check begins |

---

## 5. SSM Parameter Schema

All parameters live under `/selene/` namespace in `us-east-1`.

| Parameter Name | Type | Value | Set When | Read By |
|---|---|---|---|---|
| `/selene/opensearch_endpoint` | String | OpenSearch VPC endpoint hostname | After selene-opensearch deploys | EC2 UserData |
| `/selene/cloudtrail_bucket` | String | `logs.infillion.com` | Before first EC2 launch | EC2 UserData → Ansible |
| `/selene/cloudtrail_prefix` | String | `AWSLogs/o-z70v8p3t14/` | Before first EC2 launch | EC2 UserData → Ansible |

**Setting all parameters (run once, in order):**
```bash
# Set static values first (known before any stack deploys)
aws ssm put-parameter \
  --name /selene/cloudtrail_bucket \
  --value "logs.infillion.com" \
  --type String

aws ssm put-parameter \
  --name /selene/cloudtrail_prefix \
  --value "AWSLogs/o-z70v8p3t14/" \
  --type String

# Set after selene-opensearch stack deploys (see Section 4.3 post-deploy step)
aws ssm put-parameter \
  --name /selene/opensearch_endpoint \
  --value "<endpoint from stack output>" \
  --type String
```

**IAM permission required:**
EC2 instance role reads these via `ssm:GetParameter` on
`arn:aws:ssm:us-east-1:757548139022:parameter/selene/*`

---

## 6. Ansible Variable Interface

Variables that `ansible-playbook site.yml` expects via `--extra-vars`.
All are sourced from SSM in UserData — none are hardcoded.

| Variable | Source (SSM Parameter) | Used By Role |
|---|---|---|
| `opensearch_endpoint` | `/selene/opensearch_endpoint` | wazuh_indexer |
| `cloudtrail_bucket` | `/selene/cloudtrail_bucket` | wazuh_config |
| `cloudtrail_prefix` | `/selene/cloudtrail_prefix` | wazuh_config |

**Contract:** If a new Ansible role requires a new runtime variable,
a corresponding SSM parameter must be defined here in SPEC-008 before
the role is implemented. No variable may be hardcoded in a role task —
all environment-specific values flow from SSM → UserData → Ansible.

---

## 7. Security Group Reference Model

Security groups reference each other (not CIDRs) for inter-component
traffic. This is the exact reference model:

```
selene-alb-sg
  inbound:  Your IP /32 → 80, 443
  outbound: selene-ec2-sg → 443

selene-ec2-sg
  inbound:  selene-alb-sg → 443        (dashboard traffic)
  inbound:  Your IP /32 → 22           (SSH, temporary)
  outbound: selene-opensearch-sg → 443  (alert forwarding)
  outbound: 0.0.0.0/0 → 443            (GitHub, AWS APIs)
  outbound: 0.0.0.0/0 → 80             (yum package updates)

selene-opensearch-sg
  inbound:  selene-ec2-sg → 443        (Wazuh writes alerts)
  outbound: (none required)
```

**Implementation note:** In CloudFormation, inter-SG references use
`AWS::EC2::SecurityGroupIngress` resources with `SourceSecurityGroupId`
rather than inline ingress rules. This avoids circular dependency errors
when two SGs need to reference each other (in this case, ALB SG and EC2 SG
both reference each other for inbound/outbound rules).

---

## 8. Golden AMI Interface

The AMI is not a CloudFormation resource — it is a parameter to the
selene-ec2 stack. The interface contract is:

**What the AMI must provide (baked in):**
- Wazuh all-in-one installed (manager, indexer, dashboard binaries present)
- Wazuh services stopped (not configured, not running)
- Ansible installed at system level
- git installed
- aws CLI v2 installed
- No environment-specific configuration (no IPs, no endpoints, no certs)

**What the AMI must NOT contain:**
- Any value from RESULTS.md (no subnet IDs, no bucket names, no endpoints)
- Any running Wazuh services
- Any Wazuh-generated certificates (these are regenerated by Ansible)
- Any ossec.conf content (written by Ansible at runtime)

**The AMI ID is the only value that changes in the selene-ec2 stack
between deployments.** All other parameters are stable.

---

## 9. Acceptance Criteria

| ID | Criterion |
|---|---|
| AC1 | `selene-iam` deploys without errors using only its own parameters |
| AC2 | `selene-networking` deploys and all five exports are visible in CloudFormation console |
| AC3 | `selene-opensearch` deploys using `Fn::ImportValue` for all four imports |
| AC4 | `selene-ec2` deploys using `Fn::ImportValue` for all three imports |
| AC5 | No stack uses a hardcoded value that is also defined as a cross-stack export |
| AC6 | All three SSM parameters exist before EC2 UserData runs |
| AC7 | EC2 UserData reads all three SSM parameters without error |
| AC8 | Ansible receives all three variables and they appear correctly in rendered ossec.conf |

---

## 10. Related Specs

- [SPEC-002 Networking](../components/SPEC-002-networking.md) — SG definitions
- [SPEC-003 EC2/ASG](../components/SPEC-003-ec2-asg.md) — Launch Template and UserData
- [SPEC-004 OpenSearch](../components/SPEC-004-opensearch.md) — Domain config
- [SPEC-005 IAM](../components/SPEC-005-iam.md) — Role and policies
- [SPEC-006 Ansible](../components/SPEC-006-ansible.md) — Variable interface
