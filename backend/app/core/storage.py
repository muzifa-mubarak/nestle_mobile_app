"""Local disk storage, or S3 when S3_BUCKET is set."""

from app.core.config import get_settings


def presigned_url(key: str) -> str | None:
    settings = get_settings()
    if not settings.s3_bucket or not key:
        return None
    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        aws_access_key_id=settings.s3_access_key or None,
        aws_secret_access_key=settings.s3_secret_key or None,
        region_name=settings.s3_region,
    )
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=300,
    )
