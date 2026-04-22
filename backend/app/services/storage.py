"""对象存储封装：MinIO/S3 兼容接口，用于原始课件文件。"""
from __future__ import annotations

import io
import os
from pathlib import Path

from minio import Minio
from minio.error import S3Error
from loguru import logger

from app.core.config import settings


class Storage:
    def __init__(self):
        self.bucket = settings.S3_BUCKET
        self.local_root = Path(os.getenv("LOCAL_STORAGE_DIR", "/tmp/ai-tp-420-storage"))
        self.local_root.mkdir(parents=True, exist_ok=True)
        self.client: Minio | None = None
        self._use_local = False

        endpoint = (settings.S3_ENDPOINT or "").strip()
        if not endpoint:
            self._use_local = True
            logger.warning("S3_ENDPOINT 未配置，回退到本地文件存储")
            return

        try:
            endpoint = endpoint.replace("https://", "").replace("http://", "")
            self.client = Minio(
                endpoint=endpoint,
                access_key=settings.S3_ACCESS_KEY,
                secret_key=settings.S3_SECRET_KEY,
                secure=settings.S3_USE_SSL,
                region=settings.S3_REGION,
            )
            self._ensure_bucket()
        except Exception as e:  # noqa: BLE001
            self._use_local = True
            self.client = None
            logger.exception(f"S3 初始化失败，回退到本地文件存储: {e}")

    def _ensure_bucket(self):
        if self.client is None:
            return
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except Exception as e:  # noqa: BLE001
            self._use_local = True
            self.client = None
            logger.exception(f"S3 bucket 检查失败，回退到本地文件存储: {e}")

    def _local_path(self, key: str) -> Path:
        return self.local_root / self.bucket / Path(key)

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        if self._use_local or self.client is None:
            path = self._local_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return key

        self.client.put_object(
            self.bucket, key, io.BytesIO(data), length=len(data), content_type=content_type,
        )
        return key

    def download_to(self, key: str, dst_path: str) -> None:
        if self._use_local or self.client is None:
            src = self._local_path(key)
            Path(dst_path).write_bytes(src.read_bytes())
            return
        self.client.fget_object(self.bucket, key, dst_path)

    def presigned_get(self, key: str, expires_sec: int = 3600) -> str:
        if self._use_local or self.client is None:
            return str(self._local_path(key))
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
