import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# 立即加载 .env 文件（如果存在）
load_dotenv()


def _get_env(name: str, default: str = "") -> str:
    """获取环境变量并去除空白和 BOM"""
    value = os.getenv(name, default)
    if value is None:
        return default
    # 去除空白、换行、BOM
    return value.strip().lstrip('\ufeff')


@dataclass
class Config:
    # MySQL
    MYSQL_HOST: str = _get_env("MYSQL_HOST", "")  # 必须配置，不能有空值
    MYSQL_PORT: str = _get_env("MYSQL_PORT", "3306")
    MYSQL_DB: str = _get_env("MYSQL_DB", "ai_image")
    MYSQL_USER: str = _get_env("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = _get_env("MYSQL_PASSWORD", "")

    # Redis (Celery)
    REDIS_URL: str = _get_env("REDIS_URL", "")  # Redis 连接串

    # Celery - 默认使用 Redis，如果没有设置 REDIS_URL 则使用内存队列
    CELERY_BROKER: str = _get_env("CELERY_BROKER", "")  # 空表示由 REDIS_URL 决定
    CELERY_BACKEND: str = _get_env("CELERY_BACKEND", "")  # 空表示由 REDIS_URL 决定

    # 火山引擎
    ARK_API_KEY: str = _get_env("ARK_API_KEY", "")
    ARK_API_URL: str = _get_env("ARK_API_URL", "https://ark.cn-beijing.volces.com/api/v3/images/generations")
    SEEDREAM_MODEL: str = _get_env("SEEDREAM_MODEL", "doubao-seedream-5-0-260128")
    SEEDREAM_SIZE: str = _get_env("SEEDREAM_SIZE", "2K")

    # 云存储 (COS)
    COS_REGION: str = _get_env("COS_REGION", "ap-guangzhou")
    COS_BUCKET: str = _get_env("COS_BUCKET", "")
    COS_SECRET_ID: str = _get_env("COS_SECRET_ID") or _get_env("TENCENT_CLOUD_SECRET_ID", "")
    COS_SECRET_KEY: str = _get_env("COS_SECRET_KEY") or _get_env("TENCENT_CLOUD_SECRET_KEY", "")

    # 小程序
    WECHAT_APPID: str = _get_env("WECHAT_APPID", "")
    WECHAT_SECRET: str = _get_env("WECHAT_SECRET", "")
    WECHAT_JSCODE2SESSION_URL: str = "https://api.weixin.qq.com/sns/jscode2session"

    # JWT
    JWT_SECRET: str = _get_env("JWT_SECRET", "change-me-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 168  # 7 days

    # 任务超时与重试
    TASK_TIMEOUT_SECONDS: int = 30 * 60
    TASK_MAX_RETRIES: int = 2
    TASK_RETRY_DELAY: int = 60  # seconds

    # 清理策略
    RESULT_RETENTION_DAYS: int = 7

config = Config()


def validate_required():
    """启动时校验必需配置，缺失则抛出异常"""
    required = [
        ('MYSQL_HOST', config.MYSQL_HOST),
        ('MYSQL_PORT', config.MYSQL_PORT),
        ('MYSQL_DB', config.MYSQL_DB),
        ('MYSQL_USER', config.MYSQL_USER),
        ('MYSQL_PASSWORD', config.MYSQL_PASSWORD),
        ('ARK_API_KEY', config.ARK_API_KEY),
        ('COS_REGION', config.COS_REGION),
        ('COS_BUCKET', config.COS_BUCKET),
    ]
    # REDIS_URL 可选（内存队列模式）

    # 如果配置了 COS_BUCKET，则 COS 密钥也必须配置
    if config.COS_BUCKET:
        cos_creds = [
            ('COS_SECRET_ID', config.COS_SECRET_ID),
            ('COS_SECRET_KEY', config.COS_SECRET_KEY),
        ]
        required.extend(cos_creds)

    missing = [name for name, value in required if not value]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")

# 可选：启动即校验（在 main.py 顶部调用 validate_required）