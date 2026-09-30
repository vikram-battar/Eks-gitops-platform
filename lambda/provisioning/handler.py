"""Provisioning Lambda: idempotent setup of VPC tags, an IAM role, and a KMS key alias.

Expected event:
{
    "vpc_id": "vpc-0123456789abcdef0",
    "role_name": "eks-gitops-provisioning-role",
    "kms_alias": "eks-gitops-platform/dev",
    "extra_tags": {"Environment": "dev"}      # optional
}

Returns {"status": "SUCCEEDED", ...} or {"status": "FAILED", "error": ...}
so a Step Functions Choice state can branch on $.Payload.status.
"""

from __future__ import annotations

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

PROJECT = os.environ.get("PROJECT_TAG", "eks-gitops-platform")


def _clients():
    """Build AWS clients lazily so cold starts stay cheap and tests can stub."""
    return boto3.client("ec2"), boto3.client("iam"), boto3.client("kms")


def tag_vpc(ec2, vpc_id: str, extra_tags: dict) -> dict:
    """Apply Project/ManagedBy tags plus caller-supplied tags to a VPC."""
    tags = {"Project": PROJECT, "ManagedBy": "provisioning-lambda"}
    tags.update(extra_tags or {})
    try:
        ec2.create_tags(
            Resources=[vpc_id],
            Tags=[{"Key": key, "Value": value} for key, value in tags.items()],
        )
    except ClientError:
        logger.exception("create_tags failed for vpc %s", vpc_id)
        raise
    logger.info("tagged vpc %s with %d tags", vpc_id, len(tags))
    return {"vpc_id": vpc_id, "tags_applied": tags}


def ensure_iam_role(iam, role_name: str) -> dict:
    """Get-or-create an IAM role with a least-privilege EC2 trust policy."""
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "ec2.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }
    try:
        role = iam.get_role(RoleName=role_name)["Role"]
        logger.info("iam role %s already exists", role_name)
        return {"role_name": role_name, "role_arn": role["Arn"], "created": False}
    except iam.exceptions.NoSuchEntityException:
        logger.info("creating iam role %s", role_name)
    except ClientError:
        logger.exception("get_role failed for %s", role_name)
        raise

    try:
        role = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Provisioned by %s provisioning lambda" % PROJECT,
            Tags=[{"Key": "Project", "Value": PROJECT}],
        )["Role"]
    except ClientError:
        logger.exception("create_role failed for %s", role_name)
        raise
    logger.info("created iam role %s", role["Arn"])
    return {"role_name": role_name, "role_arn": role["Arn"], "created": True}


def ensure_kms_alias(kms, alias_name: str, description: str) -> dict:
    """Get-or-create a KMS key and attach the requested alias to it."""
    full_alias = alias_name if alias_name.startswith("alias/") else "alias/%s" % alias_name
    try:
        existing = kms.describe_key(KeyId=full_alias)["KeyMetadata"]
        logger.info("kms alias %s already exists", full_alias)
        return {"alias": full_alias, "key_id": existing["KeyId"], "created": False}
    except kms.exceptions.NotFoundException:
        logger.info("creating kms key for alias %s", full_alias)
    except ClientError:
        logger.exception("describe_key failed for %s", full_alias)
        raise

    try:
        key_id = kms.create_key(
            Description=description,
            Tags=[{"TagKey": "Project", "TagValue": PROJECT}],
        )["KeyMetadata"]["KeyId"]
        kms.create_alias(AliasName=full_alias, TargetKeyId=key_id)
    except ClientError:
        logger.exception("kms create_key/create_alias failed for %s", full_alias)
        raise
    logger.info("created kms key %s with alias %s", key_id, full_alias)
    return {"alias": full_alias, "key_id": key_id, "created": True}


def handler(event, context):
    """Lambda entry point."""
    logger.info("received event: %s", json.dumps(event))

    try:
        vpc_id = event["vpc_id"]
        role_name = event["role_name"]
        kms_alias = event["kms_alias"]
    except KeyError as exc:
        logger.error("missing required field: %s", exc)
        return {"status": "FAILED", "error": "missing required field: %s" % exc}

    extra_tags = event.get("extra_tags") or {}
    if not isinstance(extra_tags, dict):
        return {"status": "FAILED", "error": "extra_tags must be an object"}

    ec2, iam, kms = _clients()
    try:
        vpc_result = tag_vpc(ec2, vpc_id, extra_tags)
        role_result = ensure_iam_role(iam, role_name)
        kms_result = ensure_kms_alias(
            kms, kms_alias, "%s provisioning key for %s" % (PROJECT, role_name)
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        logger.exception("aws api call failed")
        return {"status": "FAILED", "error": "aws api error: %s" % code}
    except Exception:
        logger.exception("unexpected failure")
        return {"status": "FAILED", "error": "unexpected internal error"}

    return {
        "status": "SUCCEEDED",
        "vpc": vpc_result,
        "iam_role": role_result,
        "kms": kms_result,
    }
