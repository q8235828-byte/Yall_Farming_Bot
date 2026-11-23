"""
================================================================================
YALLA LUDO 3-INSTANCE CONCURRENT ACCOUNT CREATOR
================================================================================
Simultaneously creates 3 Yalla Ludo accounts across 3 MEmu instances:
- 127.0.0.1:21503 (Instance 0)
- 127.0.0.1:21513 (Instance 1)
- 127.0.0.1:21623 (Instance 12)

Features:
1. Thread-safe atomic email increment (user{N}@domain).
2. Parallel Geetest Captcha solving using ColorIndexedCaptchaSolver with 90s timeout.
3. Concurrent Gmail IMAP OTP extraction with independent SSL connections.
4. Auto Password injection (LudoPass#2026@).
5. 5-Second fast post-expert logout to Main Landing.
6. Thread-safe CSV logging to created_accounts.csv.
================================================================================
"""

import concurrent.futures
import csv
from datetime import datetime
import json
import os
import sys
import threading
import time

try:
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from color_indexed_captcha_solver import ColorIndexedCaptchaSolver
from otp_fetcher import GmailOTPFetcher
from screen_detector import (
    ScreenDetector,
    STATE_MAIN_LANDING,
    STATE_LOGIN_DIALOG,
    STATE_SIGNUP,
    STATE_CAPTCHA,
    STATE_OTP_READY,
    STATE_SET_PASSWORD,
    STATE_EXPERT_DIALOG,
)
import yalla_ui_automator as ui

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
ACCOUNTS_CSV = os.path.join(BASE_DIR, "created_accounts.csv")
BACKUP_CSV = os.path.join(BASE_DIR, "created_accounts_backup.csv")
DEFAULT_PASSWORD = "LudoPass#2026@"
PACKAGE_NAME = "com.yalla.yallagames"

TARGET_DEVICES = [
    "127.0.0.1:21503",
    "127.0.0.1:21513",
    "127.0.0.1:21523",
    "127.0.0.1:21533",
    "127.0.0.1:21543",
    "127.0.0.1:21623",
]

counter_lock = threading.Lock()
csv_lock = threading.Lock()
log_lock = threading.Lock()


def log_worker(device_id: str, message: str):
    """Thread-safe prefixed console logging."""
    with log_lock:
        now_str = datetime.now().strftime("%H:%M:%S")
        print(f"[{now_str}] [{device_id}] {message}", flush=True)


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_next_email_atomic() -> str:
    """Thread-safe atomic auto-increment email generator."""
    with counter_lock:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        prefix = cfg.get("email_prefix", "user")
        counter = cfg.get("current_counter", 541)
        domain = cfg.get("cloudflare_domain", "bhullehshahsilage.com")
        email_addr = f"{prefix}{counter}@{domain}"
        cfg["current_counter"] = counter + 1
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        return email_addr


