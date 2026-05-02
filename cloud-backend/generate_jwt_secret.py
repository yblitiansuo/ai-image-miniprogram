#!/usr/bin/env python
"""
生成 JWT_SECRET 密钥

用法：
    python generate_jwt_secret.py

输出：
    生成一个 64 字符的随机密钥，可直接复制到 .env 文件中
"""

import secrets
import string

def generate_jwt_secret(length=64):
    """
    生成安全的 JWT_SECRET
    
    Args:
        length: 密钥长度，默认 64 字符
        
    Returns:
        随机生成的密钥字符串
    """
    # 使用 secrets 模块生成加密安全的随机字符串
    characters = secrets.choice(string.ascii_letters + string.digits + "!@#$%^&*")
    secret = ''.join(secrets.choice(string.ascii_letters + string.digits + "!@#$%^&*_") for _ in range(length))
    return secret

def main():
    """生成并打印 JWT_SECRET"""
    secret = generate_jwt_secret(64)
    
    print("=" * 60)
    print("JWT_SECRET 已生成")
    print("=" * 60)
    print()
    print("请复制以下内容到 .env 文件中：")
    print()
    print(f"JWT_SECRET={secret}")
    print()
    print("=" * 60)
    print()
    print("💡 提示：")
    print("1. 不要将生成的密钥提交到 Git")
    print("2. 定期更换密钥（建议每年一次）")
    print("3. 密钥长度建议至少 32 字符")
    print()

if __name__ == "__main__":
    main()
