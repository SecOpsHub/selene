# Discovery Results
# Populated by running docs/discovery/discover.sh
# Last updated: TBD

## AWS Account
- Management Account ID: TBD
- Region: us-east-1 (confirm)

## VPC
- VPC ID: vpc-06cdf666adc9f698d
- CIDR: TBD
- Name: TBD

## Subnets
Fill in after running discover.sh. Format:

| Subnet ID | AZ | CIDR | Public/Private | Name |
|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD |

Key decisions needed:
- Which 2 public subnets for ALB?
- Which private subnet for EC2 + OpenSearch?

## CloudTrail
- Trail name: TBD
- S3 bucket: TBD
- Multi-region: TBD (expected: true)
- Log file validation: TBD (expected: true)

## S3 Folder Structure
Expected pattern: AWSLogs/{account-id}/CloudTrail/{region}/{year}/{month}/{day}/

Actual top-level prefixes: (paste from cloudtrail_s3_top_level.json)

## Existing Security Groups (notable ones)
(paste relevant entries from security_groups.json)

## SSM Parameters
Existing /selene/ parameters: (paste from ssm_parameters.json)
Expected to be empty until deployment.
