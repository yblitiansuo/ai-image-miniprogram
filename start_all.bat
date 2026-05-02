@echo off
title AI Image MiniProgram - Start All Services
color 0A

echo ========================================
echo AI Image MiniProgram - Full Startup
echo ========================================
echo.

REM Change to project directory
cd /d "D:\code\projects\ai_image_miniprogram\cloud-backend"

REM Check .env
if not exist ".env" (
    echo [ERROR] .env file missing
    echo Please copy .env.example to .env and fill in values
    pause
    exit /b 1
)
echo [OK] .env file found
echo.

REM Start Docker (MySQL + Redis)
echo [1/4] Starting Docker containers (MySQL + Redis)...
docker compose up -d mysql redis
if errorlevel 1 (
    echo [ERROR] Docker failed. Make sure Docker Desktop is running
    pause
    exit /b 1
)
echo Waiting for DB to be ready...
timeout /t 5 /nobreak >nul
echo [OK] Database ready
echo.

REM Install dependencies
echo [2/4] Installing Python dependencies...
pip install -r requirements.txt --quiet
echo [OK] Dependencies installed
echo.

REM Start FastAPI
echo [3/4] Starting FastAPI backend...
echo URL: http://127.0.0.1:9999
echo Health: http://127.0.0.1:9999/health
echo.
start "FastAPI Backend" cmd /k "python main.py"

REM Start Celery Worker
echo [4/4] Starting Celery Worker & Beat...
start "Celery Worker" cmd /k "celery -A tasks worker --loglevel=info --concurrency=1 --pool=solo -n worker@%COMPUTERNAME%"
timeout /t 2 /nobreak >nul
start "Celery Beat" cmd /k "celery -A tasks beat --loglevel=info"

echo.
echo ========================================
echo All services started successfully!
echo ========================================
echo.
echo Backend: http://127.0.0.1:9999
echo Health: http://127.0.0.1:9999/health
echo.
echo Next steps:
echo 1. Open WeChat DevTools
echo 2. Import project: D:\code\projects\ai_image_miniprogram\miniprogram
echo 3. Set BASE_URL in miniprogram/utils/api.js to http://127.0.0.1:9999
echo.
pause
