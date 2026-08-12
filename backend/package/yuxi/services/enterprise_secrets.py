"""企业数据源密码的写入式密钥处理。"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


def _fernet() -> Fernet:
    """使用 Coda 已有 JWT/实例密钥派生数据源加密密钥。"""
    secret = os.getenv("JWT_SECRET_KEY") or os.getenv("YUXI_INSTANCE_ID")
    if not secret:
        raise ValueError("缺少 JWT_SECRET_KEY 或 YUXI_INSTANCE_ID，无法保存数据源密码")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    """加密密码并返回可持久化密文。"""
    if not value:
        raise ValueError("数据源密码不能为空")
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    """解密数据源密码，密钥变化或密文损坏时显式失败。"""
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("数据源密码无法解密，请检查部署密钥是否保持一致") from exc


def resolve_data_source_password(source) -> str:
    """按环境变量引用优先、数据库密文其次的顺序读取密码。"""
    if source.password_env:
        value = os.getenv(source.password_env)
        if not value:
            raise ValueError(f"数据源密码环境变量未配置: {source.password_env}")
        return value
    if source.password_ciphertext:
        return decrypt_secret(source.password_ciphertext)
    raise ValueError("数据源未配置密码或密码环境变量")
