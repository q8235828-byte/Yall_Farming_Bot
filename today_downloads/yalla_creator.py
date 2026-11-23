import csv
from datetime import datetime
import json
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from airplane_mode import run_adb_command, toggle_airplane_mode
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
    STATE_LOBBY_POPUP,
    STATE_GAME_HALL,
    STATE_SETTINGS_DIALOG,
)
import yalla_ui_automator as ui

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
ACCOUNTS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "created_accounts.csv")
DEFAULT_PASSWORD = "Yalla#2026@Pass"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def get_next_email(config: dict) -> tuple[str, dict]:
    prefix = config.get("email_prefix", "user")
    counter = config.get("current_counter", 101)
    domain = config.get("cloudflare_domain", "bhullehshahsilage.com")
    
    email_address = f"{prefix}{counter}@{domain}"
    config["current_counter"] = counter + 1
    save_config(config)
    return email_address, config


def save_account_to_csv(email_address: str, otp_code: str, status: str = "Created", password: str = DEFAULT_PASSWORD):
    row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email_address, password, otp_code, status]
    target_path = ACCOUNTS_CSV
    
    for attempt in range(3):
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
            print(f"[!] Warning: {target_path} is open in Excel/another program. Retrying...")
            time.sleep(1.0)
            target_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "created_accounts_session.csv")
    
    print(f"[!] Saved record to backup session file: {target_path}")


