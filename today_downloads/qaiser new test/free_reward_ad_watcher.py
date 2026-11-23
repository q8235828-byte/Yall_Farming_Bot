"""
================================================================================
REWARD COLLECT - ULTRA-FAST 6/6 VIDEO ADS WATCHER & COLLECTOR
================================================================================
Module: today_downloads/qaiser new test/free_reward_ad_watcher.py

User Rule & Real-time State Machine:
1. Tap 'Watch AD' at (400, 1181) or d(resourceId='com.yalla.yallagames:id/ll_watch')
2. During the video ad:
   - Real-time focus monitoring via uiautomator2 (<15ms).
   - If Play Store app card appears (com.android.vending): d.press('back') ONCE immediately!
   - Real-time Probing:
     * (740, 36) -> 'Next Ad >>' (Skips Ad 1 in 2-segment ads!)
     * (762, 39) -> 'Reward granted X' (Exits ad instantly upon reward!)
     * (706, 36) -> 'Continue >|' / 'Skip'
3. As soon as ad closes and focus returns to Yalla Ludo:
   - Instantly taps Yellow Confirm at (400, 818) for 'Congratulations' popup.
4. Checks progress (curr / 6):
   - If curr < 6: Launches next ad immediately!
   - If curr >= 6 (button disabled / grey): Cleanly exits via Back key to Main Lobby!
================================================================================
"""

import os
import re
import sys
import time
import uiautomator2 as u2

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

from tips_ad_handler import handle_tips_ad_popup
from screen_detector import get_screen_xml, detect_current_screen

_U2_CACHE = {}


def get_u2(device_id: str = "127.0.0.1:21503"):
    global _U2_CACHE
    dev = device_id or "127.0.0.1:21503"
    if dev not in _U2_CACHE:
        _U2_CACHE[dev] = u2.connect(dev)
    return _U2_CACHE[dev]


def get_current_focus_u2(d) -> str:
    """Returns focused app/activity in <15ms directly from memory."""
    try:
        app = d.app_current()
        pkg = app.get("package", "")
        act = app.get("activity", "")
        return f"{pkg}/{act}"
    except Exception:
        return ""


def ensure_yalla_foreground(d, max_back: int = 3) -> bool:
    """
    User Core Rule:
    'jb yeh ads par by mistake tab kr k chala gia tha toh phr es ne
     auto detect nai kiya k yaeh yalla ludo k screen hai k nai aur na phr
     yeh yalla pat again land howa . esko fix krdo'
    Guarantees device immediately auto-recovers back into Yalla Ludo if an ad
    click accidentally opens Chrome, Play Store, or ANY external app/browser!
    """
    try:
        app = d.app_current()
        pkg = app.get("package", "")
        if pkg and pkg != "com.yalla.yallagames":
            print(f"[!] [AppGuard] Device outside Yalla Ludo in [{pkg}]. Auto-recovering...")
            for _ in range(max_back):
                d.press("back")
                time.sleep(0.4)
                if d.app_current().get("package") == "com.yalla.yallagames":
                    print("[+] [AppGuard] Returned to Yalla Ludo via Back key [OK]!")
                    return True

            # Force stop external package and bring Yalla Ludo to front!
            print(f"[*] [AppGuard] Force-stopping {pkg} and bringing Yalla Ludo to front...")
            try:
                d.app_stop(pkg)
            except Exception:
                pass
            d.app_start("com.yalla.yallagames", ".main.MainActivity")
            time.sleep(1.5)
            return d.app_current().get("package") == "com.yalla.yallagames"
    except Exception as e:
        print(f"[!] AppGuard error: {e}")
    return True


def dismiss_play_store_card_if_present(d) -> bool:
    """If Play Store card is covering screen, dismisses with 1 Back key."""
    focus = get_current_focus_u2(d)
    if any(p in focus for p in ["vending", "market", "Google Play"]):
        print("[!] [Detector] Play Store card DETECTED! Pressing Back key ONCE...")
        d.press("back")
        time.sleep(0.5)
        return True
    return False


def get_ad_watched_progress(device_id: str = "127.0.0.1:21503") -> tuple:
    """Parses 'AD watched times today: X/6' in real-time."""
    d = get_u2(device_id)
    try:
        elem = d(textContains="AD watched times today")
        if elem.exists:
            txt = elem.get_text()
            m = re.search(r'(\d+)/(\d+)', txt)
            if m:
                return int(m.group(1)), int(m.group(2))
    except Exception:
        pass

    # Fast memory dump fallback (<40ms)
    xml = get_screen_xml(device_id)
    m = re.search(r'text="AD watched times today:\s*(\d+)/(\d+)"', xml)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def is_watch_ad_button_active(device_id: str = "127.0.0.1:21503") -> bool:
    """Checks if Watch AD button is Active (Yellow) or Disabled (Grey/6 of 6)."""
    curr, total = get_ad_watched_progress(device_id)
    if curr is not None and total is not None:
        if curr < total:
            return True
        if curr >= total:
            print(f"[+] Progress verified: {curr}/{total} ads watched today. Button is DISABLED!")
            return False

    d = get_u2(device_id)
    watch_btn = d(resourceId="com.yalla.yallagames:id/ll_watch")
    if watch_btn.exists:
        clickable = watch_btn.info.get("clickable", True)
        if not clickable:
            return False

    return True


