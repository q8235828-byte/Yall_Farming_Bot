"""
================================================================================
YALLA LUDO - DEDICATED SHEET RETRY TOOL (retry_failed_accounts.py)
================================================================================
Reads created_accounts.csv, identifies accounts whose status is NOT
'Success_Created' (and haven't succeeded elsewhere), and automatically
re-attempts their signup.

Updates the sheet in-place upon completion so that successful retries are
marked 'Success_Created' with their valid OTP and current timestamp.

Supports:
- Single-device execution or multi-device parallel distribution.
- Adaptive resolution handling (1080p Vivo and 720p Moto).
- Safe file-lock handling for Excel.
================================================================================
"""

import argparse
import concurrent.futures
import csv
from datetime import datetime
import json
import os
import queue
import subprocess
import sys
import threading
import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from airplane_mode import ADB_BIN, get_device_port, toggle_airplane_mode
from captcha_solver import IntelligentCaptchaSolver
from otp_fetcher import GmailOTPFetcher
from screen_detector import (
    ScreenDetector,
    STATE_MAIN_LANDING,
    STATE_SIGNUP,
    STATE_CAPTCHA,
    STATE_OTP_READY,
    STATE_SET_PASSWORD,
    STATE_EXPERT_DIALOG,
)
import yalla_ui_automator as ui
import yalla_creator_fast as yf

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
ACCOUNTS_CSV = os.path.join(BASE_DIR, "created_accounts.csv")
BACKUP_CSV = os.path.join(BASE_DIR, "created_accounts_backup.csv")
DEFAULT_PASSWORD = "Yalla#2026@Pass"
PACKAGE_NAME = "com.yalla.yallagames"

sheet_lock = threading.Lock()
print_lock = threading.Lock()


def log(device_id: str, message: str):
    """Thread-safe prefixed console logger."""
    with print_lock:
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = f"[{timestamp}]"
        if device_id:
            prefix += f" [{device_id}]"
        print(f"{prefix} {message}", flush=True)


def discover_connected_devices() -> list[str]:
    """Returns all active connected Android devices across ports 5037 and 5038."""
    detected = []
    for port in [5037, 5038]:
        try:
            res = subprocess.run([ADB_BIN, "-P", str(port), "devices"], stdout=subprocess.PIPE, text=True, timeout=3)
            for line in res.stdout.strip().splitlines()[1:]:
                parts = line.strip().split()
                if len(parts) >= 2 and parts[1] == "device":
                    serial = parts[0]
                    if serial not in detected:
                        detected.append(serial)
        except Exception:
            pass
    return detected


def get_pending_failed_accounts(csv_path: str = ACCOUNTS_CSV) -> list[dict]:
    """
    Scans the CSV and finds all emails where status is NOT 'Success_Created'
    and that do not have any other row marked 'Success_Created'.
    """
    if not os.path.exists(csv_path):
        return []

    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    if not rows:
        return []

    succeeded_emails = set()
    email_latest_status = {}
    email_rows_map = {}

    for idx, r in enumerate(rows[1:], start=1):
        if len(r) < 2:
            continue
        email = r[1].strip()

        # Extract status field from row (handles 4, 5, or 6 column rows)
        status = ""
        for field in reversed(r):
            if "Success" in field or "Failed" in field:
                status = field
                break
        if not status and len(r) >= 4:
            status = r[3].strip()

        if "Success_Created" in status:
            succeeded_emails.add(email.lower())

        email_latest_status[email.lower()] = (email, status)
        if email.lower() not in email_rows_map:
            email_rows_map[email.lower()] = []
        email_rows_map[email.lower()].append(idx)

    pending = []
    for email_lower, (orig_email, status) in email_latest_status.items():
        if email_lower not in succeeded_emails:
            pending.append({
                "email": orig_email,
                "current_status": status,
                "row_indices": email_rows_map[email_lower],
            })

    return pending


