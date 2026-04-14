# ADR-003 — S3 Polling vs SQS-Based Log Ingestion

**Date:** 2025  
**Status:** Accepted  
**Decider:** Aslan  

## Context

Wazuh's `aws-s3` wodle supports two modes for detecting new CloudTrail
log files in S3: periodic polling and SQS event notifications.

## Options Considered

**Option A: Periodic polling**
Wazuh polls the S3 bucket on a configurable interval (e.g., every 5
minutes) and lists new objects since the last run.

**Option B: SQS-based event notification**
S3 sends a notification to an SQS queue when a new object is written.
Wazuh polls the SQS queue instead of S3 directly. This is near-real-time.

## Decision

Option A: Periodic polling for POC.

## Rationale

Polling is simpler to set up and requires no additional AWS resources
(no SQS queue, no S3 event notification configuration). For the POC
goal of validating that CloudTrail logs are ingested and rules fire
correctly, a 5-minute lag is entirely acceptable.

SQS-based ingestion provides lower latency (~seconds vs ~5 minutes)
and lower S3 API cost at scale (fewer LIST calls). These become
meaningful at high log volume or when near-real-time alerting is
required for critical events.

## Consequences

- Alert latency: up to 5 minutes from log delivery to Wazuh alert
- S3 LIST API calls: ~288/day (every 5 min, 24h). Negligible cost.
- No SQS queue or S3 notification configuration needed for POC

Planned upgrade to SQS-based ingestion in Phase 5 once the POC is
validated and alert latency becomes a concern.
