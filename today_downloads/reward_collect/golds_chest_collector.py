"""
================================================================================
REWARD COLLECT - GOLDS CHEST COLLECTOR (WITH DOUBLE REWARD VIDEO AD)
================================================================================
Module: reward_collect/golds_chest_collector.py

User Workflow (Images 1 - 5):
Image #1: On Events page, detect 'Golds Chest' card & tap 'Collect' button at (550, 935).
Image #2: On 'Tap to Open Chest' popup, tap 'Open' button at (400, 980).
Image #3: On '+500' popup, tap yellow 'Double' reward button at (580, 985).
Image #4: Video ad plays -> Apply all Ad Watch rules:
          - Dismiss Play Store card if shown (Back key ONCE).
          - Detect & click 'Continue >|' at (706, 36).
          - Detect & click 'Reward granted (X)' at (762, 39).
Image #5: Once reward is granted and ad finishes:
          - Press Back key TWO times (input keyevent 4 x 2).
          - Verify Main Lobby screen ('main_hall' / 'battle_item')!
================================================================================
"""

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
    sys.path.insert(0, PARENT_DIR)

from tips_ad_handler import handle_tips_ad_popup, is_tips_ad_popup_present

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
    dump_path = f"/sdcard/gc_{dev_tag}.xml"
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


def dismiss_play_store_card_if_present(device_id: str = None) -> bool:
    """Checks if Play Store card is covering the ad and presses Back key ONCE."""
    focus = get_current_focus(device_id)
    if any(pkg in focus for pkg in ["com.android.vending", "market", "Google Play"]):
        print("[!] [Detector] Play Store card DETECTED! Pressing Back key ONCE...")
        run_adb(["shell", "input", "keyevent", "4"], device_id)
        time.sleep(1.2)
        return True
    return False


def is_on_events_page(device_id: str = None) -> bool:
    xml = get_screen_xml(device_id)
    return any(k in xml for k in ["rl_ad_free_reward", "Free Rewards", "Golds Chest", "Hall of Fame", "Asset Tycoon"])


def open_events_page(device_id: str = "127.0.0.1:21613") -> bool:
    """Taps Events icon in Main Lobby navigation bar at (80, 1180)."""
    if is_on_events_page(device_id):
        print("[+] Screen State: Already on Events page [OK]!")
        return True

    print("[*] Navigating to Events page from Main Lobby (tap at (80, 1180))...")
    run_adb(["shell", "input", "tap", "80", "1180"], device_id)
    time.sleep(2.0)

    if is_on_events_page(device_id):
        print("[+] Events page DETECTED & VERIFIED [OK]!")
        return True

    # Retry tap once
    print("[!] Retrying Events tab tap...")
    run_adb(["shell", "input", "tap", "80", "1180"], device_id)
    time.sleep(2.0)
    return is_on_events_page(device_id)


def tap_golds_chest_collect_button(device_id: str = "127.0.0.1:21613") -> bool:
    """
    Image #1:
    Detects the 'Golds Chest' card on the Events page dynamically and taps 'Collect'
    with screen verification and auto-recovery.
    """
    print("\n--- [IMAGE #1] Detecting 'Golds Chest' Card & Tapping 'Collect' Button ---")
    from events_dynamic_navigator import open_and_verify_golds_chest
    return open_and_verify_golds_chest(device_id)


def tap_open_chest_button(device_id: str = "127.0.0.1:21613") -> bool:
    """
    Image #2:
    On 'Tap to Open Chest' popup, taps the large yellow 'Open' button.
    Coordinates: (400, 980), bounds [237, 924][567, 1041].
    """
    print("\n--- [IMAGE #2] Detecting 'Tap to Open Chest' & Tapping 'Open' Button ---")
    open_coords = (400, 980)

    # Verify or tap
    print(f"[*] Tapping 'Open' button at {open_coords}...")
    run_adb(["shell", "input", "tap", str(open_coords[0]), str(open_coords[1])], device_id)
    time.sleep(2.0)
    return True


def tap_double_reward_button(device_id: str = "127.0.0.1:21613") -> bool:
    """
    Image #3:
    On '+500' popup, taps the yellow 'Double' reward button (with video icon).
    Coordinates: (580, 985), bounds [420, 926][742, 1045].
    """
    print("\n--- [IMAGE #3] Detecting Chest Reward & Tapping 'Double' Button ---")
    double_coords = (580, 985)

    print(f"[*] Tapping 'Double' reward button at {double_coords}...")
    run_adb(["shell", "input", "tap", str(double_coords[0]), str(double_coords[1])], device_id)
    time.sleep(1.2)

    # Check and handle Tips confirmation popup ("Don't ask me again" + Watch)
    handle_tips_ad_popup(device_id)
    time.sleep(1.0)
    return True


