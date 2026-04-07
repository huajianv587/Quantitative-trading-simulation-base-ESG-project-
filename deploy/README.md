# AWS 部署指南 - ESG Agentic RAG Copilot

本目录包含部署应用到 AWS 的配置文件和脚本。

## 📋 目录结构

```
deploy/
├── nginx.conf              # Nginx 反向代理配置
└── aws/
    ├── ecr-push.sh        # ECR 镜像推送脚本
    └── ecs-task-def.json  # ECS 任务定义
```

## 🚀 部署流程

### 1️⃣ 前置准备

#### 安装 AWS CLI
```bash
# Mac/Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Windows (PowerShell)
msiexec.exe /i https://awscli.amazonaws.com/AWSCLIV2.msi

# 验证
aws --version
```

#### 配置 AWS 凭证
```bash
aws configure
# 输入：
# AWS Access Key ID: YOUR_ACCESS_KEY
# AWS Secret Access Key: YOUR_SECRET_KEY
# Default region name: us-east-1
# Default output format: json
```

#### 安装 Docker
```bash
# Mac: https://www.docker.com/products/docker-desktop
# Linux: sudo apt-get install docker.io
# Windows: https://www.docker.com/products/docker-desktop

# 验证
docker --version
```

### 2️⃣ 构建并推送 Docker 镜像到 ECR

```bash
# 赋予脚本执行权限
chmod +x deploy/aws/ecr-push.sh

# 推送镜像（自动创建 ECR 仓库）
deploy/aws/ecr-push.sh us-east-1 123456789012 esg-agentic-rag-copilot

# 或使用默认值（需要先配置 AWS CLI）
cd deploy/aws
./ecr-push.sh
```

脚本会：
- ✅ 登录 AWS ECR
- ✅ 创建 ECR 仓库（如果不存在）
- ✅ 构建 Docker 镜像
- ✅ 推送到 AWS

### 3️⃣ 更新 ECS 任务定义

编辑 `deploy/aws/ecs-task-def.json`，替换以下占位符：

```json
"YOUR_AWS_ACCOUNT_ID"    → 你的 AWS 账户 ID（12 位数字）
"YOUR_REGION"            → AWS 区域（如 us-east-1）
```

获取账户 ID：
```bash
aws sts get-caller-identity --query Account --output text
```

### 4️⃣ 在 AWS 上创建 ECS 服务

#### 创建 ECS 集群
```bash
aws ecs create-cluster --cluster-name esg-rag-cluster --region us-east-1
```

#### 注册任务定义
```bash
aws ecs register-task-definition \
  --cli-input-json file://deploy/aws/ecs-task-def.json \
  --region us-east-1
```

#### 创建 ECS 服务
```bash
aws ecs create-service \
  --cluster esg-rag-cluster \
  --service-name esg-rag-service \
  --task-definition esg-agentic-rag-copilot:1 \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxx],securityGroups=[sg-xxxxx],assignPublicIp=ENABLED}" \
  --region us-east-1
```

### 5️⃣ 配置 AWS Secrets Manager（管理敏感信息）

```bash
# 存储 OpenAI API 密钥
aws secretsmanager create-secret \
  --name esg-rag-openai-key \
  --secret-string '{"OPENAI_API_KEY":"sk-xxxxx"}' \
  --region us-east-1

# 存储其他密钥...
# （Deepseek, Supabase, AWS 凭证等）
```

### 6️⃣ 配置 ALB（Application Load Balancer）

```bash
# 创建目标组
aws elbv2 create-target-group \
  --name esg-rag-targets \
  --protocol HTTP \
  --port 80 \
  --vpc-id vpc-xxxxx \
  --target-type ip \
  --region us-east-1

# 创建 ALB
aws elbv2 create-load-balancer \
  --name esg-rag-alb \
  --subnets subnet-xxxxx subnet-xxxxx \
  --security-groups sg-xxxxx \
  --scheme internet-facing \
  --type application \
  --region us-east-1

# 创建监听器
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:... \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:... \
  --region us-east-1
```

### 7️⃣ 配置 CloudFront（CDN）和 HTTPS

1. 在 AWS Certificate Manager 申请 SSL 证书
2. 配置 CloudFront 分布
3. 更新 DNS 记录指向 CloudFront

## 📊 监控和日志

### 查看 ECS 任务日志
```bash
aws logs tail /ecs/esg-agentic-rag-copilot --follow --region us-east-1
```

### 查看 ECS 服务状态
```bash
aws ecs describe-services \
  --cluster esg-rag-cluster \
  --services esg-rag-service \
  --region us-east-1
```

### CloudWatch 监控
在 AWS 控制台 → CloudWatch → Dashboards 中创建监控仪表板

## 🔄 更新部署

### 推送新版本
```bash
./deploy/aws/ecr-push.sh us-east-1 123456789012 esg-agentic-rag-copilot v2.0
```

### 更新 ECS 服务
```bash
aws ecs update-service \
  --cluster esg-rag-cluster \
  --service esg-rag-service \
  --force-new-deployment \
  --region us-east-1
```

## 🔐 安全最佳实践

- ✅ 使用 IAM 角色而不是硬编码凭证
- ✅ 在 Secrets Manager 中存储敏感信息
- ✅ 启用 VPC 安全组和 NACLs
- ✅ 使用 HTTPS/TLS
- ✅ 定期扫描 ECR 镜像的漏洞
- ✅ 启用 CloudTrail 审计日志
- ✅ 使用 WAF 保护 ALB

## 📚 相关资源

- [AWS ECS 文档](https://docs.aws.amazon.com/ecs/)
- [AWS ECR 文档](https://docs.aws.amazon.com/ecr/)
- [AWS Secrets Manager 文档](https://docs.aws.amazon.com/secretsmanager/)
- [Nginx 文档](https://nginx.org/en/docs/)
- [FastAPI 部署指南](https://fastapi.tiangolo.com/deployment/concepts/)

## 🆘 故障排查

### 镜像推送失败
```bash
# 检查 Docker 登录
docker ps

# 重新登录 ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
```

### ECS 任务无法启动
```bash
# 查看任务日志
aws ecs describe-tasks \
  --cluster esg-rag-cluster \
  --tasks <task-arn> \
  --region us-east-1

# 查看详细日志
aws logs tail /ecs/esg-agentic-rag-copilot --follow
```

### 健康检查失败
```bash
# 手动测试健康检查端点
curl http://YOUR_ALB_DNS/health

# 检查安全组规则是否允许健康检查
```

## 💰 成本优化

- 使用 Fargate Spot 实例降低成本（非关键环境）
- 配置自动扩展策略
- 定期审查 CloudWatch 成本
- 删除未使用的资源

---

**需要帮助？** 查看 [AWS 支持中心](https://console.aws.amazon.com/support/)
