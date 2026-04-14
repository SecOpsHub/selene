# Selene CloudFormation Templates

This directory contains one CloudFormation template per component.
Templates are written during Phase 4 (Implementation Plan) of the SDD process.

## Deploy Order (strict — stacks reference each other via Outputs/Imports)

1. `iam.yml`         → selene-iam stack
2. `networking.yml`  → selene-networking stack
3. `opensearch.yml`  → selene-opensearch stack
4. `ec2-asg.yml`     → selene-ec2 stack

## Status

| Template | Spec | Status |
|---|---|---|
| `iam.yml` | SPEC-005 | ⏳ Not yet written |
| `networking.yml` | SPEC-002 | ⏳ Not yet written |
| `opensearch.yml` | SPEC-004 | ⏳ Not yet written |
| `ec2-asg.yml` | SPEC-003 | ⏳ Not yet written |

## Stack Dependency Map

```
selene-iam
    └── exports: InstanceRoleArn, InstanceProfileArn
            ↓ imported by
    selene-networking
        └── exports: AlbDnsName, AlbTargetGroupArn, Ec2SecurityGroupId, OpensearchSecurityGroupId
                ↓ imported by
        selene-opensearch
            └── exports: OpenSearchEndpoint, OpenSearchArn, OpenSearchDomainName
                    ↓ OpenSearchEndpoint stored in SSM, read by EC2 UserData
            selene-ec2
                (imports InstanceProfileArn, Ec2SecurityGroupId, AlbTargetGroupArn)
```
