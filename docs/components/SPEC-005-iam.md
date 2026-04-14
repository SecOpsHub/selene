# SPEC-005 — IAM Roles and Policies

**Version:** 0.1  
**Status:** Draft  
**Depends on:** SPEC-001  
**CloudFormation stack:** `selene-iam`

---

## 1. Overview

Selene follows the principle of least privilege. One IAM role is created
for the Wazuh EC2 instance. It grants exactly the permissions needed —
no more. No cross-account role assumption is required because the
CloudTrail S3 bucket is in the same management account as the EC2.

---

## 2. EC2 Instance Role

**Role name:** `selene-wazuh-instance-role`  
**Instance profile:** `selene-wazuh-instance-profile`  
**Trust policy:** EC2 service (`ec2.amazonaws.com`)

### 2.1 Policy: CloudTrail S3 Read

**Policy name:** `selene-cloudtrail-s3-read`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListBucket",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::logs.infillion.com",
      "Condition": {
        "StringLike": {
          "s3:prefix": "AWSLogs/o-z70v8p3t14/*"
        }
      }
    },
    {
      "Sid": "GetObjects",
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::logs.infillion.com/AWSLogs/o-z70v8p3t14/*"
    }
  ]
}
```

The `s3:prefix` condition on ListBucket scopes the listing to the org
prefix only, preventing Wazuh from inadvertently listing the management
account's direct log prefix (`AWSLogs/757548139022/`).

### 2.2 Policy: SSM Parameter Read

**Policy name:** `selene-ssm-read`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadSeleneParameters",
      "Effect": "Allow",
      "Action": ["ssm:GetParameter", "ssm:GetParameters"],
      "Resource": "arn:aws:ssm:us-east-1:757548139022:parameter/selene/*"
    }
  ]
}
```

### 2.3 Policy: OpenSearch Write

**Policy name:** `selene-opensearch-write`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "OpenSearchHttpAccess",
      "Effect": "Allow",
      "Action": ["es:ESHttpGet", "es:ESHttpPost", "es:ESHttpPut", "es:ESHttpHead"],
      "Resource": "arn:aws:es:us-east-1:757548139022:domain/selene-findings/*"
    }
  ]
}
```

### 2.4 AWS Managed Policy

Attach `AmazonSSMManagedInstanceCore` to support SSM Session Manager
access in a future phase without requiring code changes.

---

## 3. CloudTrail S3 Bucket Policy Amendment

The `logs.infillion.com` bucket policy must be amended to allow the
Wazuh instance role to read log objects. This is the only change made
to existing infrastructure.

Add this statement to the existing bucket policy:

```json
{
  "Sid": "AllowSeleneWazuhRead",
  "Effect": "Allow",
  "Principal": {
    "AWS": "arn:aws:iam::757548139022:role/selene-wazuh-instance-role"
  },
  "Action": ["s3:GetObject", "s3:ListBucket"],
  "Resource": [
    "arn:aws:s3:::logs.infillion.com",
    "arn:aws:s3:::logs.infillion.com/AWSLogs/o-z70v8p3t14/*"
  ]
}
```

The resource scope is limited to the org prefix `o-z70v8p3t14` only.
Selene has no access to any other path in this bucket.

---

## 4. What This Role Does NOT Have

Explicitly excluded to enforce least privilege:

- No `s3:DeleteObject` or `s3:PutObject` on the CloudTrail bucket
- No `iam:*` permissions
- No `ec2:*` permissions beyond what SSMManagedInstanceCore requires
- No cross-account role assumption
- No `es:CreateDomain` or `es:DeleteDomain`
- No wildcard `*` actions anywhere

---

## 5. CloudFormation Stack Outputs

| Export Name | Value | Consumed By |
|---|---|---|
| `selene-InstanceRoleArn` | EC2 instance role ARN | selene-ec2 stack, selene-opensearch (fine-grained access) |
| `selene-InstanceProfileArn` | Instance profile ARN | selene-ec2 Launch Template |

---

## 6. Acceptance Criteria

| ID | Criterion |
|---|---|
| AC1 | EC2 can `aws s3 ls s3://CLOUDTRAIL_BUCKET/AWSLogs/` without explicit credentials |
| AC2 | EC2 can `aws s3 cp` a CloudTrail log file without explicit credentials |
| AC3 | EC2 can read SSM parameters under `/selene/` |
| AC4 | EC2 can write to the OpenSearch domain without username/password |
| AC5 | EC2 cannot `aws s3 rm` an object from the CloudTrail bucket (permission denied) |
| AC6 | No policy contains a wildcard `*` action |
