import os
import subprocess
import psutil
import time
import requests
import threading
import re 
import sys
import socket
import json
import urllib3
import glob
import shutil
from urllib.parse import urlparse
from flask import Flask, request, jsonify

# Matikan Warning SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# ==========================================
# ⚙️ CONFIG
# ==========================================
PANEL_URL = [
    "https://dashboard.jujulefek.qzz.io"
]

AUTH_KEY = "GHOST_SECRET_2026"

FILE_LOGIN = "login.py"
FILE_LOOP = "loop.py"
LOG_FILE = "bot_log.txt"
MAPPING_FILE = "mapping_profil.txt"

# --- PATH CONFIG ---
BASE_DIR = os.getcwd()
PROFILE_DIR = os.path.join(BASE_DIR, "chrome_profiles")

# --- RESOLUSI LAYAR ---
SCREEN_LOGIN = "1280x720x24" 
SCREEN_LOOP = "500x500x24"   

# GLOBAL VARIABLE UNTUK MENYIMPAN SLOT ID
CURRENT_SLOT = None 

# ==========================================
# 📊 DASHBOARD MONITORING INTEGRATION
# ==========================================
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://dashboard.jujulefek.qzz.io")
DASHBOARD_AUTH_KEY = os.getenv("DASHBOARD_AUTH_KEY", "GHOST_SECRET_2026")

def register_to_dashboard():
    """Register panel ke dashboard monitoring saat startup"""
    global CURRENT_SLOT
    try:
        # Get IP panel
        try:
            my_ip = requests.get('https://api.ipify.org', timeout=10, verify=False).text.strip()
        except:
            my_ip = "127.0.0.1"
        
        # Get URL panel
        hf_host = os.environ.get("SPACE_HOST")
        if hf_host:
            bot_url = f"https://{hf_host}"
        else:
            bot_url = "http://localhost"
        
        payload = {
            "slot": CURRENT_SLOT if CURRENT_SLOT else 1,
            "ip": my_ip,
            "url": bot_url,
            "port": 7860
        }
        
        resp = requests.post(
            f"{DASHBOARD_URL}/api/register",
            json=payload,
            headers={"X-Auth-Key": DASHBOARD_AUTH_KEY},
            timeout=10,
            verify=False
        )
        
        if resp.status_code == 200:
            print(f"✅ [DASHBOARD] Registered successfully", flush=True)
        else:
            print(f"⚠️ [DASHBOARD] Registration failed: {resp.status_code}", flush=True)
    except Exception as e:
        print(f"⚠️ [DASHBOARD] Failed to register: {e}", flush=True)

def send_heartbeat_to_dashboard():
    """Send heartbeat ke dashboard setiap 30 detik"""
    global CURRENT_SLOT
    
    print("💓 [HEARTBEAT] Starting heartbeat thread...", flush=True)
    
    while True:
        try:
            # ✅ TUNGGU SAMPAI CURRENT_SLOT SET (max 5 menit)
            wait_count = 0
            while not CURRENT_SLOT and wait_count < 10:
                print(f"⏳ [HEARTBEAT] Waiting for CURRENT_SLOT... ({wait_count})", flush=True)
                time.sleep(3)
                wait_count += 1
            
            if not CURRENT_SLOT:
                print(f"❌ [HEARTBEAT] CURRENT_SLOT still not set after 30s. Skipping.", flush=True)
                time.sleep(30)
                continue
            
            # Count emails dan links
            emails_count = 0
            links_count = 0
            
            if os.path.exists('email.txt'):
                with open('email.txt', 'r') as f:
                    emails_count = len([line for line in f if line.strip()])
            
            if os.path.exists('link.txt'):
                with open('link.txt', 'r') as f:
                    links_count = len([line for line in f if line.strip()])
            
            # Determine current state
            state = "IDLE"
            if check_process(FILE_LOGIN):
                state = "BUSY_LOGIN"
            elif check_process(FILE_LOOP):
                state = "BUSY_LOOP"
            
            payload = {
                "slot": CURRENT_SLOT,
                "state": state,
                "data": {
                    "emails": emails_count,
                    "links": links_count
                }
            }
            
            print(f"💓 [HEARTBEAT] Sending: slot={CURRENT_SLOT}, state={state}", flush=True)
            
            requests.post(
                f"{DASHBOARD_URL}/api/heartbeat",
                json=payload,
                headers={"X-Auth-Key": DASHBOARD_AUTH_KEY},
                timeout=10,
                verify=False
            )
        except Exception as e:
            print(f"❌ [HEARTBEAT] Error: {e}", flush=True)
        
        time.sleep(30)

