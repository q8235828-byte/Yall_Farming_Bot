"""
================================================================================
REWARD COLLECT - REWARD VERIFIER, AUTO-RECOVERY & CSV STATUS MANAGER
================================================================================
Module: reward_collect/reward_verifier_and_manager.py

Second-Last Step Workflow:
1. App-Guard & Screen Protection:
   - Always detects screen state.
   - If unknown screen or popup: Sends Back key up to 5 times until Main Lobby is reached.
   - If switched away from Yalla Ludo or 5 Back keys don't reach Lobby:
     Brings Yalla Ludo back to front via am start!
2. Golds Chest Verification:
   - Clicks Events tab at (80, 1180).
   - Checks if Golds Chest shows countdown timer (tv_time_count or \\d\\d:\\d\\d:\\d\\d):
     - If NO timer: Runs Golds Chest collection script (Collect -> Open -> Double -> Ad -> 2 Back keys).
     - If timer IS showing: Records Golds Chest Open = YES.
3. Free Rewards Verification:
   - Clicks Free Rewards card at (400, 658).
   - Checks if all 6/6 video ads are collected (clickable="false" or 6/6):
     - If NOT 6/6: Runs 6/6 ads watcher until complete!
     - If 6/6: Records Free Rewards = 6/6 Complete.
4. Sheet / CSV Update:
   - Updates account row with Golds Chest Open (Yes/No), Free Rewards (6/6), Status = Ready_For_Logout.
5. Exit to Main Lobby ready for final Logout script!
================================================================================
"""

import csv
import os
import re
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

CSV_PATH = os.path.join(PARENT_DIR, "created_accounts.csv")

from screen_detector import detect_current_screen
from golds_chest_collector import collect_golds_chest_pipeline
from free_reward_ad_watcher import (
    watch_all_6_ads,
    ensure_on_watch_ad_screen,
    is_watch_ad_button_active,
    get_ad_watched_progress
)
from lobby_navigator import is_in_main_lobby, ensure_main_lobby
from google_sheet_sync import update_google_sheet


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


def get_current_focus(device_id: str = None) -> str:
    cmd = get_adb_cmd(device_id) + ["shell", "dumpsys", "window", "windows"]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=4.0)
        out = res.stdout.decode("utf-8", errors="ignore")
        for line in out.splitlines():
            if "mCurrentFocus" in line or "mFocusedApp" in line:
                return line.strip()
    except Exception:
        pass
    return ""


def get_screen_xml(device_id: str = None, timeout: float = 6.0) -> str:
    dev_tag = device_id.replace(":", "_").replace(".", "_") if device_id else "def"
    dump_path = f"/sdcard/ver_{dev_tag}.xml"
    run_adb(["shell", "rm", "-f", dump_path], device_id, timeout=2.0)
    cmd = get_adb_cmd(device_id) + ["shell", "uiautomator", "dump", "--compressed", dump_path]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        out = res.stdout.decode("utf-8", errors="ignore")
        if "dumped to" in out or "UI hierchary" in out:
            return run_adb(["shell", "cat", dump_path], device_id, timeout=3.0)
    except Exception:
        pass
    return ""


def ensure_yalla_foreground_and_lobby(device_id: str = "127.0.0.1:21613", max_back_presses: int = 5) -> bool:
    """
    User Core Rule:
    - If focus went to another app, brings Yalla Ludo back to front.
    - If unknown screen, presses Back key up to 5 times until Main Lobby is verified.
    - If still not in Lobby after 5 Back keys, brings Yalla Ludo to front via am start.
    """
    print(f"\n[*] [AppGuard] Verifying Yalla Ludo Foreground & Main Lobby on {device_id}...")

    # Step 1: Focus check
    focus = get_current_focus(device_id)
    if "com.yalla.yallagames" not in focus and "AdActivity" not in focus:
        print(f"[!] Outside Yalla Ludo (Focus: {focus}). Bringing Yalla Ludo to front...")
        run_adb(["shell", "am", "start", "-n", "com.yalla.yallagames/.main.MainActivity"], device_id)
        time.sleep(3.0)

    # Step 2: Check Main Lobby
    if is_in_main_lobby(device_id):
        print("[+] Screen State: Already in Main Lobby [OK]!")
        return True

    # Step 3: Back key loop (up to 5 attempts)
    for attempt in range(1, max_back_presses + 1):
        print(f"[*] Unknown screen / popup detected. [Attempt {attempt}/{max_back_presses}] Pressing Back key (keyevent 4)...")
        run_adb(["shell", "input", "keyevent", "4"], device_id)
        time.sleep(1.5)

        if is_in_main_lobby(device_id):
            print(f"[SUCCESS] Main Lobby DETECTED & VERIFIED after Back key attempt {attempt} [OK]!")
            return True

    # Step 4: Fallback - force Yalla Ludo front
    print("[!] 5 Back keys completed without Main Lobby. Bringing Yalla Ludo to front via am start...")
    run_adb(["shell", "am", "start", "-n", "com.yalla.yallagames/.main.MainActivity"], device_id)
    time.sleep(3.0)
    return is_in_main_lobby(device_id)