def ensure_on_watch_ad_screen(device_id: str = "127.0.0.1:21503") -> bool:
    """Ensures device is on 'Watch AD & Win Rewards' screen."""
    from events_dynamic_navigator import is_reward_chest_screen_open, open_and_verify_free_rewards
    d = get_u2(device_id)

    # AppGuard: Guarantee Yalla Ludo is foreground
    ensure_yalla_foreground(d)

    # Check if Congratulations popup is blocking
    if d(text="Confirm").exists or d(resourceId="com.yalla.yallagames:id/btn_collect").exists:
        print("[*] Dismissing Congratulations popup at (400, 818)...")
        d.click(400, 818)
        time.sleep(0.5)

    if is_reward_chest_screen_open(device_id):
        return True

    return open_and_verify_free_rewards(device_id)


def claim_congratulations_popup(d) -> bool:
    """Instantly claims 'Congratulations' popup via Confirm button at (400, 818)."""
    ensure_yalla_foreground(d)
    time.sleep(0.3)
    d.click(400, 818)
    time.sleep(0.3)

    # If still present, re-click once
    if d(text="Confirm").exists or d(resourceId="com.yalla.yallagames:id/btn_collect").exists:
        print("[+] 'Congratulations' popup confirmed! Clicking 'Confirm' at (400, 818)...")
        d.click(400, 818)
        time.sleep(0.3)
    return True


def watch_single_ad_cycle(device_id: str = "127.0.0.1:21503", ad_index: int = 1) -> bool:
    """
    Ultra-Fast Real-Time Ad Watcher:
    1. Taps 'Watch AD' at (400, 1181) or ll_watch.
    2. Real-time Ad Monitor Loop (<15ms per check):
       - Play Store card -> d.press('back') ONCE!
       - (740, 36) -> 'Next Ad >>' (Skips Ad 1 in 2-segment ads!)
       - (762, 39) -> 'Reward granted X' (Exits ad instantly upon reward!)
       - (706, 36) -> 'Continue >|' / 'Skip'
       - Focus back to Yalla Ludo -> Instant exit!
    3. Instant Congratulations Confirm at (400, 818).
    """
    print(f"\n=======================================================")
    print(f"       STARTING FAST REAL-TIME AD CYCLE #{ad_index}")
    print(f"=======================================================")

    d = get_u2(device_id)
    ad_active = False

    for attempt in range(1, 4):
        print(f"[*] Tapping 'Watch AD' button (Attempt {attempt}/3)...")
        watch_btn = d(resourceId="com.yalla.yallagames:id/ll_watch")
        if watch_btn.exists:
            watch_btn.click()
        else:
            d.click(400, 1181)
        time.sleep(0.6)

        # Handle Tips ad confirmation if present
        handle_tips_ad_popup(device_id)

        # Fast check if ad launched (<15ms per check)
        start_wait = time.time()
        while time.time() - start_wait < 7.0:
            focus = get_current_focus_u2(d)
            if any(k in focus for k in ["AdActivity", "UnityAds", "AppLovin", "vending", "com.google.android.gms.ads"]):
                ad_active = True
                print(f"[+] Video Ad launched successfully! Focus: {focus}")
                break
            if handle_tips_ad_popup(device_id):
                time.sleep(0.3)
                continue
            time.sleep(0.4)

        if ad_active:
            break

        # Buffer wait / self-healing if video failed to load
        if attempt < 3:
            print("\n[!] Ad buffer delay. Refreshing screen...")
            d.press("back")
            time.sleep(1.0)
            ensure_on_watch_ad_screen(device_id)
            time.sleep(10.0)

    if not ad_active:
        print("[-] Video Ad could not load after retries.")
        return False

    # Proactive Fast Real-Time In-Ad Monitor Loop
    print("[*] Real-Time Ad Playback Monitor Active...")
    ad_start = time.time()
    last_probe = 0.0

    while time.time() - ad_start < 60.0:
        elapsed = time.time() - ad_start

        # Check 0: Has device switched away to ANY external app/browser? (Chrome, Browser, Play Store, etc.)
        app = d.app_current()
        pkg = app.get("package", "")
        if pkg and pkg != "com.yalla.yallagames":
            print(f"[{elapsed:.1f}s] [AppGuard] Accidental click opened external app [{pkg}]! Auto-returning to Yalla Ludo...")
            ensure_yalla_foreground(d)
            time.sleep(0.5)
            continue

        # Check A: Focus returned to Yalla Ludo MainActivity (<15ms)
        focus = get_current_focus_u2(d)
        if "com.yalla.yallagames" in focus and not any(k in focus for k in ["AdActivity", "UnityAds", "AppLovin", "vending"]):
            print(f"[+] Focus returned to Yalla Ludo after {elapsed:.1f}s [FAST-EXIT OK]!")
            break

        # Check B: Play Store Card Detection -> 1 Back key
        if any(p in focus for p in ["vending", "market", "Google Play"]):
            print(f"[{elapsed:.1f}s] [Detector] Play Store card DETECTED! Pressing Back key ONCE...")
            d.press("back")
            time.sleep(0.6)
            continue

        # Check C: Proactive Real-Time Probing:
        # - (740, 36) -> 'Next Ad >>' (Image 1: Skips Ad 1!)
        # - (762, 39) -> 'Reward granted X' (Image 2: Exits Ad 2!)
        # - (706, 36) -> 'Continue >|'
        if elapsed >= 3.0 and elapsed - last_probe >= 1.2:
            # Check Close element by text
            try:
                close_elem = d(text="Close")
                if close_elem.exists:
                    close_elem.click()
                    time.sleep(0.2)
            except Exception:
                pass

            # Probe Next Ad >> (Image 1)
            d.click(740, 36)
            time.sleep(0.1)

            # Probe Reward Granted X (Image 2)
            d.click(762, 39)
            time.sleep(0.1)

            # Probe Continue
            d.click(706, 36)
            last_probe = elapsed

            # Instant check if ad closed
            focus_after = get_current_focus_u2(d)
            if "com.yalla.yallagames" in focus_after and not any(k in focus_after for k in ["AdActivity", "UnityAds", "AppLovin", "vending"]):
                print(f"[+] Probed Exit/Close at {elapsed:.1f}s -> Ad closed immediately [FAST-EXIT OK]!")
                break

        time.sleep(0.3)

    # Claim 'Congratulations' popup immediately
    print("[*] Claiming 'Congratulations' popup...")
    claim_congratulations_popup(d)

    curr_after, total = get_ad_watched_progress(device_id)
    if curr_after is not None:
        print(f"[+] Current Ad Progress: {curr_after}/{total} [OK]!")
    return True


