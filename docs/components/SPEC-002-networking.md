# SPEC-002 — Networking

**Version:** 0.1  
**Status:** Draft  
**Depends on:** SPEC-001  
**CloudFormation stack:** `selene-networking`

---

## 1. Overview

All Selene components live inside the existing production VPC
(`vpc-06cdf666adc9f698d`). This spec defines the ALB, security groups,
and traffic routing. No new VPC is created.

---

## 2. Components

### 2.1 Application Load Balancer (ALB)

| Property | Value |
|---|---|
| Type | Internet-facing |
| Scheme | internet-facing |
| Subnets | 2 public subnets (from RESULTS.md — multi-AZ required by ALB) |
| Listeners | Port 80 → redirect to 443; Port 443 → forward to target group |
| Certificate | Self-signed (POC); ACM in Phase 2 |
| Target group | Wazuh EC2, port 443, HTTPS health check `/` |
| Health check | HTTPS, path `/`, healthy threshold 2, interval 30s, grace 600s |

### 2.2 Security Groups

**ALB Security Group (`selene-alb-sg`)**

| Direction | Protocol | Port | Source | Purpose |
|---|---|---|---|---|
| Inbound | TCP | 80 | Your IP /32 | HTTP (redirects to 443) |
| Inbound | TCP | 443 | Your IP /32 | HTTPS dashboard access |
| Outbound | TCP | 443 | EC2 SG | Forward to Wazuh |

**EC2 Security Group (`selene-ec2-sg`)**

| Direction | Protocol | Port | Source | Purpose |
|---|---|---|---|---|
| Inbound | TCP | 443 | ALB SG | Dashboard traffic from ALB |
| Inbound | TCP | 22 | Your IP /32 | SSH (temporary; Phase 4 removes this) |
| Outbound | TCP | 443 | OpenSearch SG | Send alerts to OpenSearch |
| Outbound | TCP | 443 | 0.0.0.0/0 | GitHub (git clone), AWS APIs |
| Outbound | TCP | 80 | 0.0.0.0/0 | Package updates (yum) |

**OpenSearch Security Group (`selene-opensearch-sg`)**

| Direction | Protocol | Port | Source | Purpose |
|---|---|---|---|---|
| Inbound | TCP | 443 | EC2 SG | Wazuh writes alerts |
| Outbound | — | — | — | No outbound required |

---

## 3. Subnet Assignment

Populate from `docs/discovery/RESULTS.md` after running discover.sh:

| Component | Subnet Type | Subnet ID | AZ |
|---|---|---|---|
| ALB | Public | TBD | TBD |
| ALB | Public | TBD | TBD (different AZ) |
| Wazuh EC2 | Private | TBD | TBD |
| OpenSearch | Private | TBD | TBD (same as EC2) |

---

## 4. Traffic Flow

```
Your IP /32
    │ HTTPS 443
    ▼
ALB (internet-facing, public subnets)
    │ HTTPS 443 (ALB → EC2)
    ▼
Wazuh EC2 (private subnet)
    │ HTTPS 443 (EC2 → OpenSearch)
    ▼
OpenSearch VPC endpoint (private subnet)
```

Port 80 hits the ALB and is immediately redirected to port 443.
The EC2 instance has no public IP — it is only reachable via ALB on 443,
or directly via SSH on 22 from your IP.

---

## 5. CloudFormation Stack Outputs

These are exported for use by other stacks:

| Export Name | Value | Consumed By |
|---|---|---|
| `selene-AlbDnsName` | ALB DNS name | Documentation, verification |
| `selene-AlbTargetGroupArn` | Target group ARN | selene-ec2 stack |
| `selene-Ec2SecurityGroupId` | EC2 SG ID | selene-ec2 stack |
| `selene-OpensearchSecurityGroupId` | OpenSearch SG ID | selene-opensearch stack |

---

## 6. Acceptance Criteria

| ID | Criterion |
|---|---|
| AC1 | ALB returns HTTP 200 on HTTPS from allowed IP |
| AC2 | ALB returns connection refused or timeout from any other IP |
| AC3 | HTTP (port 80) from allowed IP redirects to HTTPS |
| AC4 | EC2 port 443 is not directly reachable from the internet |
| AC5 | OpenSearch endpoint is not reachable from outside the VPC |
| AC6 | EC2 can reach GitHub on port 443 (for git clone in UserData) |
| AC7 | EC2 can reach AWS SSM, S3, and OpenSearch endpoints |
