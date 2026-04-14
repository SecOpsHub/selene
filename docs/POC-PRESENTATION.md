# Selene POC — Management Presentation Guide

**Audience:** Higher management (non-technical to semi-technical)  
**Goal:** Approval to promote Selene to production  
**Format:** Live demo + slides or walking through the dashboard directly  
**Time:** 20-30 minutes recommended  

---

## The One Thing to Communicate

> "We built a security monitoring system that gives us better visibility
> into our AWS organization than what we had before, at roughly 10-15%
> of the cost. It's running now. Here's what it looks like."

Everything else in the presentation supports this sentence.

---

## Preparation Checklist (before the meeting)

- [ ] Dashboard is accessible and showing real data
- [ ] At least 7 days of CloudTrail alerts have accumulated
- [ ] You have identified 2-3 interesting real alerts to show (not just noise)
- [ ] You have the cost comparison numbers ready (Datadog invoice vs Selene estimate)
- [ ] You have terminated and recovered the EC2 at least once to verify the 10-min RTO
- [ ] The roadmap slide/section is current and matches PRODUCTION-CHECKLIST.md

---

## Presentation Flow

### 1. The Problem (2 minutes)

Frame this around cost and visibility, not technology.

**Key points:**
- We have ~60 AWS accounts generating security events 24/7
- Until now, monitoring this required [Datadog / existing tooling] at
  $[X]/month — a cost that scales with data volume
- We had limited ability to write custom detection rules for our specific
  environment (BlueJay activity, IAM Identity Center patterns, StackSets, etc.)
- This is a gap: as our AWS footprint grows, cost goes up and control stays limited

**Do not:** go into CloudTrail, S3, or any technical architecture here.

---

### 2. What Selene Is (3 minutes)

One sentence, then show it — don't describe it.

> "Selene is a security monitoring system I built specifically for our
> AWS organization. It watches everything that happens across all 60
> accounts and alerts us to suspicious activity. Let me show you."

**Open the dashboard.** Don't talk about it for more than 30 seconds
before showing the live system.

---

### 3. The Live Demo (10 minutes)

This is the heart of the presentation. Walk through the dashboard
with real data. Keep it story-driven — find events that tell a story,
not just a list of rule IDs.

**Suggested demo flow:**

**Stop 1 — The overview panel**
Show the alert volume over the past 7 days. Point out the shape of
normal activity. "This is what a normal day looks like for our org."

**Stop 2 — A real interesting alert**
Find one alert that is genuinely worth discussing — a console login
from an unusual location, an IAM policy change, a root account usage,
an unusual API call. Walk through what happened, which account it was
in, and what you would do with this information.

"Before Selene, we would not have seen this in real time."

**Stop 3 — Account coverage**
Show that events are coming from multiple accounts — ideally show
the breadth across different OUs or teams. "This is all 60 accounts,
centralized in one place."

**Stop 4 — A custom rule (if you have one)**
If you've written even one custom rule, show it firing. "I wrote a
rule specific to how our environment works. This fires when [X] happens,
which is something we care about and couldn't detect before."

**What NOT to demo:**
- The Ansible playbook
- The CloudFormation templates
- The OpenSearch index structure
- The S3 bucket policy

---

### 4. The Cost Story (5 minutes)

This is where you make the business case concrete.

**Structure:**
- Current cost: $[Datadog monthly bill] per month
- Selene cost: ~$215/month (EC2 + OpenSearch + ALB)
- Annual saving: $[difference] × 12 = $[annual saving]
- One-time build cost: [your hours × rate, or just "engineering time already invested"]

**Key framing points:**
- Selene's cost is fixed — it does not scale with data volume the way
  usage-based SIEM pricing does. As our AWS footprint grows, the cost
  stays the same.
- We own the rules. We can write detections for our specific environment,
  suppress noise specific to our tooling (BlueJay, StackSets, SSO automation),
  and tune the system ourselves without vendor involvement.
- The data stays in our AWS account. Logs never leave our infrastructure.

**Suggested cost comparison slide:**

| | Current tooling | Selene |
|---|---|---|
| Monthly cost | $X,XXX | ~$215 |
| Annual cost | $XX,XXX | ~$2,580 |
| Cost scales with data? | Yes | No |
| Custom rules? | Limited | Full control |
| Data leaves AWS? | Yes | No |
| SOC 2 log retention | [check] | 1 year, same account |

---

### 5. Reliability and Risk (3 minutes)

Management will ask: "What happens if it breaks?"

**Answer:**
"If the server goes down, it automatically replaces itself within 10
minutes. The security data — the alerts and findings — are stored
separately from the server, so nothing is lost. I've tested this.
[Optional: show the CloudWatch/ASG metrics or describe the test]"

"If we make a mistake in the configuration, the worst case is a window
of missed alerts — not an outage in our systems. Selene only reads
from AWS. It can't change anything."

**The two things they need to hear:**
1. It self-heals
2. It can't hurt anything

---

### 6. The Roadmap (3 minutes)

Show that you've thought past the demo. Management is approving a
production system, not just a prototype.

| Phase | What changes | When |
|---|---|---|
| POC (now) | Working dashboard, real alerts | Complete |
| Phase 2 | Proper URL (selene.infillion.com), valid SSL cert | ~2 weeks |
| Phase 3 | Okta login — team accesses via Okta dashboard | ~2 weeks |
| Phase 4 | Remove SSH access, SSM only | ~1 week |
| **Production** | All of the above complete | ~1 month |

"The architecture is already production-grade. These phases are
operational polish, not rebuilding the system."

---

### 7. Ask (1 minute)

Be direct.

> "I'm asking for approval to promote Selene to production. The next
> steps are getting it on a proper domain name, connecting it to Okta
> so the team can log in, and hardening the access controls. Total time
> to production: approximately 4-6 weeks of part-time work.
> After that, we retire [Datadog / current tooling] for this use case
> and save $[X] per year."

---

## Anticipated Questions and Answers

**"How is this different from AWS Security Hub?"**
Security Hub aggregates findings from AWS-native services. Selene
gives us a unified view across all accounts with full-text search,
custom detection rules we write ourselves, suppression of noise
specific to our environment, and a dashboard built for security
operations — not just a list of findings.

**"What if the open source project is abandoned?"**
Wazuh is the most widely deployed open source SIEM in the world,
backed by a commercial company (Wazuh Inc). The risk is low.
And if it ever became necessary to migrate, our data is in standard
OpenSearch — not a proprietary format.

**"Who will maintain this?"**
The security engineering team (currently: me). Maintenance is low:
monthly AMI updates, rule tuning as new threats emerge, reviewing
alerts. The system is self-healing and the configuration is in Git.

**"What about compliance?"**
Raw CloudTrail logs are retained for 1 year in S3 — same bucket,
same retention as before. This meets SOC 2 log retention requirements.
Selene adds a security monitoring layer on top; it doesn't change
the underlying log storage.

**"Can other teams see each other's data?"**
All team members who have access to the Selene dashboard see all
alerts across all accounts. This is consistent with how a centralized
security operations function works. Access is controlled via Okta
(Phase 3) — only people we explicitly grant access can log in.

---

## After the Meeting

If approved:
- [ ] Record approval in `docs/DECISIONS.md` with date and attendees
- [ ] Check off Gate 0 in `docs/PRODUCTION-CHECKLIST.md`
- [ ] Begin Phase 2 work (DNS + ACM)

If deferred (questions, concerns):
- [ ] Document feedback in `docs/DECISIONS.md`
- [ ] Address concerns and reschedule
- [ ] Update this document with new talking points based on feedback
