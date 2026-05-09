from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import formatdate
from pathlib import Path
from typing import Optional
import base64
import hashlib
import hmac
import mimetypes
import time
import urllib.parse
import uuid

import requests

from src.config import AppConfig


@dataclass(frozen=True)
class PublicAsset:
    local_path: str
    public_url: Optional[str] = None
    expires_at: Optional[str] = None
    storage_provider: Optional[str] = None


class PublicAssetStore:
    def ensure_public_url(self, local_path: str, ttl_seconds: int = 86400) -> PublicAsset:
        raise NotImplementedError

    def is_enabled(self) -> bool:
        return False

    def status_message(self) -> str:
        return "Public asset upload is disabled."


class DisabledPublicAssetStore(PublicAssetStore):
    def __init__(self, enabled_flag: bool) -> None:
        self._enabled_flag = enabled_flag

    def ensure_public_url(self, local_path: str, ttl_seconds: int = 86400) -> PublicAsset:
        raise RuntimeError("Public URL upload is not configured.")

    def is_enabled(self) -> bool:
        return self._enabled_flag

    def status_message(self) -> str:
        if self._enabled_flag:
            return "Public URL upload is enabled but no store is implemented yet."
        return "Public URL upload is disabled."


class AliyunOssPublicAssetStore(PublicAssetStore):
    def __init__(self, config: AppConfig) -> None:
        self._access_key_id = config.aliyun_oss_access_key_id
        self._access_key_secret = config.aliyun_oss_access_key_secret
        self._endpoint = config.aliyun_oss_endpoint
        self._bucket = config.aliyun_oss_bucket
        self._base_url = (config.aliyun_oss_public_base_url or "").rstrip("/")

    def is_enabled(self) -> bool:
        return True

    def status_message(self) -> str:
        return f"Aliyun OSS enabled: bucket={self._bucket or 'unknown'}"

    def ensure_public_url(self, local_path: str, ttl_seconds: int = 86400) -> PublicAsset:
        if local_path.startswith("http://") or local_path.startswith("https://"):
            return PublicAsset(local_path=local_path, public_url=local_path)

        path = Path(local_path)
        if not path.exists():
            raise FileNotFoundError(f"Asset not found: {local_path}")

        object_key = f"public/{uuid.uuid4().hex}{path.suffix.lower()}"
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        upload_url = self._build_object_url(object_key)
        date_header = formatdate(usegmt=True)

        canonical_resource = f"/{self._bucket}/{object_key}"
        string_to_sign = (
            f"PUT\n\n{content_type}\n{date_header}\n{canonical_resource}"
        )
        signature = _oss_sign(self._access_key_secret, string_to_sign)

        headers = {
            "Content-Type": content_type,
            "Date": date_header,
            "Authorization": f"OSS {self._access_key_id}:{signature}",
        }

        with path.open("rb") as handle:
            response = requests.put(upload_url, data=handle, headers=headers, timeout=15)

        if response.status_code not in {200, 201, 204}:
            raise RuntimeError(
                f"OSS upload failed: HTTP {response.status_code} {response.text}"
            )

        signed_url = _oss_build_signed_get_url(
            self._access_key_id,
            self._access_key_secret,
            self._bucket,
            self._endpoint,
            self._base_url,
            object_key,
            ttl_seconds,
        )
        expires_at = (datetime.utcnow() + timedelta(seconds=ttl_seconds)).isoformat()
        return PublicAsset(
            local_path=local_path,
            public_url=signed_url,
            expires_at=expires_at,
            storage_provider="aliyun_oss",
        )

    def _build_object_url(self, object_key: str) -> str:
        if self._base_url:
            return f"{self._base_url}/{object_key}"
        return f"https://{self._bucket}.{self._endpoint}/{object_key}"


def _oss_sign(secret: str, string_to_sign: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("utf-8")


def _oss_build_signed_get_url(
    access_key_id: str,
    access_key_secret: str,
    bucket: str,
    endpoint: str,
    base_url: str,
    object_key: str,
    ttl_seconds: int,
) -> str:
    """Build a time-limited signed GET URL for OSS object access."""
    expires = int(time.time()) + ttl_seconds
    canonical_resource = f"/{bucket}/{object_key}"
    string_to_sign = f"GET\n\n\n{expires}\n{canonical_resource}"
    signature = _oss_sign(access_key_secret, string_to_sign)

    if base_url:
        url = f"{base_url.rstrip('/')}/{object_key}"
    else:
        url = f"https://{bucket}.{endpoint}/{object_key}"

    encoded_sig = urllib.parse.quote(signature, safe="")
    return f"{url}?Expires={expires}&OSSAccessKeyId={access_key_id}&Signature={encoded_sig}"


def build_public_asset_store(config: AppConfig) -> PublicAssetStore:
    if not config.enable_public_url_upload:
        return DisabledPublicAssetStore(False)

    required = [
        config.aliyun_oss_access_key_id,
        config.aliyun_oss_access_key_secret,
        config.aliyun_oss_endpoint,
        config.aliyun_oss_bucket,
    ]
    if all(required):
        return AliyunOssPublicAssetStore(config)

    return DisabledPublicAssetStore(True)
