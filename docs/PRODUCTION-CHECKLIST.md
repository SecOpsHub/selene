# Selene Production Readiness Checklist

This checklist defines the gate criteria for promoting Selene from POC
to production. Promotion happens in two stages:

1. **Management approval** — POC presented and approved (Gate 0)
2. **Technical production readiness** — operational shortcuts resolved (Gates 1-5)

See ADR-005 for the rationale and POC presentation plan.

---

## Gate 0 — Management Approval

This is the primary gate. Technical readiness does not trigger promotion.
Management approval does. Nothing in Gates 1-5 begins until this is complete.

- [ ] **POC presented to higher management**
  Live demo delivered. See `docs/POC-PRESENTATION.md` for the demo plan
  and talking points.

- [ ] **Approval received and documented**
  Decision recorded in DECISIONS.md with date and approvers.

- [ ] **Scope of production deployment confirmed**
  Management has confirmed: which team members need access, whether
  PagerDuty/alerting integration is in scope, any compliance requirements
  for the tool itself.

---

## Gate 1 — Security

- [ ] **TLS: ACM certificate issued for selene.infillion.com (or chosen subdomain)**
  Route 53 record created. ALB listener uses ACM cert. No browser warnings.
  _(Resolves SL-002 — self-signed cert)_

- [ ] **Access: Port 22 removed from EC2 security group**
  SSH access replaced by SSM Session Manager. No inbound 22 from any source.
  _(Resolves NG1 from SPEC-001)_

- [ ] **Access: ALB restricted to team VPN CIDR (not personal IP only)**
  Infillion VPN CIDR added to ALB security group. Personal IP /32 removed
  or supplemented. All team members who need access can reach the dashboard.

- [ ] **Auth: Okta SAML integration active for dashboard login**
  Wazuh dashboard authenticates via Okta. No local Wazuh admin credentials
  used in normal operation. Added to Okta dashboard for all security team members.
  _(Resolves NG3 from SPEC-001)_

- [ ] **IMDSv2 enforced on EC2 Launch Template**
  IMDSv1 disabled. Verified: curl to IMDSv1 endpoint returns 401.

- [ ] **OpenSearch fine-grained access control confirmed**
  No public endpoint. Only EC2 instance role can write. Verified from
  outside VPC that domain is unreachable.

---

## Gate 2 — Reliability

- [ ] **DNS: Custom domain active (selene.infillion.com or equivalent)**
  Route 53 alias record pointing to ALB. Dashboard reachable via domain name,
  not raw ALB DNS. Stable URL that doesn't change if ALB is recreated.
  _(Resolves NG2 from SPEC-001)_

- [ ] **OpenSearch: 2-node multi-AZ deployment**
  Single-node replaced with 2 nodes across 2 AZs. No single point of failure
  for findings storage.
  _(Resolves SL-003 — single OpenSearch node)_

- [ ] **Recovery tested: EC2 termination → full recovery verified**
  ASG replacement tested manually. Dashboard recovers within 10 minutes.
  Findings intact after recovery. Test documented in DECISIONS.md.

- [ ] **Golden AMI cadence documented and scheduled**
  Monthly AMI bake process on calendar. Current AMI age ≤ 30 days at time
  of promotion.

---

## Gate 3 — Observability

- [ ] **Selene monitors itself: CloudWatch alarms configured**
  Alarm on EC2 instance health (ASG). Alarm on OpenSearch cluster health.
  Alarm on ALB 5xx error rate. Alerts go to security team Slack or PagerDuty.

- [ ] **Wazuh dashboard access logged**
  ALB access logs enabled and stored in S3. Log retention ≥ 90 days.

- [ ] **SSM Parameter Store values documented**
  All `/selene/` parameters listed in docs/discovery/RESULTS.md with current
  values (redacted where sensitive). No orphaned parameters.

---

## Gate 4 — Process

- [ ] **Rule management process documented and followed**
  At least one real custom rule written, committed to Git, and deployed
  via Ansible playbook. Process confirmed working end-to-end.

- [ ] **At least one suppression in place**
  At least one known-noisy alert suppressed via local_overrides.xml,
  committed to Git, and deployed. Common candidates: IAM Identity Center
  automation, StackSets activity, BlueJay service account activity.

- [ ] **CloudTrail from all 60 accounts confirmed ingested**
  Sample of accounts from different OUs verified to have alerts in
  Wazuh dashboard. Not just 3 accounts (AC3 from SPEC-001) but full org.

- [ ] **Disaster recovery runbook tested**
  Full-stack rebuild tested from scratch using infra CloudFormation templates.
  Time to recovery documented. Runbook updated based on actual experience.

- [ ] **SPEC-001 known limitations reviewed**
  SL-001 (duplicate alerts on restart) evaluated — acceptable for production
  or resolved via EFS mount. Decision documented in DECISIONS.md.

---

## Gate 5 — Cost

- [ ] **Monthly cost confirmed within budget**
  First full month's AWS bill reviewed. Total Selene-attributable cost
  (EC2, OpenSearch, ALB, S3 API, data transfer) is ≤ $350/mo.
  Actual cost documented in DECISIONS.md.

- [ ] **Reserved Instance evaluated**
  If promoting to production, 1-year EC2 Reserved Instance evaluated.
  At ~$75/mo vs ~$120/mo on-demand, saves ~$540/year.

---

## Sign-off

| Gate | Item | Owner | Completed |
|---|---|---|---|
| 0 | Management approval received | Aslan | |
| 1 | All Security items | Aslan | |
| 2 | All Reliability items | Aslan | |
| 3 | All Observability items | Aslan | |
| 4 | All Process items | Aslan | |
| 5 | Cost confirmed | Aslan | |
| — | **Promotion declared** | Aslan | |
