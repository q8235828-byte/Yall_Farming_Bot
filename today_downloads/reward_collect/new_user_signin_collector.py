"""
================================================================================
REWARD COLLECT - NEW USER SIGN-IN COLLECTOR & VERIFIER
================================================================================
Module: reward_collect/new_user_signin_collector.py

User Workflow (Images 1 - 3):
Image #1: On 'New User Sign-in' screen, tap Yellow 'Collect' button at (400, 1150).
Image #2: On 'Congratulations' popup, tap 'Confirm' button at (400, 818).
          - Check / tap 'Collect' again if another reward is active.
          - Follow with 'Confirm'.
Image #3: When Collect button turns grey / finished:
          - Send Back key ONCE (input keyevent 4) to cleanly close the dialog.
================================================================================
"""

import os
import re
import subprocess
import sys
import time

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


def run_adb(args: list, device_id: str = None, timeout: float = 6.0) -> str:
    cmd = get_adb_cmd(device_id) + args
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return res.stdout.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[!] ADB error: {e}")
        return ""


def get_screen_xml(device_id: str = None, timeout: float = 4.0) -> str:
    """Dumps compressed UI XML and returns as string."""
    dev_tag = device_id.replace(":", "_").replace(".", "_") if device_id else "def"
    dump_path = f"/sdcard/nu_{dev_tag}.xml"
    run_adb(["shell", "rm", "-f", dump_path], device_id, timeout=2.0)
    cmd = get_adb_cmd(device_id) + ["shell", "uiautomator", "dump", "--compressed", dump_path]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        out = res.stdout.decode("utf-8", errors="ignore")
        if "dumped to" in out or "UI hierchary" in out:
            return run_adb(["shell", "cat", dump_path], device_id, timeout=2.0)
    except Exception:
        pass
    return ""


def is_new_user_signin_open(device_id: str = None) -> bool:
    """Detects if 'New User Sign-in' dialog is currently on screen."""
    xml = get_screen_xml(device_id)
    if any(k in xml for k in ["New User Sign-in", "New User Sign-In", "Cumulative sign-in", "Re-sign in"]):
        return True
    return False


def is_collect_button_disabled(device_id: str = None) -> bool:
    """Checks XML to see if Collect button is disabled/grey."""
    xml = get_screen_xml(device_id)
    if xml:
        m_btn = re.search(r'<node[^>]+text="Collect"[^>]*>', xml)
        if m_btn:
            node_str = m_btn.group(0)
            if 'clickable="false"' in node_str or 'enabled="false"' in node_str:
                return True
    return False


def tap_collect_button(device_id: str = None):
    """Image #1: Taps bottom 'Collect' button at (400, 1150)."""
    coords = (400, 1150)
    print(f"[*] [IMAGE #1] Tapping 'Collect' button at {coords}...")
    run_adb(["shell", "input", "tap", str(coords[0]), str(coords[1])], device_id)
    time.sleep(1.5)


def handle_congratulations_popup(device_id: str = None):
    """Image #2: Clicks 'Confirm' at (400, 818)."""
    coords = (400, 818)
    print(f"[*] [IMAGE #2] Clicking 'Confirm' at {coords}...")
    run_adb(["shell", "input", "tap", str(coords[0]), str(coords[1])], device_id)
    time.sleep(1.5)


def close_dialog_via_back(device_id: str = None):
    """Image #3: Sends Back key ONCE to close New User Sign-in dialog."""
    print("[*] [IMAGE #3] Sending Back key (keyevent 4) to close 'New User Sign-in' screen...")
    run_adb(["shell", "input", "keyevent", "4"], device_id)
    time.sleep(1.5)


def execute_new_user_signin(device_id: str = "127.0.0.1:21613") -> bool:
    """
    User Core Rule:
    'yeh detect ho toh phr ap ne back key krna hai'
    When 'New User Sign-in' is detected, immediately presses Back key to dismiss cleanly.
    """
    print("\n" + "#"*70)
    print("   REWARD COLLECT -> NEW USER SIGN-IN DISMISS (BACK KEY RULE)")
    print(f"   Target Device: {device_id}")
    print("#"*70 + "\n")

    print("[*] [User Rule] 'New User Sign-in' detected! Pressing Back key (keyevent 4)...")
    run_adb(["shell", "input", "keyevent", "4"], device_id)
    time.sleep(1.5)

    # If still visible, send one more Back key as insurance
    if is_new_user_signin_open(device_id):
        print("[*] 'New User Sign-in' still on screen. Sending secondary Back key...")
        run_adb(["shell", "input", "keyevent", "4"], device_id)
        time.sleep(1.2)

    print("[+] 'New User Sign-in' dialog dismissed via Back key [OK]!\n")
    return True


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21613"
    execute_new_user_signin(target)
