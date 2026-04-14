# Discovery Results
# Populated from discovery run against management account
# Last updated: 2025-04-14

> Raw JSON output files are NOT committed to this repo.
> All actionable values are captured below.

---

## AWS Account
- Management Account ID: `757548139022`
- Organization ID: `o-z70v8p3t14`
- Region: `us-east-1`

---

## VPC
- VPC ID: `vpc-06cdf666adc9f698d`
- Name: `production-vpc`
- CIDR: `10.1.0.0/16`
- State: available

---

## Subnets

| Subnet ID | AZ | CIDR | Type | Name |
|---|---|---|---|---|
| subnet-06e367114ba47947a | us-east-1a | 10.1.0.0/20 | Public | production-vpc-subnet-public1-us-east-1a |
| subnet-0a2291ca1fe4900c0 | us-east-1b | 10.1.16.0/20 | Public | production-vpc-subnet-public2-us-east-1b |
| subnet-0226274ee004a0692 | us-east-1c | 10.1.32.0/20 | Public | production-vpc-subnet-public3-us-east-1c |
| subnet-0934cf17ca2678038 | us-east-1a | 10.1.128.0/20 | Private | production-vpc-subnet-private1-us-east-1a |
| subnet-00d5b569943d8c9ab | us-east-1b | 10.1.144.0/20 | Private | production-vpc-subnet-private2-us-east-1b |
| subnet-01a9f347973314836 | us-east-1c | 10.1.160.0/20 | Private | production-vpc-subnet-private3-us-east-1c |

Note: Public subnets have MapPublicIpOnLaunch: false by VPC config. This is normal —
the subnets route to the Internet Gateway via route tables. Verify route tables
include 0.0.0.0/0 -> igw-* before deploying the ALB stack.

### Selene Subnet Assignments

| Component | Subnet | AZ |
|---|---|---|
| ALB (AZ 1) | subnet-06e367114ba47947a | us-east-1a |
| ALB (AZ 2) | subnet-0a2291ca1fe4900c0 | us-east-1b |
| Wazuh EC2 | subnet-0934cf17ca2678038 | us-east-1a |
| OpenSearch | subnet-0934cf17ca2678038 | us-east-1a |

---

## CloudTrail

Two trails exist. Only full-org-events is used by Selene.

| Trail | Bucket | Multi-Region | Log Validation | Use |
|---|---|---|---|---|
| full-org-events | logs.infillion.com | Yes | Yes | Selene source |
| cloudtrail-from-cf | presidio-cloudops-limited-cloudtrailstack-s3bucket-90fqha5pfhuj | Yes | Yes | Ignore (legacy/vendor) |

CloudTrail bucket for Selene: logs.infillion.com

---

## S3 Path Structure

IMPORTANT: The bucket uses org-level CloudTrail path structure with the
Organization ID as an intermediate prefix. This differs from a standard
per-account trail.

Full path pattern:
  s3://logs.infillion.com/AWSLogs/o-z70v8p3t14/{account-id}/CloudTrail/{region}/{year}/{month}/{day}/
  s3://logs.infillion.com/AWSLogs/o-z70v8p3t14/{account-id}/CloudTrail-Digest/
  s3://logs.infillion.com/AWSLogs/o-z70v8p3t14/{account-id}/CloudTrail-Insight/

Example log file:
  AWSLogs/o-z70v8p3t14/000212131231/CloudTrail/us-east-1/2026/04/14/
    000212131231_CloudTrail_us-east-1_20260414T0000Z_9nHTDChJlv2SAT2o.json.gz

Note: The initial discovery script showed AWSLogs/757548139022/ at the top level.
This is the management account's own logs stored directly (not under the org prefix).
Selene reads from the org prefix: AWSLogs/o-z70v8p3t14/

Wazuh aws-s3 wodle path parameter: AWSLogs/o-z70v8p3t14/

All member accounts confirmed present under the org prefix.
Coverage flag from initial discovery: RESOLVED.

Sample confirmed accounts under org prefix (partial list):
  000212131231, 004262515770, 047444642610, 051960994221,
  054523354552, 061675033078, 071506343156, ... (60+ total)

Regions confirmed (per account): ap-northeast-1/2/3, ap-south-1,
  ap-southeast-1/2, ca-central-1, eu-central-1, eu-north-1,
  eu-west-1/2/3, sa-east-1, us-east-1/2, us-west-1/2

---

## Existing Security Groups

| SG ID | Name | Notes |
|---|---|---|
| sg-01efbf21403b6cacf | bluejay-production-instance-sg | BlueJay EC2 - naming reference |
| sg-06d1a2e72f2a62a66 | bluejay-production-alb-sg | BlueJay ALB - naming reference |
| sg-0b149251af8fa324d | default | Default VPC SG - do not use |

Selene SGs to create (following BlueJay naming pattern):
  selene-alb-sg
  selene-ec2-sg
  selene-opensearch-sg

---

## SSM Parameters

No /selene/ parameters exist yet. Populate after OpenSearch stack deploys:

  aws ssm put-parameter \
    --name /selene/opensearch_endpoint \
    --value <OpenSearch VPC endpoint from stack output> \
    --type String

  aws ssm put-parameter \
    --name /selene/cloudtrail_bucket \
    --value logs.infillion.com \
    --type String

  aws ssm put-parameter \
    --name /selene/cloudtrail_prefix \
    --value AWSLogs/o-z70v8p3t14/ \
    --type String
