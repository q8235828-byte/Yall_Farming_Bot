"""
================================================================================
GOOGLE SHEET REAL-TIME SYNC & 24-HOUR REWARD CYCLE MANAGER (google_sheet_sync.py)
================================================================================
Connects the live Google Sheet with the Yalla Ludo Automation pipeline:
Sheet URL: https://docs.google.com/spreadsheets/d/1h2y1lr1WF5cOicHEIxd_26k695KZVP-ILCh36ML6Ngs/edit
Webhook URL: https://script.google.com/macros/s/AKfycbz_0cbU9GjM_FmvtqmVx7o27HLoVXUd_1EtcfvKfnFXvxauE7jvYhQfdCKwvzcaZ128/exec

Columns Synced:
- Timestamp (Col A) -> Live completion / update datetime
- Status (Col E)
- Device_ID (Col F)
- Golds_Chest (Col G)
- Free_Rewards (Col H)
- Total_Coin (Col I)

24-Hour Reward Cooldown Rule:
- When an account finishes 6/6 video ads AND Golds Chest (or Status='Success_Completed'):
  * It enters a strict 24-HOUR COOLDOWN.
  * The automation will NOT touch this account in the sheet for 24 hours.
  * Once 24 hours have elapsed since completion, the account becomes ELIGIBLE AGAIN
    for its daily reward refresh!
================================================================================
"""

import csv
import io
import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)

WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbz_0cbU9GjM_FmvtqmVx7o27HLoVXUd_1EtcfvKfnFXvxauE7jvYhQfdCKwvzcaZ128/exec"
SHEET_EXPORT_URL = "https://docs.google.com/spreadsheets/d/1h2y1lr1WF5cOicHEIxd_26k695KZVP-ILCh36ML6Ngs/export?format=csv&gid=1485006795"

import threading

HISTORY_FILE = os.path.join(CURRENT_DIR, "accounts_24h_history.json")
COOLDOWN_HOURS = 24.0
history_lock = threading.Lock()


def load_24h_history() -> dict:
    """Loads local persistent 24h completion history (process-safe & thread-safe)."""
    with history_lock:
        for _ in range(5):
            if os.path.exists(HISTORY_FILE):
                try:
                    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    time.sleep(0.08)
            else:
                return {}
        return {}


def save_24h_history(history: dict):
    """Saves local persistent 24h completion history (process-safe & thread-safe)."""
    with history_lock:
        for _ in range(5):
            try:
                tmp_file = f"{HISTORY_FILE}.{os.getpid()}.tmp"
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(history, f, indent=2)
                os.replace(tmp_file, HISTORY_FILE)
                break
            except Exception:
                time.sleep(0.08)


def record_account_completed(email: str, free_rewards: str = "6/6", golds_chest: str = "Yes", status: str = "Success_Completed"):
    """
    Records an account's completion time to enforce the 24-hour cooldown.
    """
    if not email:
        return
    history = load_24h_history()
    now_ts = time.time()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    history[email.strip().lower()] = {
        "email": email.strip(),
        "completed_at_timestamp": now_ts,
        "completed_at_datetime": now_str,
        "free_rewards": free_rewards,
        "golds_chest": golds_chest,
        "status": status
    }
    save_24h_history(history)
    next_ready = datetime.fromtimestamp(now_ts + COOLDOWN_HOURS * 3600).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[+] [24h Manager] Account {email} recorded! 24h cooldown active until: {next_ready} [OK]")


def check_account_cooldown(acc: dict, history: dict = None) -> tuple[bool, float, str]:
    """
    Checks if an account is currently on 24-hour cooldown.
    Returns: (is_on_cooldown: bool, hours_remaining: float, explanation: str)
    """
    if history is None:
        history = load_24h_history()

    email = acc.get("Email", "").strip().lower()
    status = acc.get("Status", "").strip()
    free_rewards = acc.get("Free_Rewards", "").strip()
    golds_chest = acc.get("Golds_Chest", "").strip()
    sheet_ts_str = acc.get("Timestamp", "").strip()

    # Is this account considered completed?
    is_completed = (free_rewards == "6/6" and golds_chest.lower() == "yes") or (status in ["Success_Completed", "Completed_LoggedOut"])

    if not is_completed:
        # Not completed yet (fresh, failed, or partial) -> Not on cooldown
        return False, 0.0, "Pending incomplete"

    # Determine last completion timestamp
    last_completed_ts = None

    # Priority 1: Check local persistent history
    if email in history:
        last_completed_ts = history[email].get("completed_at_timestamp")

    # Priority 2: Fallback to Sheet Timestamp column
    if last_completed_ts is None and sheet_ts_str:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S"):
            try:
                dt = datetime.strptime(sheet_ts_str, fmt)
                last_completed_ts = dt.timestamp()
                break
            except Exception:
                pass

    if last_completed_ts is None:
        # No valid timestamp available, treat as eligible
        return False, 0.0, "Completed with no timestamp, eligible for refresh"

    # Calculate elapsed time
    elapsed_seconds = time.time() - last_completed_ts
    elapsed_hours = elapsed_seconds / 3600.0

    if elapsed_hours < COOLDOWN_HOURS:
        hours_remaining = COOLDOWN_HOURS - elapsed_hours
        return True, hours_remaining, f"Completed {elapsed_hours:.1f}h ago. Cooldown active ({hours_remaining:.1f}h remaining)"
    else:
        return False, 0.0, f"Completed {elapsed_hours:.1f}h ago (>= 24h passed). Eligible for daily reward refresh!"


