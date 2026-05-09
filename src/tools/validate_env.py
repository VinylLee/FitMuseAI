from __future__ import annotations

from dataclasses import dataclass
from email.utils import formatdate
from hashlib import sha1
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse
import argparse
import base64
import hmac
import sys
import time
import urllib.parse
import uuid
import xml.etree.ElementTree as ET

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config
from src.public_asset_store import build_public_asset_store
from src.providers import build_provider_registry


ALLOWED_IMAGE_QUALITIES = {"preview", "high", "compare"}
ALLOWED_ASSET_CATEGORIES = {
    "upper_body",
    "lower_body",
    "dress",
    "outerwear",
    "set",
    "shoes",
    "other",
}


@dataclass
class CheckResult:
    name: str
    ok: bool
    message: str


def _redact(value: Optional[str]) -> str:
    if not value:
        return "<missing>"
    return "<set>"


def _check_path_exists(label: str, path: Path) -> CheckResult:
    if path.exists():
        return CheckResult(label, True, str(path))
    return CheckResult(label, False, f"Missing path: {path}")


def _check_quality(value: str) -> CheckResult:
    if value in ALLOWED_IMAGE_QUALITIES:
        return CheckResult("DEFAULT_IMAGE_QUALITY", True, value)
    return CheckResult("DEFAULT_IMAGE_QUALITY", False, f"Invalid: {value}")


def _check_public_base_url(bucket: str, endpoint: str, base_url: str, label: str) -> list[CheckResult]:
    results: list[CheckResult] = []
    if not base_url:
        results.append(CheckResult(label, False, "Missing public base URL"))
        return results

    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"}:
        results.append(CheckResult(label, False, f"Invalid URL scheme: {parsed.scheme}"))
        return results

    expected_host = ""
    if bucket and endpoint:
        expected_host = f"{bucket}.{endpoint}"
        if parsed.netloc != expected_host:
            results.append(
                CheckResult(
                    label,
                    False,
                    f"Host mismatch: expected {expected_host}, got {parsed.netloc}",
                )
            )
        else:
            results.append(CheckResult(label, True, base_url))
    else:
        results.append(CheckResult(label, False, "Missing bucket or endpoint"))

    return results


def _check_network(urls: Iterable[str]) -> list[CheckResult]:
    results: list[CheckResult] = []
    session = requests.Session()
    for url in urls:
        if not url:
            continue
        try:
            response = session.head(url, timeout=5)
            ok = response.status_code < 500
            results.append(CheckResult(f"HEAD {url}", ok, f"status={response.status_code}"))
        except requests.RequestException as exc:
            results.append(CheckResult(f"HEAD {url}", False, f"error={exc}"))
    return results


def _oss_build_resource(bucket: str, subresource: str = "") -> str:
    if subresource:
        if not subresource.startswith("?"):
            subresource = f"?{subresource}"
        return f"/{bucket}/{subresource}"
    return f"/{bucket}/"


def _oss_sign(secret: str, string_to_sign: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), sha1).digest()
    return base64.b64encode(digest).decode("utf-8")


def _oss_parse_error(text: str) -> tuple[Optional[str], Optional[str]]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None, None
    code = root.findtext("Code")
    message = root.findtext("Message")
    return code, message


