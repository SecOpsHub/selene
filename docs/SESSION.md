# Session Brief

> Update this file at the end of every working session.
> This is your bookmark — not a history log.
> Keep it under 300 words.

---

## Last updated
2025 — initial project setup

## Current SDD phase
Phase 2 complete — all component specs drafted (SPEC-001 through SPEC-007)
Phase 3 (Interface Contracts) not yet started

## What is done
- [x] Repository structure created
- [x] README.md written
- [x] SPEC-001 through SPEC-007 drafted
- [x] ADR-001, ADR-002, ADR-003 written
- [x] Discovery script written (not yet run)
- [x] SESSION.md and DECISIONS.md templates created

## What is NOT done yet
- [ ] Discovery script run against real AWS environment
- [ ] docs/discovery/RESULTS.md populated with real subnet IDs, bucket name
- [ ] Phase 3: Interface Contracts (stack outputs/inputs, SSM parameter schema)
- [ ] Phase 4: Implementation Plan (ordered build sequence)
- [ ] Phase 5: Verification Criteria
- [ ] Any CloudFormation templates
- [ ] Any Ansible playbooks

## Blocked on
- Real subnet IDs from prod VPC (needed for SPEC-002 to be complete)
- Real CloudTrail bucket name (needed for SPEC-005 and SPEC-007)
- Run `docs/discovery/discover.sh` to get these values

## Next task (start here next session)
1. Run `docs/discovery/discover.sh` with management account credentials
2. Fill in `docs/discovery/RESULTS.md` with real values
3. Update SPEC-002 subnet table with real subnet IDs
4. Begin Phase 3: Interface Contracts

## Key decisions made (this session)
- Project name: Selene
- Findings backend: Amazon OpenSearch Service (not S3)
- EC2 stateless via Git + Ansible
- S3 polling for POC (not SQS)
- Rules in GitHub under SecOpsHub/selene
- t3.medium.search for OpenSearch, t3.xlarge for EC2
- Personal IP /32 only for ALB and SSH during POC
- **POC will be presented to higher management before production transition**
- **Management approval is Gate 0 on the production checklist — explicit hard gate**
- POC has two jobs: technical validation AND management demo
- docs/POC-PRESENTATION.md created — demo script and talking points
- docs/PRODUCTION-CHECKLIST.md restructured into Gate 0-5 with approval as Gate 0

## Open questions
- Does the prod VPC have a NAT gateway on private subnets?
  (EC2 needs outbound 443 to GitHub and AWS APIs)
- Should the selene repo be public or private?
  (Affects whether a deploy key is needed for UserData git clone)
