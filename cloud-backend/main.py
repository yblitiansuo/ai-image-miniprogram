# cloud-backend/main.py
import os
import uuid
import json
import logging
from datetime import datetime, UTC
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Header, File, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
# from sqlalchemy import ...  # 已移至 models.py
import requests
from dotenv import load_dotenv

load_dotenv()

from config import config, validate_required
from cloud_storage import get_cloud_storage
from seedream import call_seedream_merge
from auth import create_jwt_token, verify_jwt_token, get_wechat_openid, init_user_if_not_exists, is_wechat_login_ready, register_user, login_with_password
from models import User
from payments import get_packages, create_order, complete_order

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.now(UTC).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

# 配置根日志
# 根据环境变量设置日志级别
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level, logging.INFO)

handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.basicConfig(level=log_level, handlers=[handler])
logger = logging.getLogger(__name__)

# 启动校验
validate_required()

cors_allow_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "http://127.0.0.1:9999,http://localhost:9999").split(",")
    if origin.strip()
]

# 注意：从 db 模块导入，避免循环导入
from db import engine, SessionLocal, Task, TaskStatus
from models import User, init_db

# 初始化数据库（先创建数据库，再创建表）
init_db()

app = FastAPI(title="AI Image Generator API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(status_code=400, content={"detail": "请求参数错误", "error": str(exc)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "服务器内部错误",
            "error": str(exc) if hasattr(app, 'debug') and app.debug else None
        }
    )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_token(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> User:
    if authorization and authorization.startswith("Bearer "):
        token_value = authorization[7:]
        # 优先尝试 JWT
        user_id = verify_jwt_token(token_value)
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                return user
        # 回退到直接 user_id（兼容旧版）
        user_id = token_value
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(401, "用户不存在")
        return user
    raise HTTPException(401, "未提供认证信息")

class GenerateRequest(BaseModel):
    product_images: List[str]
    reference_images: List[str]
    mapping: dict
    prompt: Optional[str] = ""

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), user: User = Depends(verify_token)):
    """
    上传图片到云存储（COS）
    前端用 wx.uploadFile 发送
    """
    file_bytes = await file.read()
    cloud_storage = get_cloud_storage()
    cloud_path = cloud_storage.generate_cloud_path('uploads', f"{uuid.uuid4().hex}.jpg")
    file_id = cloud_storage.upload_bytes(file_bytes, cloud_path)
    return {"file_id": file_id}

@app.get("/health")
async def health():
    # 检查数据库（直接连接引擎）
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.error(f"DB health check failed: {e}", exc_info=True)

    # 检查 Redis (Celery)
    redis_ok = False
    try:
        from tasks import celery_app
        with celery_app.connection() as conn:
            redis_ok = conn.ensure_connection(max_retries=0)
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")

    # 检查云存储 (COS)
    cos_ok = False
    try:
        cs = get_cloud_storage()
        cos_ok = True
    except Exception as e:
        logger.error(f"Cloud storage health check failed: {e}")

    all_ok = db_ok and redis_ok and cos_ok
    return {
        "status": "ok" if all_ok else "degraded",
        "checks": {
            "database": "ok" if db_ok else "error",
            "redis": "ok" if redis_ok else "error",
            "cloud_storage": "ok" if cos_ok else "error"
        }
    }

# ============== 认证接口 ==============

class LoginRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    code: Optional[str] = None

@app.post("/auth/register")
async def register(req: LoginRequest, db: Session = Depends(get_db)):
    """用户注册"""
    if not req.username or not req.password:
        raise HTTPException(400, "用户名和密码不能为空")
    return register_user(req.username, req.password, db)

@app.post("/auth/login")
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    """
    登录（支持密码和微信）
    请求：{ "username": "xxx", "password": "xxx" } 或 { "code": "wx_login_code" }
    返回：{ "token": "jwt_token", "user_id": "xxx", "quota": 3 }
    """
    # 密码登录
    if req.username and req.password:
        return login_with_password(req.username, req.password, db)
    
    # 微信登录
    code = req.code
    if not code:
        raise HTTPException(400, "缺少 code 或用户名密码")

    if os.getenv('DEV_MODE', '').lower() != 'true' and not is_wechat_login_ready():
        raise HTTPException(500, "服务端未配置 WECHAT_APPID / WECHAT_SECRET")

    openid = get_wechat_openid(code)
    if not openid:
        raise HTTPException(400, "微信登录失败：code 无效或微信配置错误")

    # 初始化用户（如果不存在）
    user = init_user_if_not_exists(openid)

    # 生成 JWT
    token = create_jwt_token(user.id)

    return {
        "token": token,
        "user_id": user.id,
        "quota": user.quota,
        "total_generated": user.total_generated
    }

@app.get("/user/info")
async def user_info(user: User = Depends(verify_token)):
    """获取用户信息（配额等）"""
    return {
        "user_id": user.id,
        "quota": user.quota,
        "running_tasks": user.running_tasks,
        "total_generated": user.total_generated,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }


