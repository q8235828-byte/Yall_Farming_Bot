"""
================================================================================
EVENTS DYNAMIC CARD NAVIGATOR & SCREEN VERIFIER (events_dynamic_navigator.py)
================================================================================
Addresses the dynamic Events Page layout:
- Event banners (e.g. Camel Dash) appear/disappear, pushing cards up/down.
- Dynamically locates 'Free Rewards' and 'Golds Chest' cards.
- Strict Verification (Image #2):
  * When 'Free Rewards' is tapped, verifies if 'Reward Chest' / 'Watch AD & Win Rewards'
    screen actually opened.
  * If wrong card was clicked:
    - Sends Back key (keyevent 4) to dismiss wrong card.
    - Measures card height (~220px on 800x1280) and swipes/scrolls screen.
    - Clicks on alternative candidate target until 'Reward Chest' is 100% verified!
================================================================================
"""

import os
import re
import sys
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

from screen_detector import run_adb, get_screen_xml, detect_current_screen

CARD_HEIGHT_800P = 220  # Measured height of cards on 800x1280 MEmu


def is_reward_chest_screen_open(device_id: str = None) -> bool:
    """
    User Rule (Image #2):
    Verifies if 'Reward Chest' / 'Watch AD & Win Rewards' screen is currently open.
    Checks:
    - 'Reward Chest'
    - 'Watch AD & Win Rewards' or 'Watch AD &amp; Win Rewards'
    - 'AD watched times today'
    - 'Watch AD' button
    """
    xml = get_screen_xml(device_id)
    if not xml:
        return False
    return any(k in xml for k in [
        "Reward Chest",
        "RewardChest",
        "Watch AD & Win Rewards",
        "Watch AD &amp; Win Rewards",
        "AD watched times today",
        "rl_reward_chest",
        "ll_watch"
    ])


def is_on_events_tab(device_id: str = None) -> bool:
    """Checks if currently on Events tab."""
    xml = get_screen_xml(device_id)
    if not xml:
        return False
    return any(k in xml for k in ["rl_ad_free_reward", "Free Rewards", "VIP Subscription", "Daily Tasks", "rl_event_vip"])


def ensure_events_tab(device_id: str = "127.0.0.1:21503") -> bool:
    """Navigates to Events tab at (80, 1180) from Lobby via uiautomator2."""
    if is_on_events_tab(device_id):
        return True
    try:
        import uiautomator2 as u2
        d = u2.connect(device_id)
        ev = d(resourceId="com.yalla.yallagames:id/events_item")
        if ev.exists:
            ev.click()
        else:
            d.click(80, 1180)
        time.sleep(0.8)
    except Exception:
        run_adb(["shell", "input", "tap", "80", "1180"], device_id)
        time.sleep(1.0)
    return is_on_events_tab(device_id)


def scroll_events_to_top(device_id: str = "127.0.0.1:21613"):
    """Swipes down inside scroll area to reset view to very top of Events page."""
    print(f"[*] Scrolling Events page to top...")
    # Swipe down from Y=400 to Y=950 (scroll content down = go to top)
    run_adb(["shell", "input", "swipe", "400", "400", "400", "950", "600"], device_id)
    time.sleep(1.2)


def scroll_events_down(device_id: str = "127.0.0.1:21613", distance_px: int = 220):
    """Swipes up inside scroll area by card height to reveal lower cards."""
    print(f"[*] Swiping Events page up by {distance_px}px (card length)...")
    start_y = 750
    end_y = max(250, start_y - distance_px)
    run_adb(["shell", "input", "swipe", "400", str(start_y), "400", str(end_y), "500"], device_id)
    time.sleep(1.2)


