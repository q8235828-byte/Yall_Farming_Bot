"""
================================================================================
YALLA LUDO - RUN ALL ACTIVE INSTANCES RUNNER (run_all_active.py)
================================================================================
Purpose:
1. Auto-Discovery & Auto-Connect:
   - Scans all MEmu ADB ports (21503 to 21673) and connects them automatically.
   - Detects all online MEmu instances in parallel without manual adb connect.
2. Ad ID Reset & Fresh 5s Ads:
   - Before each account cycle, resets Google Advertising ID and clears ad video cache
     on that specific MEmu instance.
3. Thread-Safe Account Dispatcher:
   - Synchronized account reservation across all parallel workers.
   - Enforces 24h cooldown to prevent premature re-processing.
   - Syncs live status to Google Sheet via webhook.
4. Continuous Execution:
   - Runs across all instances simultaneously until all pending accounts finish.
================================================================================
"""

import os
import re
import socket
import subprocess
import sys
import threading
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

ADB_BIN = os.path.join(PARENT_DIR, "platform-tools", "adb.exe")
if not os.path.exists(ADB_BIN):
    ADB_BIN = "adb"

from master_pipeline import run_full_account_cycle
from google_sheet_sync import (
    fetch_all_accounts_from_sheet,
    update_google_sheet,
    is_account_eligible_to_process,
    load_24h_history
)

# Global thread lock for account reservation
account_lock = threading.Lock()
claimed_emails = set()
cached_accounts_list = []
last_sheet_fetch_time = 0.0


def auto_connect_memu_instances():
    """
    Probes all standard MEmu ADB ports and connects them to ADB server.
    Ensures every open MEmu instance is detected!
    """
    memu_ports = [
        21503, 21513, 21523, 21533, 21543, 21553, 
        21563, 21573, 21583, 21593, 21603, 21613,
        21623, 21633, 21643, 21653, 21663, 21673
    ]
    for port in memu_ports:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.05)
                if s.connect_ex(('127.0.0.1', port)) == 0:
                    subprocess.run([ADB_BIN, "connect", f"127.0.0.1:{port}"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.0)
        except Exception:
            pass


def get_connected_devices() -> list[str]:
    """Auto-connects MEmu ports and returns all online adb devices."""
    auto_connect_memu_instances()
    cmd = [ADB_BIN, "devices"]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=6)
        out = res.stdout.decode("utf-8", errors="ignore")
        devices = []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices"):
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices
    except Exception as e:
        print(f"[!] Error detecting devices: {e}")
        return []


def get_next_available_account() -> dict:
    """Thread-safe selector: picks the next eligible account respecting 24h cooldown."""
    global cached_accounts_list, last_sheet_fetch_time

    with account_lock:
        now = time.time()
        # Refresh sheet cache if empty or older than 60 seconds
        if not cached_accounts_list or (now - last_sheet_fetch_time > 60.0):
            print("[*] Refreshing accounts queue from Google Sheet...")
            cached_accounts_list = fetch_all_accounts_from_sheet()
            last_sheet_fetch_time = now

        history = load_24h_history()
        for acc in cached_accounts_list:
            email = acc.get("Email", "").strip()

            if not email or "@" not in email:
                continue
            if email in claimed_emails:
                continue
            if not is_account_eligible_to_process(acc, history=history):
                continue

            # Valid eligible account found
            claimed_emails.add(email)
            password = acc.get("Password", "").strip()
            if not password or "FAILED" in password.upper() or len(password) < 6:
                password = "Yalla#2026@Pass"
            acc["Clean_Password"] = password
            return acc

    return None


def instance_worker(device_id: str, stop_event: threading.Event):
    """Worker loop dedicated to one MEmu instance."""
    print(f"[+] [Worker Started] Instance: {device_id}")

    while not stop_event.is_set():
        acc = get_next_available_account()
        if not acc:
            print(f"[*] [{device_id}] No more pending accounts in Google Sheet. Worker finishing.")
            break

        email = acc["Email"]
        password = acc["Clean_Password"]
        print(f"\n{'='*70}\n[*] [{device_id}] Starting cycle for: {email}\n{'='*70}")

        try:
            ok = run_full_account_cycle(device_id=device_id, email=email, password=password)
            if ok:
                print(f"[SUCCESS] [{device_id}] Cycle completed for {email} [OK]!")
            else:
                print(f"[-] [{device_id}] Cycle failed or aborted for {email}.")
        except Exception as e:
            print(f"[!] [{device_id}] Exception occurred while processing {email}: {e}")

        time.sleep(2.0)

    print(f"[-] [Worker Stopped] Instance: {device_id}")


def run_all_active_pipeline(max_workers: int = None):
    print("\n" + "#"*80)
    print("   YALLA LUDO - SCANNING & CONNECTING ALL ACTIVE MEMU INSTANCES...")
    print("#"*80 + "\n")

    devices = get_connected_devices()
    if not devices:
        print("[!] No active ADB devices found! Make sure MEmu instances are open.")
        return

    if max_workers:
        devices = devices[:max_workers]

    print(f"[+] Detected Active MEmu Instances ({len(devices)}): {devices}\n")

    stop_event = threading.Event()
    threads = []

    for dev in devices:
        t = threading.Thread(target=instance_worker, args=(dev, stop_event), daemon=True)
        threads.append(t)
        t.start()
        time.sleep(6.0)  # Stagger thread starts (avoids concurrent network choke)

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("\n[!] Ctrl+C received! Stopping all instance workers...")
        stop_event.set()

    print("\n[+] All instance workers finished.")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    run_all_active_pipeline(max_workers=limit)
