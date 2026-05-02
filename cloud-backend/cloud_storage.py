"""
腾讯云 COS 客户端（HMAC-SHA1 签名 - 参考官方 SDK 实现）
"""
import os
import time
import hashlib
import hmac
import tempfile
import logging
from urllib.parse import quote, urlparse

import requests

from config import config

logger = logging.getLogger(__name__)


class CloudStorageFallback(Exception):
    """触发降级的内部异常"""
    pass


def _format_key(key: str) -> str:
    """将 header key 转为小写"""
    return key.strip().lower()


def _url_encode(value: str) -> str:
    """COS 签名要求的 URL 编码"""
    return quote(value, safe='').replace('%7E', '~')


class CloudStorage:
    """腾讯云 COS 客户端（支持云托管内置 COS 临时密钥 + 传统 COS）"""

    def __init__(self):
        secret_id = config.COS_SECRET_ID or os.getenv("TENCENT_CLOUD_SECRET_ID")
        secret_key = config.COS_SECRET_KEY or os.getenv("TENCENT_CLOUD_SECRET_KEY")
        region = config.COS_REGION
        bucket = config.COS_BUCKET

        logger.info(
            f"CloudStorage init: SECRET_ID={'OK' if secret_id else 'MISSING'}, "
            f"SECRET_KEY={'OK' if secret_key else 'MISSING'}, BUCKET={bucket or 'MISSING'}, REGION={region or 'MISSING'}"
        )

        self.region = region or "ap-guangzhou"
        self.bucket = bucket or ""
        
        # 云托管内置 COS：不传 secret，用临时密钥方式
        if not secret_id or not secret_key:
            logger.info("Using cloud托管内置 COS (临时密钥模式)")
            self.secret_id = None
            self.secret_key = None
            self.endpoint = None  # 临时密钥模式下不设置 endpoint
        else:
            # 传统 COS 方式
            self.secret_id = secret_id
            self.secret_key = secret_key
            self.endpoint = f"{bucket}.cos.{region}.myqcloud.com"

    def _sign(self, method: str, path: str, headers: dict, params: dict = None) -> str:
        """
        COS HMAC-SHA1 签名（官方格式）
        参考: https://cloud.tencent.com/document/product/436/7778
        """
        method = method.lower()

        # 签名有效期 3600 秒
        now = int(time.time())
        key_time = f"{now};{now + 3600}"

        # ========== 1. 生成 SignKey ==========
        sign_key = hmac.new(
            self.secret_key.encode('utf-8'),
            key_time.encode('utf-8'),
            hashlib.sha1
        ).hexdigest()

        # ========== 2. 生成 UrlParamList 和 HttpParameters ==========
        if params:
            param_list = []
            for k in sorted(params.keys()):
                param_list.append(f"{_url_encode(k).lower()}={_url_encode(params[k])}")
            http_params = "&".join(param_list)
            url_param_list = ";".join(sorted(_url_encode(k).lower() for k in params.keys()))
        else:
            http_params = ""
            url_param_list = ""

        # ========== 3. 生成 HeaderList 和 HttpHeaders ==========
        header_keys = sorted(_format_key(k) for k in headers.keys())
        header_list = []
        header_pairs = []
        for k in header_keys:
            # 用原始大小写 key 从 headers 取值
            orig_key = next(orig for orig in headers.keys() if _format_key(orig) == k)
            v = headers[orig_key]
            header_list.append(k)
            header_pairs.append(f"{k}={_url_encode(v)}")

        header_list_str = ";".join(header_list)
        http_headers = "&".join(header_pairs)

        # ========== 4. 生成 HttpString ==========
        http_string = f"{method}\n{path}\n{http_params}\n{http_headers}\n"

        # ========== 5. 生成 StringToSign ==========
        http_string_hash = hashlib.sha1(http_string.encode('utf-8')).hexdigest()
        string_to_sign = f"sha1\n{key_time}\n{http_string_hash}\n"

        # ========== 6. 生成 Signature ==========
        signature = hmac.new(
            sign_key.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha1
        ).hexdigest()

        # ========== 7. 拼接 Authorization ==========
        authorization = (
            f"q-sign-algorithm=sha1"
            f"&q-ak={self.secret_id}"
            f"&q-sign-time={key_time}"
            f"&q-key-time={key_time}"
            f"&q-header-list={header_list_str}"
            f"&q-url-param-list={url_param_list}"
            f"&q-signature={signature}"
        )

        logger.debug(f"COS sign: http_string={repr(http_string)}")
        logger.debug(f"COS sign: string_to_sign={repr(string_to_sign)}")
        logger.debug(f"COS auth head: {authorization[:80]}...")

        return authorization

    def _request(self, method: str, cloud_path: str, data: bytes = None, timeout: int = 60):
        """统一请求方法"""
        # COS URL 路径：必须包含 / 前缀
        url_path = "/" + cloud_path if not cloud_path.startswith("/") else cloud_path

        headers = {'Host': self.endpoint}

        if method.upper() == 'PUT' and data is not None:
            headers['Content-Type'] = 'image/jpeg'
            # 计算 Content-MD5
            import base64
            content_md5 = base64.b64encode(hashlib.md5(data).digest()).decode()
            headers['Content-MD5'] = content_md5
            headers['Content-Length'] = str(len(data))

        # 生成签名
        authorization = self._sign(method.upper(), url_path, headers)
        headers['Authorization'] = authorization

        url = f"https://{self.endpoint}{url_path}"

        logger.info(f"COS {method.upper()} {url}")

        try:
            resp = requests.request(method, url, headers=headers, data=data, timeout=timeout)
            if resp.status_code < 400:
                return resp

            logger.error(f"COS {method.upper()} {url} failed: {resp.status_code} {resp.text[:500]}")

            # 403 = 签名错误或权限不足
            if resp.status_code in (403, 401):
                raise CloudStorageFallback(f"COS auth failed ({resp.status_code}): {resp.text[:300]}")
            resp.raise_for_status()
        except CloudStorageFallback:
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"COS request exception: {e}")
            raise CloudStorageFallback(f"COS request failed: {e}")

    def download_to_temp(self, cloud_path: str) -> str:
        if not cloud_path:
            raise ValueError("cloud_path cannot be empty")

        ext = os.path.splitext(cloud_path)[1] or ".jpg"
        fd, temp_path = tempfile.mkstemp(suffix=ext, prefix="aiimg_")
        os.close(fd)

        try:
            resp = self._request('GET', cloud_path, timeout=60)
            with open(temp_path, 'wb') as f:
                f.write(resp.content)
            logger.info(f"COS download OK: {cloud_path} -> {temp_path}")
            return temp_path
        except CloudStorageFallback as e:
            logger.warning(f"COS download failed, falling back to mock: {e}")
            return MockCloudStorage().download_to_temp(cloud_path)

    def upload_bytes(self, data: bytes, cloud_path: str, content_type: str = "image/jpeg") -> str:
        if not data or not cloud_path:
            raise ValueError("data and cloud_path required")

        try:
            self._request('PUT', cloud_path, data=data, timeout=60)
            return f"cos://{cloud_path}"
        except CloudStorageFallback as e:
            logger.warning(f"COS upload failed, falling back to mock: {e}")
            return MockCloudStorage().upload_bytes(data, cloud_path, content_type)

    def delete_file(self, cloud_path: str):
        try:
            self._request('DELETE', cloud_path, timeout=10)
            logger.info(f"COS delete OK: {cloud_path}")
        except CloudStorageFallback as e:
            logger.warning(f"COS delete failed, falling back to mock: {e}")
            MockCloudStorage().delete_file(cloud_path)
        except Exception as e:
            logger.warning(f"Failed to delete {cloud_path}: {e}")

    def generate_cloud_path(self, prefix: str, filename: str) -> str:
        return os.path.join(prefix, filename).replace('\\', '/')

    def get_presigned_url(self, file_id: str, expires: int = 3600) -> str:
        if not file_id:
            raise ValueError("file_id cannot be empty")
        if file_id.startswith('http') or file_id.startswith('data:'):
            return file_id

        cloud_path = extract_cloud_path(file_id)
        if not cloud_path:
            raise ValueError(f"Invalid file_id: {file_id}")

        # 生成带签名的下载 URL
        import time
        url_path = "/" + cloud_path
        now = int(time.time())
        key_time = f"{now};{now + expires}"

        headers = {'Host': self.endpoint}
        params = {}

        sign_key = hmac.new(
            self.secret_key.encode('utf-8'),
            key_time.encode('utf-8'),
            hashlib.sha1
        ).hexdigest()

        http_params = ""
        header_keys = sorted(_format_key(k) for k in headers.keys())
        header_list = []
        header_pairs = []
        for k in header_keys:
            # 用原始大小写 key 从 headers 取值
            orig_key = next(orig for orig in headers.keys() if _format_key(orig) == k)
            v = headers[orig_key]
            header_list.append(k)
            header_pairs.append(f"{k}={_url_encode(v)}")
        http_headers = "&".join(header_pairs)
        header_list_str = ";".join(header_list)

        http_string = f"get\n{url_path}\n{http_params}\n{http_headers}\n"
        http_string_hash = hashlib.sha1(http_string.encode('utf-8')).hexdigest()
        string_to_sign = f"sha1\n{key_time}\n{http_string_hash}\n"
        signature = hmac.new(
            sign_key.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha1
        ).hexdigest()

        return f"https://{self.endpoint}{url_path}?q-sign-algorithm=sha1&q-ak={self.secret_id}&q-sign-time={key_time}&q-key-time={key_time}&q-header-list={header_list_str}&q-url-param-list=&q-signature={signature}"


