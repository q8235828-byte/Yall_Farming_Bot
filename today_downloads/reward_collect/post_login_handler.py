"""
================================================================================
REWARD COLLECT - POST-LOGIN & EXPERT DIALOG HANDLER
================================================================================
Module: reward_collect/post_login_handler.py
Purpose:
1. Handle 'I’m expert' welcome dialog:
   - Condition: Only taps if the dialog appears (not all accounts show this dialog).
   - If present: Taps 'I’m expert' button (com.yalla.yallagames:id/btn_yes at 534, 746).
   - If not present: Gracefully skips without error.
2. Inspect and report next screen state (e.g. Daily Bonus popup, Lobby, etc.).
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


def run_adb(args: list, device_id: str = None) -> str:
    cmd = get_adb_cmd(device_id) + args
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        return res.stdout.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[!] ADB error: {e}")
        return ""


def get_screen_xml(device_id: str = None) -> str:
    """Dumps compressed UI XML cleanly and returns as string."""
    dev_tag = device_id.replace(":", "_").replace(".", "_") if device_id else "def"
    dump_path = f"/sdcard/ui_{dev_tag}.xml"
    run_adb(["shell", "rm", "-f", dump_path], device_id)
    out = run_adb(["shell", "uiautomator", "dump", "--compressed", dump_path], device_id)
    if "dumped to" in out:
        return run_adb(["shell", "cat", dump_path], device_id)
    return ""


def is_expert_dialog_present(device_id: str = None) -> tuple[bool, tuple[int, int] | None]:
    """
    Checks if 'I’m expert' dialog is currently showing.
    Returns (True, (x, y)) if found, else (False, None).
    """
    xml_str = get_screen_xml(device_id)
    
    # Check for btn_yes bounds
    m = re.search(r'resource-id="com\.yalla\.yallagames:id/btn_yes"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml_str)
    if m:
        x1, y1, x2, y2 = map(int, m.groups())
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        return True, (cx, cy)
    
    # Text fallback
    if "I’m expert" in xml_str or "I'm expert" in xml_str:
        return True, (534, 746)

    return False, None


def handle_expert_dialog(device_id: str = "127.0.0.1:21613") -> bool:
    """
    User New Rule:
    'Im expert k liye new rule add krna yeh best rahe ga jb yeh detect hoga toih two times back key'
    When 'I'm expert' dialog is detected on screen, presses Back key 2 times!
    """
    print("\n" + "="*70)
    print("   REWARD COLLECT -> EXPERT DIALOG HANDLER (2X BACK KEY RULE)")
    print(f"   Target Device: {device_id}")
    print("="*70 + "\n")

    present, coords = is_expert_dialog_present(device_id)

    if present:
        print(f"[+] 'I’m expert' dialogue box DETECTED on screen!")
        print("[*] [User Rule] Pressing Back key (1/2)...")
        run_adb(["shell", "input", "keyevent", "4"], device_id)
        time.sleep(1.0)
        print("[*] [User Rule] Pressing Back key (2/2)...")
        run_adb(["shell", "input", "keyevent", "4"], device_id)
        time.sleep(1.5)
        print("[+] 2x Back keys pressed successfully for Expert dialog [OK]!")
        return True
    else:
        print("[*] 'I’m expert' dialogue box is NOT present on screen.")
        return False


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21613"
    handle_expert_dialog(target)
