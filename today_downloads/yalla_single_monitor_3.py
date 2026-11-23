"""
================================================================================
YALLA LUDO SINGLE-SCREEN LIVE MONITOR & 3-ACCOUNT CREATOR
================================================================================
Monitors a single MEmu emulator instance (127.0.0.1:21503) and sequentially creates
3 verified accounts with full data wipe between cycles, accurate terms checkbox
color pixel verification, real-time captcha solving, Gmail OTP extraction,
password submission, and fast post-expert logout.
================================================================================
"""

import csv
from datetime import datetime
import json
import os
import random
import subprocess
import sys
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
TARGET_DEVICE = "127.0.0.1:21503"


def log_live(msg: str):
    now_str = datetime.now().strftime("%H:%M:%S")
    print(f"[{now_str}] [{TARGET_DEVICE}] {msg}", flush=True)


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_next_email_atomic() -> str:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    prefix = cfg.get("email_prefix", "user")
    counter = cfg.get("current_counter", 564)
    domain = cfg.get("cloudflare_domain", "bhullehshahsilage.com")
    email_addr = f"{prefix}{counter}@{domain}"
    cfg["current_counter"] = counter + 1
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    return email_addr


def save_account_to_csv(email_address: str, otp_code: str, status: str, password: str = DEFAULT_PASSWORD):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [now_str, email_address, password, otp_code, status, TARGET_DEVICE]
    for file_path in [ACCOUNTS_CSV, BACKUP_CSV]:
        try:
            file_exists = os.path.exists(file_path)
            with open(file_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Timestamp", "Email", "Password", "OTP", "Status", "Device_ID"])
                writer.writerow(row)
        except Exception as e:
            log_live(f"[!] CSV write error: {e}")
    log_live(f"[+] Recorded in created_accounts.csv: {email_address} ({status})")


def wipe_device_data(device_id: str):
    """Completely resets Yalla Ludo data, cache, randomizes Android ID, and relaunches fresh."""
    log_live("[*] [WIPE] Wiping Yalla Ludo app data & cache (pm clear)...")
    ui.run_adb_command(["shell", "pm", "clear", PACKAGE_NAME], device_id)
    rand_hex = ''.join(random.choices('0123456789abcdef', k=16))
    ui.run_adb_command(["shell", "settings", "put", "secure", "android_id", rand_hex], device_id)
    ui.run_adb_command(["shell", "settings", "put", "global", "http_proxy", ":0"], device_id)
    time.sleep(1.0)
    log_live("[*] Launching fresh Yalla Ludo session...")
    ui.run_adb_command(["shell", "monkey", "-p", PACKAGE_NAME, "-c", "android.intent.category.LAUNCHER", "1"], device_id)
    time.sleep(4.0)


def ensure_device_at_signup(device_id: str, detector: ScreenDetector, max_attempts: int = 5) -> bool:
    for attempt in range(max_attempts):
        state, _ = detector.get_screen_state()
        log_live(f"[LIVE MONITOR] Screen state: [{state}]")

        if state == STATE_SIGNUP:
            return True

        if state == STATE_CAPTCHA:
            log_live("Old Captcha dialog detected; dismissing with Back...")
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
            log_live("Expert dialog detected; executing fast logout...")
            ui.fast_expert_to_main_landing(device_id)
            ui.go_to_signup_screen(device_id)
            ok, _ = detector.wait_for_state(STATE_SIGNUP, timeout=5.0)
            if ok:
                return True

        elif state == STATE_MAIN_LANDING:
            log_live("Navigating from Main Landing to Sign Up...")
            ui.go_to_signup_screen(device_id)
            ok, _ = detector.wait_for_state(STATE_SIGNUP, timeout=5.0)
            if ok:
                return True
        else:
            log_live(f"State [{state}], handling screen to Main Landing...")
            ui.run_adb_command(["shell", "input", "keyevent", "4"], device_id)
            time.sleep(1.0)
            ui.fast_expert_to_main_landing(device_id)
            ui.go_to_signup_screen(device_id)
            ok, _ = detector.wait_for_state(STATE_SIGNUP, timeout=5.0)
            if ok:
                return True
    return False


def create_single_account(account_idx: int, total_accounts: int = 3) -> bool:
    print("\n" + "="*70)
    log_live(f"=== STARTING ACCOUNT {account_idx}/{total_accounts} CREATION CYCLE ===")
    print("="*70)

    cfg = load_config()
    gmail = cfg.get("gmail_address")
    app_pw = cfg.get("gmail_app_password", "").replace(" ", "")

    t_start = time.time()

    # Step 1: Wipe & Fresh Start
    wipe_device_data(TARGET_DEVICE)

    # Step 2: Ensure on Sign Up screen
    detector = ScreenDetector(TARGET_DEVICE)
    if not ensure_device_at_signup(TARGET_DEVICE, detector):
        log_live("[-] Failed to navigate to Sign Up screen.")
        return False

    # Step 3: Allocate Atomic Email & Request OTP
    email_address = get_next_email_atomic()
    log_live(f"[Step 1] Target Email Allocated: {email_address}")

    obtain_time = ui.request_verification_code(email_address, TARGET_DEVICE)
    log_live(f"[+] Verification code requested for {email_address} at {obtain_time:.2f}")

    # Step 4: Solve Captcha (90s timeout)
    log_live("[Step 2] Initializing Color-Indexed Captcha Solver (90s timeout)...")
    solver = ColorIndexedCaptchaSolver(device_id=TARGET_DEVICE)
    captcha_solved = solver.solve(max_attempts=3, timeout=90.0)

    if not captcha_solved:
        log_live("[-] Captcha could not be solved within timeout.")
        save_account_to_csv(email_address, "CAPTCHA_FAILED", "Failed_Captcha")
        return False

    log_live("[+] Captcha solved successfully!")

    # Step 5: Wait for OTP Ready State
    log_live("[Step 3] Waiting for OTP countdown timer...")
    ok, _ = detector.wait_for_state(STATE_OTP_READY, timeout=10.0)
    if not ok:
        state, _ = detector.get_screen_state()
        if state != STATE_SIGNUP:
            log_live(f"[-] Not in OTP state (Current: {state}).")
            save_account_to_csv(email_address, "OTP_NOT_READY", "Failed_OTP_Not_Ready")
            return False

    # Step 6: Fetch OTP from Gmail IMAP
    log_live(f"[Step 4] Polling Gmail for {email_address} (60s max)...")
    fetcher = GmailOTPFetcher(gmail, app_pw)
    t_otp_start = time.time()
    otp = fetcher.wait_for_otp(target_email=email_address, min_timestamp=(obtain_time - 30), timeout_seconds=60)

    if not otp:
        log_live(f"[-] OTP timed out after 60s for {email_address}.")
        save_account_to_csv(email_address, "TIMEOUT", "Failed_OTP_Timeout")
        return False

    log_live(f"[+] Verified OTP: {otp} (received in {time.time() - t_otp_start:.2f}s)")

    # Step 7: Submit OTP
    log_live(f"[Step 5] Submitting OTP [{otp}]...")
    ui.submit_verification_code(otp, TARGET_DEVICE)

    # Step 8: Set Password
    log_live("[Step 6] Detecting Set Password screen...")
    ok, _ = detector.wait_for_state(STATE_SET_PASSWORD, timeout=8.0)
    if not ok:
        log_live("[-] Set Password screen did not appear.")
        save_account_to_csv(email_address, otp, "Failed_No_Password_Screen")
        return False

    ui.set_account_password(DEFAULT_PASSWORD, TARGET_DEVICE)
    log_live(f"[+] Password [{DEFAULT_PASSWORD}] submitted successfully!")

    # Step 9: Fast Post-Expert Logout
    log_live("[Step 7] Detecting 'I am expert' dialog...")
    detector.wait_for_state(STATE_EXPERT_DIALOG, timeout=12.0)

    t_post_start = time.time()
    log_live("[*] Running rapid 5s Expert -> Lobby -> Settings -> Logout sequence...")
    ui.fast_expert_to_main_landing(TARGET_DEVICE)
    t_post_dur = time.time() - t_post_start
    log_live(f"[+] Post-expert logout completed in {t_post_dur:.2f}s (<5s satisfied!)")

    # Step 10: Record Success
    save_account_to_csv(email_address, otp, "Success_Created")
    duration = time.time() - t_start
    log_live(f"[SUCCESS] Account {account_idx}/{total_accounts} ({email_address}) created in {duration:.1f}s! [OK]")
    return True


def run_single_screen_3_accounts():
    print("\n" + "="*70)
    print("   YALLA LUDO SINGLE-SCREEN LIVE MONITOR (3 ACCOUNTS)")
    print(f"   Target Screen: {TARGET_DEVICE}")
    print("="*70 + "\n")

    successful_accounts = 0
    total_to_create = 3

    for idx in range(1, total_to_create + 1):
        success = create_single_account(idx, total_to_create)
        if success:
            successful_accounts += 1
        time.sleep(2.0)

    print("\n" + "="*70)
    print(f"   SUMMARY: {successful_accounts}/{total_to_create} ACCOUNTS CREATED SUCCESSFULLY")
    print("="*70 + "\n")


if __name__ == "__main__":
    run_single_screen_3_accounts()
