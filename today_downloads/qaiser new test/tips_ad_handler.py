"""
================================================================================
TIPS AD POPUP HANDLER (tips_ad_handler.py)
================================================================================
Handles the pre-video ad confirmation popup:
"Tips: You are about to watch a video ad. After watching, you can receive a reward. Do you want to continue?"

User Instruction:
"box ko checkout krn ahai es k bade phr watch par click and done"
1. Taps 'Don't ask me again' checkbox at (227, 906).
2. Taps yellow 'Watch' button at (536, 764).
================================================================================
"""

import os
import subprocess
import sys
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
ADB_BIN = os.path.join(PARENT_DIR, "platform-tools", "adb.exe")
if not os.path.exists(ADB_BIN):
    ADB_BIN = "adb"


def run_adb(args: list, device_id: str = None) -> str:
    cmd = [ADB_BIN]
    if device_id:
        cmd.extend(["-s", device_id])
    cmd.extend(args)
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=4.0)
        return res.stdout.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def is_tips_ad_popup_present(device_id: str = None) -> bool:
    dev_tag = device_id.replace(":", "_").replace(".", "_") if device_id else "def"
    dump_path = f"/sdcard/tips_{dev_tag}.xml"
    run_adb(["shell", "rm", "-f", dump_path], device_id)
    run_adb(["shell", "uiautomator", "dump", "--compressed", dump_path], device_id)
    xml = run_adb(["shell", "cat", dump_path], device_id)
    return any(k in xml for k in ["Don't ask me again", "Don’t ask me again", "You are about to watch a video ad", "receive a reward"])


def handle_tips_ad_popup(device_id: str = "127.0.0.1:21613", force: bool = False) -> bool:
    """
    User Rule:
    'box ko checkout krn ahai es k bade phr watch par click and done'
    - Checkbox: (227, 906)
    - Yellow Watch button: (536, 764)
    """
    if not force and not is_tips_ad_popup_present(device_id):
        return False

    print(f"\n[*] [TipsAdPopup] DETECTED on {device_id}! Ticking 'Don’t ask me again' checkbox at (227, 906)...")
    # 1. Tap checkbox
    run_adb(["shell", "input", "tap", "227", "906"], device_id)
    time.sleep(0.5)

    # 2. Tap Yellow Watch button
    print(f"[*] [TipsAdPopup] Tapping Yellow 'Watch' button at (536, 764)...")
    run_adb(["shell", "input", "tap", "536", "764"], device_id)
    time.sleep(1.2)
    print(f"[+] [TipsAdPopup] Checkbox ticked & Watch button clicked [DONE]!\n")
    return True


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21533"
    handle_tips_ad_popup(target, force=True)
