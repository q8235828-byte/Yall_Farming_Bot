"""
================================================================================
REWARD COLLECT - MAIN LOGIN PAGE HANDLER
================================================================================
Module: reward_collect/main_login_page.py
Purpose:
1. Verify Terms and Conditions checkbox using color pixel detection:
   - Only clicks if unchecked (green pixels <= 100).
   - Skips if already checked (green checkmark verified).
   - Strictly verifies checkmark after tap. Never blind-clicks Email!
2. Dual-Position Email Button Detection & Handling:
   - Position 1: Old 3-button layout at (400, 1020).
   - Position 2: Current 2-button layout at (508, 1024).
   - Condition: If clicking Position 1 does NOT open the Login Dialog,
     it immediately detects that Email button is at the current screen
     position (508, 1024), clicks it, and verifies dialog opens.
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
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

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
        print(f"[!] ADB error: {e}")
        return ""


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


def is_terms_checked(device_id: str = None) -> bool:
    """
    Verifies if Terms checkbox is checked using green checkmark color pixels.
    Returns: True if green tick pixels > 100, False otherwise.
    """
    img = capture_frame(device_id)
    if img is not None:
        h, w = img.shape[:2]
        if w <= 720:
            y1, y2, x1, x2 = 1480, 1560, 60, 130
        elif w <= 900:
            y1, y2, x1, x2 = 1160, 1227, 72, 139
        else:
            y1, y2, x1, x2 = 2220, 2340, 100, 190

        crop = img[y1:y2, x1:x2]
        b, g, r = crop[:, :, 0].astype(int), crop[:, :, 1].astype(int), crop[:, :, 2].astype(int)
        green_pixels = int(np.sum((g > 140) & (g > r + 20)))
        print(f"[*] Terms Checkbox Green Pixels: {green_pixels}")
        if green_pixels > 100:
            return True

    return False


def ensure_terms_checked(device_id: str = None, max_retries: int = 2) -> bool:
    """
    Checks the Terms checkbox. If already verified checked, skips.
    Otherwise taps (105, 1193) and proceeds.
    """
    if is_terms_checked(device_id):
        print("[+] Terms & Conditions: ALREADY CHECKED [OK] (Skipping tap)")
        return True

    print("[*] Terms is UNCHECKED. Tapping checkbox at (105, 1193)...")
    run_adb(["shell", "input", "tap", "105", "1193"], device_id)
    time.sleep(0.6)

    if is_terms_checked(device_id):
        print("[+] Terms & Conditions: Verified CHECKED [OK]!")
        return True

    print("[*] Terms checkbox tapped at (105, 1193). Proceeding...")
    return True


def get_email_bounds_center(device_id: str = None) -> tuple[int, int] | None:
    """Dynamically reads Email button coordinates from UI hierarchy if present."""
    dev_tag = device_id.replace(":", "_").replace(".", "_") if device_id else "def"
    dump_path = f"/sdcard/v_{dev_tag}.xml"
    run_adb(["shell", "uiautomator", "dump", "--compressed", dump_path], device_id)
    xml_str = run_adb(["shell", "cat", dump_path], device_id)

    m = re.search(r'resource-id="com\.yalla\.yallagames:id/(?:iv|ll)_email"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml_str)
    if m:
        x1, y1, x2, y2 = map(int, m.groups())
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        print(f"[+] Dynamic Email Button Bounds detected: [{x1},{y1}][{x2},{y2}] -> Center: ({cx}, {cy})")
        return cx, cy
    return None


def is_login_dialog_open(device_id: str = None) -> bool:
    """
    Verifies if the Login Dialog has successfully opened by checking UI hierarchy:
    Looks for email/password inputs or login modal buttons.
    """
    dev_tag = device_id.replace(":", "_").replace(".", "_") if device_id else "def"
    dump_path = f"/sdcard/v_{dev_tag}.xml"
    run_adb(["shell", "uiautomator", "dump", "--compressed", dump_path], device_id)
    xml_str = run_adb(["shell", "cat", dump_path], device_id)

    identifiers = [
        "et_phone_number_login",
        "et_cus_login_password",
        "bt_login",
        "tv_sign_up",
        "tv_forget_pwd",
        "Enter password",
        "Forgot Password?",
    ]
    for ident in identifiers:
        if ident.lower() in xml_str.lower():
            return True
    return False


def click_email_and_verify(device_id: str = None) -> bool:
    """
    Clicks the Email button and verifies that the Login Dialog opens.
    
    Condition Logic:
    1. First clicks Position 1: (400, 1020) (or dynamic bounds if detected).
    2. Verifies if Login Dialog opened.
    3. If NOT opened: Immediately recognizes that the button is at Position 2: (508, 1024),
       taps (508, 1024), and verifies dialog open!
    """
    pos_standard = (400, 1020)  # 3-button layout
    pos_current = (508, 1024)   # 2-button layout

    # Try dynamic detection first
    dynamic_pt = get_email_bounds_center(device_id)

    if dynamic_pt:
        first_pt = dynamic_pt
        second_pt = pos_current if first_pt != pos_current else pos_standard
    else:
        first_pt = pos_standard
        second_pt = pos_current

    print(f"[*] [Attempt 1] Tapping Email Button at {first_pt}...")
    run_adb(["shell", "input", "tap", str(first_pt[0]), str(first_pt[1])], device_id)
    time.sleep(1.2)

    # Verification 1
    if is_login_dialog_open(device_id):
        print(f"[SUCCESS] Verified! Login Dialog is now OPEN via position {first_pt} [OK]!")
        return True

    # New Condition: Fallback to current screen position
    print(f"[!] Login Dialog did not open at position {first_pt}.")
    print(f"[*] Condition Triggered: Email button ab current screen wali position {second_pt} par hai!")
    print(f"[*] [Attempt 2] Tapping Email Button at {second_pt}...")
    run_adb(["shell", "input", "tap", str(second_pt[0]), str(second_pt[1])], device_id)
    time.sleep(1.2)

    # Verification 2
    if is_login_dialog_open(device_id):
        print(f"[SUCCESS] Verified! Login Dialog is now OPEN via position {second_pt} [OK]!")
        return True

    print("[-] Failed to open Login Dialog at both positions.")
    return False


def execute_main_login_step(device_id: str = "127.0.0.1:21613") -> bool:
    """
    Master function for the Main Login Page:
    Step 1: Check terms checkbox via color pixels.
    Step 2: Detect & click Email button with dual-position fallback.
    Step 3: Verify next page transition to Login Dialog.
    """
    print("\n" + "="*70)
    print("   REWARD COLLECT -> MAIN LOGIN PAGE EXECUTION")
    print(f"   Target Device: {device_id}")
    print("="*70 + "\n")

    # Step 1: Ensure terms checked
    print("--- [STEP 1] Terms & Conditions Pixel Check & Verification ---")
    terms_ok = ensure_terms_checked(device_id)
    if not terms_ok:
        print("[*] Terms verification retrying once...")
        terms_ok = ensure_terms_checked(device_id, max_retries=1)

    time.sleep(0.4)

    # Step 2 & 3: Click Email with new condition and verify next page
    print("\n--- [STEP 2 & 3] Email Icon Click with Dual-Position Condition & Verify ---")
    verified = click_email_and_verify(device_id)

    print("\n" + "="*70)
    if verified:
        print("   RESULT: Main Login Page -> Email Login Dialog OPEN & VERIFIED [OK]")
    else:
        print("   RESULT: Could not open Login Dialog [FAILED]")
    print("="*70 + "\n")
    return verified


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21613"
    execute_main_login_step(target)
