import subprocess
import time
import os

# 停止旧的后端服务
print("停止旧的后端服务...")
result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe'], capture_output=True, text=True, encoding='gbk')
for line in result.stdout.split('\n'):
    if 'python.exe' in line and 'PID' not in line:
        parts = line.split()
        if len(parts) >= 2:
            pid = parts[1]
            print(f"停止进程 {pid}")
            subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)

time.sleep(2)

# 启动新的后端服务
print("启动新的后端服务...")
os.chdir(r'D:\code\projects\ai_image_miniprogram\cloud-backend')
subprocess.Popen(['python', 'main.py'], creationflags=subprocess.CREATE_NEW_CONSOLE)

print("后端服务已重启")
