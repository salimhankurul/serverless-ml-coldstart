#!/usr/bin/env bash
# Remove EVERYTHING this project created in AWS, then verify nothing is left.
# Only touches resources whose names start with "citf7001-" (plus the project tag check
# for stacks), so other resources in the account are never affected.
# Usage: scripts/cleanup.sh            delete + verify
#        scripts/cleanup.sh --verify   verify only
set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh

if [ "${1:-}" != "--verify" ]; then
  # 1) CloudFormation stacks (Lambda function, IAM role, log group)
  for s in $(aws cloudformation list-stacks \
      --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE ROLLBACK_COMPLETE UPDATE_ROLLBACK_COMPLETE CREATE_FAILED DELETE_FAILED \
      --query "StackSummaries[?starts_with(StackName, '${NAME_PREFIX}-')].StackName" --output text); do
    tag=$(aws cloudformation describe-stacks --stack-name "$s" \
      --query "Stacks[0].Tags[?Key=='$PROJECT_TAG_KEY'].Value | [0]" --output text)
    if [ "$tag" = "$PROJECT_TAG_VALUE" ]; then
      echo "deleting stack $s"
      aws cloudformation delete-stack --stack-name "$s"
      aws cloudformation wait stack-delete-complete --stack-name "$s" || echo "WARN: stack $s did not delete cleanly"
    else
      echo "skip stack $s (no project tag)"
    fi
  done

  # 2) Log groups Lambda may have created outside the stack
  for lg in $(aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/${NAME_PREFIX}-" \
      --query 'logGroups[].logGroupName' --output text); do
    echo "deleting log group $lg"; aws logs delete-log-group --log-group-name "$lg"
  done

  # 3) Artifact bucket (all objects, then the bucket; versioning is never enabled)
  if aws s3api head-bucket --bucket "$ARTIFACT_BUCKET" >/dev/null 2>&1; then
    echo "emptying and deleting bucket $ARTIFACT_BUCKET"
    aws s3 rm --only-show-errors "s3://$ARTIFACT_BUCKET" --recursive
    aws s3api delete-bucket --bucket "$ARTIFACT_BUCKET"
  fi

  # 4) ECR repositories (container-image half of the design)
  for r in $(aws ecr describe-repositories \
      --query "repositories[?starts_with(repositoryName, '${NAME_PREFIX}')].repositoryName" --output text); do
    echo "deleting ECR repository $r"; aws ecr delete-repository --repository-name "$r" --force >/dev/null
  done
fi

# ---- Verification ----
echo; echo "== verification ($AWS_REGION, $(date -u +%Y-%m-%dT%H:%M:%SZ))"
left=0
check() {  # label, command output
  if [ -n "$2" ] && [ "$2" != "None" ]; then echo "LEFT: $1 -> $2"; left=1; else echo "ok:   $1"; fi
}
check "lambda functions" "$(aws lambda list-functions --query "Functions[?starts_with(FunctionName, '${NAME_PREFIX}-')].FunctionName" --output text)"
check "cloudformation stacks" "$(aws cloudformation list-stacks --query "StackSummaries[?starts_with(StackName, '${NAME_PREFIX}-') && StackStatus!='DELETE_COMPLETE'].StackName" --output text)"
check "log groups" "$(aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/${NAME_PREFIX}-" --query 'logGroups[].logGroupName' --output text)"
check "s3 buckets" "$(aws s3api list-buckets --query "Buckets[?starts_with(Name, '${NAME_PREFIX}-')].Name" --output text)"
check "iam roles" "$(aws iam list-roles --query "Roles[?starts_with(RoleName, '${NAME_PREFIX}-')].RoleName" --output text)"
check "ecr repositories" "$(aws ecr describe-repositories --query "repositories[?starts_with(repositoryName, '${NAME_PREFIX}')].repositoryName" --output text)"
check "tagged resources" "$(aws resourcegroupstaggingapi get-resources --tag-filters Key=$PROJECT_TAG_KEY,Values=$PROJECT_TAG_VALUE --query 'ResourceTagMappingList[].ResourceARN' --output text)"
if [ $left -eq 0 ]; then echo "RESULT: CLEAN - nothing from this project is left in $AWS_REGION"; else echo "RESULT: LEFTOVERS FOUND"; exit 1; fi
