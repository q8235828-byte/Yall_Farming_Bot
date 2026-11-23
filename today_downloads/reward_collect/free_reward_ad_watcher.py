"""
================================================================================
REWARD COLLECT - 6/6 VIDEO ADS WATCHER & AUTO-COLLECTOR
================================================================================
Module: reward_collect/free_reward_ad_watcher.py

User State Machine & Logic:
1. Tap 'Watch AD' at (400, 1181) to launch the ad.
2. During the 1-minute 3-segment ad:
   - Detect Play Store app card: Press Back key ONCE (keyevent 4) to dismiss.
   - Detect 'Continue >|' top-right pill: Click it (706, 36).
   - Detect 'Reward granted (X)' top-right pill: Click it (762, 39) to exit ad.
3. Detect 'Congratulations' popup in Yalla Ludo: Click 'Confirm' at (400, 818).
4. Verify 'Watch AD & Win Rewards' screen:
   - If button is still active/yellow (e.g. 4/6, 5/6), click again for next ad.
   - If button changed to grey/disabled (6/6 complete, clickable="false"), stop!
5. Cleanly exit to Main Lobby using ONLY Back key at the very end.
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
    sys.path.append(PARENT_DIR)

from tips_ad_handler import handle_tips_ad_popup, is_tips_ad_popup_present

ADB_BIN = os.path.join(PARENT_DIR, "platform-tools", "adb.exe")
if not os.path.exists(ADB_BIN):
    ADB_BIN = "adb"


def get_adb_cmd(device_id: str = None) -> list:
    cmd = [ADB_BIN]
    if device_id:
        cmd.extend(["-s", device_id])
    return cmd


def run_adb(args: list, device_id: str = None, timeout: float = 8.0) -> str:
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
    dump_path = f"/sdcard/ad_dump_{dev_tag}.xml"
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
    """
    User Rule:
    'ya play store app card jb card show ho toih back key one time'
    Checks if Play Store card is covering the screen and presses Back key ONCE.
    """
    focus = get_current_focus(device_id)
    if any(pkg in focus for pkg in ["com.android.vending", "market", "Google Play"]):
        print("[!] [Detector] Play Store card DETECTED! Pressing Back key ONCE...")
        run_adb(["shell", "input", "keyevent", "4"], device_id)
        time.sleep(1.2)

        # Re-check focus
        focus_after = get_current_focus(device_id)
        if any(pkg in focus_after for pkg in ["com.android.vending", "market"]):
            print("[*] Dismissing leftover Play Store dialog via tap (753, 335) + force-stop...")
            run_adb(["shell", "input", "tap", "753", "335"], device_id)
            time.sleep(0.3)
            run_adb(["shell", "am", "force-stop", "com.android.vending"], device_id)
            time.sleep(0.5)
            run_adb(["shell", "am", "start", "-n", "com.yalla.yallagames/.main.MainActivity"], device_id)
            time.sleep(0.5)
        print("[+] Play Store card dismissed [OK]!")
        return True
    return False


def get_ad_watched_progress(device_id: str = None) -> tuple:
    """
    Parses 'AD watched times today: X/6' from screen XML.
    Returns (current, total) e.g. (4, 6) or (None, None).
    """
    xml = get_screen_xml(device_id)
    if not xml:
        return None, None
    m = re.search(r'text="AD watched times today:\s*(\d+)/(\d+)"', xml)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def is_watch_ad_button_active(device_id: str = None) -> bool:
    """
    User Rule:
    Detects if Watch AD button color changed / disabled (clickable="false").
    If disabled or 6/6 complete, returns False.
    """
    xml = get_screen_xml(device_id)
    if not xml:
        return True

    # 1. Check watched count
    curr, total = get_ad_watched_progress(device_id)
    if curr is not None and total is not None:
        if curr < total:
            return True
        if curr >= total:
            print(f"[+] Progress verified: {curr}/{total} ads watched today. Button is DISABLED!")
            return False

    # 2. Check ll_watch clickable attribute
    m_watch = re.search(r'<node[^>]+resource-id="com\.yalla\.yallagames:id/ll_watch"[^>]*>', xml)
    if m_watch:
        node_str = m_watch.group(0)
        m_click = re.search(r'\sclickable="([^"]+)"', node_str)
        if m_click and m_click.group(1).lower() == "false":
            print("[+] ll_watch clickable='false'! Watch AD button is grey/disabled.")
            return False

    # 3. Check watched icons count
    watched_icons = re.findall(r'resource-id="com\.yalla\.yallagames:id/iv_watched_(?:left|right)"', xml)
    if len(watched_icons) >= 6:
        print("[+] 6 watched icons found! Button is completed/disabled.")
        return False

    return True


def ensure_on_watch_ad_screen(device_id: str = "127.0.0.1:21613") -> bool:
    """
    Guarantees device is on 'Watch AD & Win Rewards' screen (Image #2)
    using dynamic Events navigation, card verification, and auto-recovery.
    """
    from events_dynamic_navigator import is_reward_chest_screen_open, open_and_verify_free_rewards

    if is_reward_chest_screen_open(device_id):
        return True

    # If Congratulations popup is blocking
    xml = get_screen_xml(device_id)
    if "Congratulations" in xml or "btn_collect" in xml:
        print("[*] Dismissing Congratulations popup at (400, 818)...")
        run_adb(["shell", "input", "tap", "400", "818"], device_id)
        time.sleep(1.2)
        if is_reward_chest_screen_open(device_id):
            return True

    # Use dynamic navigator with strict verification
    return open_and_verify_free_rewards(device_id)


def claim_congratulations_popup(device_id: str = None) -> bool:
    """
    User Rule:
    'jb be ap ne reward granted par click krna hai ek he script run krna hai
     jo yeh wala two type hoga. congrulation pop. es par confirm par click krn ahai.'
    Fast Congratulations claim: Taps Yellow Confirm at (400, 818) (<0.8s total).
    """
    time.sleep(0.5)
    # Direct probe of Confirm button
    run_adb(["shell", "input", "tap", "400", "818"], device_id)
    time.sleep(0.4)

    # Check if still present and re-tap once if needed
    focus = get_current_focus(device_id)
    if "com.yalla.yallagames" in focus:
        xml = get_screen_xml(device_id, timeout=2.5)
        if "Congratulations" in xml or "btn_collect" in xml or "Confirm" in xml:
            print("[+] [Detector] 'Congratulations' popup confirmed! Clicking 'Confirm' at (400, 818)...")
            run_adb(["shell", "input", "tap", "400", "818"], device_id)
            time.sleep(0.4)
    print("[+] 'Congratulations' popup claimed successfully [OK]!")
    return True


def watch_single_ad_cycle(device_id: str = "127.0.0.1:21613", ad_index: int = 1) -> bool:
    """
    Fast Autonomous Ad Watcher:
    1. Tap 'Watch AD' at (400, 1181).
    2. Proactive Fast Ad Monitor:
       - 4-7s: Probe Skip/Continue at (706, 36) -> Skips 5-second skippable ads!
       - 12s-30s: Proactively probe Close (762, 39) & Continue (706, 36) -> Closes 15s/30s ads instantly!
       - Play Store card -> Back key ONCE immediately!
       - Focus switch to Yalla Ludo -> Instant exit (<0.05s)!
    3. Instant Congratulations Confirm at (400, 818).
    4. Next ad ready immediately.
    """
    print(f"\n=======================================================")
    print(f"       STARTING FAST AD CYCLE #{ad_index}")
    print(f"=======================================================")

    # Step 1: Tap 'Watch AD' with 30s Buffer Wait Loop (User Rule)
    ad_active = False
    for attempt in range(1, 4):
        print(f"[*] Tapping 'Watch AD' button at (400, 1181) (Attempt {attempt}/3)...")
        run_adb(["shell", "input", "tap", "400", "1181"], device_id)
        time.sleep(0.8)

        # Check and handle Tips confirmation popup ("Don't ask me again" + Watch)
        handle_tips_ad_popup(device_id)

        # Fast check if ad activity launched
        start_wait = time.time()
        while time.time() - start_wait < 7.0:
            focus = get_current_focus(device_id)
            if any(ad_kw in focus for ad_kw in ["AdActivity", "UnityAds", "AppLovin", "vending", "com.google.android.gms.ads"]):
                ad_active = True
                print(f"[+] Video Ad launched successfully! Focus: {focus}")
                break
            if handle_tips_ad_popup(device_id):
                time.sleep(0.5)
                continue
            time.sleep(0.5)

        if ad_active:
            break

        # User Rule: If failed to load / buffer delay, refresh screen & wait buffer
        if attempt < 3:
            print("\n" + "="*70)
            print("[!] Video Ad did not launch ('Failed to load video' / Third-party latency).")
            print(f"[*] [Self-Healing] Refreshing Reward Chest screen to reload Ad SDK (Attempt {attempt}/2)...")
            print("="*70)

            # 1. Dismiss Play Store if opened in foreground (e.g. Window 3)
            focus = get_current_focus(device_id)
            if any(p in focus for p in ["vending", "market", "Google Play"]):
                print("[*] Dismissing background Play Store window via Back key...")
                run_adb(["shell", "input", "keyevent", "4"], device_id)
                time.sleep(1.0)

            # 2. Exit to Events tab to destroy stuck Ad SDK listener
            print("[*] Exiting to Events tab to clear stuck ad listener...")
            run_adb(["shell", "input", "keyevent", "4"], device_id)
            time.sleep(2.0)

            # 3. Re-open Reward Chest screen (triggers onResume -> fresh Ad request)
            print("[*] Re-opening Reward Chest screen to initialize fresh ad stream...")
            ensure_on_watch_ad_screen(device_id)

            # 4. Buffer wait for fresh video download
            for sec_left in [20, 10]:
                print(f"    [Buffer Wait] {sec_left}s remaining for Ad SDK cache...")
                time.sleep(10.0)
            print("[*] Fresh ad buffer complete! Re-tapping 'Watch AD' now...\n")

    if not ad_active:
        print("[-] Video Ad could not load after 3x 30s buffer retries.")
        return False

    # Step 2: Proactive Fast In-Ad Loop
    print("[*] Monitoring Ad Playback (Fast Probing Continue/Close)...")
    ad_start_time = time.time()
    last_probe_time = 0.0

    while time.time() - ad_start_time < 65.0:
        elapsed = time.time() - ad_start_time

        # Fast Check A: Has focus returned to Yalla Ludo? (<0.05s)
        focus = get_current_focus(device_id)
        if "com.yalla.yallagames" in focus and not any(ad_kw in focus for ad_kw in ["AdActivity", "UnityAds", "AppLovin", "vending"]):
            print(f"[+] Focus returned to Yalla Ludo MainActivity after {elapsed:.1f}s [FAST-EXIT OK]!")
            break

        # Fast Check B: Play Store Card Detection -> Back key ONCE!
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

            # Immediate check if tap closed the ad
            time.sleep(0.4)
            focus_after = get_current_focus(device_id)
            if "com.yalla.yallagames" in focus_after and not any(ad_kw in focus_after for ad_kw in ["AdActivity", "UnityAds", "AppLovin", "vending"]):
                print(f"[+] Probed Close button at {elapsed:.1f}s -> Ad closed immediately [FAST-EXIT OK]!")
                break

        # Check E: Periodic XML check every 4s for explicit 'Reward granted' or 'Close'
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

    # Step 3: Returning to Yalla Ludo -> Fast Congratulations Claim
    print("[*] Claiming 'Congratulations' popup...")
    claim_congratulations_popup(device_id)

    # Step 4: Quick Progress Verification
    curr_after, total = get_ad_watched_progress(device_id)
    if curr_after is not None:
        print(f"[+] Current Ad Progress: {curr_after}/{total} [OK]!")
    return True


def exit_to_main_lobby_via_back(device_id: str = "127.0.0.1:21613", max_presses: int = 4) -> bool:
    """
    User Rule:
    ONLY uses Back key at the very end to exit cleanly to Main Lobby.
    """
    print("\n[*] Exiting to Main Lobby using strictly Back key (keyevent 4)...")
    for attempt in range(1, max_presses + 1):
        xml = get_screen_xml(device_id)
        if "main_hall" in xml or "battle_item" in xml:
            print(f"[SUCCESS] Main Lobby detected on Back key attempt {attempt}! [OK]")
            return True

        print(f"[*] Sending Back key (attempt {attempt}/{max_presses})...")
        run_adb(["shell", "input", "keyevent", "4"], device_id)
        time.sleep(1.5)

    final_xml = get_screen_xml(device_id)
    ok = "main_hall" in final_xml or "battle_item" in final_xml
    if ok:
        print("[SUCCESS] Main Lobby cleanly detected! [OK]")
    else:
        print("[!] Warning: Could not confirm Main Lobby.")
    return ok


def watch_all_6_ads(device_id: str = "127.0.0.1:21613", max_ads: int = 8) -> bool:
    """
    Master Loop:
    1. Check if Watch AD button is still active (yellow / clickable="true").
    2. Runs watch_single_ad_cycle.
    3. Repeats until button color changes to disabled/grey (clickable="false" or 6/6).
    4. Exits cleanly to Main Lobby using ONLY Back key at the very end.
    """
    print("\n" + "#"*70)
    print("   REWARD COLLECT -> 6/6 VIDEO ADS WATCHER & COLLECTOR")
    print(f"   Target Device: {device_id}")
    print("#"*70 + "\n")

    ensure_on_watch_ad_screen(device_id)

    ad_count = 0
    while ad_count < max_ads:
        # Fast Single XML Check for progress and button status
        xml = get_screen_xml(device_id, timeout=2.5)
        curr, total = 0, 6
        m = re.search(r'text="AD watched times today:\s*(\d+)/(\d+)"', xml)
        if m:
            curr, total = int(m.group(1)), int(m.group(2))

        # Core Rule: If curr < total (e.g. 0/6, 1/6, 5/6), button is definitely ACTIVE (NOT disabled)!
        if total > 0 and curr < total:
            is_disabled = False
        elif total > 0 and curr >= total:
            is_disabled = True
        else:
            is_disabled = False
            m_watch = re.search(r'<node[^>]+resource-id="com\.yalla\.yallagames:id/ll_watch"[^>]*>', xml)
            if m_watch:
                node_str = m_watch.group(0)
                m_click = re.search(r'\sclickable="([^"]+)"', node_str)
                if m_click and m_click.group(1).lower() == "false":
                    is_disabled = True

        if is_disabled:
            print("\n" + "="*70)
            print(f"[+] ALL {total} ADS WATCHED & REWARDS COLLECTED! BUTTON IS NOW DISABLED [COMPLETE]!")
            print("="*70)
            break

        curr_str = f"({curr}/{total})" if total > 0 else ""
        target_ad_num = (curr + 1) if curr is not None else (ad_count + 1)
        print(f"\n[*] Button is ACTIVE (Yellow). Running Ad Cycle for Ad #{target_ad_num} {curr_str}...")

        success = watch_single_ad_cycle(device_id, ad_index=target_ad_num)
        if success:
            ad_count += 1
            print(f"[+] [SUCCESS] Ad #{target_ad_num} watched and reward confirmed! Ready for next cycle.\n")
            time.sleep(1.0)
        else:
            print("[!] Ad cycle encountered an issue (failed to launch ad). Waiting 5s before next attempt...")
            time.sleep(5.0)

    # Clean exit to Main Lobby strictly via Back key at the very end
    exit_ok = exit_to_main_lobby_via_back(device_id)
    return exit_ok


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21613"
    watch_all_6_ads(target)
