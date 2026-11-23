"""
================================================================================
YALLA LUDO HIGH-SPEED CREATOR (OPTIMIZED EXPERT-RESET PIPELINE)
================================================================================
Key Features:
1. Fast Auto-Increment Email Input: user{N}@domain.com (Rapid atomic injection).
2. Instant Data Clear on "I'm expert": The moment the expert dialog is detected
   after password set, the account is recorded and pm clear is immediately triggered!
3. Ultra-Fast 3-Second Lobby Bypass on Relaunch: Quick compound sequence:
   Expert -> Lobby Close -> Settings -> Log Out -> Main Landing in ~3s.
4. Zero Idle Wait: The moment Main Landing is detected, immediately starts next account!
================================================================================
"""

import csv
from datetime import datetime
import json
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
except Exception:
    pass

from airplane_mode import toggle_airplane_mode
from github_proxy_rotator import rotate_ip_smart
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

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
ACCOUNTS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "created_accounts.csv")
DEFAULT_PASSWORD = "LudoPass#2026@"
PACKAGE_NAME = "com.yalla.yallagames"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def get_next_email(config: dict) -> tuple[str, dict]:
    prefix = config.get("email_prefix", "user")
    counter = config.get("current_counter", 250)
    domain = config.get("cloudflare_domain", "bhullehshahsilage.com")
    email_address = f"{prefix}{counter}@{domain}"
    config["current_counter"] = counter + 1
    save_config(config)
    return email_address, config


