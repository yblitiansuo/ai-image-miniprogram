# 重启后端服务
Write-Host "停止旧的后端服务..."
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*main.py*" } | Stop-Process -Force

Start-Sleep -Seconds 2

Write-Host "启动后端服务..."
cd "D:\code\projects\ai_image_miniprogram\cloud-backend"
python main.py
