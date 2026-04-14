# ADR-002 — Stateless EC2 with Git as Source of Truth

**Date:** 2025  
**Status:** Accepted  
**Decider:** Aslan  

## Context

Wazuh stores custom rules as XML files on the EC2 filesystem at
`/var/ossec/etc/rules/`. The EC2 instance is replaced automatically
by the ASG on failure. A decision was needed on where rules and
configuration live to ensure they survive instance replacement.

## Options Considered

**Option A: Git as source of truth (stateless EC2)**
All rules, suppressions, and configuration live in GitHub. Ansible
applies them on every boot. EC2 is fully ephemeral.

**Option B: EBS snapshot**
Attach a separate EBS volume for Wazuh state. Snapshot it periodically.
On replacement, attach the latest snapshot.

**Option C: Manual backup to S3**
A cron job copies rules to S3. On replacement, UserData restores from S3.

## Decision

Option A: Git as source of truth.

## Rationale

Git is already the natural home for configuration files. It provides:
- Full version history and audit trail for every rule change
- Easy rollback to any previous rule state
- Peer review via pull requests before changes go live
- No additional AWS resources (no EBS snapshots, no S3 backup scripts)
- Immediate visibility into what is deployed vs. what is in Git

The Ansible playbook is idempotent — re-running it produces the same
result. This means recovery is completely unattended: clone repo,
run playbook, done.

Option B (EBS snapshot) introduces complexity: snapshot lifecycle
management, attachment logic in UserData, and a delay if the snapshot
is hours old. Option C (S3 backup) is a custom mechanism that can
drift from the server state.

## Consequences

- All rule changes require a Git commit — no direct server edits
- During an incident, rule changes still go through Git (60-second
  turnaround via playbook re-run — acceptable)
- A GitHub outage during EC2 replacement would block recovery.
  Mitigation: keep the GitHub repo public or use a deploy key with
  a fallback S3 copy of the repo as a secondary bootstrap source
  (future enhancement)