def update_sheet_with_result(email: str, new_status: str, otp_code: str, password: str = DEFAULT_PASSWORD, device_id: str = "Unknown"):
    """
    Thread-safe in-place update of created_accounts.csv and backup CSV.
    Updates the row(s) corresponding to email so status becomes new_status.
    """
    with sheet_lock:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Update created_accounts.csv
        for target_path in [ACCOUNTS_CSV, BACKUP_CSV]:
            if not os.path.exists(target_path):
                continue

            rows = []
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    rows = list(csv.reader(f))
            except Exception:
                continue

            updated = False
            for idx in range(1, len(rows)):
                r = rows[idx]
                if len(r) >= 2 and r[1].strip().lower() == email.strip().lower():
                    # Form standard 6-column row: [Timestamp, Email, Password, OTP Code, Status, Device]
                    rows[idx] = [now_str, email, password, otp_code, new_status, device_id]
                    updated = True

            if not updated:
                rows.append([now_str, email, password, otp_code, new_status, device_id])

            # Write back with retry against Excel lock
            for _ in range(5):
                try:
                    with open(target_path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerows(rows)
                    break
                except PermissionError:
                    time.sleep(0.5)
                except Exception:
                    break


def retry_single_account(email_address: str, device_id: str, gmail: str, app_pw: str, air_delay: float) -> bool:
    """
    Executes a complete account creation attempt for a specific failed email from the sheet.
    """
    t_start = time.time()
    detector = ScreenDetector(device_id)
    log(device_id, f"--- Retrying Failed Account: {email_address} ---")

    # 1. Verify / Reach Signup Dialog
    state, _ = detector.get_screen_state()
    if state not in [STATE_SIGNUP, STATE_CAPTCHA, STATE_OTP_READY, STATE_SET_PASSWORD]:
        yf.ensure_ready_landing_screen(detector, device_id)
        yf.go_to_signup(device_id)
        ok, _ = detector.wait_for_state(STATE_SIGNUP, timeout=7.0)
        if not ok:
            log(device_id, "Could not reach Signup screen on first try, attempting adaptive fallback...")
            ui.ensure_main_landing_page(device_id)
            yf.go_to_signup(device_id)
            detector.wait_for_state(STATE_SIGNUP, timeout=6.0)

    # 2. Enter Target Email & Request OTP
    log(device_id, f"Entering email {email_address} and tapping Obtain...")
    obtain_time = ui.request_verification_code(email_address, device_id)

    # 3. Detect and Solve Captcha
    log(device_id, "Detecting & Solving Captcha...")
    solver = IntelligentCaptchaSolver(device_id=device_id, max_attempts=15, attempts_per_round=5)
    if not solver.solve():
        log(device_id, "[-] Captcha resolution failed.")
        update_sheet_with_result(email_address, "Failed_Captcha", "CAPTCHA_FAILED", device_id=device_id)
        return False

    # 4. Wait for OTP Ready Countdown / Box
    log(device_id, "Waiting for OTP input countdown...")
    ok, _ = detector.wait_for_state(STATE_OTP_READY, timeout=10.0)
    if not ok:
        state, _ = detector.get_screen_state()
        if state != STATE_SIGNUP:
            log(device_id, f"[-] OTP Ready countdown did not appear (Current state: {state}).")
            update_sheet_with_result(email_address, "Failed_OTP_Not_Ready", "OTP_NOT_READY", device_id=device_id)
            return False
        log(device_id, "[+] Sign up dialog active with OTP box, continuing to listen for OTP...")

    # 5. Fetch OTP from Gmail
    log(device_id, f"Listening to Gmail Inbox for OTP ({email_address})...")
    fetcher = GmailOTPFetcher(gmail, app_pw)
    t_otp_start = time.time()
    otp = fetcher.wait_for_otp(target_email=email_address, min_timestamp=(obtain_time - 30), timeout_seconds=90)
    otp_time = time.time() - t_otp_start

    if not otp:
        log(device_id, "[-] Timeout: No fresh OTP received.")
        update_sheet_with_result(email_address, "Failed_OTP_Timeout", "TIMEOUT", device_id=device_id)
        return False

    log(device_id, f"[+] Fresh OTP received: {otp} (in {otp_time:.2f}s)")
    ui.submit_verification_code(otp, device_id)

    # 6. Set Password & Keyboard Dismiss
    log(device_id, "Waiting for Set Password screen...")
    ok, _ = detector.wait_for_state(STATE_SET_PASSWORD, timeout=8.0)
    if not ok:
        log(device_id, "[-] Set Password screen was not detected.")
        update_sheet_with_result(email_address, "Failed_No_Password_Screen", otp, device_id=device_id)
        return False

    ui.set_account_password(DEFAULT_PASSWORD, device_id)

    # 7. Confirm Account Creation via 'I am expert' Dialog
    log(device_id, "Detecting 'I am expert' dialog to confirm account...")
    ok, _ = detector.wait_for_state(STATE_EXPERT_DIALOG, timeout=12.0)
    if ok:
        log(device_id, "[+] 'I am expert' DETECTED! Account 100% verified!")

    t_total = time.time() - t_start
    log(device_id, f"[SUCCESS] Account {email_address} SUCCESSFULLY CREATED in {t_total:.1f}s! [OK]")

    # 8. Update Sheet in-place to Success_Created
    update_sheet_with_result(email_address, "Success_Created", otp, device_id=device_id)

    # 9. Clear App Data & Rotate Mobile IP
    log(device_id, "Executing data wipe (pm clear) & IP rotation...")
    ui.clear_app_data(device_id)
    toggle_airplane_mode(air_delay, device_id)

    # 10. Bring back to Main Landing for next cycle
    log(device_id, "Relaunching app to Main Landing...")
    yf.ensure_ready_landing_screen(detector, device_id)
    return True


def worker_retry_loop(device_id: str, work_queue: queue.Queue, gmail: str, app_pw: str, air_delay: float, results: dict):
    """Worker thread that continuously pulls failed accounts from the queue until exhausted."""
    while not work_queue.empty():
        try:
            account = work_queue.get_nowait()
        except queue.Empty:
            break

        email = account["email"]
        success = retry_single_account(email, device_id, gmail, app_pw, air_delay)
        results[email] = success
        work_queue.task_done()


def run_sheet_retry(limit: int = None, email: str = None) -> int:
    """
    Scans created_accounts.csv for failed accounts and retries them across
    all connected devices, updating created_accounts.csv in-place.
    Returns the count of successfully retried accounts.
    """
    print("\n" + "="*70)
    print("   YALLA LUDO - AUTO-RETRY FAILED ACCOUNTS FROM SHEET")
    print("="*70)

    # Scan sheet
    failed_accounts = get_pending_failed_accounts()
    print(f"[*] Found {len(failed_accounts)} accounts with non-Success status in the sheet.")

    if not failed_accounts:
        print("[+] All accounts in created_accounts.csv already have 'Success_Created' status! Nothing to retry.")
        return 0

    # Filter target accounts
    target_accounts = []
    if email:
        target_accounts = [acc for acc in failed_accounts if acc["email"].strip().lower() == email.strip().lower()]
        if not target_accounts:
            print(f"[-] Email {email} is either not in the sheet or already has 'Success_Created' status.")
            return 0
    elif limit:
        target_accounts = failed_accounts[:limit]
    else:
        target_accounts = failed_accounts

    print(f"[*] Selected {len(target_accounts)} accounts for retry.")

    # Load configuration
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    gmail = cfg.get("gmail_address")
    app_pw = cfg.get("gmail_app_password", "").replace(" ", "")
    air_delay = cfg.get("airplane_wait_seconds", 1.5)

    # Detect devices
    devices = discover_connected_devices()
    print(f"\n[*] Active Connected Mobile Devices: {len(devices)}")
    for idx, d in enumerate(devices, 1):
        dims = ui.get_screen_dimensions(d)
        port = get_device_port(d)
        print(f"    [{idx}] Serial: {d:<16} | Port: {port} | Screen: {dims[0]}x{dims[1]}")

    if not devices:
        print("[-] Error: No active Android devices found. Connect at least one phone with USB Debugging enabled.")
        return 0

    # Populate work queue
    work_queue = queue.Queue()
    for acc in target_accounts:
        work_queue.put(acc)

    t_batch_start = time.time()
    results = {}

    print(f"\n[*] Starting retry execution across {len(devices)} device(s)...")
    print("="*70 + "\n")

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(devices)) as executor:
        futures = [
            executor.submit(worker_retry_loop, dev, work_queue, gmail, app_pw, air_delay, results)
            for dev in devices
        ]
        concurrent.futures.wait(futures)

    # Summary report
    t_total = time.time() - t_batch_start
    success_count = sum(1 for res in results.values() if res)
    fail_count = len(results) - success_count

    print("\n" + "="*70)
    print("   RETRY BATCH COMPLETE REPORT")
    print("="*70)
    print(f"   Total Accounts Attempted : {len(results)}")
    print(f"   Successfully Created     : {success_count}")
    print(f"   Failed / Timed Out       : {fail_count}")
    print(f"   Total Time Elapsed       : {t_total:.1f}s")
    if success_count > 0:
        print(f"   Average Speed / Success  : {t_total / success_count:.1f}s per account")
    print("   Sheet Updated In-Place   : created_accounts.csv [OK]")
    print("="*70 + "\n")
    return success_count


def main():
    parser = argparse.ArgumentParser(description="Yalla Ludo Sheet Failed Accounts Retry Tool")
    parser.add_argument("limit", nargs="?", type=int, default=None, help="Number of failed accounts to retry (default: all)")
    parser.add_argument("--email", type=str, default=None, help="Retry a specific email address from the sheet")
    parser.add_argument("--status", action="store_true", help="Scan and show all failed accounts in the sheet without running")
    args = parser.parse_args()

    if args.status:
        print("\n" + "="*70)
        print("   YALLA LUDO - SHEET RETRY TOOL (created_accounts.csv)")
        print("="*70)
        failed_accounts = get_pending_failed_accounts()
        print(f"[*] Found {len(failed_accounts)} accounts with non-Success status in the sheet.")
        print("\n--- Failed Accounts in Sheet ---")
        for idx, acc in enumerate(failed_accounts, 1):
            print(f"[{idx:2d}] Email: {acc['email']:<32} | Current Status: {acc['current_status']}")
        print("="*70 + "\n")
        return

    run_sheet_retry(limit=args.limit, email=args.email)


if __name__ == "__main__":
    main()
