"""
================================================================================
REWARD COLLECT - MAIN LOGIN PAGE HANDLER (uiautomator2 Real-time Engine)
================================================================================
Module: today_downloads/qaiser new test/main_login_page.py

User Rule:
1. Checkbox live memory detection using bright checkmark pixels:
   - Green channel > 175, (G - R) > 70, (G - B) > 50
   - Unchecked: 0 pixels. Checked: ~870 pixels. Threshold: 150 pixels.
2. If already checked:
   - Completely skips tap (Never unchecks!).
3. If unchecked:
   - Taps checkbox.
   - Live checks screen. If still unchecked, taps again until verified!
4. Once verified 100% checked:
   - Taps Email icon via uiautomator2.
   - Verifies Login Dialog opens instantly.
================================================================================
"""

import os
import sys
import time
import cv2
import numpy as np
import uiautomator2 as u2

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

_U2_CACHE = {}


def get_u2_device(device_id: str = "127.0.0.1:21503"):
    global _U2_CACHE
    if device_id not in _U2_CACHE:
        _U2_CACHE[device_id] = u2.connect(device_id)
    return _U2_CACHE[device_id]


def count_checkmark_pixels(crop: np.ndarray) -> int:
    """Calculates bright green checkmark pixels (immune to dark green background)."""
    if crop is None or crop.size == 0:
        return 0
    b = crop[:, :, 0].astype(int)
    g = crop[:, :, 1].astype(int)
    r = crop[:, :, 2].astype(int)
    return int(np.sum((g > 175) & (g - r > 70) & (g - b > 50)))


def is_terms_checked(device_id: str = "127.0.0.1:21503") -> bool:
    """Verifies if Terms checkbox is checked using live in-memory screen buffer."""
    d = get_u2_device(device_id)
    select_elem = d(resourceId="com.yalla.yallagames:id/iv_select")
    if not select_elem.exists:
        return True

    bounds = select_elem.info.get("bounds")
    if not bounds:
        return False

    pil_img = d.screenshot()
    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    crop = img[bounds["top"]:bounds["bottom"], bounds["left"]:bounds["right"]]
    px = count_checkmark_pixels(crop)
    print(f"[{device_id}] Terms Checkmark Pixels: {px} (Threshold > 150)")
    return px > 150


def ensure_terms_checked(device_id: str = "127.0.0.1:21503", max_retries: int = 4) -> bool:
    """
    User Core Rule:
    'term and condition k box par tab k bade yeh check kray ga
     agr nai howa toh again tab ho ga es k bade email par tab'
    """
    d = get_u2_device(device_id)

    # 1. Check if already checked
    if is_terms_checked(device_id):
        print(f"[{device_id}] [+] Terms & Conditions: ALREADY CHECKED [OK] -> Skipping tap completely! (NO CLICK)")
        return True

    # 2. Tap and verify loop
    for attempt in range(1, max_retries + 1):
        print(f"[{device_id}] [*] Terms is UNCHECKED. Tapping checkbox (Attempt {attempt}/{max_retries})...")
        try:
            d(resourceId="com.yalla.yallagames:id/iv_select").click(timeout=1.0)
        except Exception:
            d.click(105, 1193)
        time.sleep(0.4)
        if not is_terms_checked(device_id):
            # Fallback direct coordinate tap on checkbox center
            d.click(105, 1193)
            time.sleep(0.4)

        if is_terms_checked(device_id):
            print(f"[{device_id}] [+] Terms & Conditions: Successfully verified CHECKED on attempt {attempt} [OK]!")
            return True

        print(f"[{device_id}] [!] Still unchecked after tap! Retrying tap...")

    return is_terms_checked(device_id)


def is_login_dialog_open(device_id: str = "127.0.0.1:21503") -> bool:
    """Instant check via uiautomator2 element presence (<0.05s)."""
    d = get_u2_device(device_id)
    return d(resourceId="com.yalla.yallagames:id/et_phone_number_login").exists or \
           d(resourceId="com.yalla.yallagames:id/bt_login").exists or \
           d(text="Enter password").exists


def execute_main_login_step(device_id: str = "127.0.0.1:21503") -> bool:
    """
    Master function:
    Step 1: Checkbox verified in memory (never double clicks if checked).
    Step 2: Taps Email button.
    Step 3: Verifies Login Dialog open in <0.2s.
    """
    print("\n" + "="*70)
    print("   REWARD COLLECT -> MAIN LOGIN PAGE (UIAUTOMATOR2 ENGINE)")
    print(f"   Target Device: {device_id}")
    print("="*70 + "\n")

    d = get_u2_device(device_id)

    # Step 1: Ensure terms checked with live verification
    print("--- [STEP 1] Terms & Conditions In-Memory Check & Verification ---")
    checked = ensure_terms_checked(device_id)
    if not checked:
        print("[-] Could not verify Terms checkbox checked.")
        return False

    # Step 2: Email Button Click
    print("\n--- [STEP 2] Tapping Email Button ---")
    email_btn = d(resourceId="com.yalla.yallagames:id/ll_email")
    if not email_btn.exists:
        email_btn = d(resourceId="com.yalla.yallagames:id/iv_email")

    if email_btn.exists:
        print("[*] Tapping Email button via uiautomator2...")
        email_btn.click()
    else:
        print("[*] Using coordinate fallback for Email button at (508, 1024)...")
        d.click(508, 1024)

    # Step 3: Fast Dialog Wait
    print("[*] Verifying Login Dialog opened...")
    opened = d(resourceId="com.yalla.yallagames:id/et_phone_number_login").wait(timeout=3.0) or is_login_dialog_open(device_id)

    if opened:
        print("[SUCCESS] Verified! Login Dialog is now OPEN [OK]!")
        return True

    # Retry once if needed
    print("[!] Retrying Email tap at (508, 1042)...")
    d.click(508, 1042)
    time.sleep(0.5)
    opened = is_login_dialog_open(device_id)
    if opened:
        print("[SUCCESS] Verified on retry! Login Dialog is now OPEN [OK]!")
        return True

    print("[-] Failed to open Login Dialog.")
    return False


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21503"
    ok = execute_main_login_step(target)
    print(f"Result: {ok}")
