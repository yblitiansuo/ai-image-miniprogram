"""
Celery 任务定义

包含：
- generate_task: 图片生成主任务
- cleanup_old_results: 定期清理过期结果
"""

from __future__ import annotations

import os
import uuid
import datetime
import logging
import requests
import tempfile
from typing import List, Tuple
# 内存队列不需要 redis
# from urllib.parse import urlparse  # 暂时保留，后续清理

import time
import celery
from celery import Celery
from celery.schedules import crontab
from sqlalchemy.orm import Session
from config import config
from db import SessionLocal, Task, User, TaskStatus, get_cloud_storage, extract_cloud_path
from seedream import call_seedream_merge, DEFAULT_PROMPT
from datetime import datetime as dt

logger = logging.getLogger(__name__)

# 初始化 Celery - 支持 Redis 和内存队列
# 注意：启动时使用 -n 参数指定唯一节点名称
# 如果设置了 REDIS_URL，使用 Redis；否则使用内存队列

if config.REDIS_URL:
    # 使用 Redis
    celery_app = Celery(
        'tasks',
        broker=config.REDIS_URL,
        backend=config.REDIS_URL,
    )
else:
    # 使用内存队列
    celery_broker = config.CELERY_BROKER if config.CELERY_BROKER else 'memory://'
    celery_backend = config.CELERY_BACKEND if config.CELERY_BACKEND else 'cache+memory://'
    celery_app = Celery(
        'tasks',
        broker=celery_broker,
        backend=celery_backend,
    )

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 分钟超时
    worker_max_tasks_per_child=100,
    worker_prefetch_multiplier=1,  # 一次取一个任务，避免占用过多
    worker_send_task_events=True,  # 发送任务事件
    result_expires=7 * 24 * 3600,  # 结果保留 7 天
    # 内存队列不需要重试配置
    # task_acks_late=True,
)

def _ensure_local_file(file_id: str, cloud_storage) -> str:
    """确保 file_id 对应的图片在本地有文件，返回本地路径"""
    # 处理 mock 格式：mock_xxx 或 mock://xxx
    if file_id.startswith('mock_') or file_id.startswith('mock://'):
        if file_id.startswith('mock://'):
            cloud_path = file_id[7:]
        else:
            cloud_path = file_id[5:]
        # 直接调用 cloud_storage.download_to_temp，它会走 Mock 逻辑
        return cloud_storage.download_to_temp(cloud_path)
    # 其他格式（cos://, cloud://）提取路径
    cloud_path = extract_cloud_path(file_id)
    return cloud_storage.download_to_temp(cloud_path)

def cleanup_temp_files(files: List[Tuple[str, str]]):
    """清理临时文件"""
    for path, _ in files:
        try:
            os.remove(path)
        except Exception:
            pass


