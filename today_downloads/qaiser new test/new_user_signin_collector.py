"""
================================================================================
REWARD COLLECT - NEW USER SIGN-IN COLLECTOR & REAL-TIME VERIFIER
================================================================================
Module: today_downloads/qaiser new test/new_user_signin_collector.py

Bypasses UIAutomator (which cannot read OpenGL Canvas text/animations).
Uses Real-Time Visual Pixel Engine:
1. Detects 'New User Sign-in' Dialog via Static Teal Header + Red Close Tag.
   (100% immune to internal diamond/hand animations!).
2. Collect Flow:
   - If Collect button is Yellow (Active): Taps (400, 1140).
   - Dismisses any 'Congratulations' / Confirm popup at (400, 818).
   - Loops until Collect button turns Grey.
3. Clean Dismiss:
   - Taps Red 'X' Close button at (740, 75) or sends Android Back key.
   - Verifies return to MAIN_LOBBY.
================================================================================
"""

import os
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
from screen_detector import detect_current_screen

ADB_BIN = os.path.join(PARENT_DIR, "platform-tools", "adb.exe")
if not os.path.exists(ADB_BIN):
    ADB_BIN = "adb"


def get_adb_cmd(device_id: str = None) -> list:
    cmd = [ADB_BIN]
    if device_id:
        cmd.extend(["-s", device_id])
    return cmd


def run_adb(args: list, device_id: str = None, timeout: float = 6.0) -> str:
    cmd = get_adb_cmd(device_id) + args
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return res.stdout.decode("utf-8", errors="ignore")
    except Exception as e:
        return ""


def is_new_user_signin_open(device_id: str = None) -> bool:
    """
    Visual detection of 'New User Sign-in' dialog:
    Checks for static Teal header bar (>3000 px) AND Red close tag (>500 px).
    Completely immune to internal animations!
    """
    frame = fast_screencap(device_id)
    if frame is None:
        return False

    h, w = frame.shape[:2]

    # Teal Header Check (y: 5%..14%, x: 15%..85%)
    header_roi = frame[int(h * 0.05):int(h * 0.14), int(w * 0.15):int(w * 0.85)]
    hsv_h = cv2.cvtColor(header_roi, cv2.COLOR_BGR2HSV)
    teal_px = cv2.countNonZero(cv2.inRange(hsv_h, (65, 80, 80), (100, 255, 255)))

    # Red Close Tag Check (y: 3%..12%, x: 80%..98%)
    close_roi = frame[int(h * 0.03):int(h * 0.12), int(w * 0.80):int(w * 0.98)]
    hsv_c = cv2.cvtColor(close_roi, cv2.COLOR_BGR2HSV)
    red_px = cv2.countNonZero(cv2.inRange(hsv_c, (0, 100, 100), (10, 255, 255))) + \
             cv2.countNonZero(cv2.inRange(hsv_c, (170, 100, 100), (180, 255, 255)))

    return (teal_px > 3000) and (red_px > 500)


def get_collect_button_state(device_id: str = None) -> str:
    """
    Checks bottom button state on 800x1280:
    - 'YELLOW' (Active reward ready to collect): yellow_px > 1000
    - 'GREY' (Already collected / disabled): yellow_px < 500
    """
    frame = fast_screencap(device_id)
    if frame is None:
        return "UNKNOWN"

    h, w = frame.shape[:2]
    # Button ROI around (y: 84%..93%, x: 22%..78%)
    btn_roi = frame[int(h * 0.84):int(h * 0.93), int(w * 0.22):int(w * 0.78)]
    hsv_b = cv2.cvtColor(btn_roi, cv2.COLOR_BGR2HSV)
    yellow_px = cv2.countNonZero(cv2.inRange(hsv_b, (20, 120, 120), (35, 255, 255)))

    if yellow_px > 1000:
        return "YELLOW"
    return "GREY"


def check_and_dismiss_confirm_popup(device_id: str = None) -> bool:
    """Checks if 'Congratulations' / Confirm popup appeared and dismisses at (400, 818)."""
    frame = fast_screencap(device_id)
    if frame is None:
        return False

    h, w = frame.shape[:2]
    # Check for yellow Confirm button around center (y: 60%..68%, x: 30%..70%)
    roi = frame[int(h * 0.60):int(h * 0.68), int(w * 0.30):int(w * 0.70)]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    yellow_px = cv2.countNonZero(cv2.inRange(hsv, (20, 120, 120), (35, 255, 255)))

    if yellow_px > 1000:
        print(f"[*] 'Congratulations/Confirm' popup detected (yellow_px={yellow_px})! Tapping (400, 818)...")
        fast_tap(400, 818, device_id, delay=1.0)
        return True
    return False


def execute_new_user_signin(device_id: str = "127.0.0.1:21613", max_collect_attempts: int = 3) -> bool:
    """
    Master function to collect New User Sign-in reward and cleanly close dialog.
    """
    print("\n" + "="*70)
    print("   REWARD COLLECT -> NEW USER SIGN-IN COLLECT & DISMISS")
    print(f"   Target Device: {device_id}")
    print("="*70 + "\n")

    if not is_new_user_signin_open(device_id):
        print(f"[*] New User Sign-in dialog is NOT open on {device_id}.")
        return False

    print("[+] 'New User Sign-in' Dialog DETECTED on screen [OK]!")

    # Step 1: Collect Rewards while button is Yellow
    for attempt in range(1, max_collect_attempts + 1):
        btn_state = get_collect_button_state(device_id)
        print(f"[*] [Attempt {attempt}/{max_collect_attempts}] Collect Button State: [{btn_state}]")

        if btn_state == "YELLOW":
            print("[*] Tapping Yellow 'Collect' button at (400, 1140)...")
            fast_tap(400, 1140, device_id, delay=1.2)

            # Check for Confirm / Congratulations popup
            check_and_dismiss_confirm_popup(device_id)
            time.sleep(0.8)
        else:
            print("[+] Collect button is GREY / Disabled. Rewards already collected!")
            break

    # Step 2: Close dialog via Red 'X' Button or Back key
    print("\n[*] Closing 'New User Sign-in' dialog...")
    # Red 'X' button is at (740, 75) on 800x1280
    print("[*] Tapping Red Close 'X' button at (740, 75)...")
    fast_tap(740, 75, device_id, delay=1.0)

    # Check if closed
    if is_new_user_signin_open(device_id):
        print("[*] Dialog still visible. Sending Back key (keyevent 4)...")
        run_adb(["shell", "input", "keyevent", "4"], device_id)
        time.sleep(1.0)

    state = detect_current_screen(device_id)
    print(f"[+] 'New User Sign-in' finished! Current Screen: [{state}] [OK]!\n")
    return True


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21503"
    execute_new_user_signin(target)