def is_account_eligible_to_process(acc: dict, history: dict = None) -> bool:
    """
    Determines whether an account should be picked up by the automation.
    - Returns False if on 24-hour cooldown.
    - Returns True if incomplete OR if completed > 24 hours ago.
    """
    email = acc.get("Email", "").strip()
    if not email or "@" not in email:
        return False

    is_cooldown, hours_rem, reason = check_account_cooldown(acc, history=history)
    if is_cooldown:
        return False
    return True


def update_google_sheet(
    email: str,
    status: str = None,
    device_id: str = None,
    golds_chest: str = None,
    free_rewards: str = None,
    total_coin: str = None,
    latest_update: str = None,
    timestamp: str = None
) -> bool:
    """
    Sends a real-time update to the live Google Sheet via Google Apps Script Webhook.
    Also automatically records 24h completion history when rewards finish.
    """
    if not email:
        print("[!] GoogleSheetSync: email is required to update sheet.")
        return False

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    update_time = latest_update or now_str

    payload = {
        "email": email.strip(),
        "timestamp": timestamp or now_str,
        "latest_update": update_time,
        "Latest_Update": update_time
    }
    if status is not None:
        payload["status"] = str(status)
    if device_id is not None:
        payload["device_id"] = str(device_id)
    if golds_chest is not None:
        payload["golds_chest"] = str(golds_chest)
    if free_rewards is not None:
        payload["free_rewards"] = str(free_rewards)
    if total_coin is not None:
        payload["total_coin"] = str(total_coin)

    # If completed 6/6 ads and golds chest or success, record in 24h history
    if (free_rewards == "6/6" and str(golds_chest).lower() == "yes") or (status == "Success_Completed"):
        record_account_completed(
            email=email,
            free_rewards=free_rewards or "6/6",
            golds_chest=golds_chest or "Yes",
            status=status or "Success_Completed"
        )

    payload_json = json.dumps(payload)
    print(f"[*] [GoogleSheetSync] Syncing update for {email}: {payload}")

    try:
        # Use curl.exe which natively follows Google Apps Script 302 redirects
        cmd = [
            "curl.exe", "-L", "-s",
            "-H", "Content-Type: application/json",
            "-d", payload_json,
            WEBHOOK_URL
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
        out = res.stdout.strip()
        if "UPDATED" in out:
            print(f"[+] [GoogleSheetSync] Google Sheet LIVE UPDATED for {email} [OK]!")
            return True
        else:
            print(f"[-] [GoogleSheetSync] Webhook response: {out}")
            return False
    except Exception as e:
        print(f"[!] [GoogleSheetSync] Error syncing to Google Sheet: {e}")
        return False


def fetch_all_accounts_from_sheet() -> list[dict]:
    """
    Reads the full live Google Sheet and returns all accounts as a list of dicts.
    """
    try:
        req = urllib.request.Request(SHEET_EXPORT_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = resp.read().decode("utf-8", errors="ignore")

        reader = csv.reader(io.StringIO(data))
        rows = list(reader)
        if not rows:
            return []

        header = [h.strip() for h in rows[0]]
        accounts = []
        for r in rows[1:]:
            if not r or len(r) < 2 or not r[1].strip():
                continue
            acc = {}
            for idx, col_name in enumerate(header):
                acc[col_name] = r[idx].strip() if idx < len(r) else ""
            accounts.append(acc)

        print(f"[+] [GoogleSheetSync] Fetched {len(accounts)} accounts from live Google Sheet [OK]!")
        return accounts
    except Exception as e:
        print(f"[!] [GoogleSheetSync] Error fetching sheet: {e}")
        return []


def get_next_accounts_to_process(max_count: int = 10) -> list[dict]:
    """
    Scans the live Google Sheet and returns accounts that are eligible to process.
    - Excludes accounts that finished 6/6 ads + Golds Chest within the last 24 hours.
    - Includes accounts completed > 24 hours ago (daily reset).
    - Includes all pending/incomplete accounts.
    """
    all_accounts = fetch_all_accounts_from_sheet()
    history = load_24h_history()
    pending = []

    for acc in all_accounts:
        email = acc.get("Email", "").strip()
        if not email or "@" not in email:
            continue

        if not is_account_eligible_to_process(acc, history=history):
            continue

        password = acc.get("Password", "").strip()
        # Clean password fallback
        if not password or "FAILED" in password.upper() or len(password) < 6:
            password = "Yalla#2026@Pass"

        acc["Clean_Password"] = password
        pending.append(acc)

        if len(pending) >= max_count:
            break

    print(f"[+] [GoogleSheetSync] Found {len(pending)} eligible accounts ready for processing (24h cooldown respected).")
    return pending


if __name__ == "__main__":
    import sys
    test_email = sys.argv[1] if len(sys.argv) > 1 else "user221@bhullehshahsilage.com"
    update_google_sheet(test_email, status="Ready_For_Logout", golds_chest="Yes", free_rewards="6/6")
