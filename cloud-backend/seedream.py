"""
火山引擎 Seedream API 调用（正确格式参考网页版）
"""

import os
import time
import logging
import requests
from typing import Optional

from config import config

logger = logging.getLogger(__name__)

# 默认提示词
DEFAULT_PROMPT = """\
请将第一张图片中的商品主体，与后续图片的风格进行深度融合。
商品主体的形状、细节、纹理必须完全保留，不可改变。
仅改变其背景、光影、色调、氛围，使其风格与后续图片一致。
生成一张高质量电商主图，专业灯光，精美构图，适合电商平台展示。"""

# 检查 config 对象
if not hasattr(config, 'ARK_API_KEY'):
    raise RuntimeError("config 对象缺少 ARK_API_KEY 属性，请检查 .env 配置")

def sanitize_text(text: str) -> str:
    """清理文本，移除可能破坏 JSON/Markdown 的特殊字符"""
    if not text:
        return ""
    import re
    text = text.strip()
    text = re.sub(r'[\x00-\x1F\x7F-\x9F\r\n]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text[:500]


def call_seedream_merge(
    product_path: str,
    ref_paths: list[str],
    prompt: str,
    custom_text: str = '',
    api_key: Optional[str] = None
) -> str:
    """
    调用火山引擎 Seedream 5.0 进行图片融合生成（正确格式）

    Args:
        product_path: 商品图本地路径
        ref_paths: 参考图本地路径列表
        prompt: 提示词（已融合全局模板）
        custom_text: 自定义文案（可选）
        api_key: 可选的 API Key，若不传则使用配置文件

    Returns:
        结果图片的临时 URL（可直接下载）
    """
    if api_key is None:
        api_key = getattr(config, 'ARK_API_KEY', None) or os.getenv('ARK_API_KEY')
    if not api_key:
        raise ValueError("ARK_API_KEY 未配置，请在 .env 中设置")

    base_url = getattr(config, 'ARK_API_URL', 'https://ark.cn-beijing.volces.com/api/v3/images/generations')
    model = getattr(config, 'SEEDREAM_MODEL', 'doubao-seedream-5-0-260128')
    size = getattr(config, 'SEEDREAM_SIZE', '2K')

    # 读取图片并转为 base64
    import base64
    with open(product_path, 'rb') as f:
        product_b64 = base64.b64encode(f.read()).decode('utf-8')
    image_urls = [f"data:image/jpeg;base64,{product_b64}"]
    for ref in ref_paths:
        with open(ref, 'rb') as f:
            ref_b64 = base64.b64encode(f.read()).decode('utf-8')
        image_urls.append(f"data:image/jpeg;base64,{ref_b64}")

    # 构建 prompt（参考网页版的 prompt 组合方式）
    base_template = (
        "请将第一张图片中的商品主体，与后续图片的风格进行深度融合。"
        "商品主体的形状、细节、纹理必须完全保留，不可改变。"
        "仅改变其背景、光影、色调、氛围，使其风格与后续图片一致。"
    )
    if custom_text:
        text_part = f"请在图片中添加以下文案：'{custom_text}'，字体美观，位置合理。"
    else:
        # 不添加任何文案提示，让 AI 自由发挥
        text_part = ""

    if prompt:
        final_prompt = f"{prompt}\n{text_part}"
    else:
        final_prompt = f"{base_template}\n{text_part}\n最终生成一张高质量、专业的电商主图。"

    final_prompt = sanitize_text(final_prompt)

    payload = {
        "model": model,
        "prompt": final_prompt,
        "image": image_urls,
        "response_format": "url",
        "size": size
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = requests.post(base_url, json=payload, headers=headers, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                if 'data' not in data or not isinstance(data['data'], list) or len(data['data']) == 0:
                    raise ValueError(f"API 返回格式异常: {data}")
                img_url = data['data'][0].get('url')
                if not img_url:
                    raise ValueError(f"API 未返回图片 URL: {data}")
                logger.info(f"Seedream call succeeded (attempt {attempt+1})")
                return img_url
            elif resp.status_code == 429:
                retry_after = int(resp.headers.get('Retry-After', 2 ** attempt))
                logger.warning(f"Seedream API rate limited (429), waiting {retry_after}s")
                time.sleep(retry_after)
                continue
            else:
                logger.warning(f"Seedream API error {resp.status_code}: {resp.text}")
                resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if attempt < max_retries - 1:
                logger.warning(f"Seedream retry {attempt+1} after error: {e}")
                time.sleep(2 ** attempt)
            else:
                logger.error(f"Seedream failed after {max_retries} attempts")
                raise
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Seedream retry {attempt+1} after error: {e}")
                time.sleep(2 ** attempt)
            else:
                logger.error(f"Seedream failed after {max_retries} attempts")
                raise

    raise RuntimeError("Seedream request failed after retries")
