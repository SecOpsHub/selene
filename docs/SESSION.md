# Session Brief
# Updated at end of every working session. Overwrite, do not append.

---

## Last updated
2025-04-14 — Phase 4 complete

## Current SDD phase
All five SDD phases complete:
Phase 5 (Verification Criteria) is embedded in SPEC-009 T09 and SPEC-001 AC items.
Ready to build.

## What is done
- [x] SPEC-001 — Architecture
- [x] SPEC-002 through SPEC-007 — Component specs (all with real values)
- [x] SPEC-008 — Interface Contracts
- [x] SPEC-009 — Implementation Plan (task backlog)
- [x] ADR-001 through ADR-005
- [x] PRODUCTION-CHECKLIST.md (Gate 0-5)
- [x] POC-PRESENTATION.md
- [x] Discovery complete, RESULTS.md fully populated

## What is NOT done yet (build tasks)
- [ ] P0 — Push repo to GitHub, set static SSM params, verify IGW routes
- [ ] T01 — infra/iam.yml + deploy selene-iam
- [ ] T02 — infra/networking.yml + deploy selene-networking
- [ ] T03 — infra/opensearch.yml + deploy selene-opensearch  [parallel]
- [ ] T04 — Golden AMI bake                                  [parallel]
- [ ] T05 — Ansible roles + ossec.conf.j2                   [parallel]
- [ ] T06 — Set /selene/opensearch_endpoint SSM param
- [ ] T07 — infra/ec2-asg.yml + deploy selene-ec2
- [ ] T08 — Bucket policy amendment on logs.infillion.com
- [ ] T09 — End-to-end verification (all AC items from SPEC-001)

## Next task (start here next session)
P0 — Environment prep:
  1. Push repo to GitHub (SecOpsHub/selene)
  2. Set static SSM params (cloudtrail_bucket, cloudtrail_prefix)
  3. Verify public subnet IGW route tables
Then begin T01: write infra/iam.yml

## Key environment values
- Account: 757548139022 | Org: o-z70v8p3t14 | Region: us-east-1
- VPC: vpc-06cdf666adc9f698d
- ALB subnets: subnet-06e367114ba47947a (1a), subnet-0a2291ca1fe4900c0 (1b)
- EC2/OpenSearch subnet: subnet-0934cf17ca2678038 (private, 1a)
- CloudTrail bucket: logs.infillion.com
- CloudTrail prefix: AWSLogs/o-z70v8p3t14/

## Fixed names (from SPEC-008 — do not change)
- OpenSearch cluster: selene-findings
- Public dashboard URL: selene.infillion.com (Phase 2)
- IAM role: selene-wazuh-instance-role
- Stacks: selene-iam, selene-networking, selene-opensearch, selene-ec2
- ASG: selene-asg | Launch Template: selene-wazuh-lt | ALB: selene-alb
