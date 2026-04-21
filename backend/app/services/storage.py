"""对象存储封装：MinIO/S3 兼容接口，用于原始课件文件。"""
from __future__ import annotations

import io

from minio import Minio
from minio.error import S3Error

from app.core.config import settings


class Storage:
    def __init__(self):
        endpoint = settings.S3_ENDPOINT.replace("https://", "").replace("http://", "")
        self.client = Minio(
            endpoint=endpoint,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            secure=settings.S3_USE_SSL,
            region=settings.S3_REGION,
        )
        self.bucket = settings.S3_BUCKET
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except S3Error:
            pass

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self.client.put_object(
            self.bucket, key, io.BytesIO(data), length=len(data), content_type=content_type,
        )
        return key

    def download_to(self, key: str, dst_path: str) -> None:
        self.client.fget_object(self.bucket, key, dst_path)

    def presigned_get(self, key: str, expires_sec: int = 3600) -> str:
        from datetime import timedelta
        return self.client.presigned_get_object(
            self.bucket, key, expires=timedelta(seconds=expires_sec)
        )


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = Storage()
    return _storage
