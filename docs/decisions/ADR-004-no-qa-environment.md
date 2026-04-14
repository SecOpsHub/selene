# ADR-004 — No QA/Test Environment

**Date:** 2025  
**Status:** Accepted  
**Decider:** Aslan  

## Context

Most production systems benefit from a QA or staging environment where
changes can be validated before reaching production. A decision was
needed on whether Selene requires one.

## Decision

No QA environment. Changes are applied directly to the single Selene
deployment.

## Rationale

Selene is a **read-only observation tool**. It has no write access to
any customer infrastructure. This fundamentally bounds the blast radius
of any failure or misconfiguration.

**What Selene can write to:**
- Its own OpenSearch domain (alerts/findings)
- Its own EC2 instance (via Ansible, during configuration)
- Its own CloudFormation stacks (during infrastructure changes)

**What Selene cannot write to:**
- Any member account infrastructure
- The CloudTrail S3 bucket (read-only IAM policy — SPEC-005)
- Any other AWS resource in the org

**Failure modes and their consequences:**

| Failure | Consequence | Severity |
|---|---|---|
| Bad Wazuh rule | Noisy or missing alerts | Low — operational |
| Bad Ansible playbook | EC2 misconfigured, ASG replaces it | Low — self-healing |
| Bad CloudFormation change | Stack rollback, dashboard temporarily down | Medium — ops impact |
| OpenSearch fills up | Alerts stop writing | Medium — ops impact |
| EC2 instance dies | Dashboard down ≤10 min | Low — auto-recovery |

None of these failure modes cause data loss, infrastructure changes,
or security incidents in the monitored environment. The worst realistic
outcome is a window of missed alerts — not a breach or an outage
in the systems being monitored.

**Additional safeguards that substitute for QA:**

- All rule/config changes go through Git with a commit history
- Ansible is idempotent — re-running the playbook is always safe
- CloudFormation stacks have rollback on failure enabled
- The ASG provides automatic recovery from EC2-level failures
- OpenSearch findings survive any EC2-level failure

## Consequences

- Changes ship directly to production — no staging validation step
- The Git review process (even informal) is the primary change gate
- CloudFormation changes carry the most risk and warrant the most care
- This decision is revisited if Selene ever gains write access to
  monitored infrastructure (e.g., automated remediation actions)
