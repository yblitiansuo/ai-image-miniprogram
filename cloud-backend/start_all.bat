@echo off
chcp 65001 >nul
title AI Image Generator - 启动所有服务

echo ============================================
echo   AI Image Generator - 启动所有服务
echo ============================================
echo.

cd /d D:\code\projects\ai_image_miniprogram\cloud-backend

echo [1/3] 启动后端服务 (端口 9999)...
start "Backend" cmd /k "python main.py"

echo.
echo [2/3] 启动 Celery Worker...
start "Celery Worker" cmd /k "celery -A tasks worker --loglevel=info --concurrency=1 --pool=solo -n worker@%%COMPUTERNAME%%"

echo.
echo [3/3] 启动 Celery Beat...
start "Celery Beat" cmd /k "celery -A tasks beat --loglevel=info"

echo.
echo ============================================
echo   所有服务已启动！
echo ============================================
echo.
echo 后端服务：http://127.0.0.1:9999
echo Celery Worker: 查看 "Celery Worker" 窗口
echo Celery Beat: 查看 "Celery Beat" 窗口
echo.
echo 按任意键退出...
pause >nul