def run_account_creation_cycle() -> bool:
    """
    Smart Screen-Resumed Account Creation Pipeline:
    Detects current screen state dynamically and starts right from the active screen!
    """
    config = load_config()
    gmail = config.get("gmail_address")
    app_pw = config.get("gmail_app_password", "").replace(" ", "")
    air_delay = config.get("airplane_wait_seconds", 1.5)
    device_id = config.get("device_serial")

    detector = ScreenDetector(device_id)

    print("\n" + "="*65)
    print("   SMART RESUME YALLA ACCOUNT CREATION PIPELINE")
    print("="*65)

    t_cycle_start = time.time()
    otp_wait_seconds = 0.0

    # 1. DETECT CURRENT SCREEN IMMEDIATELY TO RESUME
    state, data = detector.get_screen_state()
    print(f"[*] Initial Detected Screen State: [{state}]")

    email_address = None
    otp = None

    # Check if we are already on Sign Up with OTP filled in
    if state in [STATE_SIGNUP, STATE_OTP_READY]:
        tree = detector.dump_ui_tree()
        cur_email = ""
        cur_otp = ""
        if tree is not None:
            for node in tree.iter("node"):
                rid = node.get("resource-id", "")
                txt = node.get("text", "")
                if "phone_number_sign" in rid and "@" in txt:
                    cur_email = txt
                elif "verification_code_sign" in rid and len(txt) == 6 and txt.isdigit():
                    cur_otp = txt

        if cur_otp:
            print(f"[+] Screen already has OTP [{cur_otp}] filled for [{cur_email}]! Resuming directly from Confirm...")
            email_address = cur_email or f"user{config.get('current_counter', 101)}@{config.get('cloudflare_domain')}"
            otp = cur_otp
            
            # Dismiss keyboard so Yellow Confirm button is completely visible
            ui.keyevent(111, device_id, 0.25)
            time.sleep(0.3)
            confirm_pt = ui.get_element_coords(ui.RESOURCE_IDS["signup_confirm_btn"], device_id)
            if not confirm_pt:
                confirm_pt = ui.get_calibrated_coords("signup_confirm_btn", device_id)
            print(f"[*] Tapping yellow Confirm button at {confirm_pt}...")
            ui.tap(confirm_pt[0], confirm_pt[1], device_id, 0.5)

    if not otp:
        # Standard flow if not resuming with OTP
        if state not in [STATE_SIGNUP, STATE_CAPTCHA, STATE_OTP_READY, STATE_SET_PASSWORD, STATE_EXPERT_DIALOG]:
            print("\n[Step 1] Navigating to Sign Up Screen...")
            ui.ensure_main_landing_page(device_id)
            detector.wait_for_state(STATE_MAIN_LANDING, timeout=6.0)
            ui.ensure_terms_checked(device_id)
            ui.go_to_signup_screen(device_id)
            detector.wait_for_state(STATE_SIGNUP, timeout=6.0)

        # If on Sign Up screen without email/obtain
        if state == STATE_SIGNUP or state == STATE_MAIN_LANDING or not email_address:
            print("\n[Step 2] Preparing new Email & Requesting Code...")
            email_address, config = get_next_email(config)
            print(f"[+] Target Email: {email_address}")
            obtain_time = ui.request_verification_code(email_address, device_id)
        else:
            obtain_time = time.time()

        # Step 3: Always Detect & Solve Captcha
        print("\n[Step 3] Detecting & Solving Captcha...")
        solver = IntelligentCaptchaSolver(device_id=device_id, max_attempts=15, attempts_per_round=5)
        captcha_solved = solver.solve()
        if not captcha_solved:
            print("[-] Captcha could not be resolved.")
            save_account_to_csv(email_address, "CAPTCHA_FAILED", status="Failed_Captcha")
            return False

        # Step 4: Verify OTP Sent / Countdown Running
        print("\n[Step 4] Detecting OTP Ready State (Countdown running)...")
        ok, _ = detector.wait_for_state(STATE_OTP_READY, timeout=7.0)
        if not ok:
            print("[-] Screen did not enter OTP Ready state. Stopping cycle safely.")
            save_account_to_csv(email_address, "OTP_NOT_READY", status="Failed_OTP_Not_Ready")
            return False

        # Step 5: Fetch OTP from Gmail
        print("\n[Step 5] Listening to Gmail Inbox for OTP...")
        fetcher = GmailOTPFetcher(gmail, app_pw)
        t_otp_start = time.time()
        otp = fetcher.wait_for_otp(target_email=email_address, min_timestamp=obtain_time, timeout_seconds=90)
        otp_wait_seconds = time.time() - t_otp_start
        if not otp:
            save_account_to_csv(email_address, "TIMEOUT", status="Failed_OTP_Timeout")
            return False

        print(f"\n[+] Fresh OTP: {otp} (in {otp_wait_seconds:.2f}s)")
        ui.submit_verification_code(otp, device_id)

    # NOW CONTINUE TO SET PASSWORD
    print("\n[Step 6] Detecting Set Password Screen...")
    ok, _ = detector.wait_for_state(STATE_SET_PASSWORD, timeout=8.0)
    if not ok:
        print("[-] Set Password screen was not detected.")
        save_account_to_csv(email_address, otp, status="Failed_No_Password_Screen")
        return False

    ui.set_account_password(DEFAULT_PASSWORD, device_id)

    # DETECT 'I am expert'
    print("\n[Step 7] Detecting 'I am expert' Dialog...")
    ok, _ = detector.wait_for_state(STATE_EXPERT_DIALOG, timeout=15.0)
    if ok:
        ui.fast_click("btn_expert", device_id, 0.5)
    else:
        ui.fast_click("btn_expert", device_id, 0.5)

    # DETECT LOBBY POPUP DIALOGUE & CLOSE IT
    print("\n[Step 8] Detecting Lobby Popup Dialogue & Closing...")
    ok, _ = detector.wait_for_state(STATE_LOBBY_POPUP, timeout=7.0)
    if ok:
        ui.fast_click("popup_close_btn", device_id, 0.5)
    else:
        ui.fast_click("popup_close_btn", device_id, 0.4)

    # DETECT GAME HALL & TAP SETTINGS GEAR
    print("\n[Step 9] Detecting Game Hall & Tapping Settings Gear...")
    ok, _ = detector.wait_for_state(STATE_GAME_HALL, timeout=7.0)
    if ok:
        ui.fast_click("settings_gear_btn", device_id, 0.5)
    else:
        ui.fast_click("settings_gear_btn", device_id, 0.4)

    # DETECT SETTINGS DIALOG & TAP LOG OUT
    print("\n[Step 10] Detecting Settings Dialog & Tapping Log Out...")
    ok, _ = detector.wait_for_state(STATE_SETTINGS_DIALOG, timeout=6.0)
    if ok:
        ui.fast_click("logout_btn", device_id, 0.5)
    else:
        ui.fast_click("logout_btn", device_id, 0.4)

    # DETECT RETURN TO MAIN LANDING SCREEN
    print("\n[Step 11] Detecting Return to Main Landing Screen...")
    detector.wait_for_state(STATE_MAIN_LANDING, timeout=7.0)

    # SAVE TO CSV
    save_account_to_csv(email_address, otp, status="Success_Created", password=DEFAULT_PASSWORD)
    print(f"\n[SUCCESS] Account {email_address} created and verified end-to-end! [OK]")

    # CLEAR APP DATA & ROTATE IP
    print("\n[Step 12] Wiping app cache (pm clear) & Rotating IP (Airplane Mode)...")
    ui.clear_app_data(device_id)
    toggle_airplane_mode(air_delay, device_id)
    time.sleep(1.5)
    ui.ensure_main_landing_page(device_id)
    return True


def run_batch(total_accounts: int = 5):
    print("\n" + "="*65)
    print(f"      STARTING BATCH RUN: {total_accounts} ACCOUNTS")
    print("="*65)
    
    success_count = 0
    for i in range(1, total_accounts + 1):
        print(f"\n{'#'*65}")
        print(f"  CYCLE {i}/{total_accounts} (Progress: {success_count}/{i-1} Successful)")
        print(f"{'#'*65}")
        
        try:
            status = run_account_creation_cycle()
            if status:
                success_count += 1
                print(f"\n[+] Account {i}/{total_accounts} CREATED SUCCESSFULLY! [OK]")
            else:
                print(f"\n[-] Account {i}/{total_accounts} was not completed. Moving to next...")
        except Exception as e:
            print(f"\n[!] Unexpected error in cycle {i}: {e}")
        
        if i < total_accounts:
            print("[*] Cooling down 3 seconds before starting next account...")
            time.sleep(3.0)
            
    print("\n" + "="*65)
    print(f"      BATCH COMPLETED: {success_count}/{total_accounts} ACCOUNTS CREATED")
    print("="*65)
    return success_count


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    run_batch(count)