def extract_cloud_path(file_id: str) -> str:
    """从 file_id 提取云存储路径"""
    if file_id.startswith('cos://'):
        return file_id[6:]
    elif file_id.startswith('cloud://'):
        idx = file_id.find('/', 8)
        return file_id[idx+1:] if idx != -1 else file_id
    return file_id


def get_cloud_storage(force_rebuild=False):
    """返回 CloudStorage 实例，配置缺失时自动降级

    如果是 Mock 降级状态，每次调用都会尝试重建（避免配置恢复后一直用 Mock）
    """
    instance = getattr(get_cloud_storage, "_instance", None)

    # 从未创建过，或强制重建
    if instance is None or force_rebuild:
        try:
            instance = CloudStorage()
        except ValueError as e:
            logger.warning(f"CloudStorage config incomplete, falling back to mock: {e}")
            instance = MockCloudStorage()
        get_cloud_storage._instance = instance
        return instance

    # 如果当前是 Mock，尝试重建真实实例（轻量检查）
    if isinstance(instance, MockCloudStorage):
        mock_ref = instance  # 保留引用，避免重建失败时丢失
        try:
            real = CloudStorage()
            # 快速验证：发个 HEAD 请求确认 COS 可用
            try:
                real._request('HEAD', '/', timeout=5)
                get_cloud_storage._instance = real
                logger.info("CloudStorage recovered from mock to real COS")
                return real
            except Exception:
                pass  # 验证失败，继续用 Mock
        except Exception:
            pass

    return instance