def find_free_rewards_card_coords(device_id: str = "127.0.0.1:21503") -> tuple[int, int] | None:
    """Locates Free Rewards card in real-time via uiautomator2 element bounds."""
    try:
        import uiautomator2 as u2
        d = u2.connect(device_id)
        card = d(text="Free Rewards")
        if not card.exists:
            card = d(resourceId="com.yalla.yallagames:id/rl_ad_free_reward")
        if card.exists:
            b = card.info.get("bounds")
            if b:
                cx = (b["left"] + b["right"]) // 2
                cy = (b["top"] + b["bottom"]) // 2
                return (cx, cy)
    except Exception:
        pass

    xml = get_screen_xml(device_id)
    m = re.search(r'resource-id="[^"]*rl_ad_free_reward"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml)
    if not m:
        m = re.search(r'text="Free Rewards"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml)

    if m:
        x1, y1, x2, y2 = map(int, m.groups())
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        if 150 <= cy <= 1050:
            return (cx, cy)
    return None


def open_and_verify_free_rewards(device_id: str = "127.0.0.1:21613", max_attempts: int = 5) -> bool:
    """
    User Core Rule (Images 1 & 2):
    1. If already on 'Reward Chest' (Image 2), returns True immediately.
    2. Navigates to Events tab.
    3. Finds 'Free Rewards' card dynamically (from XML bounds).
    4. Clicks the target.
    5. VERIFIES Image #2 ('Reward Chest' / 'Watch AD & Win Rewards').
    6. If verified -> Continues!
    7. If NOT verified (wrong card opened, e.g. Camel Dash or VIP):
       - Sends Back key ONCE to dismiss wrong screen.
       - Measures card length, scrolls/swipes screen to adjust.
       - Clicks different target until 'Reward Chest' is 100% verified!
    """
    # Check 1: Already open?
    if is_reward_chest_screen_open(device_id):
        print("[+] Screen State: Already on 'Reward Chest' screen (Image #2) [OK]!")
        return True

    # Check 2: Ensure on Events tab
    ensure_events_tab(device_id)

    candidate_targets = [
        (400, 658),  # Most common layout
        (400, 520),  # Top banner layout
        (400, 440),  # No banner layout
        (400, 780),  # Large banner layout
    ]

    for attempt in range(1, max_attempts + 1):
        print(f"\n[*] [Free Rewards Navigation] Attempt {attempt}/{max_attempts}...")

        # Step A: Check if 'Reward Chest' already opened
        if is_reward_chest_screen_open(device_id):
            print("[+] [VERIFIED] 'Reward Chest' screen (Image #2) DETECTED [OK]!")
            return True

        # Step B: Dynamically locate card from live XML
        coords = find_free_rewards_card_coords(device_id)
        if coords:
            print(f"[+] Dynamically located 'Free Rewards' card at {coords}!")
            target_x, target_y = coords
        else:
            if attempt == 1:
                scroll_events_to_top(device_id)
                coords = find_free_rewards_card_coords(device_id)
                if coords:
                    target_x, target_y = coords
                else:
                    target_x, target_y = candidate_targets[0]
            else:
                scroll_events_down(device_id, distance_px=CARD_HEIGHT_800P)
                coords = find_free_rewards_card_coords(device_id)
                if coords:
                    target_x, target_y = coords
                else:
                    target_x, target_y = candidate_targets[min(attempt - 1, len(candidate_targets) - 1)]

        # Step C: Tap target
        print(f"[*] Tapping Free Rewards candidate at ({target_x}, {target_y})...")
        run_adb(["shell", "input", "tap", str(target_x), str(target_y)], device_id)
        time.sleep(2.0)

        # Step D: VERIFY Image #2 ('Reward Chest')
        if is_reward_chest_screen_open(device_id):
            print("[+] [SUCCESS] 'Reward Chest' screen (Image #2) VERIFIED [OK]!")
            return True

        # Step E: WRONG TARGET OPENED! Follow User Rule:
        print("[-] [WRONG TARGET] 'Reward Chest' screen did NOT open!")
        print("[*] [User Rule] Sending Back key (keyevent 4) to dismiss wrong screen...")
        run_adb(["shell", "input", "keyevent", "4"], device_id)
        time.sleep(1.5)

        # Ensure back on Events tab
        ensure_events_tab(device_id)

    print("[-] Failed to open 'Reward Chest' screen after all attempts.")
    return False


def is_golds_chest_popup_open(device_id: str = None) -> bool:
    """
    Checks if 'Tap to Open Chest' or '+500 / Double' popup is open.
    Markers:
    - 'Tap to Open Chest' or 'Tap to Open'
    - 'btn_open'
    - 'Double' button with '+500' or '+1000'
    - 'fl_chest'
    """
    xml = get_screen_xml(device_id)
    if not xml:
        return False
    return any(k in xml for k in [
        "Tap to Open Chest",
        "Tap to Open",
        "btn_open",
        "fl_chest",
        "Double"
    ]) and "Privileges" not in xml and "You can create or join a VIP room!" not in xml


def is_wrong_event_subscreen_open(device_id: str = None) -> bool:
    """Checks if an unintended sub-screen (e.g. Privileges) is open."""
    xml = get_screen_xml(device_id)
    if not xml:
        return False
    # Only true if Privileges subscreen is open, and NOT on Events tab or Main Lobby
    if ("Privileges" in xml or "You can create or join a VIP room!" in xml) and "main_hall" not in xml and "rl_ad_free_reward" not in xml:
        return True
    return False


def dismiss_wrong_event_subscreen(device_id: str = "127.0.0.1:21613"):
    """Sends Back key to cleanly dismiss wrong subscreen (e.g. Privileges) back to Events tab."""
    if is_wrong_event_subscreen_open(device_id):
        print("[!] [User Rule] Wrong screen ('Privileges') opened! Dismissing via Back key...")
        run_adb(["shell", "input", "keyevent", "4"], device_id)
        time.sleep(1.5)
        ensure_events_tab(device_id)


def find_golds_chest_card_coords(device_id: str = "127.0.0.1:21613") -> tuple[int, int] | None:
    """
    Dynamically searches screen XML for Golds Chest card or its Collect button.
    Returns (center_x, center_y) if visible.
    """
    xml = get_screen_xml(device_id)
    if not xml:
        return None

    # Search for Golds Chest title or container
    for pattern in [
        r'text="[^"]*(?:Golds?\s*Chest)[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
        r'resource-id="[^"]*(?:gold_chest|golds_chest|rl_chest)[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
    ]:
        m = re.search(pattern, xml, re.IGNORECASE)
        if m:
            x1, y1, x2, y2 = map(int, m.groups())
            cy = (y1 + y2) // 2
            if 150 <= cy <= 1050:
                # The 'Collect' button on the Golds Chest card is on the right side (~550)
                return (550, cy)

    return None


def open_and_verify_golds_chest(device_id: str = "127.0.0.1:21613", max_attempts: int = 3) -> bool:
    """
    User Core Rule (Golds Chest):
    1. If already on Chest popup, returns True.
    2. Navigates to Events tab.
    3. Checks if countdown timer is active (already claimed) -> returns True.
    4. Searches dynamically for 'Golds Chest' card:
       - Checks current view, scrolls down by card length (220px), checks again.
       - If NOT found on Events tab (e.g. not available today):
         * SKIPS Golds Chest gracefully!
         * Does NOT tap random coordinates or run remaining script!
         * Returns False so caller immediately proceeds to Free Rewards!
    5. If card IS found:
       - Taps target.
       - STRICTLY VERIFIES if Chest popup opened.
       - If wrong screen opened (e.g. 'Privileges' / 'VIP Room'):
         * Sends Back key ONCE to dismiss wrong screen.
         * Swipes/scrolls by card length (220px) and retries.
       - If chest popup still does not open:
         * Dismisses wrong screen, logs skip, and returns False!
    """
    # Check 1: Already on Chest popup?
    if is_golds_chest_popup_open(device_id):
        print("[+] Screen State: Already on Golds Chest popup [OK]!")
        return True

    ensure_events_tab(device_id)

    # Check 2: Is countdown timer showing? (Already claimed today)
    xml = get_screen_xml(device_id)
    if re.search(r'text="(\d{2}:\d{2}:\d{2})"', xml) or "tv_time_count" in xml:
        print("[+] Golds Chest countdown timer is showing (already opened today) [OK]!")
        return True

    # Check 3: Dynamically search for Golds Chest card on Events page
    print("[*] Searching for 'Golds Chest' card dynamically on Events tab...")
    coords = find_golds_chest_card_coords(device_id)

    if not coords:
        # Try scrolling down 220px to see if it's further down
        print("[*] Golds Chest card not in top view. Swiping down by 220px...")
        scroll_events_down(device_id, distance_px=CARD_HEIGHT_800P)
        coords = find_golds_chest_card_coords(device_id)

    if not coords:
        # Try scrolling to top
        scroll_events_to_top(device_id)
        coords = find_golds_chest_card_coords(device_id)

    # If card is NOT present on the Events page at all (User Rule: Not available today)
    if not coords:
        print("\n" + "="*70)
        print("[!] [Golds Chest Detector] 'Golds Chest' card is NOT available on Events tab today!")
        print("[*] [User Rule] Skipping Golds Chest script and proceeding directly to Free Rewards!")
        print("="*70 + "\n")
        dismiss_wrong_event_subscreen(device_id)
        return False

    # Check 4: Card was found -> tap and strictly verify
    target_x, target_y = coords
    for attempt in range(1, max_attempts + 1):
        print(f"\n[*] [Golds Chest Navigation] Attempt {attempt}/{max_attempts}: Tapping at ({target_x}, {target_y})...")
        run_adb(["shell", "input", "tap", str(target_x), str(target_y)], device_id)
        time.sleep(2.0)

        # STRICT VERIFICATION
        if is_golds_chest_popup_open(device_id):
            print("[+] [SUCCESS] Golds Chest popup VERIFIED [OK]!")
            return True

        # Check if wrong screen opened (e.g. VIP Room / Privileges)
        if is_wrong_event_subscreen_open(device_id):
            dismiss_wrong_event_subscreen(device_id)
            scroll_events_down(device_id, distance_px=CARD_HEIGHT_800P)
            new_coords = find_golds_chest_card_coords(device_id)
            if new_coords:
                target_x, target_y = new_coords
            else:
                break

    # If all attempts failed to open Chest popup
    print("[-] [User Rule] Golds Chest popup could not be opened. Skipping to Free Rewards...")
    dismiss_wrong_event_subscreen(device_id)
    return False


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21613"
    print(f"Testing open_and_verify_free_rewards on {target}...")
    res = open_and_verify_free_rewards(target)
    print(f"Result: {res}")
