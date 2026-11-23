"""
================================================================================
REWARD COLLECT - LOGIN FORM HANDLER & REAL-TIME VERIFICATION
================================================================================
Module: today_downloads/qaiser new test/login_form_handler.py

Purpose:
1. Picks Credentials from live Google Sheet (if not provided).
2. Taps email field, clears residual text, and injects email via Clipper.
3. Taps password field, clears residual text, and injects password via Clipper.
4. Taps Login button at (400, 853).
5. NO CAPTCHA: Captcha checks & 90s waits are bypassed (Old Yalla Ludo Version).
6. Real-Time Verification via Real-Time Screen Detector:
   - If EXPERT_DIALOG, MAIN_LOBBY, DAILY_REWARD_POPUP, etc. is detected:
     -> SUCCESS: Updates Google Sheet column Status to 'Login_Success'.
   - If error detected or still on EMAIL_LOGIN_DIALOG after timeout:
     -> FAILED: Updates Google Sheet column Status to 'Login_Failed'.
================================================================================
"""

import os
import re
import subprocess
import sys
import time
import cv2
import numpy as np

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

from fast_screen_engine import fast_screencap, fast_tap
from screen_detector import detect_current_screen, get_screen_xml
from google_sheet_sync import update_google_sheet, get_next_accounts_to_process

ADB_BIN = os.path.join(PARENT_DIR, "platform-tools", "adb.exe")
if not os.path.exists(ADB_BIN):
    ADB_BIN = "adb"


def get_adb_cmd(device_id: str = None) -> list:
    cmd = [ADB_BIN]
    if device_id:
        cmd.extend(["-s", device_id])
    return cmd


def run_adb(args: list, device_id: str = None) -> str:
    cmd = get_adb_cmd(device_id) + args
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        return res.stdout.decode("utf-8", errors="ignore")
    except Exception as e:
        return ""


def copy_to_clipboard(text: str, device_id: str = None) -> bool:
    """Copies text directly to Android clipboard via Clipper helper."""
    cmd = [
        "shell", "am", "broadcast",
        "-a", "clipper.set",
        "-e", "text", text,
        "-n", "ca.zgrs.clipper/.ClipperReceiver",
        "-f", "0x01000000"
    ]
    out = run_adb(cmd, device_id)
    return "copied into clipboard" in out or "result=-1" in out


def paste_clipboard(device_id: str = None, delay: float = 0.2):
    """Pastes clipboard contents into focused field via keyevent 279."""
    run_adb(["shell", "input", "keyevent", "279"], device_id)
    if delay > 0:
        time.sleep(delay)


def clear_and_type_email(email: str, device_id: str = "127.0.0.1:21503"):
    """Focuses email box, clears residual text, and injects email via uiautomator2."""
    try:
        import uiautomator2 as u2
        d = u2.connect(device_id)
        email_elem = d(resourceId="com.yalla.yallagames:id/et_phone_number_login")
        if email_elem.exists:
            email_elem.set_text(email)
            print(f"[+] Email [{email}] injected via uiautomator2 [OK]!")
            return
    except Exception as e:
        print(f"[!] u2 email error: {e}")

    # Fallback
    fast_tap(450, 520, device_id, delay=0.3)
    run_adb(["shell", "input", "keyevent", "123"], device_id)
    run_adb(["shell", "input", "keyevent"] + ["67"] * 60, device_id)
    time.sleep(0.2)
    if copy_to_clipboard(email, device_id):
        paste_clipboard(device_id, 0.2)
    else:
        run_adb(["shell", "input", "text", email.replace(" ", "%s")], device_id)
    print(f"[+] Email [{email}] injected successfully!")


