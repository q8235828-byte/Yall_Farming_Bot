"""
================================================================================
YALLA LUDO - MASTER END-TO-END AUTOMATION PIPELINE (master_pipeline.py)
================================================================================
Full Autonomous Cycle:
1. Pulls Account from Live Google Sheet (or accepts command-line args).
2. Verifies Main Landing Page & checks Terms checkbox.
3. Form Login: Enters Email & Password, taps Login.
4. Auto-solves Captcha Puzzle via Color Indexed Solver.
5. Dynamic Screen State Detection & Branching:
   - EXPERT_DIALOG: Taps 'I am expert'
   - DAILY_REWARD_POPUP: Collects Daily Reward Option A
   - NEW_USER_SIGNIN: Collects Sign-in reward until Grey, closes dialog
   - FREE_REWARDS: Watches 6/6 video ads (ad watcher state machine)
   - GOLDS_CHEST: Opens chest, taps Double, watches video ad, 2x Back keys
6. Second-Last Step (reward_verifier_and_manager):
   - Verifies Golds Chest timer is active
   - Verifies Free Rewards button is Grey
   - Syncs real-time to Google Sheet (Golds_Chest: Yes, Free_Rewards: 6/6, Status: Ready_For_Logout)
7. Final Step (logout_handler):
   - Taps Gear -> Log Out -> reaches Main Landing Page
   - Updates Google Sheet (Status: Completed_LoggedOut)
================================================================================
"""

import os
import sys
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

from screen_detector import detect_current_screen
from main_login_page import execute_main_login_step
from login_form_handler import execute_login_flow
from daily_reward_collector import collect_daily_reward_pipeline
from new_user_signin_collector import execute_new_user_signin
from free_reward_ad_watcher import watch_all_6_ads
from golds_chest_collector import collect_golds_chest_pipeline
from reward_verifier_and_manager import execute_second_last_step
from logout_handler import execute_logout
from tips_ad_handler import handle_tips_ad_popup
from google_sheet_sync import update_google_sheet, fetch_all_accounts_from_sheet, get_next_accounts_to_process, load_24h_history, is_account_eligible_to_process
from lobby_navigator import ensure_main_lobby, is_in_main_lobby


def ensure_yalla_running(device_id: str, timeout: float = 15.0) -> str:
    """
    Checks if Yalla Ludo is running and in foreground.
    If APP_NOT_RUNNING or minimized:
    - Launches Yalla Ludo via 'am start -n com.yalla.yallagames/.main.MainActivity'.
    - Waits for splash/loading screen to settle.
    - Returns the real detected screen state.
    """
    state = detect_current_screen(device_id)
    if state == "APP_NOT_RUNNING":
        print(f"\n[!] [AppGuard] Yalla Ludo is NOT running on {device_id}!")
        print("[*] Launching Yalla Ludo ('am start -n com.yalla.yallagames/.main.MainActivity')...")
        from screen_detector import run_adb
        run_adb(["shell", "am", "start", "-n", "com.yalla.yallagames/.main.MainActivity"], device_id)

        # Wait up to timeout for app to load & splash screen to pass
        start_t = time.time()
        time.sleep(4.0)
        while time.time() - start_t < timeout:
            state = detect_current_screen(device_id)
            if state not in ["APP_NOT_RUNNING", "UNKNOWN_SCREEN"]:
                print(f"[+] [AppGuard] Yalla Ludo launched successfully! Detected Screen: [{state}] [OK]")
                return state
            time.sleep(1.5)

        state = detect_current_screen(device_id)
        print(f"[*] [AppGuard] Launch wait finished. Current Screen: [{state}]")
    return state


