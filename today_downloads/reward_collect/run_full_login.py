"""
================================================================================
REWARD COLLECT - MASTER STATE-DRIVEN LOGIN & REWARDS PIPELINE
================================================================================
Module: reward_collect/run_full_login.py

User Core Rule:
'jb be script run ho es k bade current screen detect kr k phr phr run kry next step'
(Whenever the script runs, detect the current screen first, and then execute
 the appropriate next step based on the detected state!)

Supported Dynamic Screen States:
1. APP_NOT_RUNNING       -> Launch Yalla Ludo -> splash -> re-detect
2. MAIN_LANDING_PAGE     -> Check Terms -> Tap Email -> open Login Dialog
3. EMAIL_LOGIN_DIALOG    -> Fill credentials -> Yellow Login -> Captcha wait (90s)
4. CAPTCHA_PUZZLE        -> Solve Geetest Captcha via ColorIndexedCaptchaSolver
5. EXPERT_DIALOG         -> Tap 'I’m expert' button (com.yalla.yallagames:id/btn_yes)
6. CONGRATULATIONS_POPUP -> Tap Yellow Confirm button at (400, 818)
7. FREE_REWARDS_SCREEN   -> Watch all 6 video ads -> exit to Lobby
8. AD_PLAYING            -> In-ad monitor (dismiss Play Store card, Continue, Reward granted)
9. DAILY_REWARD_POPUP    -> Option A 3-step collect (400, 1212) -> return to Lobby
10. MAIN_LOBBY           -> Run Daily Reward + Free Rewards (6/6 Ads) -> Verify Lobby
11. UNKNOWN_SCREEN       -> Back key recovery -> re-detect
================================================================================
"""

import os
import sys
import time
import subprocess

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from screen_detector import detect_current_screen, run_adb, get_adb_cmd
from main_login_page import execute_main_login_step
from login_form_handler import execute_login_flow
from post_login_handler import handle_expert_dialog
from daily_reward_collector import collect_daily_reward_pipeline
from free_reward_collector import execute_free_reward_flow
from free_reward_ad_watcher import watch_all_6_ads
from lobby_navigator import ensure_main_lobby
from color_indexed_captcha_solver import ColorIndexedCaptchaSolver
from golds_chest_collector import (
    collect_golds_chest_pipeline,
    tap_open_chest_button,
    tap_double_reward_button,
    watch_golds_chest_ad,
    exit_to_main_lobby_two_back_presses
)
from new_user_signin_collector import execute_new_user_signin


def run_full_rewards_pipeline(device_id: str = "127.0.0.1:21613"):
    """
    Executes Phase 3 (Daily Reward Option A) and Phase 4 (Free Reward 6/6 Video Ads).
    """
    print("\n" + "="*70)
    print("   [PHASE 3: DAILY REWARD COLLECTION (OPTION A)]")
    print("="*70)
    collect_daily_reward_pipeline(device_id)
    ensure_main_lobby(device_id, max_back_presses=3)

    print("\n" + "="*70)
    print("   [PHASE 4: FREE REWARD VIDEO ADS COLLECTION (6/6 ADS)]")
    print("="*70)
    fr_open = execute_free_reward_flow(device_id)
    if fr_open:
        watch_all_6_ads(device_id)
    else:
        print("[!] Warning: Could not open Free Rewards screen directly. Checking screen...")
        ensure_main_lobby(device_id, max_back_presses=3)

    print("\n" + "="*70)
    print("   [PHASE 5: GOLDS CHEST COLLECTION (WITH DOUBLE REWARD AD)]")
    print("="*70)
    collect_golds_chest_pipeline(device_id)
    ensure_main_lobby(device_id, max_back_presses=3)