@app.post("/api/generate")
async def generate(req: GenerateRequest, user: User = Depends(verify_token), db: Session = Depends(get_db)):
    # 配额检查
    if user.quota <= 0:
        raise HTTPException(402, "配额不足，请购买套餐")

    if user.running_tasks >= 3:
        raise HTTPException(429, "并发任务数已达上限（最多 3 个）")

    # 减少配额并增加已生成数量
    user.quota -= 1
    user.running_tasks += 1
    user.total_generated += 1
    db.commit()

    task = Task(
        id=str(uuid.uuid4()),
        user_id=user.id,
        status=TaskStatus.pending,
        params=req.model_dump()
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 提交到 Celery 异步队列
    try:
        from tasks import generate_task
        generate_task.delay(task.id)
    except Exception as e:
        # 如果 Celery 不可用，抛出错误（建议启动 worker）
        raise HTTPException(500, f'异步任务提交失败：{e}')

    logger.info(f"User {user.id} created task {task.id}, running_tasks increased to {user.running_tasks}")
    return {"task_id": task.id, "status": "queued"}

@app.get("/api/task/{task_id}")
async def get_task(task_id: str, user: User = Depends(verify_token), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(404, "任务不存在")

    result_urls = task.result_urls or []
    if task.status == TaskStatus.completed and result_urls:
        cloud_storage = get_cloud_storage()
        public_urls = []
        for file_id in result_urls:
            try:
                url = cloud_storage.get_presigned_url(file_id, expires=3600)
                public_urls.append(url)
            except Exception as e:
                logger.warning(f"Failed to get presigned URL for {file_id}: {e}")
                public_urls.append(file_id)
        result_urls = public_urls

    return {
        "id": task.id,
        "status": task.status.value,
        "result_urls": result_urls,
        "error": task.error,
        "created_at": task.created_at.isoformat(),
        "finished_at": task.finished_at.isoformat() if task.finished_at else None
    }

@app.get("/api/tasks")
async def list_tasks(page: int = 1, limit: int = 20, user: User = Depends(verify_token), db: Session = Depends(get_db)):
    offset = (page - 1) * limit
    tasks = db.query(Task).filter(Task.user_id == user.id).order_by(Task.created_at.desc()).offset(offset).limit(limit).all()

    cloud_storage = get_cloud_storage()
    result = []
    for t in tasks:
        urls = t.result_urls or []
        if t.status == TaskStatus.completed and urls:
            public_urls = []
            for file_id in urls:
                try:
                    url = cloud_storage.get_presigned_url(file_id, expires=3600)
                    public_urls.append(url)
                except Exception as e:
                    logger.warning(f"Failed to get presigned URL for {file_id}: {e}")
                    public_urls.append(file_id)
            urls = public_urls
        result.append({
            "id": t.id,
            "status": t.status.value,
            "result_urls": urls,
            "error": t.error,
            "created_at": t.created_at.isoformat()
        })
    return {"tasks": result}

@app.delete("/api/task/{task_id}")
async def delete_task(task_id: str, user: User = Depends(verify_token), db: Session = Depends(get_db)):
    try:
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
        if not task:
            logger.warning(f"Delete task {task_id} not found for user {user.id}")
            raise HTTPException(404, "任务不存在")
        logger.info(f"Deleting task {task_id}, status={task.status}, user.running_tasks before={user.running_tasks}")
        # 尝试从 Celery 撤销任务
        try:
            from tasks import celery_app
            async_result = celery_app.AsyncResult(task_id)
            if async_result.state in ['pending', 'processing']:
                async_result.revoke(terminate=True, signal='SIGTERM')
        except Exception as e:
            logger.warning(f"Failed to revoke task {task_id}: {e}")
        # 如果任务在运行中或待处理，减少用户 running_tasks 计数
        if task.status in [TaskStatus.pending, TaskStatus.processing]:
            if user.running_tasks > 0:
                user.running_tasks -= 1
                logger.info(f"Decreased running_tasks to {user.running_tasks}")
        db.delete(task)
        db.commit()
        logger.info("Task deleted successfully")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in delete_task: {e}")
        raise HTTPException(500, f"服务器内部错误：{type(e).__name__}: {e}")

# ============== 支付路由 ==============
@app.get("/pay/packages")
async def list_packages(user: User = Depends(verify_token)):
    """获取可购买套餐列表"""
    return {"packages": get_packages()}

@app.post("/pay/create")
async def create_payment(data: dict, user: User = Depends(verify_token), db: Session = Depends(get_db)):
    """创建订单"""
    package_id = data.get("package_id")
    if not package_id:
        raise HTTPException(400, "缺少 package_id")
    order = create_order(user.id, package_id)
    return {
        "order_id": order.id,
        "package_name": order.package_name,
        "price": order.price,
        "quota_added": order.quota_added,
        "status": order.status.value,
        "message": "订单已创建，请调用 /pay/complete 完成支付（生产环境需调微信支付）"
    }

@app.post("/pay/complete")
async def complete_payment(data: dict, user: User = Depends(verify_token), db: Session = Depends(get_db)):
    """模拟支付完成（生产环境由微信回调此接口）"""
    order_id = data.get("order_id")
    if not order_id:
        raise HTTPException(400, "缺少 order_id")
    order = complete_order(order_id)
    if not order:
        raise HTTPException(400, "订单不存在或已处理")
    return {"ok": True, "quota_added": order.quota_added, "message": "支付完成，配额已增加"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("BACKEND_PORT", 9999))
    # 生产环境（Docker）使用 gunicorn + uvicorn workers，支持多进程
    # 本地开发用 uvicorn 单进程（Windows 兼容）
    logger.info(f"Starting dev server on 0.0.0.0:{port} (uvicorn single-process)")
    logger.info("For production, use: gunicorn main:app --bind 0.0.0.0:PORT --workers 4 --worker-class uvicorn.workers.UvicornWorker")
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
