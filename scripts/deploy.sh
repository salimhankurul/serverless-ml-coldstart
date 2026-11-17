#!/usr/bin/env bash
# Deploy one configuration as its own CloudFormation (SAM) stack.
# Usage: scripts/deploy.sh <model_id> <x86_64|arm64> <memory_mb>
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh

MODEL=${1:?model id}
ARCH=${2:?arch}
MEM=${3:?memory MB}
ARCH_SHORT=$([ "$ARCH" = "x86_64" ] && echo x86 || echo arm)
CONFIG_ID="${MODEL%%_*}-${ARCH_SHORT}-zip-${MEM}"          # e.g. m3-x86-zip-512
FUNCTION_NAME="${NAME_PREFIX}-${CONFIG_ID}"
STACK_NAME="${NAME_PREFIX}-${CONFIG_ID}"
ZIP="build/${MODEL}-${ARCH}/${MODEL}-${ARCH}.zip"
[ -f "$ZIP" ] || { echo "missing $ZIP - run scripts/build_zip.sh $MODEL $ARCH" >&2; exit 1; }
KEY="packages/$(shasum -a 256 "$ZIP" | cut -c1-16)/${MODEL}-${ARCH}.zip"

# Artifact bucket (private, encrypted, tagged). Removed by scripts/cleanup.sh.
if ! aws s3api head-bucket --bucket "$ARTIFACT_BUCKET" >/dev/null 2>&1; then
  aws s3api create-bucket --bucket "$ARTIFACT_BUCKET" \
    --create-bucket-configuration LocationConstraint="$AWS_REGION" >/dev/null
  aws s3api put-public-access-block --bucket "$ARTIFACT_BUCKET" --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  aws s3api put-bucket-tagging --bucket "$ARTIFACT_BUCKET" \
    --tagging "TagSet=[{Key=$PROJECT_TAG_KEY,Value=$PROJECT_TAG_VALUE}]"
  echo "created bucket $ARTIFACT_BUCKET"
fi
aws s3 cp --only-show-errors "$ZIP" "s3://$ARTIFACT_BUCKET/$KEY"

aws cloudformation deploy \
  --stack-name "$STACK_NAME" \
  --template-file infra/template.yaml \
  --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
  --tags "$PROJECT_TAG_KEY=$PROJECT_TAG_VALUE" "config=$CONFIG_ID" \
  --parameter-overrides FunctionName="$FUNCTION_NAME" Architecture="$ARCH" \
      MemorySize="$MEM" CodeBucket="$ARTIFACT_BUCKET" CodeKey="$KEY" \
  --no-fail-on-empty-changeset

echo "deployed $FUNCTION_NAME (config $CONFIG_ID)"
aws lambda get-function-configuration --function-name "$FUNCTION_NAME" \
  --query '{arch:Architectures[0],mem:MemorySize,runtime:Runtime,codeSize:CodeSize,sha:CodeSha256,state:State}'
