# 微信云托管改造与上线清单

## 适用场景

- 希望减少服务器运维成本
- 保留当前 FastAPI + Celery + MySQL + Redis 架构
- 使用微信云托管运行 web/worker/beat 三个服务

## 需要改什么

### 1. 镜像与服务编排

- 使用 `cloud-backend/cloud.yaml` 作为云托管编排文件
- 将 `image` 替换为你推送到 CCR 的真实镜像地址
- 确认 `web` 服务端口与应用监听一致（当前统一为 9999）

### 2. 环境变量

云托管控制台中至少需要配置以下变量：

- MYSQL_HOST
- MYSQL_PORT
- MYSQL_DB
- MYSQL_USER
- MYSQL_PASSWORD
- REDIS_URL
- ARK_API_KEY
- ARK_API_URL
- SEEDREAM_MODEL
- SEEDREAM_SIZE
- COS_REGION
- COS_BUCKET
- COS_SECRET_ID
- COS_SECRET_KEY
- JWT_SECRET
- WECHAT_APPID
- WECHAT_SECRET
- DEV_MODE=false
- BACKEND_PORT=9999
- CORS_ALLOW_ORIGINS=https://你的云托管域名

### 3. 小程序前端

- 将 `miniprogram/utils/api.js` 的发布环境地址改为真实 HTTPS 域名
- 微信公众平台配置合法域名：
  - request
  - uploadFile
  - downloadFile

### 4. 安全与配置

- `DEV_MODE` 设为 `false`
- CORS 白名单仅保留生产域名
- 不在代码仓库提交 `.env`、证书和密钥

## 需要做什么（执行步骤）

### 1. 构建并推送镜像

在项目根目录执行：

1. 进入 `cloud-backend`
2. 构建镜像
3. 登录 CCR
4. 打标签并推送镜像

### 2. 创建云托管服务

在腾讯云云托管中按 `cloud.yaml` 创建三类服务：

- web（FastAPI）
- worker（Celery worker）
- beat（Celery beat）

并填写上面的环境变量。

### 3. 绑定访问域名

- 在云托管配置自定义域名并开启 HTTPS
- 拿到最终访问域名后，更新小程序发布域名

### 4. 业务联调验收

按顺序验证：

1. `/health` 返回可用
2. 登录成功
3. 图片上传成功
4. 创建任务成功
5. 状态轮询可到 completed
6. 结果图可预览和保存

## 与自建服务器方案的主要区别

- 不需要自建 Nginx 反代与证书部署
- 不需要维护系统级 Docker 自启与安全组端口策略
- 仍需维护业务侧 MySQL/Redis/COS/ARK 参数与可用性
- 成本结构从固定资源转向按托管资源计费