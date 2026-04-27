import os
import time
import subprocess
import sys
import pyautogui
import mss
import json

# ==========================================
# CONFIG
# ==========================================
BASE_PATH = os.getcwd()
PROFILE_DIR = os.path.join(BASE_PATH, "chrome_profiles")
TASK_PAYLOAD_FILE = os.path.join(BASE_PATH, "task_payload.json")
CHROME_PATH = "/usr/bin/google-chrome"

# Buat profile dir jika belum ada
os.makedirs(PROFILE_DIR, exist_ok=True)

def read_task_payload():
    """Baca task dari agent.py"""
    if not os.path.exists(TASK_PAYLOAD_FILE):
        print(f"❌ Task file not found", flush=True)
        return None
    try:
        with open(TASK_PAYLOAD_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error reading task: {e}", flush=True)
        return None

# ==========================================
# MAIN
# ==========================================
task = read_task_payload()

if not task:
    print("❌ No task payload", flush=True)
    sys.exit(1)

EMAIL = task.get('email')
PASSWORD = task.get('password')
URLs = task.get('urls', [])

if not EMAIL or not PASSWORD or not URLs:
    print("❌ Invalid task", flush=True)
    sys.exit(1)

print(f"📧 Email: {EMAIL}", flush=True)
print(f"🔗 URLs: {len(URLs)}", flush=True)

# ==========================================
# SETUP CHROME PROFILE
# ==========================================

PROFILE_NAME = "profile_01"
PROFILE_PATH = os.path.join(PROFILE_DIR, PROFILE_NAME)

print(f"📁 Profile path: {PROFILE_PATH}", flush=True)

# Jika profile belum ada, create folder
if not os.path.exists(PROFILE_PATH):
    os.makedirs(PROFILE_PATH, exist_ok=True)
    print(f"✅ Created new profile", flush=True)
else:
    print(f"✅ Using existing profile", flush=True)

# ==========================================
# JALANKAN CHROME
# ==========================================

cmd = [
    CHROME_PATH,
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--start-maximized",
    "--disable-session-crashed-bubble",
    "--no-first-run",
    "--no-default-browser-check",
    f"--user-data-dir={PROFILE_PATH}",  # ← PROFILE PERSISTENT
    "https://accounts.google.com/login"
]

print(f"🚀 Starting Chrome...", flush=True)
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Wait untuk Chrome fully load
time.sleep(10)

try:
    print(f"⌨️ Typing email...", flush=True)
    pyautogui.write(EMAIL, interval=0.05)
    pyautogui.press("enter")
    time.sleep(5)
    
    print(f"⌨️ Typing password...", flush=True)
    pyautogui.write(PASSWORD, interval=0.05)
    pyautogui.press("enter")
    time.sleep(10)
    
    print(f"✅ Login completed", flush=True)
    
    # ==========================================
    # BUKA URLs DALAM TABS
    # ==========================================
    print(f"🔗 Opening {len(URLs)} URLs...", flush=True)
    
    for i, url in enumerate(URLs):
        if i == 0:
            # First URL - navigate
            pyautogui.hotkey('ctrl', 'l')
            time.sleep(0.5)
            pyautogui.write(url, interval=0.02)
            pyautogui.press("enter")
        else:
            # Open new tab
            pyautogui.hotkey('ctrl', 't')
            time.sleep(1)
            pyautogui.write(url, interval=0.02)
            pyautogui.press("enter")
        
        time.sleep(2)
    
    print(f"✅ All URLs opened", flush=True)
    
    # ==========================================
    # SCREENSHOT
    # ==========================================
    ss_path = os.path.join(BASE_PATH, f"screenshot_{PROFILE_NAME}.png")
    try:
        with mss.mss() as sct:
            sct.shot(mon=-1, output=ss_path)
        print(f"📸 Screenshot saved: {ss_path}", flush=True)
    except Exception as e:
        print(f"⚠️ Screenshot error: {e}", flush=True)
    
    # ==========================================
    # HOLD WINDOW OPEN
    # ==========================================
    print(f"⏳ Holding Chrome open for 5 minutes...", flush=True)
    time.sleep(300)
    
except Exception as e:
    print(f"❌ Error: {e}", flush=True)

finally:
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except:
        proc.kill()
    
    print(f"✅ Chrome closed", flush=True)
