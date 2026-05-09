from __future__ import annotations

from src.config import AppConfig
from src.providers.base import GenerationProvider
from src.providers.aliyun_aitryon_provider import AliyunAitryonProvider
from src.providers.dummy_provider import DummyProvider
from src.providers.placeholder_provider import PlaceholderProvider


def build_provider_registry(config: AppConfig, public_asset_store) -> dict[str, GenerationProvider]:
    registry: dict[str, GenerationProvider] = {
        "dummy": DummyProvider(public_asset_store),
        "aliyun_aitryon": AliyunAitryonProvider(config, public_asset_store),
        "aliyun_aitryon_plus": PlaceholderProvider(
            name="aliyun_aitryon_plus",
            required_env={"DASHSCOPE_API_KEY": config.dashscope_api_key},
            supports_tryon=True,
            supports_video=False,
            requires_public_url=True,
            public_asset_store=public_asset_store,
        ),
        "tencent_changeclothes": PlaceholderProvider(
            name="tencent_changeclothes",
            required_env={
                "TENCENT_SECRET_ID": config.tencent_secret_id,
                "TENCENT_SECRET_KEY": config.tencent_secret_key,
            },
            supports_tryon=True,
            supports_video=False,
            requires_public_url=True,
            public_asset_store=public_asset_store,
        ),
        "kling_virtual_tryon": PlaceholderProvider(
            name="kling_virtual_tryon",
            required_env={
                "KLING_ACCESS_KEY": config.kling_access_key,
                "KLING_SECRET_KEY": config.kling_secret_key,
            },
            supports_tryon=True,
            supports_video=False,
            requires_public_url=True,
            public_asset_store=public_asset_store,
        ),
        "dummy_video": PlaceholderProvider(
            name="dummy_video",
            required_env={},
            supports_tryon=False,
            supports_video=True,
            requires_public_url=False,
            public_asset_store=public_asset_store,
        ),
        "aliyun_wan2_7_i2v": PlaceholderProvider(
            name="aliyun_wan2_7_i2v",
            required_env={"DASHSCOPE_API_KEY": config.dashscope_api_key},
            supports_tryon=False,
            supports_video=True,
            requires_public_url=True,
            public_asset_store=public_asset_store,
        ),
        "volcengine_seedance": PlaceholderProvider(
            name="volcengine_seedance",
            required_env={"ARK_API_KEY": config.ark_api_key},
            supports_tryon=False,
            supports_video=True,
            requires_public_url=True,
            public_asset_store=public_asset_store,
        ),
        "baidu_qianfan_video": PlaceholderProvider(
            name="baidu_qianfan_video",
            required_env={
                "BAIDU_QIANFAN_API_KEY": config.baidu_qianfan_api_key,
                "BAIDU_QIANFAN_SECRET_KEY": config.baidu_qianfan_secret_key,
            },
            supports_tryon=False,
            supports_video=True,
            requires_public_url=True,
            public_asset_store=public_asset_store,
        ),
        "tencent_hunyuan_video": PlaceholderProvider(
            name="tencent_hunyuan_video",
            required_env={
                "TENCENT_SECRET_ID": config.tencent_secret_id,
                "TENCENT_SECRET_KEY": config.tencent_secret_key,
            },
            supports_tryon=False,
            supports_video=True,
            requires_public_url=True,
            public_asset_store=public_asset_store,
        ),
        "minimax_hailuo_video": PlaceholderProvider(
            name="minimax_hailuo_video",
            required_env={"MINIMAX_API_KEY": config.minimax_api_key},
            supports_tryon=False,
            supports_video=True,
            requires_public_url=True,
            public_asset_store=public_asset_store,
        ),
    }

    return registry
