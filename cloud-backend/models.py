import uuid
from sqlalchemy import create_engine, Column, String, Integer, JSON, DateTime, Float, Enum as SQLEnum, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import enum
from datetime import datetime, timezone


def utcnow():
    """Python 3.12 兼容：替代已废弃的 datetime.utcnow()"""
    return datetime.now(timezone.utc)
from urllib.parse import quote_plus

from config import config

# 数据库引擎配置
encoded_password = quote_plus(config.MYSQL_PASSWORD)

# 先连接到 MySQL 服务器（不指定数据库），用于建库
DATABASE_URL_NO_DB = f"mysql+pymysql://{config.MYSQL_USER}:{encoded_password}@{config.MYSQL_HOST}:{config.MYSQL_PORT}/"
engine_no_db = create_engine(
    DATABASE_URL_NO_DB,
    pool_recycle=3600,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

# 目标数据库的连接串（init_db 创建数据库后使用）
DATABASE_URL = f"mysql+pymysql://{config.MYSQL_USER}:{encoded_password}@{config.MYSQL_HOST}:{config.MYSQL_PORT}/{config.MYSQL_DB}"
engine = create_engine(
    DATABASE_URL,
    pool_recycle=3600,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class TaskStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"

class User(Base):
    __tablename__ = "users"
    id = Column(String(64), primary_key=True)
    username = Column(String(50), unique=True, index=True, nullable=True)  # 用户名（可选）
    password_hash = Column(String(255), nullable=True)  # 密码哈希（可选）
    running_tasks = Column(Integer, default=0)
    quota = Column(Integer, default=3)
    total_generated = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)

class Task(Base):
    __tablename__ = "tasks"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(64), nullable=False, index=True)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.pending, nullable=False)
    params = Column(JSON, nullable=False)
    result_urls = Column(JSON, nullable=True)
    error = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    finished_at = Column(DateTime, nullable=True)

class OrderStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    cancelled = "cancelled"
    refunded = "refunded"

class Order(Base):
    __tablename__ = "orders"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(64), nullable=False, index=True)
    package_id = Column(String(50), nullable=False)
    package_name = Column(String(100), nullable=False)
    quota_added = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.pending, nullable=False)
    wechat_transaction_id = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    paid_at = Column(DateTime, nullable=True)

def init_db():
    """初始化数据库和表"""
    try:
        # 使用 engine_no_db 连接（不指定数据库）来创建数据库
        with engine_no_db.connect() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{config.MYSQL_DB}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            conn.commit()
        # 创建表（用指向目标库的 engine）
        Base.metadata.create_all(bind=engine)
        print(f"Database '{config.MYSQL_DB}' initialized successfully")
    except Exception as e:
        print(f"Failed to initialize database: {e}")
        print("You may need to create the database manually in cloud console")
        raise
