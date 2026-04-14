# Session Brief
# Updated at end of every working session. Overwrite, do not append.

---

## Last updated
2025 — discovery complete, all specs updated with real values

## Current SDD phase
Phase 2 complete — all component specs have real environment values
Phase 3 (Interface Contracts) is next

## What is done
- [x] Repository structure created
- [x] README.md written
- [x] SPEC-001 through SPEC-007 drafted and updated with real values
- [x] ADR-001 through ADR-005 written
- [x] Runbooks: golden-ami-bake, disaster-recovery
- [x] PRODUCTION-CHECKLIST.md with Gate 0-5 structure
- [x] POC-PRESENTATION.md — demo script and management talking points
- [x] Discovery run — RESULTS.md populated with real values
- [x] SPEC-002 subnet table filled in with real subnet IDs
- [x] SPEC-005 IAM policies have real account ID (757548139022) and bucket (logs.infillion.com)
- [x] SPEC-007 updated with real trail name and bucket, coverage flag noted

## What is NOT done yet
- [ ] Phase 3: Interface Contracts (CloudFormation stack outputs/imports)
- [ ] Phase 4: Implementation Plan (ordered build sequence)
- [ ] Phase 5: Verification Criteria
- [ ] Any CloudFormation templates (infra/*.yml)
- [ ] Full Ansible role implementations
- [ ] Golden AMI bake
- [ ] Verify public subnet route tables have IGW route (before ALB deploy)
- [ ] Confirm all 60 accounts present in logs.infillion.com (after deploy)

## Blocked on
Nothing — ready to begin Phase 3

## Next task (start here next session)
Begin Phase 3: Interface Contracts
- Define CloudFormation stack outputs and cross-stack imports
- Define SSM parameter schema (already partially documented)
- This unlocks Phase 4: Implementation Plan (ordered build sequence)

## Key environment values (from discovery)
- Account: 757548139022
- VPC: vpc-06cdf666adc9f698d (production-vpc, 10.1.0.0/16)
- ALB subnets: subnet-06e367114ba47947a (1a), subnet-0a2291ca1fe4900c0 (1b)
- EC2/OpenSearch subnet: subnet-0934cf17ca2678038 (private, 1a)
- CloudTrail bucket: logs.infillion.com (trail: full-org-events, org-level path)
- CloudTrail S3 prefix: AWSLogs/o-z70v8p3t14/ (org ID in path — NOT AWSLogs/{account-id})
- Organization ID: o-z70v8p3t14
- Region: us-east-1

## Key decisions made
- Project name: Selene
- Findings backend: Amazon OpenSearch Service
- EC2 stateless via Git + Ansible
- S3 polling (not SQS) for POC
- Rules in GitHub (SecOpsHub/selene)
- t3.medium.search for OpenSearch, t3.xlarge for EC2
- Personal IP /32 for POC access
- POC to be presented to management — approval is Gate 0 for production
- No QA environment (ADR-004) — read-only tool, bounded blast radius
- Two CloudTrail trails exist; use only full-org-events / logs.infillion.com

## Open flags
- Public subnets show MapPublicIpOnLaunch: false — verify IGW route tables before ALB deploy
- Discovery only showed management account (757548139022) in S3 top-level scan;
  full 60-account coverage to be verified post-deployment
