@echo off
chcp 65001 >nul
title Celery Worker - AI Image Generator

echo ============================================
echo   启动 Celery Worker
echo ============================================
echo.
echo 节点名称：worker@%COMPUTERNAME%
echo.

celery -A tasks worker --loglevel=info --concurrency=1 --pool=solo -n worker@%COMPUTERNAME%

echo.
echo ============================================
echo   Worker 已停止
echo ============================================
pause
