import subprocess
import time
import os

BACKEND_PORT = 9999

# 停止占用指定端口的进程
print(f"停止占用端口 {BACKEND_PORT} 的进程...")
result = subprocess.run(
    ['netstat', '-ano', '-p', 'tcp'],
    capture_output=True, text=True, encoding='gbk'
)
killed_pids = set()
for line in result.stdout.split('\n'):
    if f':{BACKEND_PORT}' in line and 'LISTENING' in line:
        parts = line.split()
        pid = parts[-1]
        if pid.isdigit() and pid not in killed_pids:
            print(f"停止进程 {pid}")
            subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
            killed_pids.add(pid)

time.sleep(2)

# 启动新的后端服务
print("启动新的后端服务...")
os.chdir(r'D:\code\projects\ai_image_miniprogram\cloud-backend')
subprocess.Popen(['python', 'main.py'], creationflags=subprocess.CREATE_NEW_CONSOLE)

print("后端服务已重启")