class MockCloudStorage:
    """降级存储：文件保存在共享临时目录（跨进程/实例共享）"""

    _shared_temp_dir = None

    @classmethod
    def _get_shared_temp_dir(cls):
        if cls._shared_temp_dir is None:
            cls._shared_temp_dir = os.path.join(tempfile.gettempdir(), "aiimg_mock_shared")
            os.makedirs(cls._shared_temp_dir, exist_ok=True)
            logger.info(f"MockCloudStorage shared temp dir: {cls._shared_temp_dir}")
        return cls._shared_temp_dir

    def __init__(self):
        self.temp_dir = self._get_shared_temp_dir()

    def download_to_temp(self, cloud_path: str) -> str:
        if cloud_path.startswith('mock_'):
            fd, path = tempfile.mkstemp(suffix='.png', prefix='mock_')
            with os.fdopen(fd, 'wb') as f:
                f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\xf3\xff\xff\x00\x00\x00\x00\x00\x02\x00\x01\xe2!\x87\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
            return path
        local_path = os.path.join(self.temp_dir, cloud_path)
        if os.path.exists(local_path):
            return local_path
        raise FileNotFoundError(f"Mock file not found: {cloud_path}")

    def upload_bytes(self, data: bytes, cloud_path: str, content_type: str = "image/jpeg") -> str:
        local_path = os.path.join(self.temp_dir, cloud_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'wb') as f:
            f.write(data)
        return f"mock://{cloud_path}"

    def delete_file(self, cloud_path: str):
        try:
            os.remove(os.path.join(self.temp_dir, cloud_path))
        except Exception:
            pass

    def get_presigned_url(self, file_id: str, expires: int = 3600) -> str:
        if file_id.startswith('http') or file_id.startswith('data:'):
            return file_id
        if file_id.startswith('mock://'):
            cloud_path = file_id[7:]
            local_path = os.path.join(self.temp_dir, cloud_path)
            if os.path.exists(local_path):
                with open(local_path, 'rb') as f:
                    return f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
            return ""
        return f"https://mock.storage/{file_id}"

    def generate_cloud_path(self, prefix: str, filename: str) -> str:
        return os.path.join(prefix, filename).replace('\\', '/')