# === TAMBAHKAN SETELAH send_heartbeat_to_dashboard() ===

# ==========================================
# 🔄 POLL COMMANDS FROM DASHBOARD
# ==========================================
def poll_commands_from_dashboard():
    """Background thread yang pull commands dari dashboard setiap 5 detik"""
    global CURRENT_SLOT
    
    print("🔄 [POLL] Starting command polling thread...", flush=True)
    
    while True:
        try:
            if not CURRENT_SLOT:
                time.sleep(5)
                continue
            
            # Build full URL dengan environment variable
            dashboard_url = os.getenv("DASHBOARD_URL", "https://dashboard.jujulefek.qzz.io")
            url = f"{dashboard_url}/api/command/get/{CURRENT_SLOT}"
            
            response = requests.get(
                url,
                headers={"X-Auth-Key": DASHBOARD_AUTH_KEY},
                timeout=10,
                verify=False
            )
            
            if response.status_code == 200:
                commands = response.json()
                if isinstance(commands, list) and len(commands) > 0:
                    print(f"📨 [POLL] Received {len(commands)} commands", flush=True)
                    
                    # Execute each command
                    for cmd in commands:
                        if cmd.get('status') == 'PENDING':
                            execute_command(cmd)
            
            elif response.status_code == 404:
                # No commands - silent
                pass
            else:
                print(f"⚠️ [POLL] API Error: {response.status_code}", flush=True)
                
        except Exception as e:
            print(f"❌ [POLL] Error: {e}", flush=True)
        
        time.sleep(5)

# ========== agent.py (UPDATE) ==========
# Ganti line 189-219 execute_command dengan:

def execute_command(cmd):
    """Execute command received from dashboard"""
    global CURRENT_SLOT
    
    cmd_id = cmd.get('id', 'unknown')
    action = cmd.get('action')
    payload = cmd.get('payload', {})
    
    print(f"⚡ [EXEC] Executing: {action} (ID: {cmd_id[:8]}...)", flush=True)
    
    try:
        if action == "start_login":
            if check_process(FILE_LOGIN) or check_process(FILE_LOOP):
                print(f"⚠️ [EXEC] Process already running", flush=True)
                return
            
            # ✅ SAVE PAYLOAD (email, password, urls) KE FILE
            task_file = os.path.join(BASE_DIR, "task_payload.json")
            try:
                with open(task_file, 'w') as f:
                    json.dump({
                        'email': payload.get('email'),
                        'password': payload.get('password'),
                        'urls': payload.get('urls', [])
                    }, f)
                print(f"✅ [EXEC] Task payload saved: {task_file}", flush=True)
            except Exception as e:
                print(f"❌ [EXEC] Error saving payload: {e}", flush=True)
                return
            
            cmd_login = (
                f"xvfb-run -a --server-args='-screen 0 {SCREEN_LOGIN}' "
                f"{sys.executable} {FILE_LOGIN}"
            )
            threading.Thread(target=run_and_monitor, args=(cmd_login, "LOGIN"), daemon=True).start()
            print(f"✅ [EXEC] Login started with payload", flush=True)
            
            # Report status
            requests.post(
                f"{DASHBOARD_URL}/api/command/update/{cmd_id}",
                json={"status": "EXECUTING"},
                headers={"X-Auth-Key": DASHBOARD_AUTH_KEY},
                timeout=10,
                verify=False
            )
            
        elif action == "start_loop":
            if check_process(FILE_LOOP):
                print(f"⚠️ [EXEC] Loop already running", flush=True)
                return
            
            cmd_loop = (
                f"xvfb-run -a --server-args='-screen 0 {SCREEN_LOOP}' "
                f"{sys.executable} -u {FILE_LOOP}"
            )
            threading.Thread(target=run_and_monitor, args=(cmd_loop, "LOOP"), daemon=True).start()
            print(f"✅ [EXEC] Loop started", flush=True)
            
            requests.post(
                f"{DASHBOARD_URL}/api/command/update/{cmd_id}",
                json={"status": "EXECUTING"},
                headers={"X-Auth-Key": DASHBOARD_AUTH_KEY},
                timeout=10,
                verify=False
            )
            
        elif action == "stop":
            kill_processes()
            clean_system()
            print(f"✅ [EXEC] Stopped all processes", flush=True)
            
            requests.post(
                f"{DASHBOARD_URL}/api/command/update/{cmd_id}",
                json={"status": "SUCCESS"},
                headers={"X-Auth-Key": DASHBOARD_AUTH_KEY},
                timeout=10,
                verify=False
            )
            
        elif action == "clean_ram":
            clean_system()
            mem = psutil.virtual_memory()
            print(f"✅ [EXEC] RAM Cleaned: {mem.available // 1048576} MB free", flush=True)
            
            requests.post(
                f"{DASHBOARD_URL}/api/command/update/{cmd_id}",
                json={"status": "SUCCESS"},
                headers={"X-Auth-Key": DASHBOARD_AUTH_KEY},
                timeout=10,
                verify=False
            )
        
        else:
            print(f"❌ [EXEC] Unknown action: {action}", flush=True)
            
    except Exception as e:
        print(f"❌ [EXEC] Error executing {action}: {e}", flush=True)