class _FileLock:
    """跨平台文件锁（替换 fcntl，兼容 Windows）"""
    def __init__(self, path):
        self.path = path
        self.fd = None

    def acquire(self, nonblocking=False):
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL)
            return True
        except FileExistsError:
            if nonblocking:
                return False
            time.sleep(0.1)
            return self.acquire(nonblocking=False)

    def release(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        try:
            os.remove(self.path)
        except OSError:
            pass


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def generate_task(self, task_id: str):
    """
    Celery 任务：处理图片生成
    """
    db: Session = SessionLocal()
    try:
        # 1. 查询任务（加锁避免并发修改）
        task = db.query(Task).filter(Task.id == task_id).with_for_update().first()
        if not task:
            logger.error(f"Task {task_id} not found")
            return

        # 2. 检查任务状态：只处理 pending 状态，避免重复执行或僵尸任务
        if task.status != TaskStatus.pending:
            logger.warning(f"Task {task_id} status is {task.status}, skipping (already processed or in progress)")
            return

        # 3. 更新状态为处理中
        task.status = TaskStatus.processing
        db.commit()

        # 3. 提取参数
        params = task.params
        product_file_ids = params['product_images']  # list of cloud fileIDs
        ref_file_ids = params['reference_images']
        mapping = params['mapping']  # {product_idx: {refs: [...], text: "..."}}
        global_prompt = params.get('prompt', '').strip() or DEFAULT_PROMPT

        # 获取 API Key（从环境或 config 对象）
        api_key = os.getenv('ARK_API_KEY') or getattr(config, 'ARK_API_KEY', None)
        if not api_key:
            raise ValueError("ARK_API_KEY not configured")

        # 4. 下载所有图片到本地临时文件
        cloud_storage = get_cloud_storage()
        product_paths = []  # [(local_path, fileID)]
        ref_paths = []

        # 下载商品图（支持 mock file_id）
        for i, file_id in enumerate(product_file_ids):
            local_path = _ensure_local_file(file_id, cloud_storage)
            product_paths.append((local_path, file_id))

        # 下载参考图（支持 mock file_id）
        for i, file_id in enumerate(ref_file_ids):
            local_path = _ensure_local_file(file_id, cloud_storage)
            ref_paths.append((local_path, file_id))

        # 5. 对每个商品图调用 Seedream
        result_urls = []
        for product_idx, config in mapping.items():
            product_idx = int(product_idx)
            if product_idx >= len(product_paths):
                continue

            product_path, _ = product_paths[product_idx]
            ref_indices = config.get('refs', [])
            custom_text = config.get('text', '')

            selected_refs = []
            for ref_idx in ref_indices:
                if ref_idx < len(ref_paths):
                    selected_refs.append(ref_paths[ref_idx][0])

            if not selected_refs:
                raise Exception(f"商品图 {product_idx} 未选择有效参考图")

            result_url = call_seedream_merge(
                product_path=product_path,
                ref_paths=[p for p in selected_refs],
                prompt=global_prompt,
                custom_text=custom_text,
                api_key=api_key
            )
            result_urls.append(result_url)

        # 6. 将 Seedream 返回的临时 URL 下载并上传到云存储（COS）持久化
        cloud_storage = get_cloud_storage()
        final_file_ids = []
        for img_url in result_urls:
            try:
                # 下载临时图片
                resp = requests.get(img_url, timeout=60)
                resp.raise_for_status()
                img_data = resp.content
                # 上传到云存储
                cloud_path = cloud_storage.generate_cloud_path('results', f"{uuid.uuid4().hex}.jpg")
                file_id = cloud_storage.upload_bytes(img_data, cloud_path)
                final_file_ids.append(file_id)
                logger.info(f"Persisted result to cloud storage: {file_id}")
            except Exception as e:
                logger.error(f"Failed to persist result from {img_url}: {e}")
                # 回退：如果云存储不可用，仍使用临时 URL（生产环境建议抛出异常）
                final_file_ids.append(img_url)

        # 7. 更新任务完成 + 减少 running_tasks (原子操作，加锁避免竞态)
        task.status = TaskStatus.completed
        task.result_urls = final_file_ids
        task.finished_at = dt.now(dt.UTC)
        # 原子减少 running_tasks
        user = db.query(User).filter(User.id == task.user_id).with_for_update().first()
        if user and user.running_tasks > 0:
            user.running_tasks -= 1
        db.commit()
        logger.info(f"Task {task_id} completed successfully, running_tasks decreased to {user.running_tasks if user else 'N/A'}")

    except Exception as e:
        db.rollback()
        logger.exception(f"Task {task_id} failed (attempt {self.request.retries + 1}): {e}")

        # 还有重试次数，让 Celery 自动重试
        if self.request.retries < self.max_retries:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.error = f"重试中 ({self.request.retries + 1}/{self.max_retries}): {e}"
                db.commit()
            raise self.retry(exc=e)

        # 重试耗尽，标记为失败
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.error = str(e)
            task.status = TaskStatus.failed
            task.finished_at = dt.now(dt.UTC)
            # 原子减少 running_tasks
            user = db.query(User).filter(User.id == task.user_id).with_for_update().first()
            if user and user.running_tasks > 0:
                user.running_tasks -= 1
            db.commit()
            logger.info(f"Task {task_id} failed after {self.max_retries} retries, running_tasks decreased to {user.running_tasks if user else 'N/A'}")
    finally:
        db.close()
        cleanup_temp_files(locals().get('product_paths', []) + locals().get('ref_paths', []))

@celery_app.task(bind=True, name='tasks.cleanup_old_results')
def cleanup_old_results(self):
    """每天清理超过 7 天的任务结果文件（云存储）"""
    lock_file = os.path.join(tempfile.gettempdir(), 'cleanup_old_results.lock')
    lock = _FileLock(lock_file)
    if not lock.acquire(nonblocking=True):
        logger.info('Cleanup task skipped: another instance is running')
        return

    try:
        db: Session = SessionLocal()
        cloud_storage = get_cloud_storage()
        try:
            cutoff = dt.now(dt.UTC) - dt.timedelta(days=config.RESULT_RETENTION_DAYS)
            old_tasks = db.query(Task).filter(
                Task.finished_at < cutoff,
                Task.status == TaskStatus.completed,
                Task.result_urls.isnot(None)
            ).all()
            for task in old_tasks:
                for file_id in task.result_urls:
                    try:
                        cloud_path = extract_cloud_path(file_id)
                        cloud_storage.delete_file(cloud_path)
                    except Exception as e:
                        logger.warning(f"Failed to delete cloud file {file_id}: {e}")
                task.result_urls = None
            db.commit()
            logger.info(f"Cleaned up results for {len(old_tasks)} old tasks")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
    finally:
        lock.release()

@celery_app.task(bind=True, name='tasks.cleanup_stale_tasks')
def cleanup_stale_tasks(self):
    """
    清理僵尸任务：
    - 状态为 processing 但超过 1 小时未完成的任务（视为 worker 崩溃）
    - 将状态设为 failed，并减少用户 running_tasks 计数
    """
    lock_file = os.path.join(tempfile.gettempdir(), 'cleanup_stale_tasks.lock')
    lock = _FileLock(lock_file)
    if not lock.acquire(nonblocking=True):
        logger.info('Stale tasks cleanup skipped: another instance is running')
        return

    try:
        db: Session = SessionLocal()
        try:
            cutoff = dt.now(dt.UTC) - dt.timedelta(hours=1)
            stale_tasks = db.query(Task).filter(
                Task.status == TaskStatus.processing,
                Task.created_at < cutoff
            ).all()
            for task in stale_tasks:
                user = db.query(User).filter(User.id == task.user_id).with_for_update().first()
                if user and user.running_tasks > 0:
                    user.running_tasks -= 1
                task.status = TaskStatus.failed
                task.error = "任务执行超时，自动取消"
                task.finished_at = dt.now(dt.UTC)
                logger.info(f"Cleaned stale task {task.id}, corrected running_tasks for user {user.id if user else 'unknown'}")
            db.commit()
            logger.info(f"Cleaned up {len(stale_tasks)} stale tasks")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Stale tasks cleanup failed: {e}")
    finally:
        lock.release()


# Beat 定时任务
celery_app.conf.beat_schedule = {
    'cleanup-old-results-daily': {
        'task': 'tasks.cleanup_old_results',
        'schedule': crontab(hour=2, minute=0),
    },
    'cleanup-stale-tasks-hourly': {
        'task': 'tasks.cleanup_stale_tasks',
        'schedule': crontab(minute=0),  # 每小时整点执行
    },
}
