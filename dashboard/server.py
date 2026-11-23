import os
import sys
import json
import csv
import time
import subprocess
import threading
import io
from datetime import datetime
from flask import Flask, render_template, request, jsonify

# Set paths
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
PIPELINE_DIR = os.path.join(PROJECT_ROOT, "today_downloads", "qaiser new test")

if PIPELINE_DIR not in sys.path:
    sys.path.insert(0, PIPELINE_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from google_sheet_sync import fetch_all_accounts_from_sheet, update_google_sheet, load_24h_history
from licensing import get_machine_hwid, is_activated, verify_and_activate, PAGES_DEV_BUY_URL

app = Flask(__name__, template_folder=os.path.join(CURRENT_DIR, "templates"))

# Global App State
APP_STATE = {
    "accounts": [],
    "is_running": False,
    "logs": ["[SYSTEM] Dashboard backend initialized. Ready."],
    "threads": [],
    "stop_requested": False
}
STATE_LOCK = threading.Lock()
ACCOUNTS_CACHE_FILE = os.path.join(CURRENT_DIR, "cached_accounts.json")


def log_msg(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    formatted = f"[{ts}] {msg}"
    print(formatted)
    with STATE_LOCK:
        APP_STATE["logs"].append(formatted)
        if len(APP_STATE["logs"]) > 100:
            APP_STATE["logs"].pop(0)


def save_cached_accounts(accounts):
    try:
        with open(ACCOUNTS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(accounts, f, indent=2)
    except Exception as e:
        log_msg(f"Error saving cached accounts: {e}")


def load_cached_accounts():
    if os.path.exists(ACCOUNTS_CACHE_FILE):
        try:
            with open(ACCOUNTS_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


# Load initially from cache or Google Sheet
initial_accs = load_cached_accounts()
if not initial_accs:
    try:
        initial_accs = fetch_all_accounts_from_sheet()
        save_cached_accounts(initial_accs)
    except Exception as e:
        log_msg(f"Could not load initial sheet: {e}")

APP_STATE["accounts"] = initial_accs


@app.route("/")
def index():
    return render_template("index.html")


MEMUC_PATHS = [
    r"D:\Program Files\Microvirt\MEmu\memuc.exe",
    r"C:\Program Files\Microvirt\MEmu\memuc.exe",
    r"C:\Program Files (x86)\Microvirt\MEmu\memuc.exe"
]
MEMUC_BIN = next((p for p in MEMUC_PATHS if os.path.exists(p)), None)


@app.route("/api/devices")
def get_devices():
    """Detects active and available MEmu instances with real live status."""
    online_adb_ports = set()
    try:
        out = subprocess.check_output(["adb", "devices"], text=True, timeout=5)
        for line in out.splitlines():
            line = line.strip()
            if "\tdevice" in line:
                online_adb_ports.add(line.split("\t")[0].strip())
    except Exception:
        pass

    devices = []

    # Query memuc if available
    if MEMUC_BIN:
        try:
            out = subprocess.check_output([MEMUC_BIN, "listvms"], text=True, timeout=5)
            for line in out.splitlines():
                parts = line.strip().split(",")
                if len(parts) >= 4:
                    idx = int(parts[0])
                    name = parts[1]
                    is_running = parts[3].strip() == "1"
                    port = f"127.0.0.1:{21503 + idx * 10}"

                    # Double check with adb
                    is_online = is_running and (port in online_adb_ports)

                    devices.append({
                        "index": idx,
                        "name": name,
                        "port": port,
                        "is_online": is_online,
                        "status_text": "Online" if is_online else "Offline"
                    })
        except Exception as e:
            log_msg(f"memuc error: {e}")

    # Fallback if memuc not accessible
    if not devices:
        for idx, p in enumerate(["127.0.0.1:21503", "127.0.0.1:21513", "127.0.0.1:21523"]):
            is_on = p in online_adb_ports
            devices.append({
                "index": idx,
                "name": f"MEmu - {idx}",
                "port": p,
                "is_online": is_on,
                "status_text": "Online" if is_on else "Offline"
            })

    return jsonify({"devices": devices})


@app.route("/api/launch_instance", methods=["POST"])
def launch_instance():
    """Starts a MEmu emulator instance via memuc."""
    if not MEMUC_BIN:
        return jsonify({"success": False, "error": "memuc.exe not found"}), 400

    idx = request.json.get("index", 0)
    log_msg(f"[*] Requesting MEmu to launch instance index {idx}...")
    try:
        subprocess.Popen([MEMUC_BIN, "start", "-i", str(idx)])
        return jsonify({"success": True, "message": f"Launching MEmu instance {idx}..."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/upload_sheet", methods=["POST"])
def upload_sheet():
    """Accepts uploaded CSV / Excel / TXT sheet and loads it into memory & UI."""
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"success": False, "error": "Empty filename"}), 400

    filename = file.filename.lower()
    parsed_accounts = []

    try:
        if filename.endswith(".csv") or filename.endswith(".txt"):
            stream = io.StringIO(file.stream.read().decode("utf-8", errors="ignore"))
            reader = csv.reader(stream)
            headers = [h.strip().lower() for h in next(reader, [])]

            # Find columns
            email_idx = next((i for i, h in enumerate(headers) if "email" in h or "user" in h), 0)
            pwd_idx = next((i for i, h in enumerate(headers) if "pass" in h), 1)
            status_idx = next((i for i, h in enumerate(headers) if "status" in h), None)
            coin_idx = next((i for i, h in enumerate(headers) if "coin" in h), None)

            for row in reader:
                if not row or len(row) <= email_idx:
                    continue
                email = row[email_idx].strip()
                if not email or "@" not in email:
                    continue
                pwd = row[pwd_idx].strip() if len(row) > pwd_idx else "Yalla#2026@Pass"
                st = row[status_idx].strip() if status_idx is not None and len(row) > status_idx else "Pending"
                coin = row[coin_idx].strip() if coin_idx is not None and len(row) > coin_idx else "-"

                parsed_accounts.append({
                    "Email": email,
                    "Password": pwd,
                    "Clean_Password": pwd,
                    "Status": st,
                    "Total_Coin": coin,
                    "Free_Rewards": "0/6",
                    "Latest_Update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

        with STATE_LOCK:
            APP_STATE["accounts"] = parsed_accounts
            save_cached_accounts(parsed_accounts)

        log_msg(f"[+] Successfully loaded {len(parsed_accounts)} accounts from uploaded file: {file.filename}")
        return jsonify({"success": True, "count": len(parsed_accounts)})

    except Exception as e:
        log_msg(f"[-] Failed to parse uploaded file: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/sync_google_sheet", methods=["POST"])
def sync_google_sheet():
    """Fetches fresh accounts from live Google Sheet."""
    try:
        accs = fetch_all_accounts_from_sheet()
        with STATE_LOCK:
            APP_STATE["accounts"] = accs
            save_cached_accounts(accs)
        log_msg(f"[+] Synced {len(accs)} accounts from Live Google Sheet [OK]!")
        return jsonify({"success": True, "count": len(accs)})
    except Exception as e:
        log_msg(f"[-] Google Sheet sync error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/state")
def get_state():
    """Returns current live dashboard state."""
    with STATE_LOCK:
        accs = APP_STATE["accounts"]
        total = len(accs)
        completed = sum(1 for a in accs if a.get("Status") in ["Success_Completed", "Completed_LoggedOut"])
        
        # Calculate coins
        total_coins_num = 0
        for a in accs:
            c = str(a.get("Total_Coin", "0")).upper().replace(",", "").strip()
            if "K" in c:
                try:
                    total_coins_num += float(c.replace("K", "")) * 1000
                except Exception:
                    pass
            elif c.isdigit():
                total_coins_num += int(c)

        coins_str = f"{total_coins_num / 1000:.1f}K" if total_coins_num >= 1000 else str(int(total_coins_num))

        active, lic = is_activated()
        return jsonify({
            "is_running": APP_STATE["is_running"],
            "license": {
                "activated": active,
                "hwid": get_machine_hwid(),
                "details": lic,
                "buy_url": PAGES_DEV_BUY_URL
            },
            "stats": {
                "total": total,
                "completed": completed,
                "total_coins": coins_str
            },
            "accounts": accs,
            "logs": APP_STATE["logs"][-30:]
        })


def worker_instance_runner(device_id: str, accounts_slice: list):
    """Background worker thread for an emulator instance."""
    from master_pipeline import run_full_account_cycle
    log_msg(f"[{device_id}] Worker started. Assigned {len(accounts_slice)} accounts.")

    for acc in accounts_slice:
        if APP_STATE["stop_requested"]:
            log_msg(f"[{device_id}] Stop signal received. Halting.")
            break

        email = acc["Email"]
        pwd = acc.get("Clean_Password") or acc.get("Password") or "Yalla#2026@Pass"

        # Update in-memory state
        with STATE_LOCK:
            for a in APP_STATE["accounts"]:
                if a["Email"].lower() == email.lower():
                    a["Status"] = "Processing"
                    a["Device_ID"] = device_id
                    a["Latest_Update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    break

        log_msg(f"[{device_id}] Processing: {email}")

        try:
            ok = run_full_account_cycle(device_id=device_id, email=email, password=pwd)
            with STATE_LOCK:
                for a in APP_STATE["accounts"]:
                    if a["Email"].lower() == email.lower():
                        a["Status"] = "Success_Completed" if ok else "Failed_Processing"
                        a["Free_Rewards"] = "6/6" if ok else a.get("Free_Rewards", "0/6")
                        a["Latest_Update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        break
            save_cached_accounts(APP_STATE["accounts"])
            log_msg(f"[{device_id}] Account {email} finished! Result: {'SUCCESS' if ok else 'FAILED'}")
        except Exception as e:
            log_msg(f"[{device_id}] Error processing {email}: {e}")

        time.sleep(2.0)

    log_msg(f"[{device_id}] Worker completed all assigned accounts.")


@app.route("/api/license/status")
def license_status():
    active, data = is_activated()
    return jsonify({
        "activated": active,
        "hwid": get_machine_hwid(),
        "details": data,
        "buy_url": PAGES_DEV_BUY_URL
    })


@app.route("/api/license/activate", methods=["POST"])
def license_activate():
    req_data = request.json or {}
    key = req_data.get("license_key", "").strip()
    email = req_data.get("email", "").strip()
    worker_url = req_data.get("worker_url", "https://yalla-licensing.workers.dev")

    if not key:
        return jsonify({"success": False, "error": "Please enter a license key."}), 400

    ok, res = verify_and_activate(key, email=email, cloudflare_url=worker_url)
    if ok:
        log_msg(f"[+] License ACTIVATED successfully for {email} ({res.get('plan')}) [OK]!")
        return jsonify({"success": True, "details": res})
    else:
        log_msg(f"[-] License activation failed: {res.get('error')}")
        return jsonify({"success": False, "error": res.get("error", "Invalid license key.")}), 400


@app.route("/api/start_farming", methods=["POST"])
def start_farming():
    """Starts farming across selected emulator instances with slice partitioning."""
    # Security: Verify License first!
    active, lic_data = is_activated()
    if not active:
        return jsonify({
            "success": False,
            "error": "Software is NOT activated! Please activate your license key to unlock farming."
        }), 403

    data = request.json or {}
    devices = data.get("devices", [])
    if not devices:
        return jsonify({"success": False, "error": "No emulator devices selected"}), 400

    start_num = data.get("start_num", 233)
    end_num = data.get("end_num")

    with STATE_LOCK:
        if APP_STATE["is_running"]:
            return jsonify({"success": False, "error": "Farming is already running"}), 400

        # Filter eligible accounts
        import re
        def parse_user_num(e):
            m = re.search(r'user(\d+)', e.lower())
            return int(m.group(1)) if m else 0

        eligible = []
        for a in APP_STATE["accounts"]:
            num = parse_user_num(a.get("Email", ""))
            if num >= start_num and (end_num is None or num <= end_num):
                if a.get("Status") != "Success_Completed":
                    eligible.append(a)

        if not eligible:
            return jsonify({"success": False, "error": f"No eligible accounts found in range >= {start_num}"}), 400

        APP_STATE["is_running"] = True
        APP_STATE["stop_requested"] = False
        APP_STATE["threads"] = []

        # Split eligible accounts evenly among devices
        num_devices = len(devices)
        chunk_size = (len(eligible) + num_devices - 1) // num_devices

        log_msg(f"[*] Starting farming across {num_devices} devices for {len(eligible)} accounts...")

        for i, dev in enumerate(devices):
            chunk = eligible[i * chunk_size : (i + 1) * chunk_size]
            if chunk:
                t = threading.Thread(target=worker_instance_runner, args=(dev, chunk), daemon=True)
                t.start()
                APP_STATE["threads"].append(t)

        # Monitor thread to reset is_running when all finish
        def supervisor():
            for t in APP_STATE["threads"]:
                t.join()
            with STATE_LOCK:
                APP_STATE["is_running"] = False
            log_msg("[+] [ALL WORKERS FINISHED] Farming batch completed.")

        threading.Thread(target=supervisor, daemon=True).start()

    return jsonify({"success": True, "accounts_count": len(eligible)})


@app.route("/api/stop_farming", methods=["POST"])
def stop_farming():
    """Signals all worker threads to stop."""
    with STATE_LOCK:
        APP_STATE["stop_requested"] = True
        APP_STATE["is_running"] = False
    log_msg("[!] Stop requested by user from dashboard.")
    return jsonify({"success": True})


if __name__ == "__main__":
    port = 5000
    log_msg(f"[*] Yalla Farming Dashboard Server running on http://127.0.0.1:{port}")
    # Open browser automatically
    import webbrowser
    threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    app.run(host="127.0.0.1", port=port, debug=False)