# ==========================================
# 🌉 NETWORK BRIDGE & DNS BYPASS
# ==========================================
old_getaddrinfo = socket.getaddrinfo
DNS_MAP = {} 

def resolve_domain_dynamic():
    print("🌉 [BRIDGE] Memulai Resolusi DNS Dinamis...", flush=True)
    for url in PANEL_URL:
        try:
            domain = urlparse(url).netloc
            if not domain: continue
            if domain in DNS_MAP: continue

            print(f"🔍 [BRIDGE] Mencari IP untuk: {domain}...", flush=True)
            api_url = f"https://dns.google/resolve?name={domain}"
            resp = requests.get(api_url, timeout=10)
            data = resp.json()
            
            if 'Answer' in data:
                ip_address = data['Answer'][0]['data']
                DNS_MAP[domain] = ip_address
                print(f"✅ [BRIDGE] Rute Ditemukan: {domain} -> {ip_address}", flush=True)
        except Exception as e:
            print(f"❌ [BRIDGE] Error Resolve {url}: {e}", flush=True)

def new_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host in DNS_MAP:
        return old_getaddrinfo(DNS_MAP[host], port, family, type, proto, flags)
    return old_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = new_getaddrinfo
resolve_domain_dynamic()

# ==========================================
# 📡 LAPORAN STATUS
# ==========================================
def report_status(state, msg=""):
    """Mengirim laporan ke Panel Worker bahwa tugas selesai."""
    global CURRENT_SLOT
    
    if not CURRENT_SLOT:
        return
    
    payload = {
        "slot": CURRENT_SLOT,
        "state": state,
        "msg": msg
    }

    for url in PANEL_URL:
        try:
            requests.post(
                f"{url}/api/report",
                json=payload,
                headers={"X-Auth-Key": AUTH_KEY},
                timeout=10,
                verify=False
            )
        except Exception as e:
            pass # Silent error

# ==========================================
# 🛠️ PROCESS MANAGER (OPTIMIZED PSUTIL & ZOMBIE KILLER)
# ==========================================

def run_and_monitor(cmd_list, task_name):
    """
    Menjalankan proses dan memonitor hingga selesai.
    Mencegah Zombie Process dengan os.setsid.
    """
    print(f"🚀 [TASK] Memulai: {task_name}", flush=True)
    
    state_name = f"BUSY_{task_name}" 
    report_status(state_name, f"Running {task_name}...")

    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"\n--- START {task_name} : {time.ctime()} ---\n")
            f.flush()
            
            # PENTING: preexec_fn=os.setsid mencegah proses anak tertinggal jika agent mati
            process = subprocess.Popen(
                cmd_list, stdout=f, stderr=subprocess.STDOUT, shell=True, preexec_fn=os.setsid
            )
            process.wait() 
            
            f.write(f"\n--- END {task_name} : {time.ctime()} ---\n")
    
        print(f"✅ [TASK] {task_name} Selesai. Melapor ke Server...", flush=True)
        report_status("IDLE", f"{task_name} Finished")
        
    except Exception as e:
        print(f"❌ [TASK] Error saat menjalankan {task_name}: {e}", flush=True)
        report_status("IDLE", f"Error: {str(e)}")

