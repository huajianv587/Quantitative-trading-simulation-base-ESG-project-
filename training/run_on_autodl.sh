#!/bin/bash
# AutoDL 训练脚本
# 使用前提：已在 AutoDL 控制台上传数据到 /root/autodl-tmp/data/
# 或者配置了 AWS 凭证从 S3 拉数据（见注释部分）

set -e

# ========== 配置区 ==========
if [ -z "$GIT_TOKEN" ]; then
    echo "请输入 GitHub Personal Access Token："
    read -s GIT_TOKEN
fi
REPO_URL="https://${GIT_TOKEN}@github.com/huajianv587/ESG_Agentic.git"
WORK_DIR="/root/esg-copilot"
DATA_DIR="/root/autodl-tmp/data"    # AutoDL 推荐把数据放这里（高速 SSD）
OUTPUT_DIR="/root/autodl-tmp/output"
BUCKET="${TRAINING_S3_BUCKET:-jiang-data-2026-esg-training}"
S3_PREFIX="${TRAINING_S3_PREFIX:-esg-finetune/data}"
S3_OUTPUT_PREFIX="${TRAINING_S3_OUTPUT_PREFIX:-esg-finetune/output}"
# ============================

echo "====== [1/4] 克隆 / 更新代码 ======"
if [ -d "$WORK_DIR" ]; then
    echo "目录已存在，执行 git pull"
    cd "$WORK_DIR" && git pull
else
    # AutoDL 国内网络，走镜像加速
    git clone "https://gitclone.com/${REPO_URL#https://}" "$WORK_DIR" 2>/dev/null || \
    git clone "$REPO_URL" "$WORK_DIR"
    cd "$WORK_DIR"
fi

echo "====== [2/4] 安装依赖 ======"
# AutoDL 镜像已预装 PyTorch，只需装额外的包
pip install -q peft bitsandbytes transformers datasets accelerate \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

# ---- 可选：从 AWS S3 拉数据（如果没有手动上传）----
# 需要先在 AutoDL 终端执行：
#   pip install awscli
#   aws configure  （填入 Access Key / Secret Key / region）
# 然后取消下面三行注释：
# mkdir -p "$DATA_DIR"
# aws s3 cp "s3://${BUCKET}/${S3_PREFIX}/train.jsonl" "$DATA_DIR/train.jsonl"
# aws s3 cp "s3://${BUCKET}/${S3_PREFIX}/val.jsonl"   "$DATA_DIR/val.jsonl"

echo "====== [3/4] 开始训练 ======"
mkdir -p "$OUTPUT_DIR"
python "$WORK_DIR/training/finetune.py" \
    --train_data_path "$DATA_DIR/train.jsonl" \
    --val_data_path   "$DATA_DIR/val.jsonl" \
    --output_dir      "$OUTPUT_DIR"

echo "====== [4/4] 完成！======"
echo "模型保存在：$OUTPUT_DIR"
echo "可在 AutoDL 控制台「文件管理」下载，或上传到 S3："
echo "  aws s3 cp $OUTPUT_DIR/ s3://${BUCKET}/${S3_OUTPUT_PREFIX}/ --recursive"