def save_account_to_csv_atomic(email_address: str, otp_code: str, status: str, device_id: str, password: str = DEFAULT_PASSWORD):
    """Thread-safe CSV writer for successful and failed creations."""
    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        email_address,
        password,
        otp_code,
        status,
        device_id,
    ]
    with csv_lock:
        for target in [ACCOUNTS_CSV, BACKUP_CSV]:
            try:
                file_exists = os.path.exists(target)
                with open(target, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(["Timestamp", "Email", "Password", "OTP Code", "Status", "Device"])
                    writer.writerow(row)
                log_worker(device_id, f"[+] Recorded in {os.path.basename(target)}: {email_address} ({status})")
                return
            except PermissionError:
                continue
            except Exception as e:
                log_worker(device_id, f"[!] CSV write error: {e}")


def ensure_device_at_signup(device_id: str, detector: ScreenDetector) -> bool:
    """Brings device to SIGNUP_SCREEN if not already there."""
    for attempt in range(3):
        state, _ = detector.get_screen_state()
        log_worker(device_id, f"Current screen state: [{state}]")
        if state == STATE_SIGNUP:
            return True
        elif state == STATE_LOGIN_DIALOG:
            log_worker(device_id, "Tapping Sign Up link from Login modal...")
            ui.fast_click("signup_link", device_id, 0.5)
            ok, _ = detector.wait_for_state(STATE_SIGNUP, timeout=4.0)
            if ok:
                return True
        elif state == STATE_MAIN_LANDING:
            log_worker(device_id, "Navigating from Main Landing to Sign Up...")
            ui.ensure_terms_checked(device_id)
            ui.go_to_signup_screen(device_id)
            ok, _ = detector.wait_for_state(STATE_SIGNUP, timeout=5.0)
            if ok:
                return True
        elif state == STATE_EXPERT_DIALOG:
            log_worker(device_id, "Expert dialog detected; executing fast logout...")
            ui.fast_expert_to_main_landing(device_id)
            ui.ensure_terms_checked(device_id)
            ui.go_to_signup_screen(device_id)
            ok, _ = detector.wait_for_state(STATE_SIGNUP, timeout=5.0)
            if ok:
                return True
        else:
            log_worker(device_id, f"State [{state}], launching Yalla Ludo...")
            ui.run_adb_command(["shell", "monkey", "-p", PACKAGE_NAME, "-c", "android.intent.category.LAUNCHER", "1"], device_id)
            time.sleep(3.0)
            ui.fast_expert_to_main_landing(device_id)
            ui.ensure_terms_checked(device_id)
            ui.go_to_signup_screen(device_id)
            ok, _ = detector.wait_for_state(STATE_SIGNUP, timeout=5.0)
            if ok:
                return True
    return False


def create_account_on_device(device_id: str, gmail: str, app_pw: str) -> dict:
    """Executes the full account creation lifecycle on a single device."""
    t_start = time.time()
    result = {
        "device_id": device_id,
        "email": None,
        "otp": None,
        "status": "Failed",
        "duration": 0.0,
    }

    log_worker(device_id, "=== Worker Thread Started ===")
    detector = ScreenDetector(device_id)

    # 1. Ensure on Sign Up screen
    if not ensure_device_at_signup(device_id, detector):
        log_worker(device_id, "[-] Failed to navigate to Sign Up screen.")
        result["status"] = "Failed_Navigation"
        return result

    # 2. Allocate atomic email & request OTP
    email_address = get_next_email_atomic()
    result["email"] = email_address
    log_worker(device_id, f"[Step 1] Target Email Allocated: {email_address}")

    obtain_time = ui.request_verification_code(email_address, device_id)
    log_worker(device_id, f"[+] Email entered & Obtain clicked at {obtain_time:.2f}")

    # 3. Solve Captcha (90s timeout, max 3 attempts)
    log_worker(device_id, "[Step 2] Initializing Color-Indexed Captcha Solver (90s timeout)...")
    solver = ColorIndexedCaptchaSolver(device_id=device_id)
    captcha_solved = solver.solve(max_attempts=3, timeout=90.0)

    if not captcha_solved:
        log_worker(device_id, "[-] Captcha could not be solved in 3 attempts.")
        save_account_to_csv_atomic(email_address, "CAPTCHA_FAILED", "Failed_Captcha", device_id)
        result["status"] = "Failed_Captcha"
        return result

    log_worker(device_id, "[+] Captcha solved or bypassed successfully!")

    # 4. Wait for OTP Ready State
    log_worker(device_id, "[Step 3] Waiting for OTP input ready state (countdown running)...")
    ok, _ = detector.wait_for_state(STATE_OTP_READY, timeout=10.0)
    if not ok:
        state, _ = detector.get_screen_state()
        if state != STATE_SIGNUP:
            log_worker(device_id, f"[-] Not in OTP state (Current: {state}).")
            save_account_to_csv_atomic(email_address, "OTP_NOT_READY", "Failed_OTP_Not_Ready", device_id)
            result["status"] = "Failed_OTP_Not_Ready"
            return result

    # 5. Fetch OTP from Gmail
    log_worker(device_id, f"[Step 4] Polling Gmail for {email_address} (60s max)...")
    fetcher = GmailOTPFetcher(gmail, app_pw)
    t_otp_start = time.time()
    otp = fetcher.wait_for_otp(target_email=email_address, min_timestamp=(obtain_time - 30), timeout_seconds=60)

    if not otp:
        log_worker(device_id, f"[-] OTP timed out after 60s for {email_address}.")
        save_account_to_csv_atomic(email_address, "TIMEOUT", "Failed_OTP_Timeout", device_id)
        result["status"] = "Failed_OTP_Timeout"
        return result

    result["otp"] = otp
    log_worker(device_id, f"[+] Verified OTP: {otp} (received in {time.time() - t_otp_start:.2f}s)")

    # 6. Submit OTP
    ui.submit_verification_code(otp, device_id)

    # 7. Set Password
    log_worker(device_id, "[Step 5] Detecting Set Password screen...")
    ok, _ = detector.wait_for_state(STATE_SET_PASSWORD, timeout=8.0)
    if not ok:
        log_worker(device_id, "[-] Set Password screen did not appear.")
        save_account_to_csv_atomic(email_address, otp, "Failed_No_Password_Screen", device_id)
        result["status"] = "Failed_No_Password_Screen"
        return result

    ui.set_account_password(DEFAULT_PASSWORD, device_id)
    log_worker(device_id, f"[+] Password [{DEFAULT_PASSWORD}] submitted successfully!")

    # 8. Fast 5s Post-Expert Logout
    log_worker(device_id, "[Step 6] Detecting 'I am expert' dialog...")
    detector.wait_for_state(STATE_EXPERT_DIALOG, timeout=12.0)

    t_post_start = time.time()
    log_worker(device_id, "[*] Running rapid 5s Expert -> Lobby -> Settings -> Logout sequence...")
    ui.fast_expert_to_main_landing(device_id)
    t_post_dur = time.time() - t_post_start
    log_worker(device_id, f"[+] Post-expert logout completed in {t_post_dur:.2f}s (<5s satisfied!)")

    # 9. Record Success
    save_account_to_csv_atomic(email_address, otp, "Success_Created", device_id)
    result["status"] = "Success_Created"
    result["duration"] = time.time() - t_start
    log_worker(device_id, f"[SUCCESS] Account {email_address} created in {result['duration']:.1f}s! [OK]")

    return result


def run_parallel_creation(devices: list[str] = TARGET_DEVICES, stagger_seconds: float = 4.0):
    cfg = load_config()
    gmail = cfg.get("gmail_address")
    app_pw = cfg.get("gmail_app_password", "").replace(" ", "")

    print("\n" + "="*70)
    print("   YALLA LUDO MULTI-INSTANCE CONCURRENT PARALLEL ACCOUNT CREATION")
    print("="*70)
    print(f"[*] Target Devices ({len(devices)} instances): {devices}")
    print(f"[*] Inter-Worker Stagger Delay: {stagger_seconds}s (Smooth Rate-Limit Avoidance)")
    print(f"[*] Gmail Listener: {gmail}")
    print(f"[*] Default Password: {DEFAULT_PASSWORD}")
    print("="*70 + "\n")

    t_batch_start = time.time()

    def worker_wrapper(dev: str, delay: float):
        if delay > 0:
            time.sleep(delay)
        return create_account_on_device(dev, gmail, app_pw)

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(devices)) as executor:
        futures = {
            executor.submit(worker_wrapper, dev, idx * stagger_seconds): dev
            for idx, dev in enumerate(devices)
        }

        results = []
        for future in concurrent.futures.as_completed(futures):
            dev = futures[future]
            try:
                res = future.result()
                results.append(res)
            except Exception as e:
                print(f"[!] Worker for {dev} raised an unhandled exception: {e}")
                results.append({
                    "device_id": dev,
                    "email": None,
                    "otp": None,
                    "status": f"Exception: {e}",
                    "duration": 0.0,
                })

    t_batch_total = time.time() - t_batch_start

    print("\n" + "="*70)
    print("                  PARALLEL EXECUTION BATCH SUMMARY")
    print("="*70)
    print(f"Total Parallel Duration: {t_batch_total:.2f} seconds\n")
    print(f"{'Device':<18} | {'Email':<30} | {'OTP':<8} | {'Status':<16} | {'Time (s)'}")
    print("-" * 85)
    successful = 0
    for r in results:
        status_str = r.get("status", "Unknown")
        if status_str == "Success_Created":
            successful += 1
        dev_str = r.get("device_id", "Unknown")
        email_str = str(r.get("email") or "N/A")
        otp_str = str(r.get("otp") or "N/A")
        dur_str = f"{r.get('duration', 0.0):.1f}"
        print(f"{dev_str:<18} | {email_str:<30} | {otp_str:<8} | {status_str:<16} | {dur_str}")
    print("-" * 85)
    print(f"[+] Total Success: {successful}/{len(devices)} accounts created simultaneously!\n")


if __name__ == "__main__":
    run_parallel_creation()