def check_process(script_name):
    for p in psutil.process_iter(['cmdline']):
        try:
            if p.info['cmdline'] and script_name in ' '.join(p.info['cmdline']):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False

def kill_processes():
    print("🛑 [CLEANUP] Killing active processes and clearing locks...", flush=True)
    targets = [FILE_LOGIN, FILE_LOOP, 'chrome', 'chromedriver', 'xvfb']
    my_pid = os.getpid()

    # 1. Bunuh semua proses nakal secara paksa (SIGKILL)
    for p in psutil.process_iter(['name', 'cmdline']):
        try:
            if p.pid == my_pid: continue
            
            cmd_str = ' '.join(p.info['cmdline']) if p.info['cmdline'] else ''
            name_str = p.info['name'].lower()
            
            if any(t in cmd_str for t in targets) or any(t in name_str for t in targets):
                try: 
                    p.kill() # Menggunakan kill() untuk mematikan instan
                except: pass
        except: pass
            
    time.sleep(2)
    
    # 2. Hapus SEMUA Xvfb Lock Files untuk mencegah X11 stuck
    try:
        for lock_file in glob.glob('/tmp/.X*-lock'):
            os.remove(lock_file)
        # Reset socket X11
        if os.path.exists('/tmp/.X11-unix'):
            shutil.rmtree('/tmp/.X11-unix', ignore_errors=True)
            os.makedirs('/tmp/.X11-unix', exist_ok=True)
    except Exception as e:
        print(f"⚠️ Gagal bersihkan X lock: {e}", flush=True)

def clean_system():
    # 1. Bersihkan Zombie Process
    try:
        for p in psutil.process_iter(['status']):
            if p.info['status'] == psutil.STATUS_ZOMBIE:
                try: p.wait(timeout=0) 
                except: pass
    except: pass
    
    # 2. Bersihkan Cache Chrome untuk meringankan memori/storage
    try:
        for cache_dir in glob.glob(os.path.join(PROFILE_DIR, '*/Default/Cache')):
            shutil.rmtree(cache_dir, ignore_errors=True)
    except: pass

    # 3. Sinkronisasi memori disk
    try: os.system("sync") 
    except: pass

# ==========================================
# 🔄 AUTO REGISTER
# ==========================================
def auto_register():
    global CURRENT_SLOT
    print("⏳ [INIT] Menyiapkan URL Bot...", flush=True)
    time.sleep(3)

    hf_host = os.environ.get("SPACE_HOST")
    
    if hf_host:
        bot_url = f"https://{hf_host}"
        print(f"✅ [INIT] Berjalan di Hugging Face! URL: {bot_url}", flush=True)
    else:
        bot_url = "http://localhost:7860"
        print(f"⚠️ [INIT] SPACE_HOST tidak ditemukan. Menggunakan fallback: {bot_url}", flush=True)

    try:
        my_ip = requests.get('https://api.ipify.org', timeout=10, verify=False).text.strip()
    except:
        my_ip = "Unknown IP"

    # ✅ GET SLOT FROM ENV
    CURRENT_SLOT = int(os.getenv("CURRENT_SLOT", 1))
    print(f"🎯 [INIT] Using CURRENT_SLOT={CURRENT_SLOT}", flush=True)

    registered = False
    
    while not registered:
        for url in PANEL_URL:
            try:
                print(f"📡 [INIT] Register ke Panel: {url} ...", flush=True)
                
                # ✅ INCLUDE SLOT IN PAYLOAD
                payload = {
                    "slot": CURRENT_SLOT,      # ← TAMBAH INI
                    "url": bot_url, 
                    "ip": my_ip
                }
                
                resp = requests.post(
                    f"{url}/api/register", 
                    json=payload,
                    headers={"X-Auth-Key": AUTH_KEY}, 
                    timeout=20, 
                    verify=False 
                )

                if resp.status_code == 200:
                    data = resp.json()
                    print(f"\n✅ [INIT] TERDAFTAR DI SLOT: {CURRENT_SLOT}", flush=True)
                    registered = True
                    return True

                elif resp.status_code == 503:
                    print("⛔ [INIT] PANEL PENUH! Retry 10s...", flush=True)
                else:
                    print(f"⚠️ [INIT] Register failed: {resp.status_code} - {resp.text}", flush=True)
                    
            except Exception as e:
                print(f"❌ [INIT] Gagal koneksi ke panel: {e}", flush=True)
                resolve_domain_dynamic()
        
        if not registered: time.sleep(10)
