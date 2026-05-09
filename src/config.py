from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    app_data_dir: Path
    database_path: Path
    default_tryon_provider: str
    default_video_provider: str
    default_image_quality: str
    enable_public_url_upload: bool
    public_asset_ttl_seconds: int
    dashscope_api_key: str
    aliyun_region: str
    aliyun_tryon_model: str
    aliyun_tryon_preview_model: str
    aliyun_tryon_refiner_model: str
    aliyun_tryon_parsing_model: str
    aliyun_wan_video_model: str
    aliyun_oss_access_key_id: str
    aliyun_oss_access_key_secret: str
    aliyun_oss_endpoint: str
    aliyun_oss_bucket: str
    aliyun_oss_public_base_url: str
    tencent_secret_id: str
    tencent_secret_key: str
    tencent_region: str
    tencent_cos_secret_id: str
    tencent_cos_secret_key: str
    tencent_cos_region: str
    tencent_cos_bucket: str
    tencent_cos_public_base_url: str
    kling_access_key: str
    kling_secret_key: str
    kling_api_base: str
    ark_api_key: str
    volcengine_region: str
    volcengine_seedance_model: str
    volcengine_seedream_model: str
    baidu_qianfan_api_key: str
    baidu_qianfan_secret_key: str
    minimax_api_key: str
    minimax_group_id: str


def load_config() -> AppConfig:
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env", override=False)

    app_data_dir = Path(os.getenv("APP_DATA_DIR", "./data"))
    if not app_data_dir.is_absolute():
        app_data_dir = (project_root / app_data_dir).resolve()

    database_path = app_data_dir / "metadata.sqlite"

    return AppConfig(
        project_root=project_root,
        app_data_dir=app_data_dir,
        database_path=database_path,
        default_tryon_provider=os.getenv("DEFAULT_TRYON_PROVIDER", "dummy"),
        default_video_provider=os.getenv("DEFAULT_VIDEO_PROVIDER", "dummy_video"),
        default_image_quality=os.getenv("DEFAULT_IMAGE_QUALITY", "preview"),
        enable_public_url_upload=_get_bool("ENABLE_PUBLIC_URL_UPLOAD", False),
        public_asset_ttl_seconds=_get_int("PUBLIC_ASSET_TTL_SECONDS", 86400),
        dashscope_api_key=os.getenv("DASHSCOPE_API_KEY", ""),
        aliyun_region=os.getenv("ALIYUN_REGION", "cn-beijing"),
        aliyun_tryon_model=os.getenv("ALIYUN_TRYON_MODEL", "aitryon-plus"),
        aliyun_tryon_preview_model=os.getenv("ALIYUN_TRYON_PREVIEW_MODEL", "aitryon"),
        aliyun_tryon_refiner_model=os.getenv("ALIYUN_TRYON_REFINER_MODEL", "aitryon-refiner"),
        aliyun_tryon_parsing_model=os.getenv("ALIYUN_TRYON_PARSING_MODEL", "aitryon-parsing-v1"),
        aliyun_wan_video_model=os.getenv("ALIYUN_WAN_VIDEO_MODEL", "wan2.7-i2v"),
        aliyun_oss_access_key_id=os.getenv("ALIYUN_OSS_ACCESS_KEY_ID", ""),
        aliyun_oss_access_key_secret=os.getenv("ALIYUN_OSS_ACCESS_KEY_SECRET", ""),
        aliyun_oss_endpoint=os.getenv("ALIYUN_OSS_ENDPOINT", ""),
        aliyun_oss_bucket=os.getenv("ALIYUN_OSS_BUCKET", ""),
        aliyun_oss_public_base_url=os.getenv("ALIYUN_OSS_PUBLIC_BASE_URL", ""),
        tencent_secret_id=os.getenv("TENCENT_SECRET_ID", ""),
        tencent_secret_key=os.getenv("TENCENT_SECRET_KEY", ""),
        tencent_region=os.getenv("TENCENT_REGION", "ap-guangzhou"),
        tencent_cos_secret_id=os.getenv("TENCENT_COS_SECRET_ID", ""),
        tencent_cos_secret_key=os.getenv("TENCENT_COS_SECRET_KEY", ""),
        tencent_cos_region=os.getenv("TENCENT_COS_REGION", "ap-guangzhou"),
        tencent_cos_bucket=os.getenv("TENCENT_COS_BUCKET", ""),
        tencent_cos_public_base_url=os.getenv("TENCENT_COS_PUBLIC_BASE_URL", ""),
        kling_access_key=os.getenv("KLING_ACCESS_KEY", ""),
        kling_secret_key=os.getenv("KLING_SECRET_KEY", ""),
        kling_api_base=os.getenv("KLING_API_BASE", "https://api.klingai.com"),
        ark_api_key=os.getenv("ARK_API_KEY", ""),
        volcengine_region=os.getenv("VOLCENGINE_REGION", "cn-beijing"),
        volcengine_seedance_model=os.getenv("VOLCENGINE_SEEDANCE_MODEL", ""),
        volcengine_seedream_model=os.getenv("VOLCENGINE_SEEDREAM_MODEL", ""),
        baidu_qianfan_api_key=os.getenv("BAIDU_QIANFAN_API_KEY", ""),
        baidu_qianfan_secret_key=os.getenv("BAIDU_QIANFAN_SECRET_KEY", ""),
        minimax_api_key=os.getenv("MINIMAX_API_KEY", ""),
        minimax_group_id=os.getenv("MINIMAX_GROUP_ID", ""),
    )
