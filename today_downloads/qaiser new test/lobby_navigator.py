"""
================================================================================
REWARD COLLECT - LOBBY NAVIGATOR & UNKNOWN SCREEN BACK-KEY RECOVERY
================================================================================
Module: reward_collect/lobby_navigator.py
Purpose:
- User Rule: Whenever an unknown screen or unexpected popup is detected,
  use the Back key (input keyevent 4) repeatedly (up to max attempts)
  until the Main Lobby ('main_hall' / 'iv_setting') is cleanly detected & verified.
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


def run_adb(args: list, device_id: str = None) -> str:
    cmd = get_adb_cmd(device_id) + args
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        return res.stdout.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[!] ADB error: {e}")
        return ""


from screen_detector import detect_current_screen, get_screen_xml


def is_in_main_lobby(device_id: str = None) -> bool:
    """
    Checks if currently in Yalla Ludo Main Lobby.
    Uses real-time screen detection first (<80ms), with XML fallback.
    """
    if detect_current_screen(device_id) == "MAIN_LOBBY":
        return True

    xml_str = get_screen_xml(device_id)
    lobby_indicators = [
        "main_hall",
        "iv_setting",
        "fl_tab_room",
        "fl_main_header",
        "events_item",
        "battle_item",
        "tv_gold_num",
        "tv_diamonds_num",
        "1 ON 1",
        "4 PLAYERS",
        "rl_diamond",
        "fl_coin"
    ]
    return any(ind in xml_str for ind in lobby_indicators)


def ensure_main_lobby(device_id: str = "127.0.0.1:21613", max_back_presses: int = 4) -> bool:
    """
    User Core Rule:
    Whenever an unknown screen or unexpected popup is detected,
    presses Back key (input keyevent 4) until Main Lobby is cleanly detected & verified.
    """
    print(f"\n[*] [LobbyNavigator] Checking Main Lobby status on {device_id}...")

    if is_in_main_lobby(device_id):
        print("[+] Screen State: Already in Main Lobby [OK]!")
        return True

    for attempt in range(1, max_back_presses + 1):
        print(f"[*] Unknown screen / popup detected. [Attempt {attempt}/{max_back_presses}] Pressing Back key (keyevent 4)...")
        run_adb(["shell", "input", "keyevent", "4"], device_id)
        time.sleep(1.2)

        if is_in_main_lobby(device_id):
            print(f"[SUCCESS] Main Lobby DETECTED & VERIFIED after Back key attempt {attempt} [OK]!")
            return True

    print(f"[-] Warning: Main Lobby not detected after {max_back_presses} Back key presses.")
    return False


def get_lobby_account_stats(device_id: str = "127.0.0.1:21503") -> dict:
    """
    User Rule:
    'logout se phy hum ne ek aur function add krna ads watch k bade
     kitne account m kitne coins/ golds hai yeh be shhet m update kray'
    Reads account coins (gold) and diamonds directly from Lobby UI in <20ms.
    """
    stats = {"total_coin": "", "diamonds": ""}
    try:
        import uiautomator2 as u2
        d = u2.connect(device_id)
        gold_elem = d(resourceId="com.yalla.yallagames:id/tv_gold_num")
        diamond_elem = d(resourceId="com.yalla.yallagames:id/tv_diamonds_num")
        if gold_elem.exists:
            stats["total_coin"] = gold_elem.get_text()
        if diamond_elem.exists:
            stats["diamonds"] = diamond_elem.get_text()
        print(f"[+] [Lobby Stats] Gold/Coins: [{stats['total_coin']}], Diamonds: [{stats['diamonds']}]")
    except Exception as e:
        print(f"[!] Error reading lobby stats: {e}")
    return stats


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21613"
    ensure_main_lobby(target)
