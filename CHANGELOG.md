# Changelog

All notable changes to Selene are documented here.
Format: [Version] — Date — Description

---

## [0.1.2] — 2025 — Management Presentation Layer

### Added
- `docs/POC-PRESENTATION.md` — full demo script, talking points, cost story,
  anticipated Q&A, and post-meeting checklist for management presentation

### Updated
- ADR-005: Two-stage POC model documented (technical validation + management demo)
- `docs/PRODUCTION-CHECKLIST.md`: Restructured into Gate 0-5; Gate 0 is
  management approval — explicit hard gate before any production work begins
- `docs/SESSION.md`: Updated with latest decisions

---

## [0.1.1] — 2025 — POC-to-Production Strategy

### Added
- ADR-004: No QA environment — read-only safety rationale
- ADR-005: POC-to-production promotion strategy
- `docs/PRODUCTION-CHECKLIST.md` — explicit gate criteria for production promotion

### Updated
- SPEC-001: Section 3 reframed from "Non-Goals" to "Out of Scope (this phase only)"
  with planned phases for each deferred item
- SPEC-001: New Section 12 "POC-to-Production Path" added
- README.md: Roadmap updated to show production gate items clearly
- DECISIONS.md: Two new decisions documented

---

## [0.1.0] — 2025 — Project Foundation

### Added
- Full repository structure established
- README.md with architecture overview, deployment steps, and roadmap
- SPEC-001: System architecture specification
- SPEC-002: Networking (ALB, security groups)
- SPEC-003: EC2, ASG, Launch Template, Golden AMI
- SPEC-004: Amazon OpenSearch Service domain
- SPEC-005: IAM roles and policies
- SPEC-006: Ansible playbook structure
- SPEC-007: CloudTrail S3 log integration
- ADR-001: OpenSearch vs S3 for findings storage
- ADR-002: Stateless EC2 with Git as source of truth
- ADR-003: S3 polling vs SQS-based ingestion
- Runbook: Golden AMI bake procedure
- Runbook: Disaster recovery procedures
- Discovery script for AWS environment enumeration
- Ansible site.yml master playbook (placeholder)
- Ansible role stubs: wazuh_config, wazuh_rules, wazuh_indexer, wazuh_services
- Custom rules placeholder (local_rules.xml)
- Suppressions placeholder (local_overrides.xml)
- osconf.conf.j2 Jinja2 template placeholder
- DECISIONS.md running decisions log
- SESSION.md session brief template

### Not yet implemented
- CloudFormation templates (infra/*.yml)
- Full Ansible role implementations
- Golden AMI (requires manual bake)
