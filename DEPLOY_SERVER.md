# 自建服务器部署指南（9999 端口方案）

## 快速执行清单

- 准备服务器、域名、证书
- 配置 `cloud-backend/.env` 真实参数
- 启动 `docker-compose.server.yml`（web + worker + beat）
- 配置 Nginx 反代到 `127.0.0.1:9999`
- 微信公众平台配置合法域名
- 按验收清单逐项验证

## 1. 前置条件

- Ubuntu 22.04+ 服务器（腾讯云轻量/CVM 都可）
- 已备案域名（中国大陆正式服务建议）
- 可用 HTTPS 证书
- 已准备好以下参数：
  - MySQL 连接信息
  - Redis 连接信息
  - ARK API Key
  - COS 配置
  - 小程序 AppID/AppSecret

## 2. 服务器初始化

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin nginx
sudo systemctl enable docker
sudo systemctl start docker
```

## 3. 上传项目

```bash
sudo mkdir -p /opt/ai_image_miniprogram
sudo chown -R $USER:$USER /opt/ai_image_miniprogram
cd /opt/ai_image_miniprogram
# git clone 或上传项目文件到当前目录
```

## 4. 配置环境变量

编辑 `cloud-backend/.env`：

- `DEV_MODE=false`
- `BACKEND_PORT=9999`
- `CORS_ALLOW_ORIGINS=https://api.your-domain.com`
- 其余 MySQL/Redis/COS/ARK/WECHAT/JWT 改为真实值

## 5. 启动容器

```bash
cd /opt/ai_image_miniprogram
docker compose -f docker-compose.server.yml up -d --build
docker compose -f docker-compose.server.yml ps
```

检查服务：

```bash
curl http://127.0.0.1:9999/health
```

## 6. 配置 Nginx（HTTPS + 反代）

1. 复制模板：

```bash
sudo cp deploy/nginx.ai-image.conf.example /etc/nginx/sites-available/ai-image.conf
```

2. 修改以下内容：
- `server_name` 改为真实域名
- `ssl_certificate` 和 `ssl_certificate_key` 改为真实证书路径

3. 启用站点并重载：

```bash
sudo ln -s /etc/nginx/sites-available/ai-image.conf /etc/nginx/sites-enabled/ai-image.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 7. 安全组建议

仅放行：
- `22`（建议限管理 IP）
- `80`
- `443`

不要放行：
- `9999`
- `3306`
- `6379`

## 8. 小程序侧配置

- 修改 `miniprogram/utils/api.js` 中生产域名为真实 `https://` 域名
- 在微信公众平台配置合法域名：
  - request
  - uploadFile
  - downloadFile

## 9. 验收清单

- `https://api.your-domain.com/health` 可用
- 登录成功
- 图片上传成功
- 创建任务成功
- 轮询状态到 completed
- 结果可预览和保存

## 10. 常用命令

```bash
# 查看日志
docker compose -f docker-compose.server.yml logs -f web

# 重启服务
docker compose -f docker-compose.server.yml restart web worker beat

# 停止服务
docker compose -f docker-compose.server.yml down
```