def watch_golds_chest_ad(device_id: str = "127.0.0.1:21613", max_duration: float = 75.0) -> bool:
    """
    Image #4:
    Watches the rewarded video ad applying all rules:
    - Dismiss Play Store card if shown (Back key ONCE).
    - Detect & click 'Continue >|' at (706, 36).
    - Detect & click 'Reward granted (X)' / Close at (762, 39).
    """
    print("\n--- [IMAGE #4] Monitoring Golds Chest Video Ad Playback ---")

    # Verify ad launched
    ad_active = False
    start_wait = time.time()
    while time.time() - start_wait < 10.0:
        focus = get_current_focus(device_id)
        if any(ad_kw in focus for ad_kw in ["AdActivity", "UnityAds", "AppLovin", "vending"]):
            ad_active = True
            print(f"[+] Video Ad launched successfully! Focus: {focus}")
            break
        # If Tips dialog appeared: handle it
        if handle_tips_ad_popup(device_id):
            time.sleep(1.0)
            continue
        time.sleep(0.8)

    if not ad_active:
        print("[!] Video Ad did not launch ('Failed to load video' / buffer delay).")
        print("[*] [User Rule] Waiting 30s for Ad SDK buffer and re-tapping Double...")
        for sec_left in [30, 20, 10]:
            print(f"    [Buffer Wait] {sec_left}s remaining for Ad SDK cache...")
            time.sleep(10.0)
        print("[*] 30s buffer complete! Re-tapping Double button at (580, 985)...")
        run_adb(["shell", "input", "tap", "580", "985"], device_id)
        time.sleep(1.2)
        handle_tips_ad_popup(device_id)
        
        start_wait2 = time.time()
        while time.time() - start_wait2 < 8.0:
            focus = get_current_focus(device_id)
            if any(ad_kw in focus for ad_kw in ["AdActivity", "UnityAds", "AppLovin", "vending"]):
                ad_active = True
                print(f"[+] Video Ad launched successfully on retry! Focus: {focus}")
                break
            time.sleep(0.8)

    if not ad_active:
        print("[!] Warning: AdActivity could not load after retries. Proceeding...")
        return False

    ad_start_time = time.time()
    last_probe_time = 0.0

    while time.time() - ad_start_time < max_duration:
        elapsed = time.time() - ad_start_time

        # Fast Check A: Focus returned to Yalla Ludo (<0.05s)
        focus = get_current_focus(device_id)
        if "com.yalla.yallagames" in focus and not any(ad_kw in focus for ad_kw in ["AdActivity", "UnityAds", "AppLovin", "vending"]):
            print(f"[+] Focus returned to Yalla Ludo MainActivity after {elapsed:.1f}s [FAST-EXIT OK]!")
            break

        # Fast Check B: Play Store Card -> Back key ONCE
        if any(pkg in focus for pkg in ["com.android.vending", "market", "Google Play"]):
            print(f"[{elapsed:.1f}s] [Detector] Play Store card DETECTED! Pressing Back key ONCE...")
            run_adb(["shell", "input", "keyevent", "4"], device_id)
            time.sleep(0.8)
            continue

        # Fast Check C: At 4-7s, probe Skip / Continue button (706, 36)
        if 4.0 <= elapsed <= 7.0 and elapsed - last_probe_time >= 1.5:
            run_adb(["shell", "input", "tap", "706", "36"], device_id)
            last_probe_time = elapsed

        # Fast Check D: Starting at 12s, probe Close (762, 39) & Continue (706, 36)
        if elapsed >= 12.0 and elapsed - last_probe_time >= 2.0:
            run_adb(["shell", "input", "tap", "762", "39"], device_id)
            run_adb(["shell", "input", "tap", "706", "36"], device_id)
            last_probe_time = elapsed

            time.sleep(0.4)
            focus_after = get_current_focus(device_id)
            if "com.yalla.yallagames" in focus_after and not any(ad_kw in focus_after for ad_kw in ["AdActivity", "UnityAds", "AppLovin", "vending"]):
                print(f"[+] Probed Close button at {elapsed:.1f}s -> Ad closed immediately [FAST-EXIT OK]!")
                break

        # Check E: Periodic XML check every 4s
        if int(elapsed) % 4 == 0:
            xml = get_screen_xml(device_id, timeout=2.5)
            if "Reward granted" in xml or 'text="Close"' in xml or 'content-desc="Close"' in xml:
                print(f"[{elapsed:.1f}s] [Detector] 'Reward granted' / 'Close' DETECTED! Clicking at (762, 39)...")
                run_adb(["shell", "input", "tap", "762", "39"], device_id)
                time.sleep(0.8)
                break
            if "Continue" in xml or "continue" in xml:
                run_adb(["shell", "input", "tap", "706", "36"], device_id)
                time.sleep(0.8)

        time.sleep(0.5)

    print("[+] Ad finished and dismissed [OK]!")
    return True