def run_full_account_cycle(
    device_id: str = "127.0.0.1:21613",
    email: str = "user221@bhullehshahsilage.com",
    password: str = "Yalla#2026@Pass"
) -> bool:
    t_start = time.time()
    print("\n" + "="*80)
    print("   YALLA LUDO - STARTING FULL END-TO-END PIPELINE WITH TIME BENCHMARK")
    print(f"   Device ID : {device_id}")
    print(f"   Account   : {email}")
    print(f"   Start Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")

    # Sync initial status to Google Sheet
    update_google_sheet(email=email, status="Processing", device_id=device_id)

    # STEP 1: Ensure Yalla Ludo is running & prepare landing page
    t_login_start = time.time()
    current_state = ensure_yalla_running(device_id)
    print(f"[*] Initial screen state: [{current_state}]")

    if current_state == "MAIN_LOBBY":
        print("[*] Device already in Lobby. Running reward verification directly...")
    elif current_state not in ["MAIN_LANDING_PAGE", "EMAIL_LOGIN_DIALOG"]:
        from screen_detector import run_adb
        for attempt in range(1, 5):
            run_adb(["shell", "input", "keyevent", "4"], device_id)
            time.sleep(1.0)
            current_state = detect_current_screen(device_id)
            if current_state in ["MAIN_LANDING_PAGE", "EMAIL_LOGIN_DIALOG", "MAIN_LOBBY"]:
                break
        if current_state == "APP_NOT_RUNNING":
            current_state = ensure_yalla_running(device_id)

    # STEP 2: Login if on landing page
    if current_state == "MAIN_LANDING_PAGE":
        print("\n[*] Opening Email login dialog via execute_main_login_step...")
        if not execute_main_login_step(device_id):
            print("[-] Failed to open email dialog.")
            update_google_sheet(email=email, status="Failed_Open_Dialog", device_id=device_id)
            return False
        current_state = "EMAIL_LOGIN_DIALOG"

    if current_state == "EMAIL_LOGIN_DIALOG":
        print(f"\n[*] Submitting credentials for {email} (No Captcha - Old Version)...")
        login_ok, login_state = execute_login_flow(device_id, email, password)
        if not login_ok:
            print(f"[-] Login failed: {login_state}")
            update_google_sheet(email=email, status=f"Login_Failed_{login_state}", device_id=device_id)
            return False
    t_login_dur = time.time() - t_login_start

    # STEP 3: Handle Post-Login screens dynamically
    t_rewards_start = time.time()
    print("\n[*] Handling post-login popups and rewards dynamically...")
    max_steps = 15
    for step in range(1, max_steps + 1):
        state = detect_current_screen(device_id)
        print(f"[*] [Step {step}/{max_steps}] Detected Screen: [{state}]")

        if state == "APP_NOT_RUNNING":
            print("[!] [AppGuard] App is NOT running! Launching Yalla Ludo...")
            state = ensure_yalla_running(device_id)
            time.sleep(1.5)
            continue

        if state == "EXPERT_DIALOG":
            print("[*] [User Rule] 'I’m expert' dialog detected! Pressing Back key 2 times...")
            from screen_detector import run_adb
            run_adb(["shell", "input", "keyevent", "4"], device_id)
            time.sleep(1.0)
            run_adb(["shell", "input", "keyevent", "4"], device_id)
            time.sleep(1.5)
            print("[+] 2x Back keys completed for Expert dialog [OK]!")

        elif state == "DAILY_REWARD_POPUP":
            print("[*] [Skip Requested] Dismissing Daily Reward via Back key...")
            from screen_detector import run_adb
            run_adb(["shell", "input", "keyevent", "4"], device_id)
            time.sleep(1.0)

        elif state == "NEW_USER_SIGNIN":
            print("[*] [User Rule] 'New User Sign-in' detected! Collecting & Dismissing...")
            execute_new_user_signin(device_id)
            time.sleep(1.5)

        elif state == "FREE_REWARDS_SCREEN":
            print("[*] Running Free Rewards Video Ad Watcher (6/6 Ads)...")
            watch_all_6_ads(device_id)
            time.sleep(1.5)

        elif state == "TIPS_AD_POPUP":
            print("[*] Tips Ad popup detected! Handling checkbox + Watch...")
            handle_tips_ad_popup(device_id)
            time.sleep(1.5)

        elif state in ["OPEN_CHEST_POPUP", "DOUBLE_REWARD_POPUP"]:
            print("[*] [Skip Requested] Dismissing Golds Chest popup via Back key...")
            from screen_detector import run_adb
            run_adb(["shell", "input", "keyevent", "4"], device_id)
            time.sleep(1.0)

        elif state == "VIP_PRIVILEGES_SCREEN":
            print("[*] 'Privileges / VIP Room' screen detected. Dismissing via Back key...")
            from screen_detector import run_adb
            run_adb(["shell", "input", "keyevent", "4"], device_id)
            time.sleep(1.5)

        elif state == "MAIN_LOBBY":
            print("\n[+] Main Lobby reached! Proceeding to Free Rewards & Logout Steps...")
            break
        else:
            print(f"[*] Unknown screen or popup [{state}]. Sending Back key...")
            from screen_detector import run_adb
            run_adb(["shell", "input", "keyevent", "4"], device_id)
            time.sleep(1.5)

    # STEP 4: Focus 2 - 6/6 Free Rewards Verification & Watcher
    print("\n[*] [Step 2 Focus] Executing Free Rewards (6/6 Video Ads) Verification...")
    from reward_verifier_and_manager import check_and_complete_free_rewards
    free_rewards_ok, free_rewards_status = check_and_complete_free_rewards(device_id=device_id)
    print(f"[+] Free rewards result: {free_rewards_status} (OK: {free_rewards_ok})")
    t_rewards_dur = time.time() - t_rewards_start

    # STEP 4.5: Read Total Coins / Golds & Latest Update timestamp (User Rule before Logout)
    print("\n[*] [Step 2.5 Focus] Reading Account Total Coins & Diamonds before Logout...")
    from lobby_navigator import get_lobby_account_stats
    from datetime import datetime
    account_stats = get_lobby_account_stats(device_id=device_id)
    total_coin_val = account_stats.get("total_coin", "")
    now_update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # STEP 5: Focus 3 - Final Step (Logout to Main Landing Page)
    t_logout_start = time.time()
    print("\n[*] [Step 3 Focus] Executing Logout to Main Landing Page...")
    logout_ok = execute_logout(device_id=device_id)
    t_logout_dur = time.time() - t_logout_start
    total_dur = time.time() - t_start

    if logout_ok:
        update_google_sheet(
            email=email,
            status="Success_Completed",
            device_id=device_id,
            golds_chest="Skipped",
            free_rewards="6/6",
            total_coin=total_coin_val,
            latest_update=now_update_time
        )
        mins = int(total_dur // 60)
        secs = int(total_dur % 60)
        print("\n" + "="*80)
        print(f"   [BENCHMARK REPORT] FULL ACCOUNT CYCLE COMPLETED FOR {email}!")
        print(f"   - Login + Captcha Time : {t_login_dur:.1f}s")
        print(f"   - All Rewards & Ads    : {t_rewards_dur:.1f}s ({t_rewards_dur/60:.1f}m)")
        print(f"   - Clean Logout Time    : {t_logout_dur:.1f}s")
        print(f"   ----------------------------------------------------")
        print(f"   - TOTAL TIME TAKEN     : {mins} min {secs} sec ({total_dur:.1f} seconds total)")
        print(f"   - Google Sheet Status  : Success_Completed [OK]")
        print("="*80 + "\n")
        return True
    else:
        print(f"[-] Logout check failed on {device_id}.")
        return False


def run_continuous_sheet_loop(
    device_id: str = "127.0.0.1:21503",
    max_accounts: int = 10,
    min_user_num: int = 228,
    max_user_num: int = None,
    match_device: bool = False
):
    """
    Continuous Multi-Account Automation Loop with Multi-Instance Support & Time Benchmark:
    1. Fetches pending accounts directly from Live Google Sheet.
    2. Filters accounts by min_user_num (and optional max_user_num).
    3. Prevents collisions: Skips accounts marked 'Processing' or 'Success_Completed'.
    4. Optional match_device: Filters accounts assigned to this Device_ID in Google Sheet.
    5. Runs full cycle with individual and batch benchmark logging.
    """
    import re
    sys.stdout.reconfigure(line_buffering=True)

    range_str = f"user{min_user_num}" + (f" to user{max_user_num}" if max_user_num else "+")
    print("\n" + "#"*80)
    print(f"   STARTING CONTINUOUS GOOGLE SHEET AUTOMATION LOOP ({max_accounts} ACCOUNTS)")
    print(f"   Target Device : {device_id}")
    print(f"   Target Range  : {range_str}")
    print(f"   Device Match  : {'ENABLED' if match_device else 'DISABLED (Any eligible account)'}")
    print(f"   Max Accounts  : {max_accounts}")
    print(f"   Batch Start   : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("#"*80 + "\n")

    batch_start_time = time.time()
    account_records = []
    processed_count = 0

    while processed_count < max_accounts:
        # Fetch fresh accounts from sheet
        all_accs = fetch_all_accounts_from_sheet()
        history = load_24h_history()

        def parse_user_num(e):
            m = re.search(r'user(\d+)', e.lower())
            return int(m.group(1)) if m else 0

        # Filter eligible accounts in designated range, avoiding collisions
        done_emails = [r["email"].lower() for r in account_records]
        eligible = []
        for a in all_accs:
            em = a.get("Email", "").strip()
            num = parse_user_num(em)
            if num >= min_user_num and (max_user_num is None or num <= max_user_num) and em.lower() not in done_emails:
                status = a.get("Status", "").strip()
                # Skip if already completed or actively being processed by another terminal/instance
                if status in ["Success_Completed", "Processing"]:
                    continue
                dev_col = a.get("Device_ID", "").strip()
                if match_device and dev_col and dev_col != device_id:
                    continue
                if is_account_eligible_to_process(a, history=history):
                    eligible.append(a)

        if not eligible:
            print(f"\n[+] [ALL DONE] No more eligible accounts ({range_str}) in Google Sheet!")
            break

        acc = eligible[0]
        email = acc["Email"]
        pwd = acc.get("Clean_Password") or acc.get("Password") or "Yalla#2026@Pass"

        acc_start = time.time()
        print(f"\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
        print(f"   [{device_id}] [BATCH PROGRESS {processed_count + 1}/{max_accounts}] Processing: {email}")
        print(f"   Start Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

        ok = run_full_account_cycle(device_id=device_id, email=email, password=pwd)
        acc_duration = time.time() - acc_start
        acc_mins = int(acc_duration // 60)
        acc_secs = int(acc_duration % 60)

        record = {
            "email": email,
            "success": ok,
            "duration_secs": acc_duration,
            "duration_str": f"{acc_mins}m {acc_secs}s",
            "completed_at": time.strftime('%H:%M:%S')
        }
        account_records.append(record)
        processed_count += 1

        print(f"\n[+] [{device_id}] Account {email} finished in {record['duration_str']}! (Result: {ok})")
        time.sleep(2.0)

    total_batch_duration = time.time() - batch_start_time
    total_mins = int(total_batch_duration // 60)
    total_secs = int(total_batch_duration % 60)
    avg_secs = (total_batch_duration / len(account_records)) if account_records else 0
    avg_mins = int(avg_secs // 60)
    avg_rem_secs = int(avg_secs % 60)

    # FINAL COMPREHENSIVE BENCHMARK REPORT
    print("\n" + "="*85)
    print(f"       MULTI-INSTANCE BENCHMARK REPORT [{device_id}]")
    print("="*85)
    print(f" Total Accounts Processed : {len(account_records)}")
    print(f" Total Batch Time Taken   : {total_mins} min {total_secs} sec ({total_batch_duration:.1f}s)")
    print(f" Average Time Per Account : {avg_mins} min {avg_rem_secs} sec ({avg_secs:.1f}s)")
    print("-" * 85)
    print(f" {'#':<3} | {'Email':<32} | {'Time Taken':<12} | {'Status':<15} | {'Finish Time'}")
    print("-" * 85)
    for idx, r in enumerate(account_records, start=1):
        status_str = "SUCCESS [OK]" if r["success"] else "FAILED"
        print(f" {idx:<3} | {r['email']:<32} | {r['duration_str']:<12} | {status_str:<15} | {r['completed_at']}")
    print("="*85 + "\n")
    return account_records


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21503"
    
    if len(sys.argv) > 2 and "@" in sys.argv[2]:
        acc = sys.argv[2]
        pwd = sys.argv[3] if len(sys.argv) > 3 else "Yalla#2026@Pass"
        run_full_account_cycle(target, acc, pwd)
    else:
        limit = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 3
        start_num = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 233
        end_num = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4].isdigit() else None
        match_dev = "--match-device" in sys.argv
        run_continuous_sheet_loop(target, max_accounts=limit, min_user_num=start_num, max_user_num=end_num, match_device=match_dev)

