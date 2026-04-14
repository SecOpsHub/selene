# Runbook: Golden AMI Bake

**Last updated:** 2025  
**Estimated time:** 45-60 minutes  
**Requires:** Management account console or CLI access  

---

## Purpose

Create a new `selene-wazuh-YYYYMMDD` AMI with Wazuh pre-installed
but not configured. Configuration is applied at runtime by Ansible.

Rebake when:
- Wazuh releases a new version you want to adopt
- Monthly Amazon Linux 2023 security patches are available
- A base dependency needs updating (Ansible, git, aws CLI)

---

## Step 1 — Launch Bake Instance

```bash
# Use the management account, prod VPC, any public subnet temporarily
aws ec2 run-instances \
  --image-id $(aws ssm get-parameter \
    --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
    --query Parameter.Value --output text) \
  --instance-type t3.xlarge \
  --subnet-id <any-public-subnet-id> \
  --associate-public-ip-address \
  --key-name <your-key-pair> \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=selene-bake}]'
```

Or launch via console:
- AMI: Amazon Linux 2023 (latest)
- Instance type: t3.xlarge
- Subnet: any public subnet in prod VPC (temporary)
- Name tag: `selene-bake`

---

## Step 2 — Install Wazuh All-in-One

SSH to the instance and run the official Wazuh installation script:

```bash
ssh -i <your-key.pem> ec2-user@<bake-instance-ip>

# Download and run official Wazuh installer
curl -sO https://packages.wazuh.com/4.x/wazuh-install.sh
curl -sO https://packages.wazuh.com/4.x/config.yml

# Edit config.yml with placeholder values (will be overwritten by Ansible)
# Set indexer/manager/dashboard nodes all to 127.0.0.1

bash wazuh-install.sh -a
```

Wait for installation to complete (~10-15 minutes).

---

## Step 3 — Install Additional Dependencies

```bash
# Install Ansible
sudo dnf install -y ansible

# Verify git is present (should be on AL2023)
git --version

# Verify aws CLI v2 is present (should be on AL2023)
aws --version

# Install python3-boto3 (needed by some Ansible AWS modules)
sudo dnf install -y python3-boto3
```

---

## Step 4 — Clean Up for Baking

Stop all Wazuh services and remove any environment-specific config:

```bash
# Stop services
sudo systemctl stop wazuh-dashboard
sudo systemctl stop wazuh-manager
sudo systemctl stop wazuh-indexer

# Remove any IP-specific config that was created by the installer
# (Ansible will regenerate these at runtime)
sudo rm -f /var/ossec/etc/ossec.conf
sudo rm -f /etc/wazuh-indexer/opensearch.yml

# Clear any generated certificates (Ansible will handle this)
# NOTE: Check Wazuh docs for current cert locations before running
sudo rm -rf /etc/wazuh-indexer/certs/

# Remove any log files (optional — keeps AMI clean)
sudo find /var/ossec/logs -type f -delete
sudo truncate -s 0 /var/log/wazuh-install.log 2>/dev/null || true
```

---

## Step 5 — Verify AMI Is Clean

Before creating the image, verify no sensitive values are baked in:

```bash
# Should show no running Wazuh processes
ps aux | grep wazuh

# Should show no ossec.conf
ls /var/ossec/etc/ossec.conf

# Should show no environment-specific IPs in any config
grep -r "10\." /etc/wazuh-* 2>/dev/null | grep -v Binary || echo "Clean"
```

---

## Step 6 — Create the AMI

From the AWS console or CLI:

```bash
# Get the instance ID
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
TODAY=$(date +%Y%m%d)

# From your local machine (not the bake instance):
aws ec2 create-image \
  --instance-id <bake-instance-id> \
  --name "selene-wazuh-${TODAY}" \
  --description "Selene Wazuh all-in-one base image - ${TODAY}" \
  --no-reboot \
  --tag-specifications "ResourceType=image,Tags=[{Key=Project,Value=selene},{Key=CreatedDate,Value=${TODAY}}]"
```

Wait for AMI status to become `available` (~5-10 minutes).

---

## Step 7 — Update Launch Template

After AMI is available, update the EC2 Launch Template to use the new AMI:

```bash
NEW_AMI_ID=<ami-id-from-previous-step>

aws ec2 create-launch-template-version \
  --launch-template-name selene-wazuh-lt \
  --source-version '$Latest' \
  --launch-template-data "{\"ImageId\":\"${NEW_AMI_ID}\"}"

# Set new version as default
aws ec2 modify-launch-template \
  --launch-template-name selene-wazuh-lt \
  --default-version '$Latest'
```

---

## Step 8 — Terminate Bake Instance

```bash
aws ec2 terminate-instances --instance-ids <bake-instance-id>
```

---

## Step 9 — Test the New AMI

Force the ASG to use the new AMI by terminating the current instance:

```bash
# Terminate current EC2 — ASG will launch a new one from latest Launch Template
aws ec2 terminate-instances --instance-ids <current-selene-ec2-id>

# Watch the replacement launch
aws ec2 describe-instances \
  --filters "Name=tag:aws:autoscaling:groupName,Values=selene-asg" \
  --query 'Reservations[*].Instances[*].{Id:InstanceId,State:State.Name}'
```

Monitor `/var/log/selene-init.log` on the new instance to confirm
Ansible runs successfully.

---

## Step 10 — Clean Up Old AMIs

Keep the previous AMI as a fallback for 90 days, then deregister:

```bash
# List all selene AMIs
aws ec2 describe-images \
  --owners self \
  --filters "Name=name,Values=selene-wazuh-*" \
  --query 'Images[*].{ImageId:ImageId,Name:Name,Created:CreationDate}' \
  --output table
```
