"""
================================================================================
REWARD COLLECT - FAST DIRECT 3-STEP REWARD COLLECTOR (OPTION A)
================================================================================
Module: reward_collect/daily_reward_collector.py
Purpose:
Option A Direct Fast 3-Step Execution:
1. Step 1: Taps bottom 'Collect' button at (400, 1212) on Daily Sign-in screen.
2. Step 2: Dismisses post-collect popups:
   - Taps 'Confirm' at (400, 818).
   - Taps 'OK' at (208, 814).
3. Step 3: Presses Back key (input keyevent 4) to exit reward screen cleanly
   and transition to Main Lobby!
================================================================================
"""

import os
import subprocess
import sys
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

ADB_BIN = os.path.join(PARENT_DIR, "platform-tools", "adb.exe")
if not os.path.exists(ADB_BIN):
    ADB_BIN = "adb"


def get_adb_cmd(device_id: str = None) -> list:
    cmd = [ADB_BIN]
    if device_id:
        cmd.extend(["-s", device_id])
    return cmd


def run_adb(args: list, device_id: str = None, timeout: float = 5.0) -> str:
    cmd = get_adb_cmd(device_id) + args
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return res.stdout.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[!] ADB error: {e}")
        return ""


def execute_option_a_reward_collect(device_id: str = "127.0.0.1:21613") -> bool:
    """
    Executes Option A Direct Fast 3-Step Reward Collect:
    - Step 1: Tap Collect at (400, 1212).
    - Step 2: Tap Confirm at (400, 818) & OK at (208, 814).
    - Step 3: Press Back key to enter Main Lobby.
    """
    print("\n" + "="*70)
    print("   REWARD COLLECT -> OPTION A DIRECT 3-STEP EXECUTION")
    print(f"   Target Device: {device_id}")
    print("="*70 + "\n")

    # Step 1: Tap Bottom 'Collect' Button
    print("[*] [STEP 1/3] Waiting 1.5s for Daily Sign-in screen...")
    time.sleep(1.5)
    print("[+] Tapping bottom 'Collect' button at (400, 1212)...")
    run_adb(["shell", "input", "tap", "400", "1212"], device_id)
    time.sleep(1.5)

    # Step 2: Dismiss Post-Collect Popups
    print("[*] [STEP 2/3] Dismissing post-collect popups...")
    print("    - Tapping 'Confirm' button at (400, 818)...")
    run_adb(["shell", "input", "tap", "400", "818"], device_id)
    time.sleep(1.0)
    print("    - Tapping 'OK' button at (208, 814)...")
    run_adb(["shell", "input", "tap", "208", "814"], device_id)
    time.sleep(1.0)

    # Step 3: Back Key to Main Lobby
    print("[*] [STEP 3/3] Pressing Back key (keyevent 4) to exit reward screen to Main Lobby...")
    run_adb(["shell", "input", "keyevent", "4"], device_id)
    time.sleep(1.2)
    # Extra safety back press if still on modal
    run_adb(["shell", "input", "keyevent", "4"], device_id)
    time.sleep(1.0)

    print("\n[SUCCESS] Option A 3-Step Reward Collection Completed Successfully [OK]!\n")
    return True


# Alias for backward compatibility with runner
collect_daily_reward_pipeline = execute_option_a_reward_collect


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21613"
    execute_option_a_reward_collect(target)
