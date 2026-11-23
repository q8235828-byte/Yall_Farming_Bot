"""
================================================================================
YALLA LUDO - CLEAN LOGOUT HANDLER (logout_handler.py)
================================================================================
Workflow:
1. Detects current screen state:
   - If already on MAIN_LANDING_PAGE, returns True immediately.
   - If on popup or outside Lobby, brings Yalla Ludo to Lobby using 5-back key protection.
2. From MAIN_LOBBY:
   - Taps Settings Gear icon (iv_setting) at (755, 56).
   - Waits 0.8s for Settings dialog to render.
   - Taps 'Log Out' button (bt_cancellation) at (208, 938).
   - If a confirmation dialog appears ("Are you sure?"), taps Confirm at (530, 750).
   - Waits 1.5s for logout transition.
3. Verifies device has landed cleanly on MAIN_LANDING_PAGE.
================================================================================
"""

import os
import subprocess
import sys
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

ADB_BIN = os.path.join(PARENT_DIR, "platform-tools", "adb.exe")
if not os.path.exists(ADB_BIN):
    ADB_BIN = "adb"

from screen_detector import detect_current_screen
from lobby_navigator import is_in_main_lobby


def run_adb(args: list, device_id: str = None, timeout: float = 6.0) -> str:
    cmd = [ADB_BIN]
    if device_id:
        cmd.extend(["-s", device_id])
    cmd.extend(args)
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return res.stdout.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[!] ADB error: {e}")
        return ""


def execute_logout(device_id: str = "127.0.0.1:21613", max_retries: int = 3) -> bool:
    """
    Executes a guaranteed logout from Yalla Ludo to return to MAIN_LANDING_PAGE.
    """
    print(f"\n" + "="*70)
    print(f"   [FINAL STEP] EXECUTING LOGOUT ON {device_id}")
    print(f"="*70)

    for attempt in range(1, max_retries + 1):
        # Step 1: Detect current screen
        state = detect_current_screen(device_id)
        print(f"[*] [Attempt {attempt}/{max_retries}] Current Screen State: [{state}]")

        if state == "MAIN_LANDING_PAGE":
            print("[+] ALREADY ON MAIN_LANDING_PAGE [OK]! Logout verified.")
            return True

        if state != "MAIN_LOBBY":
            # Bring to lobby or close popups
            print("[*] Closing popups or ensuring Main Lobby via Back key...")
            for _ in range(4):
                run_adb(["shell", "input", "keyevent", "4"], device_id)
                time.sleep(1.0)
                if is_in_main_lobby(device_id):
                    break
            time.sleep(1.0)

        # Step 2: Tap Settings Gear at (755, 56)
        print("[*] Tapping Settings Gear icon (iv_setting) at (755, 56)...")
        run_adb(["shell", "input", "tap", "755", "56"], device_id)
        time.sleep(1.0)

        # Step 3: Tap Log Out (bt_cancellation) at (208, 938)
        print("[*] Tapping 'Log Out' button (bt_cancellation) at (208, 938)...")
        run_adb(["shell", "input", "tap", "208", "938"], device_id)
        time.sleep(1.5)

        # Step 4: Handle possible confirmation popup
        # If confirmation dialog appears, tap confirm button
        state_after = detect_current_screen(device_id)
        if state_after == "MAIN_LANDING_PAGE":
            print(f"[SUCCESS] LOGOUT COMPLETED! Device {device_id} is on MAIN_LANDING_PAGE [OK]!")
            return True

        # Check if confirmation dialog is visible
        print("[*] Checking for confirmation dialog at (530, 750)...")
        run_adb(["shell", "input", "tap", "530", "750"], device_id)
        time.sleep(2.0)

        # Step 5: Final verification
        final_state = detect_current_screen(device_id)
        if final_state == "MAIN_LANDING_PAGE":
            print(f"[SUCCESS] LOGOUT CONFIRMED! Device {device_id} is on MAIN_LANDING_PAGE [OK]!")
            return True
        else:
            print(f"[!] Warning: Device still at [{final_state}]. Retrying logout...")

    print(f"[-] Failed to reach MAIN_LANDING_PAGE after {max_retries} attempts.")
    return False


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21613"
    ok = execute_logout(target)
    print(f"Logout Result: {ok}")
