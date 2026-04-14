#!/bin/bash
# Selene Discovery Script
# Run this locally with management account credentials.
# Output is saved to docs/discovery/results/
# These scripts are throwaway — only the results are kept.
#
# Usage:
#   chmod +x discover.sh
#   AWS_PROFILE=management ./discover.sh

set -euo pipefail

OUTDIR="$(dirname "$0")/results"
mkdir -p "$OUTDIR"

echo "=== Selene Discovery ==="
echo "Account: $(aws sts get-caller-identity --query Account --output text)"
echo "Region:  $(aws configure get region)"
echo ""

# ── VPC ──────────────────────────────────────────────────────────────
echo "[1/6] VPC details..."
aws ec2 describe-vpcs \
  --vpc-ids vpc-06cdf666adc9f698d \
  --query 'Vpcs[0].{VpcId:VpcId,CidrBlock:CidrBlock,Name:Tags[?Key==`Name`]|[0].Value,State:State}' \
  --output json > "$OUTDIR/vpc.json"
echo "      Saved vpc.json"

# ── Subnets ───────────────────────────────────────────────────────────
echo "[2/6] Subnets in prod VPC..."
aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=vpc-06cdf666adc9f698d" \
  --query 'Subnets[*].{SubnetId:SubnetId,Az:AvailabilityZone,Cidr:CidrBlock,Public:MapPublicIpOnLaunch,Name:Tags[?Key==`Name`]|[0].Value}' \
  --output json > "$OUTDIR/subnets.json"
echo "      Saved subnets.json"

# ── CloudTrail S3 Buckets ─────────────────────────────────────────────
echo "[3/6] CloudTrail configuration..."
aws cloudtrail describe-trails \
  --query 'trailList[*].{Name:Name,S3Bucket:S3BucketName,HomeRegion:HomeRegion,MultiRegion:IsMultiRegionTrail,LogFileValidation:LogFileValidationEnabled}' \
  --output json > "$OUTDIR/cloudtrail_trails.json"
echo "      Saved cloudtrail_trails.json"

# Get the primary CloudTrail bucket name
CT_BUCKET=$(aws cloudtrail describe-trails \
  --query 'trailList[?IsMultiRegionTrail==`true`].S3BucketName | [0]' \
  --output text 2>/dev/null || echo "UNKNOWN")
echo "      Primary CloudTrail bucket: $CT_BUCKET"

# ── S3 Bucket — folder structure (top level only) ────────────────────
echo "[4/6] CloudTrail S3 folder structure (top-level AWSLogs)..."
if [ "$CT_BUCKET" != "UNKNOWN" ] && [ "$CT_BUCKET" != "None" ]; then
  aws s3api list-objects-v2 \
    --bucket "$CT_BUCKET" \
    --prefix "AWSLogs/" \
    --delimiter "/" \
    --query 'CommonPrefixes[*].Prefix' \
    --output json > "$OUTDIR/cloudtrail_s3_top_level.json"
  
  # Sample one account's folder structure
  FIRST_PREFIX=$(aws s3api list-objects-v2 \
    --bucket "$CT_BUCKET" \
    --prefix "AWSLogs/" \
    --delimiter "/" \
    --query 'CommonPrefixes[0].Prefix' \
    --output text)
  
  aws s3api list-objects-v2 \
    --bucket "$CT_BUCKET" \
    --prefix "$FIRST_PREFIX" \
    --delimiter "/" \
    --query 'CommonPrefixes[*].Prefix' \
    --output json > "$OUTDIR/cloudtrail_s3_sample_account.json"
  
  echo "      Saved cloudtrail_s3_top_level.json"
  echo "      Saved cloudtrail_s3_sample_account.json (prefix: $FIRST_PREFIX)"
else
  echo "      WARNING: Could not determine CloudTrail bucket name"
fi

# ── Existing Security Groups ──────────────────────────────────────────
echo "[5/6] Existing security groups in prod VPC..."
aws ec2 describe-security-groups \
  --filters "Name=vpc-id,Values=vpc-06cdf666adc9f698d" \
  --query 'SecurityGroups[*].{Id:GroupId,Name:GroupName,Description:Description}' \
  --output json > "$OUTDIR/security_groups.json"
echo "      Saved security_groups.json"

# ── SSM Parameters (existing /selene/ namespace check) ───────────────
echo "[6/6] Checking for existing SSM parameters under /selene/..."
aws ssm get-parameters-by-path \
  --path "/selene/" \
  --query 'Parameters[*].{Name:Name,Type:Type,LastModified:LastModifiedDate}' \
  --output json > "$OUTDIR/ssm_parameters.json" 2>/dev/null || echo "[]" > "$OUTDIR/ssm_parameters.json"
echo "      Saved ssm_parameters.json"

# ── Summary ───────────────────────────────────────────────────────────
echo ""
echo "=== Summary ==="
echo "CloudTrail bucket : $CT_BUCKET"
echo "VPC               : vpc-06cdf666adc9f698d"
echo ""
echo "Subnets found:"
cat "$OUTDIR/subnets.json" | python3 -c "
import json, sys
subnets = json.load(sys.stdin)
for s in subnets:
    public = 'PUBLIC ' if s.get('Public') else 'PRIVATE'
    print(f'  {public} {s[\"SubnetId\"]} {s[\"Az\"]} {s[\"Cidr\"]} ({s.get(\"Name\",\"no-name\")})')
"
echo ""
echo "Results saved to: $OUTDIR"
echo "Add results/ contents to docs/discovery/ in the selene repo."
echo "Do NOT commit sensitive values — review before git add."