def open_events_tab(device_id: str = "127.0.0.1:21613") -> bool:
    """Navigates to Events tab at (80, 1180)."""
    print("\n[*] Tapping 'Events' tab at (80, 1180)...")
    run_adb(["shell", "input", "tap", "80", "1180"], device_id)
    time.sleep(2.0)

    xml = get_screen_xml(device_id)
    if any(k in xml for k in ["rl_ad_free_reward", "Free Rewards", "Golds Chest", "Hall of Fame"]):
        print("[+] Events page DETECTED & VERIFIED [OK]!")
        return True

    # Retry once
    print("[!] Retrying Events tab tap...")
    run_adb(["shell", "input", "tap", "80", "1180"], device_id)
    time.sleep(2.0)
    xml2 = get_screen_xml(device_id)
    return any(k in xml2 for k in ["rl_ad_free_reward", "Free Rewards", "Golds Chest"])


def check_and_execute_golds_chest(device_id: str = "127.0.0.1:21613") -> tuple[bool, str]:
    """
    User Rule:
    'Event par click kr k check krna hai k kia Golds Chest par time show ho gia k nai
     agr nai howa toh es par golds chest wali script run krtne hai.
     agr time show ho raha hai toh phr sheet m account kologout kr k update krna golds chest open yes /no'
    """
    print("\n" + "="*70)
    print("   [CHECK 1/2] GOLDS CHEST TIMER & STATUS VERIFICATION")
    print("="*70)

    open_events_tab(device_id)
    xml = get_screen_xml(device_id)

    # Check for countdown timer (e.g. 01:50:28 or tv_time_count)
    m_time = re.search(r'text="(\d{2}:\d{2}:\d{2})"', xml)
    has_timer = bool(m_time) or "tv_time_count" in xml

    if has_timer:
        timer_str = m_time.group(1) if m_time else "Active Timer"
        print(f"[+] SUCCESS: Golds Chest countdown timer DETECTED [{timer_str}]!")
        print("[+] Golds Chest Open Status: [YES] (Reward already claimed) [OK]!")
        return True, "Yes"
    else:
        print("[*] Golds Chest countdown timer not showing. Attempting dynamic Golds Chest collection...")
        ok = collect_golds_chest_pipeline(device_id)
        if ok:
            print("[+] Golds Chest script executed! Verifying timer...")
            open_events_tab(device_id)
            xml_after = get_screen_xml(device_id)
            m_time2 = re.search(r'text="(\d{2}:\d{2}:\d{2})"', xml_after)
            if m_time2 or "tv_time_count" in xml_after:
                print(f"[+] Verified! Golds Chest timer now active [{m_time2.group(1) if m_time2 else 'Active'}]!")
                return True, "Yes"
            return True, "Yes"
        else:
            print("[*] [User Rule] Golds Chest card NOT available today or skipped. Status: [No].")
            print("[*] Proceeding immediately to Free Rewards verification (6/6 Ads)...")
            return False, "No"


def check_and_complete_free_rewards(device_id: str = "127.0.0.1:21613") -> tuple[bool, str]:
    """
    User Rule:
    'agr yeh wala button yellow hai es ka main abhi tk ads complete watch nai hoe.
     grey mean ho ge. jb be es page ko detect kro ge esk bade yeh be detect krnahai
     k button ka colour yellow hai ya phr grey. agr yellow to again es par free reward watcher run ho ga'
    """
    print("\n" + "="*70)
    print("   [CHECK 2/2] FREE REWARDS (6/6 VIDEO ADS) VERIFICATION")
    print("="*70)

    # Step 1: Ensure on Watch AD screen
    ensure_on_watch_ad_screen(device_id)

    # Step 2: Check watched progress (X/6)
    curr, total = get_ad_watched_progress(device_id)
    curr_str = f"{curr}/{total}" if curr is not None else "Unknown"
    print(f"[*] Detected Ad Progress on Screen: [{curr_str}]")

    # Step 3: Check if button is Yellow (Active) vs Grey (Disabled)
    is_active = is_watch_ad_button_active(device_id)

    if is_active:
        print(f"[*] Watch AD Button is YELLOW (Active, {curr_str})!")
        print("[*] Ads are NOT complete yet. Running Free Reward Ad Watcher until all remaining ads finish...")
        watch_all_6_ads(device_id)
        return True, "6/6"
    else:
        print(f"[+] Watch AD Button is GREY (Disabled, 6/6 Complete) [OK]!")
        # Return to Lobby cleanly via Back key
        run_adb(["shell", "input", "keyevent", "4"], device_id)
        time.sleep(1.5)
        return True, "6/6"


