# ADR-001 — OpenSearch Service vs S3 for Findings Storage

**Date:** 2025  
**Status:** Accepted  
**Decider:** Aslan  

## Context

Wazuh alerts (findings) need to be stored somewhere durable — separate
from the EC2 instance so they survive instance termination and replacement.
Two options were evaluated.

## Options Considered

**Option A: Amazon OpenSearch Service**
Managed OpenSearch cluster. Wazuh writes alerts directly via its
native OpenSearch output. Dashboard queries OpenSearch for display.

**Option B: S3 JSON files**
Wazuh writes alerts to S3 via its file output integration. No managed
cluster needed. Findings viewable via Athena queries or BlueJay ingestion.

## Decision

Option A: Amazon OpenSearch Service.

## Rationale

The Wazuh Dashboard (Kibana fork) requires OpenSearch as its backend.
During the POC and rule-tuning phase, the dashboard is essential for:
- Visualizing alert patterns
- Writing and testing custom rules interactively
- Suppressing noisy alerts with immediate feedback

Without OpenSearch, the dashboard does not function. S3-only would
require building a separate UI (BlueJay integration) before any
interactive rule tuning is possible, significantly delaying value.

The cost difference (~$60/mo for OpenSearch vs ~$0 for S3) is acceptable
given the productivity benefit during rule development.

## Consequences

- Monthly cost increases by ~$60/mo for the OpenSearch domain
- OpenSearch becomes a dependency that must be running before Wazuh
- S3 integration may be added in a future phase as an additional
  output alongside OpenSearch for longer-term archival
