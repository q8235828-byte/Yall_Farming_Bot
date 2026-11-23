"""
================================================================================
REWARD COLLECT - LOGIN FORM HANDLER & VERIFICATION
================================================================================
Module: reward_collect/login_form_handler.py
Purpose:
1. Fetch completed accounts (Status: 'Success_Created') from created_accounts.csv.
2. Tap email field and execute multiple backspaces (unlimited back key press)
   to completely remove any residual email before typing the new one.
3. Inject email and password via Clipper broadcast (preserving special chars).
4. Verify Login button color turns from Grey to Bright Yellow.
5. Tap Yellow Login button at (400, 853).
6. Check for Geetest Captcha via fast pixel detection and solve it with ColorIndexedCaptchaSolver.
7. Wait up to 30 SECONDS to detect "I’m expert" dialog box (or lobby):
   - If detected within 30s -> SUCCESS: Credentials VALID [GOOD]!
     Update status in CSV to 'Login_Success'.
   - If NOT detected within 30s -> FAILED: Credentials WRONG or login failed!
     Update status in CSV to 'Login_Failed_Invalid_Credentials'.
================================================================================
"""

import csv
import os
import re
import subprocess
import sys
import time
import cv2
import numpy as np

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from color_indexed_captcha_solver import ColorIndexedCaptchaSolver

ADB_BIN = os.path.join(PARENT_DIR, "platform-tools", "adb.exe")
if not os.path.exists(ADB_BIN):
    ADB_BIN = "adb"

CSV_PATH = os.path.join(PARENT_DIR, "created_accounts.csv")


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
        print(f"[!] ADB error: {e}")
        return ""


def get_next_completed_account(csv_file: str = CSV_PATH) -> tuple[str, str, int] | None:
    """
    Reads created_accounts.csv and returns the next account with Status == 'Success_Created'
    that has not yet been marked as Login_Success or Login_Failed.
    Returns: (email, password, line_idx) or None.
    """
    if not os.path.exists(csv_file):
        print(f"[!] CSV file not found: {csv_file}")
        return None

    with open(csv_file, "r", encoding="utf-8", errors="ignore") as f:
        reader = list(csv.reader(f))

    for idx, row in enumerate(reader):
        if len(row) >= 5:
            status = row[4].strip()
            if status == "Success_Created":
                email = row[1].strip()
                password = row[2].strip()
                if email and password and "@" in email:
                    return email, password, idx

    return None