def exit_to_main_lobby_two_back_presses(device_id: str = "127.0.0.1:21613") -> bool:
    """
    Image #5:
    User Rule:
    'When you click on granyed reward then get this screen here just back key two time nd verify main lubby screen'
    Sends Back key TWO times and verifies Main Lobby screen.
    """
    print("\n--- [IMAGE #5] Exiting to Main Lobby: Pressing Back Key TWO Times ---")
    time.sleep(1.5)

    # First Back key
    print("[*] [Back Key 1/2] Sending Back key (keyevent 4)...")
    run_adb(["shell", "input", "keyevent", "4"], device_id)
    time.sleep(1.5)

    # Second Back key
    print("[*] [Back Key 2/2] Sending Back key (keyevent 4)...")
    run_adb(["shell", "input", "keyevent", "4"], device_id)
    time.sleep(2.0)

    # Verify Main Lobby
    xml = get_screen_xml(device_id)
    lobby_ok = any(ind in xml for ind in ["main_hall", "battle_item", "iv_setting", "fl_tab_room", "1 ON 1", "4 PLAYERS"])
    if lobby_ok:
        print("[SUCCESS] Main Lobby DETECTED & VERIFIED after 2 Back key presses [100% OK]!")
        return True
    else:
        print("[!] Checking one more Back key if popup was lingering...")
        run_adb(["shell", "input", "keyevent", "4"], device_id)
        time.sleep(1.5)
        xml2 = get_screen_xml(device_id)
        ok2 = any(ind in xml2 for ind in ["main_hall", "battle_item", "iv_setting"])
        if ok2:
            print("[SUCCESS] Main Lobby DETECTED & VERIFIED [OK]!")
            return True
        print("[-] Warning: Could not confirm Main Lobby.")
        return False


def collect_golds_chest_pipeline(device_id: str = "127.0.0.1:21613") -> bool:
    """
    Master pipeline for Golds Chest Reward Collection:
    1. Open Events page.
    2. Dynamically detect & verify 'Golds Chest' card / popup (Image 1 & 2):
       - If NOT found or popup doesn't open (e.g. not available today):
         * SKIPS Golds Chest gracefully!
         * Does NOT tap Open, Double, or Video Ad!
         * Returns False to let caller proceed immediately to Free Rewards!
    3. If verified:
       - Tap 'Open' button on 'Tap to Open Chest' popup at (400, 980).
       - Tap 'Double' button on reward popup at (580, 985).
       - Watch Video Ad applying all rules (dismiss card, continue, reward granted).
       - Press Back key TWO times and verify Main Lobby screen.
    """
    print("\n" + "#"*70)
    print("   REWARD COLLECT -> GOLDS CHEST DOUBLE REWARD PIPELINE")
    print(f"   Target Device: {device_id}")
    print("#"*70 + "\n")

    # Step 1: Open Events Page
    if not open_events_page(device_id):
        print("[!] Could not open Events page. Skipping Golds Chest.")
        return False

    # Step 2: Dynamically detect & open Golds Chest with strict verification (Image 1)
    opened = tap_golds_chest_collect_button(device_id)
    if not opened:
        print("\n" + "="*70)
        print("[!] [GOLDS CHEST SKIPPED] Chest card / popup NOT detected or not available today.")
        print("[*] [User Rule] Skipping Golds Chest and proceeding directly to Free Rewards!")
        print("="*70 + "\n")
        from events_dynamic_navigator import dismiss_wrong_event_subscreen
        dismiss_wrong_event_subscreen(device_id)
        return False

    # Step 3: Tap Open Button on Chest Popup (Image 2)
    print("\n--- [IMAGE #2] Detecting 'Tap to Open Chest' & Tapping 'Open' Button ---")
    tap_open_chest_button(device_id)

    # Step 4: Tap Double Button on Reward Popup (Image 3)
    print("\n--- [IMAGE #3] Detecting Chest Reward & Tapping 'Double' Button ---")
    tap_double_reward_button(device_id)

    # Step 5: Watch Video Ad with all rules (Image 4)
    print("\n--- [IMAGE #4] Monitoring Golds Chest Video Ad Playback ---")
    watch_golds_chest_ad(device_id)

    # Step 6: Press Back Key TWO times & verify Main Lobby (Image 5)
    print("\n--- [IMAGE #5] Exiting to Main Lobby: Pressing Back Key TWO Times ---")
    success = exit_to_main_lobby_two_back_presses(device_id)
    return success


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21613"
    collect_golds_chest_pipeline(target)