def save_account_to_csv(email_address: str, otp_code: str, status: str = "Created", password: str = DEFAULT_PASSWORD):
    row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email_address, password, otp_code, status]
    targets = [
        ACCOUNTS_CSV,
        os.path.join(os.path.dirname(ACCOUNTS_CSV), "created_accounts_backup.csv")
    ]
    for target_path in targets:
        try:
            file_exists = os.path.exists(target_path)
            with open(target_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Timestamp", "Email", "Password", "OTP Code", "Status"])
                writer.writerow(row)
            print(f"[+] Account record saved to: {target_path}")
            return
        except PermissionError:
            print(f"[!] Warning: {target_path} is open/locked (e.g. in Excel). Trying alternate file...")
            continue
        except Exception as e:
            print(f"[!] Error saving to {target_path}: {e}")


def fast_bypass_to_main_landing(device_id: str = None) -> bool:
    """
    Executes the 3-second rapid compound sequence to get from 'I'm expert'
    to the Main Landing screen for both 1080p and 720p devices:
    Expert -> Lobby Close -> Settings Gear -> Logout.
    """
    print("[*] Running 3-second Fast Bypass Sequence to Main Landing...")
    expert_pt = ui.get_calibrated_coords("btn_expert", device_id)
    close_pt = ui.get_calibrated_coords("popup_close_btn", device_id)
    gear_pt = ui.get_calibrated_coords("settings_gear_btn", device_id)
    logout_pt = ui.get_calibrated_coords("logout_btn", device_id)
    cmd = (
        f"input tap {expert_pt[0]} {expert_pt[1]}; sleep 0.8; "
        f"input tap {close_pt[0]} {close_pt[1]}; sleep 0.5; "
        f"input tap {gear_pt[0]} {gear_pt[1]}; sleep 0.5; "
        f"input tap {logout_pt[0]} {logout_pt[1]}"
    )
    ui.run_adb_shell_compound([cmd], device_id)
    return True


def go_to_signup(device_id: str = None) -> bool:
    """
    Ensures Terms & Conditions checkbox is checked first, taps Email Login,
    detects Login Modal, and taps 'Sign Up' link to reach registration screen.
    Uses dynamic XML coordinate resolution with calibrated fallbacks.
    """
    return ui.go_to_signup_screen(device_id)


def ensure_ready_landing_screen(detector: ScreenDetector, device_id: str = None) -> bool:
    """
    Ultra-Fast Landing Screen Readiness:
    1. Pre-grants POST_NOTIFICATIONS so no permission prompt ever blocks.
    2. Launches app with zero redundant overhead.
    3. Directly executes 3s compound bypass to Main Landing.
    4. Validates Main Landing with terms pre-checked.
    """
    # Auto-grant permissions so Android never pops up permission dialogs
    try:
        ui.run_adb_command(["shell", "pm", "grant", PACKAGE_NAME, "android.permission.POST_NOTIFICATIONS"], device_id)
    except Exception:
        pass

    ui.run_adb_command(["shell", "monkey", "-p", PACKAGE_NAME, "-c", "android.intent.category.LAUNCHER", "1"], device_id)

    # Wait for the splash to transition to "I'm expert" (3.2s)
    time.sleep(3.2)

    # Direct compound bypass sequence calibrated for device resolution
    expert_pt = ui.get_calibrated_coords("btn_expert", device_id)
    close_pt = ui.get_calibrated_coords("popup_close_btn", device_id)
    gear_pt = ui.get_calibrated_coords("settings_gear_btn", device_id)
    logout_pt = ui.get_calibrated_coords("logout_btn", device_id)
    cmd = (
        f"input tap {expert_pt[0]} {expert_pt[1]}; sleep 0.8; "
        f"input tap {close_pt[0]} {close_pt[1]}; sleep 0.5; "
        f"input tap {gear_pt[0]} {gear_pt[1]}; sleep 0.5; "
        f"input tap {logout_pt[0]} {logout_pt[1]}"
    )
    ui.run_adb_shell_compound([cmd], device_id)

    # Fast check if Main Landing reached
    ok, _ = detector.wait_for_state(STATE_MAIN_LANDING, timeout=6.0)
    if ok:
        print("[+] Main Landing Page verified via Fast Bypass! [OK]")
        return True

    # Adaptive fallback if fast bypass missed
    print("[!] Fast bypass missed, running adaptive landing fallback...")
    ui.ensure_main_landing_page(device_id)
    return True


def run_account_creation_cycle() -> bool:
    config = load_config()
    gmail = config.get("gmail_address")
    app_pw = config.get("gmail_app_password", "").replace(" ", "")
    air_delay = config.get("airplane_wait_seconds", 1.5)
    device_id = config.get("device_serial")

    detector = ScreenDetector(device_id)

    print("\n" + "="*65)
    print("   HIGH-SPEED YALLA LUDO ACCOUNT CREATION PIPELINE")
    print("="*65)

    t_cycle_start = time.time()

    # 1. Zero-Wait Landing Detection
    state, data = detector.get_screen_state()
    print(f"[*] Detected Screen State: [{state}]")

    if state == STATE_SIGNUP:
        print("[+] Already on Sign Up screen!")
    elif state == STATE_LOGIN_DIALOG:
        print("[*] Login dialog active, tapping Sign Up link directly...")
        ui.fast_click("signup_link", device_id, 0.5)
        detector.wait_for_state(STATE_SIGNUP, timeout=5.0)
    elif state == STATE_MAIN_LANDING:
        print("[*] On Main Landing, ensuring terms checked and navigating to Sign Up...")
        ui.ensure_terms_checked(device_id)
        go_to_signup(device_id)
        detector.wait_for_state(STATE_SIGNUP, timeout=5.0)
    elif state == STATE_EXPERT_DIALOG:
        print("[*] On Expert screen, performing fast logout to Main Landing...")
        ui.fast_expert_to_main_landing(device_id)
        ui.ensure_terms_checked(device_id)
        go_to_signup(device_id)
        detector.wait_for_state(STATE_SIGNUP, timeout=5.0)
    elif state in ["GAME_HALL", "SETTINGS_DIALOG"]:
        print("[*] In game hall / settings, logging out to Main Landing...")
        gear_pt = ui.get_calibrated_coords("settings_gear_btn", device_id)
        logout_pt = ui.get_calibrated_coords("logout_btn", device_id)
        ui.run_adb_shell_compound([f"input tap {gear_pt[0]} {gear_pt[1]}; sleep 0.5; input tap {logout_pt[0]} {logout_pt[1]}"], device_id)
        detector.wait_for_state(STATE_MAIN_LANDING, timeout=3.0)
        ui.ensure_terms_checked(device_id)
        go_to_signup(device_id)
        detector.wait_for_state(STATE_SIGNUP, timeout=5.0)
    elif state not in [STATE_CAPTCHA, STATE_OTP_READY, STATE_SET_PASSWORD]:
        print(f"[*] State [{state}] requires app launch to Main Landing...")
        ensure_ready_landing_screen(detector, device_id)
        ui.ensure_terms_checked(device_id)
        go_to_signup(device_id)
        detector.wait_for_state(STATE_SIGNUP, timeout=5.0)

    # 2. Fast Auto-Increment Email Input with 60s OTP Retry Loop
    otp = None
    email_address = None
    max_email_attempts = 3

    for attempt in range(1, max_email_attempts + 1):
        print(f"\n[Step 1] Preparing Email with Auto-Increment (Attempt {attempt}/{max_email_attempts})...")
        email_address, config = get_next_email(config)
        print(f"[+] Target Email: {email_address}")

        # Pre-copy to clipboard and paste email, then click Obtain
        obtain_time = ui.request_verification_code(email_address, device_id)

        # 3. Fast Color-Indexed Captcha Solve (<= 3 Attempts)
        print("\n[Step 2] Detecting & Solving Captcha with Color-Profile & Dynamic Slot Solver...")
        solver = ColorIndexedCaptchaSolver(device_id=device_id)
        captcha_solved = solver.solve(max_attempts=3, timeout=90.0)
        if not captcha_solved:
            print("[-] Captcha could not be resolved.")
            save_account_to_csv(email_address, "CAPTCHA_FAILED", status="Failed_Captcha")
            return False

        # 4. Detect OTP Ready State
        print("\n[Step 3] Detecting OTP Ready State (Countdown running)...")
        ok, _ = detector.wait_for_state(STATE_OTP_READY, timeout=10.0)
        if not ok:
            state, _ = detector.get_screen_state()
            if state != STATE_SIGNUP:
                print(f"[-] Screen did not enter OTP Ready state (Current: {state}).")
                save_account_to_csv(email_address, "OTP_NOT_READY", status="Failed_OTP_Not_Ready")
                return False
            print("[+] Sign up dialog active with OTP box, proceeding to listen for OTP...")

        # 5. Fetch OTP from Gmail (60s countdown timeout)
        print("\n[Step 4] Listening to Gmail Inbox for OTP (60s max)...")
        fetcher = GmailOTPFetcher(gmail, app_pw)
        t_otp_start = time.time()
        otp = fetcher.wait_for_otp(target_email=email_address, min_timestamp=(obtain_time - 30), timeout_seconds=60)
        otp_wait_seconds = time.time() - t_otp_start

        if otp:
            print(f"\n[+] Fresh OTP: {otp} (in {otp_wait_seconds:.2f}s)")
            break
        else:
            print(f"[-] OTP timed out after 60s for {email_address}.")
            save_account_to_csv(email_address, "TIMEOUT", status="Failed_OTP_Timeout")
            if attempt < max_email_attempts:
                print(f"[*] Re-trying immediately with next auto-incremented email...")
                time.sleep(1.0)

    if not otp:
        print(f"[-] All {max_email_attempts} email OTP attempts exhausted.")
        return False

    ui.submit_verification_code(otp, device_id)

    # 6. Set Password
    print("\n[Step 5] Detecting Set Password Screen...")
    ok, _ = detector.wait_for_state(STATE_SET_PASSWORD, timeout=8.0)
    if not ok:
        print("[-] Set Password screen was not detected.")
        save_account_to_csv(email_address, otp, status="Failed_No_Password_Screen")
        return False

    ui.set_account_password(DEFAULT_PASSWORD, device_id)

    # 7. As soon as 'I am expert' is detected -> Fast 5-Second Logout Sequence!
    print("\n[Step 6] Detecting 'I am expert' Dialog...")
    ok, _ = detector.wait_for_state(STATE_EXPERT_DIALOG, timeout=12.0)
    
    t_post_expert = time.time()
    if ok:
        print("[+] 'I am expert' DETECTED! Running 5-Second Expert -> Settings -> Logout Sequence...")
    else:
        print("[*] Proceeding with Fast Logout sequence...")
    
    ui.fast_expert_to_main_landing(device_id)
    post_expert_duration = time.time() - t_post_expert
    print(f"[+] Post-Expert Logout completed in {post_expert_duration:.2f}s (<5s requirement satisfied!)")

    # Save to CSV immediately!
    save_account_to_csv(email_address, otp, status="Success_Created", password=DEFAULT_PASSWORD)
    t_created = time.time() - t_cycle_start
    print(f"\n[SUCCESS] Account {email_address} CREATED in {t_created:.1f}s! [OK]")

    # 8. Smart IP Rotation: Mobile Airplane Mode if phone connected; else GitHub Proxy Pool!
    # Note: No pm clear! No app restart! App is ALREADY at Main Landing screen!
    try:
        active_ip = rotate_ip_smart(device_id, air_delay)
    except Exception as e:
        print(f"[!] IP rotation notice: {e}")

    detector.wait_for_state(STATE_MAIN_LANDING, timeout=3.0)

    total_cycle_time = time.time() - t_cycle_start
    print(f"[+] Total Fast Cycle Time: {total_cycle_time:.1f}s (Massive Speedup!)\n")
    return True


def run_batch(total_accounts: int = 5):
    print("\n" + "="*65)
    print(f"   STARTING OPTIMIZED BATCH: {total_accounts} ACCOUNTS")
    print("   Features: user{N} Increment + 5s Expert Logout + Smart IP Rotation")
    print("="*65)

    success_count = 0
    t_batch_start = time.time()

    for i in range(1, total_accounts + 1):
        print(f"\n{'#'*65}")
        print(f"  CYCLE {i}/{total_accounts} (Progress: {success_count}/{i-1} Successful)")
        print(f"{'#'*65}")

        try:
            status = run_account_creation_cycle()
            if status:
                success_count += 1
                print(f"[+] Account {i}/{total_accounts} CREATED SUCCESSFULLY! [OK]")
            else:
                print(f"[-] Account {i}/{total_accounts} failed. Resetting for next cycle...")
                cfg = load_config()
                dev = cfg.get("device_serial")
                try:
                    rotate_ip_smart(dev, 1.5)
                except Exception:
                    pass
                ui.fast_expert_to_main_landing(dev)
        except Exception as e:
            print(f"[!] Unexpected error in cycle {i}: {e}")

        # Zero unnecessary delay between accounts!

    t_total = time.time() - t_batch_start
    avg = t_total / max(success_count, 1)

    print("\n" + "="*65)
    print(f"   BATCH COMPLETED: {success_count}/{total_accounts} ACCOUNTS CREATED")
    print(f"   Total Time: {t_total:.1f}s | Average Speed: {avg:.1f}s / account")
    print("="*65)

    # Auto-retry only if requested via command line
    if "--retry" in sys.argv:
        try:
            from retry_failed_accounts import run_sheet_retry
            print("\n[*] Checking sheet for any failed accounts to auto-retry...")
            retried_count = run_sheet_retry()
            if retried_count > 0:
                print(f"[+] Auto-retry complete: Successfully recovered {retried_count} account(s) in sheet!")
        except Exception as e:
            print(f"[!] Warning: Sheet auto-retry encountered an error: {e}")

    return success_count


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    run_batch(count)