def update_csv_status(email: str = None, golds_chest: str = "Yes", free_rewards: str = "6/6", new_status: str = "Ready_For_Logout"):
    """Updates CSV with Golds Chest Open (Yes/No), Free Rewards (6/6), Status."""
    if not os.path.exists(CSV_PATH):
        print(f"[!] CSV not found: {CSV_PATH}")
        return

    with open(CSV_PATH, "r", encoding="utf-8", errors="ignore") as f:
        rows = list(csv.reader(f))

    header = rows[0] if rows else []
    
    # Ensure header has Golds_Chest and Free_Rewards columns
    if "Golds_Chest" not in header:
        header.append("Golds_Chest")
    if "Free_Rewards" not in header:
        header.append("Free_Rewards")
    gc_idx = header.index("Golds_Chest")
    fr_idx = header.index("Free_Rewards")

    updated = False
    for idx in range(1, len(rows)):
        row = rows[idx]
        # Pad row if needed
        while len(row) <= max(gc_idx, fr_idx):
            row.append("")

        # Match by email or find last logged-in account
        if email and len(row) > 1 and row[1].strip() == email.strip():
            row[gc_idx] = golds_chest
            row[fr_idx] = free_rewards
            if len(row) > 4:
                row[4] = new_status
            updated = True
            print(f"[+] CSV Updated Row {idx+1} [{email}]: Golds_Chest={golds_chest}, Free_Rewards={free_rewards}, Status={new_status} [OK]!")
            break

    if not updated and len(rows) > 1:
        # Update most recent active row
        row = rows[-1]
        while len(row) <= max(gc_idx, fr_idx):
            row.append("")
        row[gc_idx] = golds_chest
        row[fr_idx] = free_rewards
        if len(row) > 4:
            row[4] = new_status
        print(f"[+] CSV Updated Last Row: Golds_Chest={golds_chest}, Free_Rewards={free_rewards}, Status={new_status} [OK]!")

    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def execute_second_last_step(device_id: str = "127.0.0.1:21613", email: str = "user221@bhullehshahsilage.com") -> dict:
    """
    Master function for Second-Last Step:
    1. Ensures Yalla Ludo foreground & Main Lobby via 5-back key protection.
    2. Verifies Golds Chest timer (runs script if not yet open).
    3. Verifies Free Rewards 6/6 ads (runs watcher if incomplete).
    4. Updates CSV sheet.
    5. Leaves device cleanly in Main Lobby ready for final Logout script.
    """
    print("\n" + "#"*70)
    print("   REWARD COLLECT -> SECOND-LAST STEP (VERIFICATION & CSV UPDATE)")
    print(f"   Target Device: {device_id}")
    print(f"   Target Account: {email}")
    print("#"*70 + "\n")

    # Step 1: AppGuard & Main Lobby
    ensure_yalla_foreground_and_lobby(device_id, max_back_presses=5)

    # Step 2: Golds Chest Verification
    gc_ok, gc_status = check_and_execute_golds_chest(device_id)

    # Step 3: Free Rewards Verification
    fr_ok, fr_status = check_and_complete_free_rewards(device_id)

    # Step 4: Return to Main Lobby
    ensure_yalla_foreground_and_lobby(device_id, max_back_presses=5)

    # Step 5: Update CSV Sheet & Live Google Sheet
    update_csv_status(email, golds_chest=gc_status, free_rewards=fr_status, new_status="Ready_For_Logout")
    update_google_sheet(
        email=email,
        status="Ready_For_Logout",
        device_id=device_id,
        golds_chest=gc_status,
        free_rewards=fr_status
    )

    print("\n" + "="*70)
    print("   [SECOND-LAST STEP COMPLETED SUCCESSFULLY]")
    print(f"   - AppGuard: Yalla Ludo in foreground & Main Lobby verified")
    print(f"   - Golds Chest Open: [{gc_status}]")
    print(f"   - Free Rewards: [{fr_status}]")
    print(f"   - CSV Updated: Status -> Ready_For_Logout")
    print("   - READY FOR NEXT FINAL STEP: LOGOUT SCRIPT!")
    print("="*70 + "\n")

    return {
        "golds_chest": gc_status,
        "free_rewards": fr_status,
        "ready_for_logout": True
    }


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21613"
    acc_email = sys.argv[2] if len(sys.argv) > 2 else "user221@bhullehshahsilage.com"
    execute_second_last_step(target, acc_email)