def exit_to_main_lobby_via_back(device_id: str = "127.0.0.1:21503", max_presses: int = 4) -> bool:
    """Cleanly exits to Main Lobby using ONLY Back key at the very end."""
    print("\n[*] Exiting to Main Lobby using strictly Back key...")
    d = get_u2(device_id)
    for attempt in range(1, max_presses + 1):
        if detect_current_screen(device_id) == "MAIN_LOBBY":
            print(f"[SUCCESS] Main Lobby detected on Back key attempt {attempt}! [OK]")
            return True

        d.press("back")
        time.sleep(1.0)

    ok = (detect_current_screen(device_id) == "MAIN_LOBBY")
    if ok:
        print("[SUCCESS] Main Lobby cleanly detected! [OK]")
    return ok


def watch_all_6_ads(device_id: str = "127.0.0.1:21503", max_ads: int = 8) -> bool:
    """
    Master Loop for 6/6 Ads:
    Runs until all 6/6 ads are watched and button becomes disabled,
    then exits to Main Lobby.
    """
    print("\n" + "#"*70)
    print("   REWARD COLLECT -> 6/6 VIDEO ADS WATCHER (UIAUTOMATOR2 ENGINE)")
    print(f"   Target Device: {device_id}")
    print("#"*70 + "\n")

    ensure_on_watch_ad_screen(device_id)

    ad_count = 0
    while ad_count < max_ads:
        curr, total = get_ad_watched_progress(device_id)
        if total and curr is not None and curr >= total:
            print("\n" + "="*70)
            print(f"[+] ALL {total} ADS WATCHED & REWARDS COLLECTED! [COMPLETE]!")
            print("="*70)
            break

        if not is_watch_ad_button_active(device_id):
            print("\n" + "="*70)
            print("[+] Watch AD button is GREY/DISABLED! All rewards collected [COMPLETE]!")
            print("="*70)
            break

        target_num = (curr + 1) if curr is not None else (ad_count + 1)
        curr_str = f"({curr}/{total})" if total else ""
        print(f"\n[*] Button is ACTIVE (Yellow). Running Ad Cycle for Ad #{target_num} {curr_str}...")

        success = watch_single_ad_cycle(device_id, ad_index=target_num)
        if success:
            ad_count += 1
            time.sleep(0.8)
        else:
            print("[!] Ad buffer wait before next retry...")
            time.sleep(4.0)

    # Clean exit to Main Lobby strictly via Back key
    return exit_to_main_lobby_via_back(device_id)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21503"
    watch_all_6_ads(target)
