import os
import uuid
from pathlib import Path

import boto3
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION")
BUCKET = os.getenv("S3_BUCKET")
USE_S3 = bool(AWS_REGION and BUCKET)
LOCAL_UPLOAD_ROOT = Path(__file__).resolve().parents[1] / "static" / "uploads"


def upload_bytes_to_s3(image_bytes, folder, content_type="image/jpeg"):
    filename = f"{uuid.uuid4()}.jpg"
    file_key = f"{folder}/{filename}"

    if USE_S3:
        s3 = boto3.client("s3", region_name=AWS_REGION)
        s3.put_object(
            Bucket=BUCKET,
            Key=file_key,
            Body=image_bytes,
            ContentType=content_type,
        )
        return f"s3://{BUCKET}/{file_key}", file_key

    local_folder = LOCAL_UPLOAD_ROOT / folder
    local_folder.mkdir(parents=True, exist_ok=True)
    local_path = local_folder / filename
    local_path.write_bytes(image_bytes)
    return f"/static/uploads/{file_key}", file_key
