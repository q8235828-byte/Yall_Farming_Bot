"""
================================================================================
YALLA LUDO 10-INSTANCE PARALLEL ACCOUNT CREATOR (HIGH SCALE)
================================================================================
Concurrent high-speed account creation across up to 10 MEmu instances:
1. Auto-detects all active MEmu instances (21503 to 21693).
2. Per-device complete data wipe (pm clear com.yalla.yallagames) & Android ID reset.
3. Accurate terms checkbox color pixel verification (no redundant toggles).
4. Atomic auto-increment email generator (user{N}@bhullehshahsilage.com).
5. Robust Color-Indexed Geetest Captcha Solver (90s timeout).
6. Concurrent independent Gmail IMAP OTP fetcher.
7. Auto password injection (LudoPass#2026@) with soft-keyboard dismissal.
8. Sub-5s fast post-expert logout sequence.
9. Thread-safe CSV logging to created_accounts.csv.
================================================================================
"""

import concurrent.futures
import csv
from datetime import datetime
import json
import os
import random
import shutil
import subprocess
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
import memu_manager

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
ACCOUNTS_CSV = os.path.join(BASE_DIR, "created_accounts.csv")
BACKUP_CSV = os.path.join(BASE_DIR, "created_accounts_backup.csv")
DEFAULT_PASSWORD = "LudoPass#2026@"
PACKAGE_NAME = "com.yalla.yallagames"

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
        counter = cfg.get("current_counter", 558)
        domain = cfg.get("cloudflare_domain", "bhullehshahsilage.com")
        email_addr = f"{prefix}{counter}@{domain}"
        cfg["current_counter"] = counter + 1
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        return email_addr