def update_account_status_in_csv(email: str, new_status: str, csv_file: str = CSV_PATH):
    """Updates the status column for the given email in created_accounts.csv."""
    if not os.path.exists(csv_file):
        return

    rows = []
    updated = False
    with open(csv_file, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 5 and row[1].strip() == email and not updated:
                row[4] = new_status
                updated = True
            rows.append(row)

    if updated:
        with open(csv_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(rows)
        print(f"[+] CSV Updated: Account [{email}] status set to -> '{new_status}'")


def capture_frame(device_id: str = None) -> np.ndarray | None:
    """Captures clean screen frame via raw screencap framebuffer (with PNG fallback)."""
    cmd = get_adb_cmd(device_id)
    dev_tag = device_id.replace(":", "_").replace(".", "_") if device_id else "def"
    raw_path = f"/sdcard/cap_{dev_tag}.raw"
    try:
        subprocess.run(cmd + ["shell", "screencap", raw_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
        raw = subprocess.check_output(cmd + ["exec-out", "cat", raw_path], timeout=4)
        if len(raw) >= 16:
            w = int.from_bytes(raw[0:4], byteorder='little')
            h = int.from_bytes(raw[4:8], byteorder='little')
            if w > 0 and h > 0 and len(raw) >= 16 + w * h * 4:
                data = np.frombuffer(raw[16:16 + w * h * 4], dtype=np.uint8).reshape((h, w, 4))
                return cv2.cvtColor(data, cv2.COLOR_RGBA2BGR)
    except Exception:
        pass

    # Fallback to PNG
    tmp_dev = f"/sdcard/cap_{dev_tag}.png"
    tmp_loc = os.path.join(CURRENT_DIR, f"temp_{dev_tag}.png")
    try:
        subprocess.run(cmd + ["shell", "screencap", "-p", tmp_dev], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        subprocess.run(cmd + ["pull", tmp_dev, tmp_loc], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        if os.path.exists(tmp_loc):
            img = cv2.imread(tmp_loc)
            try:
                os.remove(tmp_loc)
            except Exception:
                pass
            return img
    except Exception as e:
        print(f"[!] Capture frame error: {e}")
    return None


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


def paste_clipboard(device_id: str = None, delay: float = 0.3):
    """Pastes clipboard contents into focused field via keyevent 279."""
    run_adb(["shell", "input", "keyevent", "279"], device_id)
    if delay > 0:
        time.sleep(delay)


def clear_and_type_email(email: str, device_id: str = None, coords: tuple[int, int] = (450, 520)):
    """
    Focuses email box at safe coordinates (clear of phone toggle) and presses
    unlimited backspaces (KeyCode 67 x 70) to completely remove residual text,
    then injects new email.
    """
    print(f"[*] Focusing Email field at {coords}...")
    run_adb(["shell", "input", "tap", str(coords[0]), str(coords[1])], device_id)
    time.sleep(0.4)

    print("[*] Clearing residual email (unlimited back key press)...")
    run_adb(["shell", "input", "keyevent", "123"], device_id)
    run_adb(["shell", "input", "keyevent"] + ["67"] * 70, device_id)
    time.sleep(0.3)

    pasted = False
    if copy_to_clipboard(email, device_id):
        paste_clipboard(device_id, 0.3)
        pasted = True
    if not pasted:
        safe_email = email.replace(" ", "%s")
        run_adb(["shell", "input", "text", safe_email], device_id)
    print(f"[+] Email [{email}] injected successfully!")


def clear_and_type_password(password: str, device_id: str = None, coords: tuple[int, int] = (450, 645)):
    """Focuses password box, clears residual text thoroughly, and injects password via Clipper."""
    print(f"[*] Focusing Password field at {coords}...")
    run_adb(["shell", "input", "tap", str(coords[0]), str(coords[1])], device_id)
    time.sleep(0.4)

    print("[*] Clearing residual password (unlimited back key press)...")
    run_adb(["shell", "input", "keyevent", "123"], device_id)
    run_adb(["shell", "input", "keyevent"] + ["67"] * 50, device_id)
    time.sleep(0.3)

    pasted = False
    if copy_to_clipboard(password, device_id):
        paste_clipboard(device_id, 0.3)
        pasted = True
    if not pasted:
        safe_pwd = password.replace("&", "\\&").replace("#", "\\#").replace("@", "\\@")
        run_adb(["shell", "input", "text", safe_pwd], device_id)
    print(f"[+] Password injected successfully!")


def check_login_button_color(device_id: str = None) -> dict:
    """
    Checks the exact pixel colors of the Login button (MEmu 800x1280: [179, 795][621, 911]).
    Distinguishes:
    - 'GREY' (Empty/Disabled): Saturation < 25, Yellow Pixels == 0
    - 'YELLOW' (Active/Enabled): Saturation > 70, Yellow Pixels > 200
    """
    img = capture_frame(device_id)
    if img is None:
        return {"status": "UNKNOWN", "yellow_pixels": 0, "mean_sat": 0.0}

    btn_crop = img[795:911, 179:621]
    hsv = cv2.cvtColor(btn_crop, cv2.COLOR_BGR2HSV)
    mean_sat = float(np.mean(hsv[:, :, 1]))

    yellow_mask = (hsv[:, :, 0] >= 15) & (hsv[:, :, 0] <= 45) & (hsv[:, :, 1] >= 80) & (hsv[:, :, 2] >= 120)
    yellow_pixels = int(np.sum(yellow_mask))

    print(f"[*] Login Button Color Analysis: Yellow Pixels = {yellow_pixels}, Mean Saturation = {mean_sat:.1f}")

    if yellow_pixels > 200 or mean_sat > 70.0:
        return {"status": "YELLOW", "yellow_pixels": yellow_pixels, "mean_sat": mean_sat}
    else:
        return {"status": "GREY", "yellow_pixels": yellow_pixels, "mean_sat": mean_sat}


def detect_post_login_state(device_id: str = None) -> tuple[str, str]:
    """
    Checks UI hierarchy to determine the post-login state:
    - 'NEW_ACCOUNT': 'I’m expert' dialogue box is present.
    - 'OLD_ACCOUNT': Main Lobby is directly present (iv_setting, main_hall, coin/diamond headers).
    - 'ERROR': Invalid credentials or login error dialog.
    - 'UNKNOWN': Still waiting / transitioning.
    """
    dev_tag = device_id.replace(":", "_").replace(".", "_") if device_id else "def"
    dump_path = f"/sdcard/expert_{dev_tag}.xml"
    run_adb(["shell", "rm", "-f", dump_path], device_id)
    out = run_adb(["shell", "uiautomator", "dump", "--compressed", dump_path], device_id)
    xml_str = run_adb(["shell", "cat", dump_path], device_id)

    # Check for error dialogs
    if any(err in xml_str.lower() for err in ["incorrect password", "wrong password", "account does not exist", "failed to login", "password error"]):
        return "ERROR", "Invalid credentials / password error"

    # 1. Check for New Account: 'I'm expert' Dialog
    new_acc_indicators = [
        "btn_yes",
        "I’m expert",
        "I'm expert",
        "btn_no",
        "Welcome to Yalla Ludo"
    ]
    for ind in new_acc_indicators:
        if ind in xml_str:
            return "NEW_ACCOUNT", "I’m expert Dialogue Box (New Account)"

    # 2. Check for Old Account: Main Lobby directly visible
    old_acc_indicators = [
        "iv_setting",       # Settings / Gear icon in top right of Lobby
        "main_hall",        # Main hall / Lobby root container
        "activity_main_hall",
        "rl_diamond",       # Diamonds header
        "fl_coin",          # Coins header
        "iv_avatar",        # Avatar image
        "iv_head",          # User profile head
        "1 ON 1",           # Main game mode button in lobby
        "4 PLAYERS",        # 4 Players game mode
        "LUDO",             # Ludo game tab
        "DOMINO"            # Domino game tab
    ]
    for ind in old_acc_indicators:
        if ind in xml_str:
            return "OLD_ACCOUNT", f"Main Lobby [{ind}] (Old Account)"

    return "UNKNOWN", ""


def wait_for_login_success(device_id: str = None, timeout: float = 30.0) -> tuple[bool, str]:
    """
    Waits up to 30 SECONDS after Captcha to detect either:
    1. 'NEW_ACCOUNT': 'I’m expert' dialog -> Account is valid & workable!
    2. 'OLD_ACCOUNT': Main Lobby directly -> Account is valid & workable!
    Returns (True, 'NEW_ACCOUNT' | 'OLD_ACCOUNT') if successful, else (False, 'FAILED').
    """
    start_time = time.time()
    print(f"[*] Waiting up to {timeout:.0f}s to detect 'I’m expert' (New Account) OR Main Lobby (Old Account)...")

    while time.time() - start_time < timeout:
        elapsed = time.time() - start_time

        state, desc = detect_post_login_state(device_id)

        if state == "NEW_ACCOUNT":
            print(f"\n[+] SUCCESS: NEW ACCOUNT DETECTED! [{desc}] appeared after {elapsed:.1f}s!")
            print("[+] Account is VALID & WORKABLE [GOOD]!")
            return True, "NEW_ACCOUNT"

        elif state == "OLD_ACCOUNT":
            print(f"\n[+] SUCCESS: OLD ACCOUNT DETECTED! [{desc}] appeared after {elapsed:.1f}s!")
            print("[+] Account is VALID & WORKABLE (Main Lobby Loaded directly) [GOOD]!")
            return True, "OLD_ACCOUNT"

        elif state == "ERROR":
            print(f"\n[-] ERROR: Login failed error detected: {desc}")
            return False, "FAILED"

        print(f"    [Waiting {elapsed:.1f}s / {timeout:.0f}s] Monitoring for 'I’m expert' OR Main Lobby...")
        time.sleep(1.0)

    print(f"\n[-] TIMEOUT: Neither 'I’m expert' nor Main Lobby detected within {timeout:.0f}s.")
    return False, "FAILED"


def execute_login_flow(device_id: str = "127.0.0.1:21613", email: str = None, password: str = None) -> bool:
    """
    Master function to execute the full login flow:
    1. Read next completed account from sheet if not provided.
    2. Clear email field thoroughly & inject email.
    3. Clear password field & inject password.
    4. Verify Login button turns Bright Yellow.
    5. Tap Yellow Login button.
    6. Check & solve Geetest Captcha via fast pixel detection.
    7. Wait up to 30s to detect 'I’m expert' dialog box:
       - If detected -> Updates CSV to 'Login_Success'
       - If NOT detected -> Updates CSV to 'Login_Failed_Invalid_Credentials'
    """
    print("\n" + "="*70)
    print("   REWARD COLLECT -> LOGIN CREDENTIAL INJECTION & EXPERT VERIFICATION")
    print(f"   Target Device: {device_id}")

    # Step 1: Credentials
    if not email or not password:
        account_info = get_next_completed_account(CSV_PATH)
        if not account_info:
            print("[-] No pending 'Success_Created' accounts found in sheet!")
            return False, "NO_ACCOUNTS"
        email, password, row_idx = account_info
        print(f"   Fetched from Sheet: Row {row_idx + 1}")

    print(f"   Email: {email}")
    print(f"   Password: {'*' * len(password)}")
    print("="*70 + "\n")

    # Step 2: Clear & Type Email (with unlimited back key press)
    print("--- [STEP 1] Clearing & Typing Email ---")
    clear_and_type_email(email, device_id)
    time.sleep(0.5)

    # Step 3: Clear & Type Password
    print("\n--- [STEP 2] Clearing & Typing Password ---")
    clear_and_type_password(password, device_id)
    time.sleep(0.6)

    # Step 4: Verify Login button turned Bright Yellow
    print("\n--- [STEP 3] Verifying Login Button Color (Grey -> Bright Yellow) ---")
    color_info = check_login_button_color(device_id)

    if color_info["status"] == "YELLOW":
        print("[+] SUCCESS: Login button turned BRIGHT YELLOW! (Active & Enabled) [OK]")
    else:
        print("[!] Warning: Login button is not detected as Yellow yet. Waiting 0.8s...")
        time.sleep(0.8)
        color_info = check_login_button_color(device_id)
        if color_info["status"] == "YELLOW":
            print("[+] SUCCESS: Login button turned BRIGHT YELLOW! [OK]")
        else:
            print("[-] ERROR: Login button is still GREY! Credentials might be incomplete.")
            update_account_status_in_csv(email, "Login_Failed_Button_Grey")
            return False, "BUTTON_GREY"

    # Step 5: Tap Yellow Login Button & Wait for Captcha (up to 90s, with retry if not loaded)
    solver = ColorIndexedCaptchaSolver(device_id=device_id)
    captcha_ready = False
    captcha_bypassed = False
    max_login_tap_attempts = 3
    login_btn_coords = (400, 853)

    for load_attempt in range(1, max_login_tap_attempts + 1):
        print(f"\n--- [STEP 4 & 5] Tapping Yellow Login Button (Attempt {load_attempt}/{max_login_tap_attempts}) & Waiting for Captcha (up to 90s) ---")
        print(f"[*] Tapping Login Button at {login_btn_coords}...")
        run_adb(["shell", "input", "tap", str(login_btn_coords[0]), str(login_btn_coords[1])], device_id)
        time.sleep(1.5)

        start_load = time.time()
        load_timeout = 90.0

        while time.time() - start_load < load_timeout:
            elapsed = time.time() - start_load

            # 1. Check if direct login already occurred (No captcha needed)
            state, desc = detect_post_login_state(device_id)
            if state in ["NEW_ACCOUNT", "OLD_ACCOUNT"]:
                print(f"[+] Direct login detected after {elapsed:.1f}s [{desc}] (No captcha required)!")
                captcha_bypassed = True
                break

            # 2. Check if Captcha Canvas & Blue slider knob is detected via frame (<0.3s)
            if solver.is_captcha_present():
                print(f"[+] Captcha Canvas & Knob DETECTED & LOADED after {elapsed:.1f}s! [OK]")
                captcha_ready = True
                break

            # 3. Check XML text every 2s for Geetest loading or ready state
            if int(elapsed) % 2 == 0:
                dev_tag = device_id.replace(":", "_").replace(".", "_") if device_id else "def"
                dump_path = f"/sdcard/c_chk_{dev_tag}.xml"
                run_adb(["shell", "rm", "-f", dump_path], device_id)
                out = run_adb(["shell", "uiautomator", "dump", "--compressed", dump_path], device_id)
                if "dumped to" in out:
                    xml = run_adb(["shell", "cat", dump_path], device_id).lower()
                    if "slide to complete the puzzle" in xml or ("refresh" in xml and "close" in xml):
                        print(f"[+] Captcha Canvas DETECTED via XML after {elapsed:.1f}s! [OK]")
                        captcha_ready = True
                        break
                    elif "geetest" in xml:
                        print(f"    [{elapsed:.1f}s / {load_timeout:.0f}s] Geetest downloading / rendering puzzle canvas...")

            time.sleep(0.8)

        if captcha_bypassed or captcha_ready:
            break

        print(f"[-] Captcha canvas did not load within {load_timeout:.0f}s on attempt {load_attempt}.")
        # If captcha did not load within 90s, check if Login Dialog is still present
        from main_login_page import is_login_dialog_open
        if is_login_dialog_open(device_id):
            print("[*] Login Dialog is STILL OPEN! Re-tapping Yellow Login button to trigger captcha...")
            time.sleep(1.0)
            continue
        else:
            print("[!] Screen not on Login Dialog. Checking post-login state...")
            state, _ = detect_post_login_state(device_id)
            if state in ["NEW_ACCOUNT", "OLD_ACCOUNT"]:
                captcha_bypassed = True
                break

    if captcha_ready:
        print("[*] Starting Captcha Solver (up to 10 live attempts)...")
        time.sleep(1.0)  # Let puzzle finish rendering fully
        cap_solved = False

        for attempt_idx in range(1, 11):
            print(f"\n---> [CAPTCHA ATTEMPT {attempt_idx}/10] <---")
            # Execute solver drag
            solved = solver.solve(max_attempts=3, timeout=15.0)
            time.sleep(2.0)  # Wait for Geetest verification animation

            # Check if solved
            state, _ = detect_post_login_state(device_id)
            if solved or state in ["NEW_ACCOUNT", "OLD_ACCOUNT"]:
                print(f"[SUCCESS] Captcha SOLVED successfully on Attempt {attempt_idx}! [OK]")
                cap_solved = True
                break
            else:
                print(f"[*] Attempt {attempt_idx} did not clear puzzle. Preparing next attempt...")
                time.sleep(1.0)

        if not cap_solved:
            print("[-] Captcha could not be solved in 10 attempts.")
            update_account_status_in_csv(email, "Login_Failed_Captcha")
            return False, "CAPTCHA_FAILED"

        print("[+] Captcha SOLVED successfully! Now proceeding to 30s verification timer.")
        time.sleep(1.0)

    elif not captcha_bypassed:
        print("[-] Captcha canvas did not load within 90s timeout after all retries.")
        # Check one more time if post-login occurred
        state, _ = detect_post_login_state(device_id)
        if state not in ["NEW_ACCOUNT", "OLD_ACCOUNT"]:
            update_account_status_in_csv(email, "Login_Failed_Captcha_Timeout")
            return False, "CAPTCHA_TIMEOUT"

    # Step 7: Wait up to 30 Seconds to detect "I’m expert" (New Account) OR Main Lobby (Old Account)
    # USER CONDITION: 30s timer strictly starts ONLY AFTER Captcha is solved!
    print("\n--- [STEP 6] Post-Captcha Verification: 30s Detection Timer Starts NOW ---")
    login_valid, acc_type = wait_for_login_success(device_id, timeout=30.0)

    print("\n" + "="*70)
    if login_valid:
        if acc_type == "NEW_ACCOUNT":
            print("   FINAL RESULT: NEW ACCOUNT DETECTED & VERIFIED [GOOD - WORKABLE]!")
        else:
            print("   FINAL RESULT: OLD ACCOUNT DETECTED (MAIN LOBBY DIRECT) [GOOD - WORKABLE]!")
        update_account_status_in_csv(email, "Login_Success")
    else:
        print("   FINAL RESULT: LOGIN CREDENTIALS WRONG OR LOGIN FAILED [FAILED]!")
        update_account_status_in_csv(email, "Login_Failed_Invalid_Credentials")
    print("="*70 + "\n")

    return login_valid, acc_type


if __name__ == "__main__":
    dev = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21613"
    em = sys.argv[2] if len(sys.argv) > 2 else None
    pw = sys.argv[3] if len(sys.argv) > 3 else None
    execute_login_flow(dev, em, pw)
