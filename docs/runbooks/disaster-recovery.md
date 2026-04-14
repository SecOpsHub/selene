# Runbook: Disaster Recovery

**Last updated:** 2025  
**Estimated recovery time:** ≤ 10 minutes (automatic) / ≤ 30 minutes (manual)  

---

## Scenario 1 — EC2 Unhealthy (automatic recovery)

The ASG monitors EC2 health via the ALB health check. If the instance
fails the health check, the ASG automatically terminates and replaces it.

**You do not need to do anything.** Monitor recovery:

```bash
# Watch ASG activity
aws autoscaling describe-scaling-activities \
  --auto-scaling-group-name selene-asg \
  --query 'Activities[0].{Status:StatusCode,Cause:Cause,Start:StartTime}'

# Watch new instance come up
aws ec2 describe-instances \
  --filters "Name=tag:aws:autoscaling:groupName,Values=selene-asg" \
  --query 'Reservations[*].Instances[*].{Id:InstanceId,State:State.Name,LaunchTime:LaunchTime}'
```

Expected timeline:
- 0:00 — Instance fails health check
- 0:30 — ASG marks instance unhealthy
- 1:00 — ASG terminates instance, launches replacement
- 3:00 — New instance running, Ansible executing
- 8:00 — Wazuh services up, ALB health check passing
- 10:00 — Dashboard accessible

---

## Scenario 2 — Manual Recovery (ASG not working)

If the ASG fails to recover automatically:

```bash
# 1. Check ASG state
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names selene-asg

# 2. If ASG is suspended, resume it
aws autoscaling resume-processes \
  --auto-scaling-group-name selene-asg

# 3. If Launch Template has a bad AMI, fix it first (see golden-ami-bake.md)
# Then force instance refresh:
aws autoscaling start-instance-refresh \
  --auto-scaling-group-name selene-asg
```

---

## Scenario 3 — Full Stack Rebuild

If both EC2 and the CloudFormation stacks need to be rebuilt from scratch:

```bash
# Prerequisites: SSM parameters must be set
# /selene/opensearch_endpoint — get from OpenSearch console
# /selene/cloudtrail_bucket   — known value

# 1. Deploy stacks in order (each waits for completion)
aws cloudformation deploy \
  --template-file infra/iam.yml \
  --stack-name selene-iam \
  --capabilities CAPABILITY_NAMED_IAM

aws cloudformation deploy \
  --template-file infra/networking.yml \
  --stack-name selene-networking

aws cloudformation deploy \
  --template-file infra/opensearch.yml \
  --stack-name selene-opensearch

aws cloudformation deploy \
  --template-file infra/ec2-asg.yml \
  --stack-name selene-ec2

# 2. Get ALB DNS name
aws cloudformation describe-stacks \
  --stack-name selene-networking \
  --query 'Stacks[0].Outputs[?OutputKey==`AlbDnsName`].OutputValue' \
  --output text
```

Note: If OpenSearch stack is redeployed, the endpoint changes.
Update SSM parameter `/selene/opensearch_endpoint` before deploying ec2 stack.

---

## Scenario 4 — Rule Rollback

If a bad rule is causing issues (false positives, Wazuh crash):

```bash
# On local machine — revert the rule change in Git
git revert <commit-hash>
git push origin main

# SSH to EC2 and re-run Ansible
ssh ec2-user@<ec2-ip>
cd /opt/selene
git pull
ansible-playbook ansible/site.yml
```

---

## Verifying Recovery

After any recovery scenario:

```bash
# 1. Dashboard accessible
curl -k -o /dev/null -w "%{http_code}" https://<alb-dns>/

# 2. Check Wazuh logs on EC2
ssh ec2-user@<ec2-ip>
sudo tail -100 /var/ossec/logs/ossec.log | grep -E "ERROR|WARNING|Started"

# 3. Check OpenSearch indices are intact
# (In Wazuh Dashboard: Stack Management → Index Management → Indices)
# Expect: wazuh-alerts-* indices present with documents

# 4. Verify CloudTrail ingestion resumed
# Wait 10 minutes, then check for new alerts in dashboard
```
