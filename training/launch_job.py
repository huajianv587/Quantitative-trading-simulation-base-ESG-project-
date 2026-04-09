import argparse
import os
from pathlib import Path

import boto3
from dotenv import load_dotenv
import sagemaker
from sagemaker.huggingface import HuggingFace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

BUCKET = os.getenv("TRAINING_S3_BUCKET", "jiang-data-2026-esg-training")
S3_PREFIX = os.getenv("TRAINING_S3_PREFIX", "esg-finetune/data")
S3_OUTPUT_PREFIX = os.getenv("TRAINING_S3_OUTPUT_PREFIX", "esg-finetune/output")
S3_OUTPUT = f"s3://{BUCKET}/{S3_OUTPUT_PREFIX}"

# 优先从 .env 读取已有云资源
IAM_ROLE = os.getenv("SAGEMAKER_EXECUTION_ROLE_ARN", "arn:aws:iam::935154424717:role/ESGtrainer")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance_type",     default="ml.g5.2xlarge",
                        help="GPU 实例类型，A10G 24GB")
    parser.add_argument("--model_name",        default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--num_train_epochs",  type=int, default=2)
    parser.add_argument("--max_steps",         type=int, default=-1,
                        help="设置 >0 用于快速验证，例如 --max_steps 100")
    parser.add_argument("--no-wait",           dest="wait", action="store_false", default=True,
                        help="加此参数则提交后立即返回，不等待训练完成（去 AWS 控制台看日志）")
    return parser.parse_args()


def main():
    args = parse_args()
    if not IAM_ROLE:
        raise RuntimeError("SAGEMAKER_EXECUTION_ROLE_ARN is not set in .env")

    sagemaker_session = sagemaker.Session(
        boto_session=boto3.Session(region_name=AWS_REGION)
    )

    # SageMaker 会把 S3 数据挂载到 /opt/ml/input/data/{channel_name}/
    train_input = sagemaker.inputs.TrainingInput(
        s3_data=f"s3://{BUCKET}/{S3_PREFIX}/train.jsonl",
        content_type="application/json",
    )
    val_input = sagemaker.inputs.TrainingInput(
        s3_data=f"s3://{BUCKET}/{S3_PREFIX}/val.jsonl",
        content_type="application/json",
    )

    estimator = HuggingFace(
        entry_point="finetune.py",           # 训练入口脚本
        source_dir=str(PROJECT_ROOT / "training"),  # 打包整个 training/ 目录上传
        role=IAM_ROLE,
        sagemaker_session=sagemaker_session,
        instance_type=args.instance_type,
        instance_count=1,
        transformers_version="4.36",
        pytorch_version="2.1",
        py_version="py310",
        output_path=S3_OUTPUT,              # 训练完成后模型权重保存到这里
        hyperparameters={
            # 这些参数会以 --key value 的形式传给 finetune.py 的 argparse
            "model_name":        args.model_name,
            "train_data_path":   "/opt/ml/input/data/train/train.jsonl",
            "val_data_path":     "/opt/ml/input/data/val/val.jsonl",
            "output_dir":        "/opt/ml/model",
            "num_train_epochs":  args.num_train_epochs,
            "max_steps":         args.max_steps,
        },
    )

    print(f"[Job] Submitting SageMaker Training Job ...")
    print(f"[Job] Instance : {args.instance_type}")
    print(f"[Job] Model    : {args.model_name}")
    print(f"[Job] Region   : {AWS_REGION}")
    print(f"[Job] Role     : {IAM_ROLE}")
    print(f"[Job] Output   : {S3_OUTPUT}")

    estimator.fit(
        inputs={"train": train_input, "val": val_input},
        wait=args.wait,   # True: 本地阻塞等完成  False: 提交后立即返回，去控制台看日志
        logs="All",
    )

    if args.wait:
        print(f"[Job] Training complete. Model saved to: {S3_OUTPUT}")


if __name__ == "__main__":
    main()
