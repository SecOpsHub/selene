# ADR-005 — POC-to-Production Promotion Strategy

**Date:** 2025  
**Status:** Accepted  
**Decider:** Aslan  

## Context

Selene is being built as a POC with the explicit expectation of promotion
to production following management approval. The POC serves two distinct
purposes: technical validation for the engineering team, and a business
case presentation to higher management. A decision was needed on how to
structure the POC phase and what promotion means in practice.

## Decision

Build the POC with production architecture from day one. The POC phase
ends with a management presentation. Promotion is contingent on approval
and is then a process of removing operational shortcuts — not a rebuild.

## Two-Stage POC Model

**Stage 1 — Technical Validation (internal)**
Prove the system works: CloudTrail ingesting, alerts firing, recovery
tested, custom rules and suppressions functional.

**Stage 2 — Management Presentation**
Demonstrate business value: live dashboard showing real org-wide activity,
cost savings vs current tooling, reliability story, credible roadmap to
production. See `docs/POC-PRESENTATION.md` for the demo plan.

## The Approval Gate

Management approval is the explicit gate between POC and production.
It is the first item on `docs/PRODUCTION-CHECKLIST.md`. Technical
readiness alone does not trigger promotion — the approval does.

Expected outcome: approval is highly likely given the cost savings and
the fact that Selene is read-only with no risk to monitored infrastructure.

## Rationale

The architecture is production-grade from day one — there is no
architectural rework at promotion time. What changes is the operational
layer:

| Shortcut | POC Value | Production Requirement |
|---|---|---|
| Self-signed TLS cert | Avoids ACM setup | ACM cert + Route 53 DNS name |
| Personal IP /32 access | Simple for solo development | Team VPN CIDR + Okta SSO |
| Port 22 open | Needed for active development | SSM Session Manager only |
| Single OpenSearch node | Acceptable for POC | 2-node multi-AZ |

These are resolved sequentially post-approval. None require a rebuild.

## Consequences

- The POC must be demo-ready, not just technically correct
- A presentation document and demo script are required artifacts
- Management approval is a hard gate — production transition does not
  begin without it
- The production checklist is the post-approval work queue
- Every architectural decision must be defensible to management, not
  just to engineers
