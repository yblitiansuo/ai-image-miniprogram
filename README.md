# AI 商品图生成小程序

电商商家上传一张随手拍的商品照片，30 秒内生成 5 张不同场景的高质量商品展示图，替代传统拍摄。

---

## 解决了什么问题

小商家拍一套 5 张商品图，需要约摄影师、布景、修图，花费 ¥50-200，耗时 2-4 小时。50+ SKU 的店铺上架经常因此推迟好几天。

这个小程序把流程变成：**拍照上传 → 30 秒出图**。

---

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | 微信小程序 |
| 后端 API | FastAPI + Gunicorn + Uvicorn |
| 异步任务 | Celery + Redis |
| 数据库 | MySQL 8.0 |
| AI 引擎 | 火山引擎 Seedream 5.0 |
| 对象存储 | 腾讯云 COS |
| 部署 | Docker Compose + Nginx |

---

## AI Agent 多模型协作架构

这是本项目的核心——不是简单调一个 API，而是一个多 Agent 协同推理流水线：

```
商品照片上传
    ↓
分割模型 → 抠出商品主体
    ↓
推理 Agent → 分析类目、材质、风格 → 链式推理最优场景参数
    ↓
生成 Agent → Seedream 5.0 生成 5 张不同场景背景
    ↓
质检 Agent → 评估真实感、光影、边缘 → 不合格自动重生成
    ↓
返回成品图（约 30 秒）
```

| Agent | 职责 | 关键决策点 |
|-------|------|-----------|
| 分割 | 商品主体提取 | 边缘精度 vs 速度 |
| 推理 | 识别类目，动态推理场景参数 | "陶瓷杯"和"真丝连衣裙"需要完全不同的场景逻辑，不能用固定模板 |
| 生成 | 多场景背景生成 | 参数组合优化 |
| 质检 | 真实感/光影/边缘评分 | 低于阈值触发自动重生成，避免低质量输出 |

---

## 目录结构

```
├── miniprogram/          # 微信小程序前端（5 个页面）
├── cloud-backend/        # FastAPI 后端 + Celery 任务队列
├── deploy/               # Nginx 配置
├── docker-compose.yml               # 本地开发环境
└── docker-compose.server.yml        # 生产部署
```

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/login` | 微信登录 |
| POST | `/api/upload` | 上传图片 |
| POST | `/api/generate` | 创建生成任务 |
| GET | `/api/task/{id}` | 查询任务状态 |
| GET | `/health` | 健康检查（DB/Redis/COS） |

---

## 本地运行

### 环境变量

复制 `cloud-backend/.env.example` 为 `.env`，填入真实密钥。COS 配置为空时自动启用 Mock 降级模式。

### 启动

```bash
# 一键启动（Windows）
start_all.bat

# 或手动
docker compose -f cloud-backend/docker-compose.yml up -d   # MySQL + Redis
cd cloud-backend
pip install -r requirements.txt
python main.py                                              # FastAPI :9999
celery -A tasks worker --loglevel=info --pool=solo          # Celery Worker
celery -A tasks beat --loglevel=info                        # Celery Beat
```

微信开发者工具打开 `miniprogram/`，设置不校验合法域名即可本地预览。

---

## 部署

详见 `DEPLOY_SERVER.md`（自建服务器）和 `DEPLOY_CLOUDHOST.md`（微信云托管）。

---

## 项目状态

API 全流程（登录 → 上传 → AI 生成 → 结果存储）已通过验证，等待 ICP 备案完成后正式上线。

详细开发进度见 `PROJECT_STATUS.md`。
