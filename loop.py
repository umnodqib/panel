import os
import subprocess
import sys
import time
import json
import pyautogui

BASE_PATH = os.getcwd()
PROFILE_DIR = os.path.join(BASE_PATH, "chrome_profiles")
TASK_PAYLOAD_FILE = os.path.join(BASE_PATH, "task_payload.json")
CHROME_PATH = "/usr/bin/google-chrome"
PROFILE_NAME = "profile_01"

os.makedirs(PROFILE_DIR, exist_ok=True)

def read_task():
    if not os.path.exists(TASK_PAYLOAD_FILE):
        return None
    try:
        with open(TASK_PAYLOAD_FILE) as f:
            return json.load(f)
    except:
        return None

PROFILE_PATH = os.path.join(PROFILE_DIR, PROFILE_NAME)

while True:
    task = read_task()
    
    if not task:
        print(f"⏳ No task, waiting 10s...", flush=True)
        time.sleep(10)
        continue
    
    EMAIL = task.get('email')
    PASSWORD = task.get('password')
    URLs = task.get('urls', [])
    
    if not EMAIL or not PASSWORD or not URLs:
        print(f"⚠️ Invalid task, waiting...", flush=True)
        time.sleep(10)
        continue
    
    print(f"🚀 [LOOP] Starting with profile...", flush=True)
    
    cmd = [
        CHROME_PATH,
        "--no-sandbox",
        "--disable-dev-shm-usage",
        f"--user-data-dir={PROFILE_PATH}",
    ] + URLs  # ← Buka semua URLs langsung
    
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print(f"✅ Chrome started with {len(URLs)} URLs", flush=True)
    print(f"⏳ Running for 10 minutes...", flush=True)
    
    time.sleep(600)  # Run 10 menit
    
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except:
        proc.kill()
    
    print(f"✅ Cycle complete, restart in 30s...", flush=True)
    time.sleep(30)