# ==========================================
# 🤖 AUTOMATION FLOW (WITH DATA CHECK)
# ==========================================
def start_automatic_flow():
    """Flow Otomatis: Register -> Cek Data -> Lapor Idle / Login -> Loop"""
    
    # 1. REGISTER
    print("\n🔹 [AUTO] STEP 1: Melakukan Registrasi...", flush=True)
    is_registered = auto_register()
    
    if not is_registered:
        print("❌ [AUTO] Registrasi gagal. Membatalkan otomatisasi.")
        return

    report_status("IDLE", "Registered. Cooldown 10s...")
    print(f"⏳ [AUTO] STEP 2: Menunggu 10 detik...", flush=True)
    time.sleep(10)

    # 2. PENGECEKAN DATA KOSONG
    has_valid_data = False
    try:
        emails_count = 0
        links_count = 0
        if os.path.exists('email.txt'):
            with open('email.txt', 'r') as f: emails_count = len([line for line in f if line.strip()])
        if os.path.exists('link.txt'):
            with open('link.txt', 'r') as f: links_count = len([line for line in f if line.strip()])
            
        if emails_count > 0 and links_count > 0:
            has_valid_data = True
    except Exception as e:
        print(f"⚠️ [AUTO] Error saat mengecek data: {e}", flush=True)

    # JIKA KOSONG: TETAP IDLE DAN DIAM
    if not has_valid_data:
        print("⚠️ [AUTO] Data Kosong (Email/Link tidak ada). Bot standby dan tidak melakukan login.", flush=True)
        report_status("IDLE", "Data Empty. Standby")
        return  # Berhenti di sini. Flask API akan tetap jalan untuk menerima request manual.

    # 3. RUN LOGIN.PY (HANYA JIKA ADA DATA)
    print("\n🔹 [AUTO] STEP 3: Data terdeteksi. Menjalankan Login.py...", flush=True)
    if not check_process(FILE_LOGIN) and not check_process(FILE_LOOP):
        cmd_login = (
            f"xvfb-run -a --server-args='-screen 0 {SCREEN_LOGIN}' "
            f"{sys.executable} {FILE_LOGIN}"
        )
        run_and_monitor(cmd_login, "LOGIN")
    else:
        print("⚠️ [AUTO] Proses lain sedang berjalan, melewati Login.")
        report_status("IDLE", "Login Skipped (Busy)")

    # 4. RUN LOOP.PY
    print("\n🔹 [AUTO] STEP 4: Login selesai. Menjalankan Loop.py...", flush=True)
    if not check_process(FILE_LOOP):
        cmd_loop = (
            f"xvfb-run -a --server-args='-screen 0 {SCREEN_LOOP}' "
            f"{sys.executable} -u {FILE_LOOP}"
        )
        run_and_monitor(cmd_loop, "LOOP")
    else:
        print("⚠️ [AUTO] Loop sudah berjalan.")

# ==========================================
# 🌐 API ENDPOINTS & DASHBOARD
# ==========================================

