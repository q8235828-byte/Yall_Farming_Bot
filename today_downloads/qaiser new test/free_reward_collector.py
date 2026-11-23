"""
================================================================================
REWARD COLLECT - FREE REWARD NAVIGATOR & SCREEN VERIFICATION
================================================================================
Module: reward_collect/free_reward_collector.py
Purpose:
1. Taps 'Events' icon in Main Lobby navigation bar at (80, 1180)
   (bounds: [0, 1095][160, 1268], resource-id: com.yalla.yallagames:id/events_item).
2. Taps 'Free Rewards' card on Events page at (400, 658)
   (bounds: [22, 548][778, 769], resource-id: com.yalla.yallagames:id/rl_ad_free_reward).
3. Verifies 'Watch AD & Win Rewards' screen:
   - Checks for 'Watch AD & Win Rewards' or 'll_btn_watch_ad' or 'AD watched times today'.
================================================================================
"""

import os
import re
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


def run_adb(args: list, device_id: str = None, timeout: float = 6.0) -> str:
    cmd = get_adb_cmd(device_id) + args
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return res.stdout.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[!] ADB error: {e}")
        return ""


def get_screen_xml(device_id: str = None) -> str:
    """Dumps compressed UI XML and returns as string."""
    dev_tag = device_id.replace(":", "_").replace(".", "_") if device_id else "def"
    dump_path = f"/sdcard/free_{dev_tag}.xml"
    run_adb(["shell", "rm", "-f", dump_path], device_id, timeout=2.0)
    cmd = get_adb_cmd(device_id) + ["shell", "uiautomator", "dump", "--compressed", dump_path]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8.0)
        out = res.stdout.decode("utf-8", errors="ignore")
        if "dumped to" in out:
            return run_adb(["shell", "cat", dump_path], device_id, timeout=3.0)
    except Exception:
        pass
    return ""


def open_events_tab(device_id: str = "127.0.0.1:21613") -> bool:
    """
    [STEP 1] Taps Events icon in Main Lobby navigation bar.
    Coordinates: (80, 1180), bounds [0, 1095][160, 1268].
    """
    print("\n--- [STEP 1] Tapping 'Events' Icon in Main Lobby ---")
    events_coords = (80, 1180)
    print(f"[*] Tapping Events tab at {events_coords}...")
    run_adb(["shell", "input", "tap", str(events_coords[0]), str(events_coords[1])], device_id)
    time.sleep(1.5)

    xml_str = get_screen_xml(device_id)
    if "rl_ad_free_reward" in xml_str or "Free Rewards" in xml_str or "Golds Chest" in xml_str:
        print("[+] Events Page DETECTED & VERIFIED [OK]!")
        return True
    
    # Retry tap once if not transitioned
    print("[!] Retrying Events tab tap...")
    run_adb(["shell", "input", "tap", str(events_coords[0]), str(events_coords[1])], device_id)
    time.sleep(1.5)
    xml_str = get_screen_xml(device_id)
    return "rl_ad_free_reward" in xml_str or "Free Rewards" in xml_str


def tap_free_rewards_card(device_id: str = "127.0.0.1:21613") -> bool:
    """
    [STEP 2] Taps 'Free Rewards' card on Events page.
    Bounds: [22, 548][778, 769], center (400, 658).
    """
    print("\n--- [STEP 2] Tapping 'Free Rewards' Card on Events Page ---")
    card_coords = (400, 658)
    print(f"[*] Tapping 'Free Rewards' card at {card_coords}...")
    run_adb(["shell", "input", "tap", str(card_coords[0]), str(card_coords[1])], device_id)
    time.sleep(1.5)
    return True


def verify_free_rewards_screen(device_id: str = "127.0.0.1:21613") -> bool:
    """
    [STEP 3] Verifies 'Watch AD & Win Rewards' screen is open.
    Looks for:
    - 'Watch AD & Win Rewards'
    - 'll_btn_watch_ad' / 'Watch AD'
    - 'AD watched times today'
    """
    print("\n--- [STEP 3] Verifying 'Free Rewards / Watch AD' Screen ---")
    xml_str = get_screen_xml(device_id)

    indicators = [
        "Watch AD & Win Rewards",
        "Watch AD &amp; Win Rewards",
        "ll_btn_watch_ad",
        "AD watched times today",
        "ll_watch",
        "tv_times"
    ]

    for ind in indicators:
        if ind in xml_str:
            print(f"[+] Screen VERIFIED! Found indicator: [{ind}] [100% SUCCESS]!")
            return True

    print("[-] Warning: Could not verify 'Watch AD & Win Rewards' screen.")
    return False


def execute_free_reward_flow(device_id: str = "127.0.0.1:21613") -> bool:
    """
    Master function:
    1. If already on Watch AD screen -> returns True immediately.
    2. If on Events tab -> taps Free Rewards card directly.
    3. If in Main Lobby -> taps Events (80, 1180) -> card (400, 658).
    4. Verifies 'Watch AD & Win Rewards' screen.
    """
    print("\n" + "#"*70)
    print("   STARTING FREE REWARDS NAVIGATOR & VERIFICATION PIPELINE")
    print(f"   Target Device: {device_id}")
    print("#"*70)

    # Fast-path: Check if already on Watch AD screen
    if verify_free_rewards_screen(device_id):
        print("[+] Screen State: Already on 'Watch AD & Win Rewards' screen [OK]!")
        return True

    # Step 1: Open Events tab
    events_ok = open_events_tab(device_id)
    if not events_ok:
        print("[!] Warning: Events tab verification not confirmed, proceeding to tap card...")

    # Step 2: Tap Free Rewards card
    tap_free_rewards_card(device_id)
    time.sleep(2.0)

    # Step 3: Verify target screen
    verified = verify_free_rewards_screen(device_id)

    print("\n" + "="*70)
    if verified:
        print("   FINAL RESULT: FREE REWARDS SCREEN REACHED & VERIFIED [SUCCESS]!")
    else:
        print("   FINAL RESULT: FREE REWARDS SCREEN VERIFICATION FAILED [!] ")
    print("="*70 + "\n")

    return verified


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21613"
    execute_free_reward_flow(target)