def clear_and_type_password(password: str, device_id: str = "127.0.0.1:21503"):
    """Focuses password box, clears residual text, and injects password via uiautomator2."""
    try:
        import uiautomator2 as u2
        d = u2.connect(device_id)
        pwd_elem = d(resourceId="com.yalla.yallagames:id/et_cus_login_password")
        if pwd_elem.exists:
            pwd_elem.set_text(password)
            print("[+] Password injected via uiautomator2 [OK]!")
            return
    except Exception as e:
        print(f"[!] u2 password error: {e}")

    # Fallback
    fast_tap(450, 645, device_id, delay=0.3)
    run_adb(["shell", "input", "keyevent", "123"], device_id)
    run_adb(["shell", "input", "keyevent"] + ["67"] * 40, device_id)
    time.sleep(0.2)
    if copy_to_clipboard(password, device_id):
        paste_clipboard(device_id, 0.2)
    else:
        safe_pwd = password.replace("&", "\\&").replace("#", "\\#").replace("@", "\\@")
        run_adb(["shell", "input", "text", safe_pwd], device_id)
    print("[+] Password injected successfully!")


def check_login_button_color(device_id: str = None) -> dict:
    """Checks Login button color in real-time."""
    img = fast_screencap(device_id)
    if img is None:
        return {"status": "UNKNOWN", "yellow_pixels": 0}

    btn_crop = img[795:911, 179:621]
    hsv = cv2.cvtColor(btn_crop, cv2.COLOR_BGR2HSV)
    yellow_mask = (hsv[:, :, 0] >= 15) & (hsv[:, :, 0] <= 45) & (hsv[:, :, 1] >= 80) & (hsv[:, :, 2] >= 120)
    yellow_pixels = int(np.sum(yellow_mask))

    if yellow_pixels > 200:
        return {"status": "YELLOW", "yellow_pixels": yellow_pixels}
    else:
        return {"status": "GREY", "yellow_pixels": yellow_pixels}


def check_login_error_popup(device_id: str = None) -> str | None:
    """Detects invalid credential or login error messages in XML/UI."""
    xml = get_screen_xml(device_id, timeout=2.0)
    if not xml:
        return None

    error_keywords = [
        "incorrect password",
        "wrong password",
        "account does not exist",
        "failed to login",
        "password error",
        "user does not exist",
        "network error",
        "login failed"
    ]
    for err in error_keywords:
        if err in xml.lower():
            return err
    return None


def verify_login_success_realtime(device_id: str = None, timeout: float = 12.0) -> tuple[bool, str]:
    """
    Real-Time Screen Detector Loop for Login Success:
    Bypasses captcha (Old Version).
    Polls real-time detector every 0.4s to verify transition away from EMAIL_LOGIN_DIALOG.
    """
    start_t = time.time()
    print(f"[*] [Real-Time Detector] Monitoring login transition (up to {timeout:.0f}s)...")

    # Success states
    SUCCESS_STATES = [
        "EXPERT_DIALOG",
        "MAIN_LOBBY",
        "DAILY_REWARD_POPUP",
        "NEW_USER_SIGNIN",
        "CONGRATULATIONS_POPUP",
        "TIPS_AD_POPUP",
        "FREE_REWARDS_SCREEN",
        "OPEN_CHEST_POPUP",
        "DOUBLE_REWARD_POPUP"
    ]

    while time.time() - start_t < timeout:
        elapsed = time.time() - start_t

        # 1. Real-Time Screen Detection
        state = detect_current_screen(device_id)

        if state in SUCCESS_STATES:
            print(f"[+] [Real-Time Detector] LOGIN SUCCESS CONFIRMED! State: [{state}] after {elapsed:.1f}s [OK]!")
            return True, state

        # 2. Check for Error Popup
        err_msg = check_login_error_popup(device_id)
        if err_msg:
            print(f"[-] [Real-Time Detector] LOGIN ERROR DETECTED: [{err_msg}]")
            return False, f"ERROR_{err_msg.upper().replace(' ', '_')}"

        time.sleep(0.4)

    # Re-check final state
    final_state = detect_current_screen(device_id)
    if final_state in SUCCESS_STATES:
        print(f"[+] [Real-Time Detector] LOGIN SUCCESS CONFIRMED! Final State: [{final_state}] [OK]!")
        return True, final_state

    print(f"[-] [Real-Time Detector] Login Timeout ({timeout:.0f}s). State remains: [{final_state}]")
    return False, "LOGIN_TIMEOUT"