def _check_oss_acl(
    access_key_id: str,
    access_key_secret: str,
    bucket: str,
    endpoint: str,
    base_url: str,
    timeout: int = 8,
) -> CheckResult:
    """Check OSS credentials validity via GetBucketAcl."""
    if not (access_key_id and access_key_secret and bucket and endpoint):
        return CheckResult("ALIYUN_OSS_ACL", False, "Missing OSS configuration")

    if base_url:
        target = base_url.rstrip("/") + "/?acl"
    else:
        target = f"https://{bucket}.{endpoint}/?acl"

    date_header = formatdate(usegmt=True)
    resource = _oss_build_resource(bucket, "acl")
    string_to_sign = f"GET\n\n\n{date_header}\n{resource}"
    signature = _oss_sign(access_key_secret, string_to_sign)

    headers = {
        "Date": date_header,
        "Authorization": f"OSS {access_key_id}:{signature}",
    }

    try:
        response = requests.get(target, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        return CheckResult("ALIYUN_OSS_ACL", False, f"Network error: {exc}")

    if response.status_code in {200, 204}:
        return CheckResult("ALIYUN_OSS_ACL", True, "OK")

    if response.status_code in {301, 302, 307, 308}:
        location = response.headers.get("Location", "")
        return CheckResult("ALIYUN_OSS_ACL", False, f"Redirected: {location or 'check endpoint'}")

    code, message = _oss_parse_error(response.text or "")
    if code in {"InvalidAccessKeyId", "SignatureDoesNotMatch", "RequestTimeTooSkewed"}:
        return CheckResult("ALIYUN_OSS_ACL", False, f"{code}: {message or 'invalid credentials'}")
    if code == "AccessDenied":
        return CheckResult(
            "ALIYUN_OSS_ACL",
            False,
            "AccessDenied: credentials valid but lacking GetBucketAcl permission",
        )
    if code == "NoSuchBucket":
        return CheckResult("ALIYUN_OSS_ACL", False, "NoSuchBucket: check bucket name")

    return CheckResult(
        "ALIYUN_OSS_ACL",
        False,
        f"HTTP {response.status_code}: {code or 'unknown error'}",
    )


def _check_oss_upload(
    access_key_id: str,
    access_key_secret: str,
    bucket: str,
    endpoint: str,
    base_url: str,
    timeout: int = 15,
) -> list[CheckResult]:
    """Test full OSS upload / read-back / delete cycle with a temporary file."""
    results: list[CheckResult] = []

    if not (access_key_id and access_key_secret and bucket and endpoint):
        results.append(CheckResult("ALIYUN_OSS_UPLOAD", False, "Missing OSS configuration"))
        return results

    object_key = f"validate_env_test_{uuid.uuid4().hex}.txt"
    content = b"FitMuseAI OSS validation test file"
    content_type = "text/plain"

    if base_url:
        upload_url = f"{base_url.rstrip('/')}/{object_key}"
    else:
        upload_url = f"https://{bucket}.{endpoint}/{object_key}"

    download_url = upload_url

    date_header = formatdate(usegmt=True)

    # --- PutObject (with public-read ACL) ---
    canonical_headers = "x-oss-object-acl:public-read\n"
    canonical_resource = f"/{bucket}/{object_key}"
    string_to_sign = (
        f"PUT\n\n{content_type}\n{date_header}\n"
        f"{canonical_headers}{canonical_resource}"
    )
    signature = _oss_sign(access_key_secret, string_to_sign)

    put_headers = {
        "Content-Type": content_type,
        "Date": date_header,
        "Authorization": f"OSS {access_key_id}:{signature}",
        "x-oss-object-acl": "public-read",
    }

    results.append(CheckResult("ALIYUN_OSS_UPLOAD", True, f"PutObject with public-read ACL to {upload_url}"))

    try:
        response = requests.put(upload_url, data=content, headers=put_headers, timeout=timeout)
    except requests.RequestException as exc:
        results.append(CheckResult("ALIYUN_OSS_UPLOAD_ACL", False, f"Network error: {exc}"))
        return results

    acl_upload_ok = response.status_code in {200, 201, 204}
    if not acl_upload_ok:
        results.append(CheckResult("ALIYUN_OSS_UPLOAD_ACL", False, f"HTTP {response.status_code}: public-read ACL rejected"))
        # Fall back: try upload without x-oss-object-acl header
        date_header2 = formatdate(usegmt=True)
        plain_resource = f"/{bucket}/{object_key}"
        plain_string = f"PUT\n\n{content_type}\n{date_header2}\n{plain_resource}"
        plain_sig = _oss_sign(access_key_secret, plain_string)
        plain_headers = {
            "Content-Type": content_type,
            "Date": date_header2,
            "Authorization": f"OSS {access_key_id}:{plain_sig}",
        }
        try:
            resp2 = requests.put(upload_url, data=content, headers=plain_headers, timeout=timeout)
        except requests.RequestException as exc2:
            results.append(CheckResult("ALIYUN_OSS_UPLOAD", False, f"Upload (no-ACL) network error: {exc2}"))
            return results

        if resp2.status_code in {200, 201, 204}:
            results.append(CheckResult("ALIYUN_OSS_UPLOAD", True, "PutObject OK (without public-read ACL)"))
            uploaded_with_acl = False
        else:
            code2, msg2 = _oss_parse_error(resp2.text or "")
            results.append(CheckResult("ALIYUN_OSS_UPLOAD", False, f"HTTP {resp2.status_code}: {code2 or msg2 or 'upload failed'}"))
            _delete_oss_object(access_key_id, access_key_secret, bucket, endpoint, base_url, object_key, timeout)
            return results
    else:
        results.append(CheckResult("ALIYUN_OSS_UPLOAD_ACL", True, "PutObject with public-read ACL OK"))
        uploaded_with_acl = True

    # --- GetObject (read-back verification) ---
    # Try public download first; fall back to authenticated download if blocked
    get_response = None
    try:
        get_response = requests.get(download_url, timeout=timeout)
    except requests.RequestException:
        pass

    if get_response is not None and get_response.status_code == 200 and get_response.content == content:
        results.append(CheckResult("ALIYUN_OSS_DOWNLOAD", True, "GetObject (public) OK"))
    elif not uploaded_with_acl:
        # Object is private — use authenticated download instead
        date_header3 = formatdate(usegmt=True)
        get_resource = f"/{bucket}/{object_key}"
        get_string = f"GET\n\n\n{date_header3}\n{get_resource}"
        get_sig = _oss_sign(access_key_secret, get_string)
        get_headers = {
            "Date": date_header3,
            "Authorization": f"OSS {access_key_id}:{get_sig}",
        }
        try:
            auth_resp = requests.get(download_url, headers=get_headers, timeout=timeout)
        except requests.RequestException as exc3:
            results.append(CheckResult("ALIYUN_OSS_DOWNLOAD", False, f"Authenticated download network error: {exc3}"))
            _delete_oss_object(access_key_id, access_key_secret, bucket, endpoint, base_url, object_key, timeout)
            return results

        if auth_resp.status_code == 200 and auth_resp.content == content:
            results.append(CheckResult("ALIYUN_OSS_DOWNLOAD", True, "GetObject (authenticated) OK"))
        else:
            results.append(CheckResult("ALIYUN_OSS_DOWNLOAD", False, f"HTTP {auth_resp.status_code}: authenticated download failed"))
            _delete_oss_object(access_key_id, access_key_secret, bucket, endpoint, base_url, object_key, timeout)
            return results
    elif get_response is not None:
        results.append(CheckResult("ALIYUN_OSS_DOWNLOAD", False, f"HTTP {get_response.status_code}: public download failed"))
        _delete_oss_object(access_key_id, access_key_secret, bucket, endpoint, base_url, object_key, timeout)
        return results
    else:
        results.append(CheckResult("ALIYUN_OSS_DOWNLOAD", False, "Public download failed (network error) and object was uploaded with public-read ACL — bucket may block public access"))
        _delete_oss_object(access_key_id, access_key_secret, bucket, endpoint, base_url, object_key, timeout)
        return results

    # --- Signed URL test ---
    signed_url = _oss_build_signed_get_url(
        access_key_id, access_key_secret, bucket, endpoint, base_url,
        object_key, ttl_seconds=300,
    )
    try:
        signed_resp = requests.get(signed_url, timeout=timeout)
    except requests.RequestException as exc4:
        results.append(CheckResult("ALIYUN_OSS_SIGNED_URL", False, f"Signed URL network error: {exc4}"))
    else:
        if signed_resp.status_code == 200 and signed_resp.content == content:
            results.append(CheckResult("ALIYUN_OSS_SIGNED_URL", True, "Signed GET URL OK"))
        else:
            results.append(CheckResult("ALIYUN_OSS_SIGNED_URL", False, f"HTTP {signed_resp.status_code}: signed URL download failed"))

    # --- DeleteObject (cleanup) ---
    if _delete_oss_object(access_key_id, access_key_secret, bucket, endpoint, base_url, object_key, timeout):
        results.append(CheckResult("ALIYUN_OSS_DELETE", True, "DeleteObject OK"))
    else:
        results.append(CheckResult("ALIYUN_OSS_DELETE", False, "DeleteObject failed (manual cleanup may be needed)"))

    return results


def _oss_build_signed_get_url(
    access_key_id: str,
    access_key_secret: str,
    bucket: str,
    endpoint: str,
    base_url: str,
    object_key: str,
    ttl_seconds: int,
) -> str:
    """Build a time-limited signed GET URL for OSS object access (mirrors public_asset_store)."""
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


def _delete_oss_object(
    access_key_id: str,
    access_key_secret: str,
    bucket: str,
    endpoint: str,
    base_url: str,
    object_key: str,
    timeout: int = 10,
) -> bool:
    """Delete a temporary test object from OSS. Returns True on success."""
    date_header = formatdate(usegmt=True)
    canonical_resource = f"/{bucket}/{object_key}"
    string_to_sign = f"DELETE\n\n\n{date_header}\n{canonical_resource}"
    signature = _oss_sign(access_key_secret, string_to_sign)

    if base_url:
        delete_url = f"{base_url.rstrip('/')}/{object_key}"
    else:
        delete_url = f"https://{bucket}.{endpoint}/{object_key}"

    headers = {
        "Date": date_header,
        "Authorization": f"OSS {access_key_id}:{signature}",
    }

    try:
        resp = requests.delete(delete_url, headers=headers, timeout=timeout)
        return resp.status_code in {200, 204}
    except requests.RequestException:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate .env configuration")
    parser.add_argument(
        "--check-network",
        action="store_true",
        help="Send HEAD requests to public base URLs",
        default=True,  # Default to True for better coverage, can be disabled if needed
    )
    parser.add_argument(
        "--check-oss",
        action="store_true",
        help="Validate Aliyun OSS credentials with a signed request",
        default=True,  # Default to True for better coverage, can be disabled if needed
    )
    args = parser.parse_args()

    config = load_config()
    public_asset_store = build_public_asset_store(config)
    providers = build_provider_registry(config, public_asset_store)

    results: list[CheckResult] = []

    results.append(_check_path_exists("APP_DATA_DIR", config.app_data_dir))
    results.append(_check_path_exists("METADATA_DB", config.database_path))
    results.append(_check_quality(config.default_image_quality))

    if config.default_tryon_provider not in providers:
        results.append(
            CheckResult(
                "DEFAULT_TRYON_PROVIDER",
                False,
                f"Unknown provider: {config.default_tryon_provider}",
            )
        )
    else:
        msg = providers[config.default_tryon_provider].validate_environment() or "Ready"
        results.append(CheckResult("DEFAULT_TRYON_PROVIDER", msg == "Ready", msg))

    if config.default_video_provider not in providers:
        results.append(
            CheckResult(
                "DEFAULT_VIDEO_PROVIDER",
                False,
                f"Unknown provider: {config.default_video_provider}",
            )
        )
    else:
        msg = providers[config.default_video_provider].validate_environment() or "Ready"
        results.append(CheckResult("DEFAULT_VIDEO_PROVIDER", msg == "Ready", msg))

    # OSS checks
    results.append(CheckResult("ALIYUN_OSS_ACCESS_KEY_ID", bool(config.aliyun_oss_access_key_id), _redact(config.aliyun_oss_access_key_id)))
    results.append(CheckResult("ALIYUN_OSS_ACCESS_KEY_SECRET", bool(config.aliyun_oss_access_key_secret), _redact(config.aliyun_oss_access_key_secret)))
    results.append(CheckResult("ALIYUN_OSS_ENDPOINT", bool(config.aliyun_oss_endpoint), _redact(config.aliyun_oss_endpoint)))
    results.append(CheckResult("ALIYUN_OSS_BUCKET", bool(config.aliyun_oss_bucket), _redact(config.aliyun_oss_bucket)))
    results.extend(
        _check_public_base_url(
            config.aliyun_oss_bucket,
            config.aliyun_oss_endpoint,
            config.aliyun_oss_public_base_url,
            "ALIYUN_OSS_PUBLIC_BASE_URL",
        )
    )

    # COS checks
    results.append(CheckResult("TENCENT_COS_SECRET_ID", bool(config.tencent_cos_secret_id), _redact(config.tencent_cos_secret_id)))
    results.append(CheckResult("TENCENT_COS_SECRET_KEY", bool(config.tencent_cos_secret_key), _redact(config.tencent_cos_secret_key)))
    results.append(CheckResult("TENCENT_COS_REGION", bool(config.tencent_cos_region), _redact(config.tencent_cos_region)))
    results.append(CheckResult("TENCENT_COS_BUCKET", bool(config.tencent_cos_bucket), _redact(config.tencent_cos_bucket)))
    if config.tencent_cos_public_base_url:
        parsed = urlparse(config.tencent_cos_public_base_url)
        ok = parsed.scheme in {"http", "https"} and bool(parsed.netloc)
        results.append(
            CheckResult(
                "TENCENT_COS_PUBLIC_BASE_URL",
                ok,
                config.tencent_cos_public_base_url if ok else "Invalid URL",
            )
        )
    else:
        results.append(CheckResult("TENCENT_COS_PUBLIC_BASE_URL", False, "Missing"))

    # API key checks (presence only)
    results.append(CheckResult("DASHSCOPE_API_KEY", bool(config.dashscope_api_key), _redact(config.dashscope_api_key)))
    results.append(CheckResult("ARK_API_KEY", bool(config.ark_api_key), _redact(config.ark_api_key)))
    results.append(CheckResult("BAIDU_QIANFAN_API_KEY", bool(config.baidu_qianfan_api_key), _redact(config.baidu_qianfan_api_key)))
    results.append(CheckResult("BAIDU_QIANFAN_SECRET_KEY", bool(config.baidu_qianfan_secret_key), _redact(config.baidu_qianfan_secret_key)))
    results.append(CheckResult("MINIMAX_API_KEY", bool(config.minimax_api_key), _redact(config.minimax_api_key)))

    # Optional config sanity checks
    if config.enable_public_url_upload:
        if not (config.aliyun_oss_public_base_url or config.tencent_cos_public_base_url):
            results.append(
                CheckResult(
                    "ENABLE_PUBLIC_URL_UPLOAD",
                    False,
                    "Enabled but no public base URL configured",
                )
            )
        else:
            results.append(CheckResult("ENABLE_PUBLIC_URL_UPLOAD", True, "Enabled"))
    else:
        results.append(CheckResult("ENABLE_PUBLIC_URL_UPLOAD", True, "Disabled"))

    # Display results
    print("\nValidation results:")
    width = max(len(item.name) for item in results) if results else 20
    for item in results:
        status = "OK" if item.ok else "WARN"
        print(f"- {item.name.ljust(width)}  [{status}]  {item.message}")

    if args.check_network:
        urls = [
            config.aliyun_oss_public_base_url,
            config.tencent_cos_public_base_url,
        ]
        print("\nNetwork checks:")
        for item in _check_network(urls):
            status = "OK" if item.ok else "WARN"
            print(f"- {item.name}  [{status}]  {item.message}")

    if args.check_oss:
        print("\nOSS auth check:")
        acl_result = _check_oss_acl(
            config.aliyun_oss_access_key_id,
            config.aliyun_oss_access_key_secret,
            config.aliyun_oss_bucket,
            config.aliyun_oss_endpoint,
            config.aliyun_oss_public_base_url,
        )
        status = "OK" if acl_result.ok else "WARN"
        print(f"- {acl_result.name}  [{status}]  {acl_result.message}")

        if acl_result.ok:
            print("\nOSS upload test:")
            for item in _check_oss_upload(
                config.aliyun_oss_access_key_id,
                config.aliyun_oss_access_key_secret,
                config.aliyun_oss_bucket,
                config.aliyun_oss_endpoint,
                config.aliyun_oss_public_base_url,
            ):
                status = "OK" if item.ok else "WARN"
                print(f"- {item.name}  [{status}]  {item.message}")


if __name__ == "__main__":
    main()