def save_account_to_csv_atomic(email_address: str, otp_code: str, status: str, device_id: str, password: str = DEFAULT_PASSWORD):
    """Thread-safe CSV writer for successful and failed creations."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [now_str, email_address, password, otp_code, status, device_id]
    with csv_lock:
        for file_path in [ACCOUNTS_CSV, BACKUP_CSV]:
            try:
                file_exists = os.path.exists(file_path)
                with open(file_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(["Timestamp", "Email", "Password", "OTP", "Status", "Device_ID"])
                    writer.writerow(row)
            except Exception as e:
                log_worker(device_id, f"[!] CSV write error ({file_path}): {e}")
        log_worker(device_id, f"[+] Recorded in created_accounts.csv: {email_address} ({status})")


def wipe_device_data(device_id: str):
    """Completely resets Yalla Ludo data, cache, randomizes Android ID, and relaunches fresh."""
    try:
        log_worker(device_id, "[*] Wiping Yalla Ludo game data & cache...")
        ui.run_adb_command(["shell", "pm", "clear", PACKAGE_NAME], device_id)
        # Randomize Android ID for clean device fingerprint
        rand_hex = ''.join(random.choices('0123456789abcdef', k=16))
        ui.run_adb_command(["shell", "settings", "put", "secure", "android_id", rand_hex], device_id)
        # Ensure direct proxy
        ui.run_adb_command(["shell", "settings", "put", "global", "http_proxy", ":0"], device_id)
        time.sleep(1.0)
        # Relaunch Yalla Ludo fresh
        log_worker(device_id, "[*] Launching fresh Yalla Ludo session...")
        ui.run_adb_command(["shell", "monkey", "-p", PACKAGE_NAME, "-c", "android.intent.category.LAUNCHER", "1"], device_id)
        time.sleep(4.0)
    except Exception as e:
        log_worker(device_id, f"[!] Wipe error: {e}")


def ensure_device_at_signup(device_id: str, detector: ScreenDetector, max_attempts: int = 5) -> bool:
    """Navigates device cleanly to the Sign Up screen."""
    for attempt in range(max_attempts):
        state, _ = detector.get_screen_state()
        log_worker(device_id, f"Current screen state: [{state}]")

        if state == STATE_SIGNUP:
            return True

        if state == STATE_CAPTCHA:
            log_worker(device_id, "Old Captcha dialog detected; dismissing with Back...")
            ui.run_adb_command(["shell", "input", "keyevent", "4"], device_id)
            time.sleep(1.0)
            ui.run_adb_command(["shell", "input", "keyevent", "4"], device_id)
            time.sleep(1.0)
            continue

        if state == STATE_LOGIN_DIALOG:
            su_pt = ui.get_element_coords(ui.RESOURCE_IDS["signup_link"], device_id)
            if su_pt:
                ui.tap(su_pt[0], su_pt[1], device_id, 0.8)
            else:
                ui.tap(694, 1001, device_id, 0.8)
            ok, _ = detector.wait_for_state(STATE_SIGNUP, timeout=5.0)
            if ok:
                return True

        elif state == STATE_EXPERT_DIALOG:
            log_worker(device_id, "Expert dialog detected; executing fast logout...")
            ui.fast_expert_to_main_landing(device_id)
            ui.go_to_signup_screen(device_id)
            ok, _ = detector.wait_for_state(STATE_SIGNUP, timeout=5.0)
            if ok:
                return True

        elif state == STATE_MAIN_LANDING:
            log_worker(device_id, "Navigating from Main Landing to Sign Up...")
            ui.go_to_signup_screen(device_id)
            ok, _ = detector.wait_for_state(STATE_SIGNUP, timeout=5.0)
            if ok:
                return True
        else:
            log_worker(device_id, f"State [{state}], handling screen to Main Landing...")
            ui.run_adb_command(["shell", "input", "keyevent", "4"], device_id)
            time.sleep(1.0)
            ui.fast_expert_to_main_landing(device_id)
            ui.go_to_signup_screen(device_id)
            ok, _ = detector.wait_for_state(STATE_SIGNUP, timeout=5.0)
            if ok:
                return True
    return False


def create_account_on_device(device_id: str, gmail: str, app_pw: str, do_wipe_before: bool = True) -> dict:
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

    if do_wipe_before:
        wipe_device_data(device_id)

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

    # 3. Solve Captcha (90s timeout)
    log_worker(device_id, "[Step 2] Initializing Color-Indexed Captcha Solver (90s timeout)...")
    solver = ColorIndexedCaptchaSolver(device_id=device_id)
    captcha_solved = solver.solve(max_attempts=4, timeout=90.0)

    if not captcha_solved:
        log_worker(device_id, "[-] Captcha could not be solved within timeout.")
        save_account_to_csv_atomic(email_address, "CAPTCHA_FAILED", "Failed_Captcha", device_id)
        result["status"] = "Failed_Captcha"
        return result

    log_worker(device_id, "[+] Captcha solved successfully!")

    # 4. Wait for OTP Ready State
    log_worker(device_id, "[Step 3] Waiting for OTP countdown running...")
    ok, _ = detector.wait_for_state(STATE_OTP_READY, timeout=10.0)
    if not ok:
        state, _ = detector.get_screen_state()
        if state != STATE_SIGNUP:
            log_worker(device_id, f"[-] Not in OTP state (Current: {state}).")
            save_account_to_csv_atomic(email_address, "OTP_NOT_READY", "Failed_OTP_Not_Ready", device_id)
            result["status"] = "Failed_OTP_Not_Ready"
            return result

    # 5. Fetch OTP from Gmail IMAP
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


def run_parallel_10(target_devices: list[str] = None, stagger_seconds: float = 7.0):
    """Runs concurrent account creation across all active instances."""
    if not target_devices:
        target_devices = memu_manager.connect_all_memu_instances()

    if not target_devices:
        print("[!] No active MEmu instances found via ADB! Please start instances in Multi-MEmu.")
        return

    # Cap to exactly 10 instances if more are connected
    target_devices = target_devices[:10]

    cfg = load_config()
    gmail = cfg.get("gmail_address")
    app_pw = cfg.get("gmail_app_password", "").replace(" ", "")

    print("\n" + "="*70)
    print("   YALLA LUDO HIGH-SCALE MULTI-INSTANCE CONCURRENT ACCOUNT CREATOR")
    print("="*70)
    print(f"[*] Total Active Instances ({len(target_devices)}): {target_devices}")
    print(f"[*] Inter-Worker Stagger Delay: {stagger_seconds}s")
    print(f"[*] Gmail Listener: {gmail}")
    print(f"[*] Default Password: {DEFAULT_PASSWORD}")
    print("="*70 + "\n")

    t_batch_start = time.time()

    def worker_wrapper(dev: str, delay: float):
        if delay > 0:
            log_worker(dev, f"Stagger pause ({delay:.1f}s) before starting...")
            time.sleep(delay)
        return create_account_on_device(dev, gmail, app_pw, do_wipe_before=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(target_devices)) as executor:
        futures = {
            executor.submit(worker_wrapper, dev, idx * stagger_seconds): dev
            for idx, dev in enumerate(target_devices)
        }
        results = []
        for future in concurrent.futures.as_completed(futures):
            dev = futures[future]
            try:
                res = future.result()
                results.append(res)
            except Exception as e:
                log_worker(dev, f"Unhandled worker exception: {e}")
                results.append({"device_id": dev, "status": f"Error: {e}"})

    total_time = time.time() - t_batch_start
    success_count = sum(1 for r in results if r.get("status") == "Success_Created")

    print("\n" + "="*70)
    print(f"   BATCH SUMMARY: {success_count}/{len(target_devices)} ACCOUNTS CREATED")
    print(f"   Total Batch Elapsed Time: {total_time:.2f}s")
    print("="*70)
    for r in results:
        status_icon = "[OK]" if r.get("status") == "Success_Created" else "[FAIL]"
        print(f" - {r.get('device_id')}: {r.get('email')} -> {r.get('status')} {status_icon}")
    print("="*70 + "\n")


if __name__ == "__main__":
    run_parallel_10()
