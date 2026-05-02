import os
import subprocess

os.chdir(r'D:\code\projects\ai_image_miniprogram\cloud-backend')
subprocess.Popen(['python', 'main.py'], creationflags=subprocess.CREATE_NEW_CONSOLE)
print("后端服务启动中...")