def execute_login_flow(device_id: str = "127.0.0.1:21613", email: str = None, password: str = None) -> tuple[bool, str]:
    """
    Master function to execute the full login flow:
    1. Picks credential from Google Sheet (if not provided).
    2. Clears & types Email.
    3. Clears & types Password.
    4. Taps Yellow Login Button at (400, 853).
    5. NO CAPTCHA: Checks login state directly via Real-Time Screen Detector.
    6. If verified: Updates Google Sheet with status='Login_Success'.
       If failed: Updates Google Sheet with status='Login_Failed'.
    """
    print("\n" + "="*70)
    print("   REWARD COLLECT -> LOGIN CREDENTIAL INJECTION & REAL-TIME VERIFICATION")
    print(f"   Target Device: {device_id}")

    # Step 1: Pick Credentials
    if not email or not password:
        print("[*] Fetching eligible pending credentials from Google Sheet...")
        eligible = get_next_accounts_to_process(max_count=1)
        if not eligible:
            print("[-] No eligible accounts found in Google Sheet!")
            return False, "NO_ACCOUNTS_IN_SHEET"
        acc = eligible[0]
        email = acc["Email"]
        password = acc["Clean_Password"]
        print(f"[+] Credential Picked from Google Sheet: [{email}]")

    print(f"   Email: {email}")
    print(f"   Password: {'*' * len(password)}")
    print("="*70 + "\n")

    # Step 2: Clear & Type Email
    print("--- [STEP 1] Clearing & Injecting Email ---")
    clear_and_type_email(email, device_id)
    time.sleep(0.4)

    # Step 3: Clear & Type Password
    print("\n--- [STEP 2] Clearing & Injecting Password ---")
    clear_and_type_password(password, device_id)
    time.sleep(0.5)

    # Step 4: Verify Login Button Color
    print("\n--- [STEP 3] Verifying Login Button Color ---")
    color_info = check_login_button_color(device_id)
    if color_info["status"] != "YELLOW":
        print("[*] Waiting 0.6s for Login button to turn Yellow...")
        time.sleep(0.6)

    # Step 5: Tap Login Button (NO CAPTCHA - Old Version)
    print(f"\n--- [STEP 4] Tapping Login Button (NO CAPTCHA - Old Version) ---")
    try:
        import uiautomator2 as u2
        d = u2.connect(device_id)
        btn = d(resourceId="com.yalla.yallagames:id/bt_login")
        if btn.exists:
            btn.click()
        else:
            fast_tap(400, 853, device_id, delay=1.0)
    except Exception:
        fast_tap(400, 853, device_id, delay=1.0)

    # Step 6: Real-Time Screen Detection for Verification
    print("\n--- [STEP 5] Real-Time Screen Detection for Login Verification ---")
    login_ok, login_state = verify_login_success_realtime(device_id=device_id, timeout=12.0)

    # Step 7: Google Sheet Sync
    print("\n--- [STEP 6] Syncing Result to Live Google Sheet ---")
    if login_ok:
        print(f"[+] [SUCCESS] Account [{email}] logged in successfully! Updating Google Sheet Status -> 'Login_Success'...")
        update_google_sheet(email=email, status="Login_Success", device_id=device_id)
        return True, login_state
    else:
        print(f"[-] [FAILED] Login failed for [{email}]! Updating Google Sheet Status -> 'Login_Failed'...")
        update_google_sheet(email=email, status=f"Login_Failed_{login_state}", device_id=device_id)
        return False, login_state


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21503"
    execute_login_flow(target)
