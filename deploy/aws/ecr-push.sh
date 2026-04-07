#!/bin/bash

# AWS ECR 推送脚本 - 将 Docker 镜像推送到 AWS Elastic Container Registry
# 使用方法：
#   ./ecr-push.sh <aws-region> <aws-account-id> <ecr-repo-name>
#   例如：./ecr-push.sh us-east-1 123456789012 esg-agentic-rag

set -e

# ── 配置 ──────────────────────────────────────────────────────────────────
AWS_REGION=${1:-us-east-1}
AWS_ACCOUNT_ID=${2:-$(aws sts get-caller-identity --query Account --output text)}
ECR_REPO_NAME=${3:-esg-agentic-rag-copilot}
IMAGE_TAG=${4:-latest}

ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_REPO="${ECR_REGISTRY}/${ECR_REPO_NAME}"

echo "=========================================="
echo "AWS ECR Push Script"
echo "=========================================="
echo "AWS Region:     $AWS_REGION"
echo "AWS Account:    $AWS_ACCOUNT_ID"
echo "ECR Repository: $ECR_REPO"
echo "Image Tag:      $IMAGE_TAG"
echo "=========================================="

# ── 检查前提条件 ────────────────────────────────────────────────────────────
if ! command -v aws &> /dev/null; then
    echo "[ERROR] AWS CLI not found. Please install it first."
    echo "See: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker not found. Please install it first."
    exit 1
fi

# ── 登录 AWS ECR ────────────────────────────────────────────────────────────
echo "[1/4] Logging in to AWS ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

# ── 创建 ECR 仓库（如果不存在） ────────────────────────────────────────────
echo "[2/4] Ensuring ECR repository exists..."
aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION 2>/dev/null || {
    echo "  Creating ECR repository: $ECR_REPO_NAME"
    aws ecr create-repository \
        --repository-name $ECR_REPO_NAME \
        --region $AWS_REGION \
        --image-tag-mutability MUTABLE \
        --image-scanning-configuration scanOnPush=true
}

# ── 构建 Docker 镜像 ────────────────────────────────────────────────────────
echo "[3/4] Building Docker image..."
cd "$(dirname "$0")/../../"  # 回到项目根目录
docker build \
    -f gateway/Dockerfile \
    -t $ECR_REPO:$IMAGE_TAG \
    -t $ECR_REPO:latest \
    .

# ── 推送到 ECR ──────────────────────────────────────────────────────────────
echo "[4/4] Pushing image to ECR..."
docker push $ECR_REPO:$IMAGE_TAG
docker push $ECR_REPO:latest

echo ""
echo "=========================================="
echo "[SUCCESS] Image pushed successfully!"
echo "=========================================="
echo "Image URL: $ECR_REPO:$IMAGE_TAG"
echo "Latest:   $ECR_REPO:latest"
echo ""
echo "Next: Update the ECS task definition with the image URI"
echo "Or use: aws ecs update-service --cluster <cluster> --service <service> --force-new-deployment"
