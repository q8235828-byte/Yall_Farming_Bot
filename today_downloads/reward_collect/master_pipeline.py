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
from google_sheet_sync import update_google_sheet, fetch_all_accounts_from_sheet, get_next_accounts_to_process
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
        print(f"\n[*] Submitting credentials & solving captcha for {email}...")
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
            print("[*] Collecting Daily Reward (Option A)...")
            collect_daily_reward_pipeline(device_id)
            time.sleep(1.5)

        elif state == "NEW_USER_SIGNIN":
            print("[*] [User Rule] 'New User Sign-in' detected! Dismissing via Back key...")
            execute_new_user_signin(device_id)
            time.sleep(1.5)

        elif state == "FREE_REWARDS_SCREEN":
            print("[*] Running Free Rewards Video Ad Watcher...")
            watch_all_6_ads(device_id)
            time.sleep(1.5)

        elif state == "TIPS_AD_POPUP":
            print("[*] Tips Ad popup detected! Handling checkbox + Watch...")
            handle_tips_ad_popup(device_id)
            time.sleep(1.5)

        elif state in ["OPEN_CHEST_POPUP", "DOUBLE_REWARD_POPUP"]:
            print("[*] Completing Golds Chest double reward...")
            collect_golds_chest_pipeline(device_id)
            time.sleep(1.5)

        elif state == "VIP_PRIVILEGES_SCREEN":
            print("[*] 'Privileges / VIP Room' screen detected. Dismissing via Back key...")
            from screen_detector import run_adb
            run_adb(["shell", "input", "keyevent", "4"], device_id)
            time.sleep(1.5)

        elif state == "MAIN_LOBBY":
            print("\n[+] Main Lobby reached! Proceeding to Verification & Final Steps...")
            break
        else:
            print(f"[*] Unknown screen or popup [{state}]. Sending Back key...")
            from screen_detector import run_adb
            run_adb(["shell", "input", "keyevent", "4"], device_id)
            time.sleep(1.5)

    # STEP 4: Second-Last Step (Verify Golds Chest, Free Rewards 6/6, Update Sheet)
    print("\n[*] Executing Second-Last Step (Verification & Sheet Update)...")
    ver_res = execute_second_last_step(device_id=device_id, email=email)
    print(f"[+] Verification result: {ver_res}")
    t_rewards_dur = time.time() - t_rewards_start

    # STEP 5: Final Step (Logout to Main Landing Page)
    t_logout_start = time.time()
    print("\n[*] Executing Final Step (Logout to Main Landing Page)...")
    logout_ok = execute_logout(device_id=device_id)
    t_logout_dur = time.time() - t_logout_start
    total_dur = time.time() - t_start

    if logout_ok:
        update_google_sheet(
            email=email,
            status="Success_Completed",
            device_id=device_id,
            golds_chest=ver_res.get("golds_chest", "Yes"),
            free_rewards=ver_res.get("free_rewards", "6/6")
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


def run_continuous_sheet_loop(device_id: str = "127.0.0.1:21613", max_accounts: int = None):
    """
    Continuous Multi-Account Automation Loop:
    1. Fetches pending accounts directly from Live Google Sheet.
    2. Runs full cycle for each account.
    3. Repeats automatically until all accounts in the sheet are completed!
    """
    print("\n" + "#"*80)
    print("   STARTING CONTINUOUS GOOGLE SHEET AUTOMATION LOOP")
    print(f"   Target Device: {device_id}")
    print(f"   Max Accounts : {max_accounts or 'Unlimited'}")
    print("#"*80 + "\n")

    processed_count = 0
    while True:
        pending = get_next_accounts_to_process(max_count=1)
        if not pending:
            print("\n[+] [ALL DONE] No more pending accounts in Google Sheet!")
            break

        acc = pending[0]
        email = acc["Email"]
        pwd = acc.get("Clean_Password", "Yalla#2026@Pass")

        print(f"\n>>> [Account #{processed_count + 1}] Processing: {email}")
        ok = run_full_account_cycle(device_id=device_id, email=email, password=pwd)

        processed_count += 1
        if max_accounts and processed_count >= max_accounts:
            print(f"\n[+] Reached requested account limit ({max_accounts}). Loop ending.")
            break

        time.sleep(3.0)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21613"
    
    # Check if specific account or continuous sheet loop
    if len(sys.argv) > 2 and "@" in sys.argv[2]:
        acc = sys.argv[2]
        pwd = sys.argv[3] if len(sys.argv) > 3 else "Yalla#2026@Pass"
        run_full_account_cycle(target, acc, pwd)
    else:
        # Run continuous mode directly from Google Sheet
        limit = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else None
        run_continuous_sheet_loop(target, max_accounts=limit)