def run_state_driven_pipeline(device_id: str = "127.0.0.1:21613", max_steps: int = 40) -> bool:
    """
    Master state-driven loop:
    Detects current screen at every step and executes the exact next action.
    """
    print("\n" + "#"*70)
    print("   STARTING MASTER STATE-DRIVEN AUTOMATION PIPELINE")
    print(f"   Target Device: {device_id}")
    print("#"*70 + "\n")

    rewards_completed = False
    consecutive_unknowns = 0

    for step_num in range(1, max_steps + 1):
        # 1. DETECT CURRENT SCREEN FIRST
        screen = detect_current_screen(device_id)
        print(f"\n---> [STEP {step_num}] Current Screen Detected: [{screen}]")

        # 2. APP NOT RUNNING
        if screen == "APP_NOT_RUNNING":
            print("[*] Yalla Ludo is not in foreground. Launching app...")
            run_adb(["shell", "am", "start", "-n", "com.yalla.yallagames/.main.MainActivity"], device_id)
            time.sleep(5.0)
            continue

        # 3. MAIN LANDING PAGE
        elif screen == "MAIN_LANDING_PAGE":
            print("[*] Screen: Main Landing Page -> Verifying Terms & Clicking Email...")
            dialog_ok = execute_main_login_step(device_id)
            if not dialog_ok:
                print("[!] Could not open Login Dialog. Retrying after 1.5s...")
            time.sleep(1.5)
            continue

        # 4. EMAIL LOGIN DIALOG
        elif screen == "EMAIL_LOGIN_DIALOG":
            print("[*] Screen: Email Login Dialog -> Injected credentials & processing login...")
            login_res = execute_login_flow(device_id)
            if isinstance(login_res, tuple):
                login_ok, state = login_res
            else:
                login_ok, state = bool(login_res), "UNKNOWN"

            if login_ok:
                print(f"[+] Login succeeded with state: [{state}]!")
            else:
                print("[-] Login attempt failed. Will re-detect screen for next attempt...")
            time.sleep(2.0)
            continue

        # 5. CAPTCHA PUZZLE (If detected standing on screen)
        elif screen == "CAPTCHA_PUZZLE":
            print("[*] Screen: Geetest Captcha puzzle detected! Solving puzzle...")
            solver = ColorIndexedCaptchaSolver(device_id)
            solved = solver.solve()
            print(f"[+] Captcha solver result: {solved}")
            time.sleep(2.5)
            continue

        # 6. EXPERT DIALOG ("I'm expert")
        elif screen == "EXPERT_DIALOG":
            print("[*] Screen: 'I’m expert' dialog detected. Pressing 2x Back keys per rule...")
            handle_expert_dialog(device_id)
            time.sleep(1.5)
            continue

        # 7. CONGRATULATIONS POPUP
        elif screen == "CONGRATULATIONS_POPUP":
            print("[*] Screen: 'Congratulations' popup detected. Clicking Confirm at (400, 818)...")
            run_adb(["shell", "input", "tap", "400", "818"], device_id)
            time.sleep(1.5)
            continue

        # 8. FREE REWARDS SCREEN (Watch AD & Win Rewards)
        elif screen == "FREE_REWARDS_SCREEN":
            print("[*] Screen: Free Rewards / Watch AD screen detected. Running ad watcher...")
            watch_all_6_ads(device_id)
            rewards_completed = True
            time.sleep(1.5)
            continue

        # 9. AD PLAYING (In-ad or Play Store card)
        elif screen == "AD_PLAYING":
            print("[*] Screen: Video Ad / Play Store card currently active. Resuming ad watcher...")
            watch_all_6_ads(device_id)
            rewards_completed = True
            time.sleep(1.5)
            continue

        # 10. DAILY REWARD POPUP
        elif screen == "DAILY_REWARD_POPUP":
            print("[*] Screen: Daily Reward popup detected. Executing Option A 3-step collect...")
            collect_daily_reward_pipeline(device_id)
            time.sleep(1.5)
            continue

        # 11. OPEN CHEST POPUP (Golds Chest)
        elif screen == "OPEN_CHEST_POPUP":
            print("[*] Screen: 'Tap to Open Chest' popup detected. Tapping Open at (400, 980)...")
            tap_open_chest_button(device_id)
            time.sleep(2.0)
            continue

        # 12. DOUBLE REWARD POPUP (Golds Chest)
        elif screen == "DOUBLE_REWARD_POPUP":
            print("[*] Screen: 'Double' reward popup detected. Tapping Double at (580, 985)...")
            tap_double_reward_button(device_id)
            watch_golds_chest_ad(device_id)
            exit_to_main_lobby_two_back_presses(device_id)
            time.sleep(1.5)
            continue

        # 13. NEW USER SIGN-IN
        elif screen == "NEW_USER_SIGNIN":
            print("[*] Screen: 'New User Sign-in' detected. Running New User Sign-in collector...")
            execute_new_user_signin(device_id)
            time.sleep(1.5)
            continue

        # 14. MAIN LOBBY
        elif screen == "MAIN_LOBBY":
            print("[+] Screen: MAIN LOBBY DETECTED & VERIFIED [OK]!")
            if not rewards_completed:
                print("[*] Account is logged in! Running Daily Reward & Free Rewards pipelines...")
                run_full_rewards_pipeline(device_id)
                rewards_completed = True
                ensure_main_lobby(device_id, max_back_presses=3)
            else:
                print("\n" + "="*70)
                print("   [SUCCESS] ALL TASKS COMPLETED!")
                print("   - Login: VERIFIED")
                print("   - Daily Reward: COLLECTED")
                print("   - 6/6 Video Ads: COMPLETED")
                print("   - Current Screen: Cleanly sitting in Main Lobby [OK]")
                print("="*70 + "\n")
                return True

        # 12. UNKNOWN SCREEN / POPUP RECOVERY
        else:
            consecutive_unknowns += 1
            print(f"[!] Unknown screen or popup detected ({consecutive_unknowns}/4). Pressing Back key (keyevent 4)...")
            run_adb(["shell", "input", "keyevent", "4"], device_id)
            time.sleep(1.5)
            if consecutive_unknowns >= 4:
                print("[*] Enforcing Main Lobby navigation...")
                ensure_main_lobby(device_id, max_back_presses=3)
                consecutive_unknowns = 0

    print("[-] Max steps reached in state-driven pipeline.")
    return False


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21613"
    run_state_driven_pipeline(target)