@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>DOT AJA</title>
    </head>
    <body>
        <div style="text-align:center">
            <h1>SERVER : ONLINE</h1>
            <p>System Status: <b>ONLINE</b></p>
        </div>
    </body>
    </html>
    """

@app.before_request
def auth():
    if request.endpoint == 'index':
        return
    if request.headers.get("X-Auth-Key") != AUTH_KEY:
        return jsonify({"error": "Unauthorized"}), 401

@app.route('/start/login', methods=['POST'])
def menu_1():
    if check_process(FILE_LOGIN): return jsonify({"msg": "Login sudah jalan!", "status": "busy"})
    if check_process(FILE_LOOP): return jsonify({"msg": "Loop sedang jalan!", "status": "busy"})
    
    cmd = (
        "xvfb-run -a --server-args='-screen 0 {screen}' "
        "{python} {login}" 
    ).format(
        screen=SCREEN_LOGIN, python=sys.executable, login=FILE_LOGIN
    )
    
    threading.Thread(target=run_and_monitor, args=(cmd, "LOGIN"), daemon=True).start()
    return jsonify({"msg": "Login Started", "status": "ok"})

@app.route('/start/loop', methods=['POST'])
def menu_2():
    if check_process(FILE_LOOP): return jsonify({"msg": "Loop sudah jalan!", "status": "busy"})
    if check_process(FILE_LOGIN): return jsonify({"msg": "Login sedang jalan!", "status": "busy"})

    cmd = (
        "xvfb-run -a --server-args='-screen 0 {screen}' "
        "{python} -u {loop}" 
    ).format(
        screen=SCREEN_LOOP, python=sys.executable, loop=FILE_LOOP
    )
    
    threading.Thread(target=run_and_monitor, args=(cmd, "LOOP"), daemon=True).start()
    return jsonify({"msg": "Loop Started", "status": "ok"})

@app.route('/logs', methods=['GET'])
def menu_3():
    if not os.path.exists(LOG_FILE): return jsonify({"logs": "No Logs."})
    try:
        raw = subprocess.check_output(['tail', '-n', '50', LOG_FILE]).decode('utf-8', errors='ignore')
        return jsonify({"logs": re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', raw)})
    except Exception as e: return jsonify({"logs": str(e)})

@app.route('/stop', methods=['POST'])
def menu_4():
    kill_processes()
    clean_system()
    open(LOG_FILE, 'w').close()
    if CURRENT_SLOT: report_status("IDLE", "Stopped by Admin")
    return jsonify({"msg": "Stopped & Cleaned"})

@app.route('/clean_ram', methods=['POST'])
def menu_7():
    clean_system()
    mem = psutil.virtual_memory()
    return jsonify({"msg": "RAM Optimized", "free": f"{mem.available // 1048576} MB"})

@app.route('/status', methods=['GET'])
def status():
    state = "IDLE"
    if check_process(FILE_LOGIN): state = "BUSY_LOGIN"
    if check_process(FILE_LOOP): state = "BUSY_LOOP"
    return jsonify({
        "login": check_process(FILE_LOGIN),
        "loop": check_process(FILE_LOOP),
        "state": state
    })
# ==========================================
# 🖼️ SCREENSHOT SERVER (FOR PANEL RELAY)
# ==========================================
@app.route('/view_screenshot', methods=['GET'])
def view_screenshot():
    """Endpoint untuk memberikan file gambar ke Panel VPS"""
    filename = request.args.get('file')
    if not filename:
        return jsonify({"error": "Missing filename parameter"}), 400
    
    # Pastikan file aman dan ada di direktori kerja
    file_path = os.path.join(BASE_DIR, filename)
    
    if os.path.exists(file_path):
        from flask import send_file
        try:
            # Mengirimkan file gambar langsung sebagai response
            return send_file(file_path, mimetype='image/png')
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": f"File {filename} not found"}), 404
        
if __name__ == '__main__':
    # Register ke dashboard
    register_to_dashboard()
    
    # Start heartbeat thread
    threading.Thread(target=send_heartbeat_to_dashboard, daemon=True).start()
    
    # Start command polling thread ✅ NEW
    threading.Thread(target=poll_commands_from_dashboard, daemon=True).start()
    
    # Start automatic flow
    threading.Thread(target=start_automatic_flow, daemon=True).start()
    
    # Run Flask API
    print("🚀 [AGENT] Starting Flask API on port 7860", flush=True)
    app.run(host='0.0.0.0', port=7860)
