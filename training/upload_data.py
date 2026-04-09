import boto3
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

BUCKET = os.getenv("TRAINING_S3_BUCKET", "jiang-data-2026-esg-training")
S3_PREFIX = os.getenv("TRAINING_S3_PREFIX", "esg-finetune/data")

LOCAL_FILES = {
    "train.jsonl": PROJECT_ROOT / "data" / "processed" / "train.jsonl",
    "val.jsonl":   PROJECT_ROOT / "data" / "processed" / "val.jsonl",
}


def upload_data(bucket: str = BUCKET, prefix: str = S3_PREFIX) -> dict:
    s3 = boto3.client("s3")
    uris = {}
    for filename, local_path in LOCAL_FILES.items():
        if not local_path.exists():
            raise FileNotFoundError(f"Not found: {local_path}")
        key = f"{prefix}/{filename}"
        print(f"Uploading {local_path.name} → s3://{bucket}/{key}")
        s3.upload_file(Filename=str(local_path), Bucket=bucket, Key=key)
        uris[filename] = f"s3://{bucket}/{key}"
        print(f"  Done.")
    return uris


def main():
    uris = upload_data()
    print("\n[S3 URIs — copy these into launch_job.py if needed]")
    for name, uri in uris.items():
        print(f"  {name}: {uri}")


if __name__ == "__main__":
    main()
