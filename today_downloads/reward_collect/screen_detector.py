"""
================================================================================
REWARD COLLECT - MASTER SCREEN DETECTOR & STATE IDENTIFIER
================================================================================
Module: reward_collect/screen_detector.py

Identifies current screen state on MEmu Android device:
- AD_PLAYING
- APP_NOT_RUNNING
- CONGRATULATIONS_POPUP
- CAPTCHA_PUZZLE
- EXPERT_DIALOG
- FREE_REWARDS_SCREEN
- DAILY_REWARD_POPUP
- EMAIL_LOGIN_DIALOG
- MAIN_LANDING_PAGE
- MAIN_LOBBY
- UNKNOWN_SCREEN
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


def get_current_focus(device_id: str = None) -> str:
    """Returns the current focused window string via dumpsys (<0.1s)."""
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
    """Dumps compressed UI XML and returns as string."""
    dev_tag = device_id.replace(":", "_").replace(".", "_") if device_id else "def"
    dump_path = f"/sdcard/det_{dev_tag}.xml"
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


def detect_current_screen(device_id: str = "127.0.0.1:21613") -> str:
    """
    User Core Rule:
    'jb be script run ho es k bade current screen detect kr k phr phr run kry next step'
    
    Detects the current screen state and returns one of:
    - 'AD_PLAYING'
    - 'APP_NOT_RUNNING'
    - 'CONGRATULATIONS_POPUP'
    - 'CAPTCHA_PUZZLE'
    - 'EXPERT_DIALOG'
    - 'FREE_REWARDS_SCREEN'
    - 'DAILY_REWARD_POPUP'
    - 'EMAIL_LOGIN_DIALOG'
    - 'MAIN_LANDING_PAGE'
    - 'MAIN_LOBBY'
    - 'UNKNOWN_SCREEN'
    """
    # 1. Fast Window Focus check
    focus = get_current_focus(device_id)
    
    # Ad or Play Store open
    if any(k in focus for k in ["AdActivity", "UnityAds", "AppLovin", "com.google.android.gms.ads", "com.android.vending", "market"]):
        return "AD_PLAYING"

    # App not running or on Home screen
    if focus and "com.yalla.yallagames" not in focus and "AdActivity" not in focus:
        return "APP_NOT_RUNNING"

    # 2. UI Automator Hierarchy Dump
    xml = get_screen_xml(device_id)
    if not xml:
        # If XML dump failed, check if focus is MainActivity
        if "com.yalla.yallagames" in focus:
            return "MAIN_LOBBY"
        return "UNKNOWN_SCREEN"

    # Check Tips Ad Confirmation Popup
    if any(k in xml for k in ["Don't ask me again", "Don’t ask me again", "You are about to watch a video ad"]):
        return "TIPS_AD_POPUP"

    # Check Captcha Puzzle
    if any(k in xml for k in ["geetest", "geetest_holder", "btn_slide", "geetest_radar_btn", "geetest_popup_wrap"]):
        return "CAPTCHA_PUZZLE"

    # Check Congratulations Popup
    if any(k in xml for k in ["Congratulations", "btn_collect"]):
        return "CONGRATULATIONS_POPUP"

    # Check Beginner vs Expert Dialog
    if any(k in xml for k in ["com.yalla.yallagames:id/btn_yes", "I’m expert", "I'm expert"]):
        return "EXPERT_DIALOG"

    # Check Free Rewards Screen (Watch AD & Win Rewards)
    if any(k in xml for k in ["com.yalla.yallagames:id/ll_watch", "Watch AD & Win Rewards", "Watch AD &amp; Win Rewards", "AD watched times today"]):
        return "FREE_REWARDS_SCREEN"

    # Check Open Chest Popup
    if "Tap to Open Chest" in xml:
        return "OPEN_CHEST_POPUP"

    # Check Double Reward Popup
    if "Double" in xml and ("Extra" in xml or "+1000" in xml or "500" in xml):
        return "DOUBLE_REWARD_POPUP"

    # Check New User Sign-in Screen
    if any(k in xml for k in ["New User Sign-in", "New User Sign-In", "Cumulative sign-in", "Re-sign in", "Remaining days:"]):
        return "NEW_USER_SIGNIN"

    # Check Daily Sign-in / Daily Reward Popup
    if any(k in xml for k in ["Daily Sign-in", "daily_bonus", "btn_sign"]):
        return "DAILY_REWARD_POPUP"

    # Check Email Login Dialog
    if any(k in xml for k in ["et_phone_number_login", "et_cus_login_password", "bt_login", "Enter password", "Forgot Password?"]):
        return "EMAIL_LOGIN_DIALOG"

    # Check Main Landing Page (Terms checkbox, Email, Facebook, etc.)
    if any(k in xml for k in ["ll_email", "iv_email", "rl_private_policy", "tv_service", "tv_chat_login", "tv_fb_login", "tv_phone_login", "Terms of Service"]):
        return "MAIN_LANDING_PAGE"

    # Check Privileges screen (accidental click on VIP Subscription in Events tab)
    if "Privileges" in xml or "You can create or join a VIP room!" in xml or ("LUDO VIP" in xml and "main_hall" not in xml):
        return "VIP_PRIVILEGES_SCREEN"

    # Check Main Lobby
    if any(k in xml for k in ["main_hall", "battle_item", "iv_setting", "fl_tab_room", "1 ON 1", "4 PLAYERS", "fl_main_header"]):
        return "MAIN_LOBBY"

    return "UNKNOWN_SCREEN"


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21613"
    screen = detect_current_screen(target)
    print(f"[*] Detected Screen on {target}: [{screen}]")
