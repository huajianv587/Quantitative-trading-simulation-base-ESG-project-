#!/bin/bash
# EC2 训练脚本
# 使用前提：EC2 实例已挂载 IAM Role（有 S3 读写权限），使用 Deep Learning AMI

set -e  # 任意一步报错就停止

# ========== 配置区 ==========
BUCKET="jiang-data-2026-esg-training"
S3_DATA="s3://${BUCKET}/esg-finetune/data"
S3_OUTPUT="s3://${BUCKET}/esg-finetune/output"
REPO_URL="https://github.com/你的用户名/你的仓库名.git"  # 改成你的 git 地址
WORK_DIR="/home/ubuntu/esg-copilot"
# ============================

echo "====== [1/5] 克隆代码 ======"
if [ -d "$WORK_DIR" ]; then
    echo "目录已存在，执行 git pull"
    cd "$WORK_DIR" && git pull
else
    git clone "$REPO_URL" "$WORK_DIR"
    cd "$WORK_DIR"
fi

echo "====== [2/5] 安装依赖 ======"
pip install -q -r training/requirements.txt 2>/dev/null || \
pip install -q peft bitsandbytes transformers datasets accelerate

echo "====== [3/5] 从 S3 拉取训练数据 ======"
mkdir -p "$WORK_DIR/data/processed"
aws s3 cp "${S3_DATA}/train.jsonl" "$WORK_DIR/data/processed/train.jsonl"
aws s3 cp "${S3_DATA}/val.jsonl"   "$WORK_DIR/data/processed/val.jsonl"
echo "数据下载完成"

echo "====== [4/5] 开始训练 ======"
python "$WORK_DIR/training/finetune.py" \
    --train_data_path "$WORK_DIR/data/processed/train.jsonl" \
    --val_data_path   "$WORK_DIR/data/processed/val.jsonl" \
    --output_dir      "$WORK_DIR/model-output"

echo "====== [5/5] 上传模型到 S3 ======"
aws s3 cp "$WORK_DIR/model-output/" "${S3_OUTPUT}/" --recursive
echo "====== 全部完成！模型已保存到 ${S3_OUTPUT} ======"
