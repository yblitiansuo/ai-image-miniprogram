@echo off
cd /d "D:\code\ai_image_miniprogram\cloud-backend"
celery -A tasks flower --port=5555
