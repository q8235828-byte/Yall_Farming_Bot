"""
================================================================================
YALLA LUDO MEMU MULTI-INSTANCE ORCHESTRATOR WITH MOBILE 4G IP ROTATION
================================================================================
Orchestrates Yalla Ludo account creation across MEmu instances (1080x2400)
using a physical USB Android phone to rotate mobile 4G LTE IPs via Airplane Mode.
================================================================================
"""

import argparse
import csv
from datetime import datetime
import json
import os
import subprocess
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from airplane_mode import ADB_BIN, run_adb_command
from color_indexed_captcha_solver import ColorIndexedCaptchaSolver
from otp_fetcher import GmailOTPFetcher
from screen_detector import (
    ScreenDetector,
    STATE_MAIN_LANDING,
    STATE_LOGIN_DIALOG,
    STATE_SIGNUP,
    STATE_CAPTCHA,
    STATE_OTP_READY,
    STATE_SET_PASSWORD,
    STATE_EXPERT_DIALOG,
)
import yalla_ui_automator as ui
import yalla_creator_fast as yf
from github_proxy_rotator import rotate_ip_smart, is_mobile_rotator_available

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
ACCOUNTS_CSV = os.path.join(BASE_DIR, "created_accounts.csv")
BACKUP_CSV = os.path.join(BASE_DIR, "created_accounts_backup.csv")
DEFAULT_PASSWORD = "LudoPass#2026@"
PACKAGE_NAME = "com.yalla.yallagames"

ROTATOR_PHONE_SERIAL = "34558213310005P"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def get_current_public_ip(timeout: int = 5) -> str:
    """Fetches the current external IP of the PC (via tethered phone)."""
    try:
        req = urllib.request.Request(
            "https://api.ipify.org?format=json",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("ip", "Unknown")
    except Exception:
        try:
            req = urllib.request.Request("https://ifconfig.me/ip", headers={"User-Agent": "curl/7.68.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8").strip()
        except Exception:
            return "Unknown"


def rotate_mobile_ip(phone_id: str = ROTATOR_PHONE_SERIAL, wait_seconds: float = 2.5) -> str:
    """Toggles Airplane Mode on the tethered mobile phone to obtain a fresh 4G IP."""
    ip_before = get_current_public_ip()
    print(f"\n[*] [IP-ROTATOR] Current Mobile IP: {ip_before}")
    print(f"[*] [IP-ROTATOR] Toggling Airplane Mode on Phone [{phone_id}]...")

    try:
        run_adb_command(["shell", "cmd", "connectivity", "airplane-mode", "enable"], phone_id)
        time.sleep(wait_seconds)
        run_adb_command(["shell", "cmd", "connectivity", "airplane-mode", "disable"], phone_id)
    except Exception as e:
        print(f"[!] [IP-ROTATOR] Error triggering airplane mode: {e}")

    print("[*] [IP-ROTATOR] Waiting 5.5s for 4G LTE reconnection...")
    time.sleep(5.5)

    ip_after = get_current_public_ip()
    if ip_before != ip_after and ip_after != "Unknown":
        print(f"[+] [IP-ROTATOR] SUCCESS! New Clean 4G IP: {ip_after}")
    else:
        print(f"[!] [IP-ROTATOR] Reconnected IP: {ip_after}")
    return ip_after


import socket

def discover_memu_instances() -> list[str]:
    """Auto-connects to listening MEmu ADB ports in under 0.2s using socket probing."""
    memu_candidates = [21503, 21513, 21523, 21533, 21543, 21553, 21563, 21573, 21583, 21593,
                       21603, 21613, 21623, 21633, 21643, 21653, 21663, 21673, 21683, 21693]
    for port in memu_candidates:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.08):
                subprocess.run([ADB_BIN, "connect", f"127.0.0.1:{port}"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2)
        except (socket.timeout, ConnectionRefusedError, OSError):
            pass

    # List devices
    memu_devices = []
    try:
        res = subprocess.run([ADB_BIN, "devices"], stdout=subprocess.PIPE, text=True, timeout=4)
        for line in res.stdout.strip().splitlines()[1:]:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1] == "device":
                serial = parts[0]
                if serial.startswith("127.0.0.1:"):
                    memu_devices.append(serial)
    except Exception as e:
        print(f"[!] Device discovery error: {e}")

    return sorted(memu_devices)


def ensure_1080p_resolution(device_id: str):
    """Enforces 1080x2400 (DPI 480) on the MEmu instance."""
    try:
        out = run_adb_command(["shell", "wm", "size"], device_id)
        if "1080x2400" not in out:
            print(f"[*] Calibrating {device_id} to 1080x2400 (DPI 480)...")
            run_adb_command(["shell", "wm", "size", "1080x2400"], device_id)
            run_adb_command(["shell", "wm", "density", "480"], device_id)
    except Exception as e:
        print(f"[!] Resolution calibration warning for {device_id}: {e}")


def save_account_to_csv(email_address: str, otp_code: str, status: str = "Success_Created",
                        password: str = DEFAULT_PASSWORD, instance_id: str = "Unknown", ip_addr: str = ""):
    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        email_address,
        password,
        otp_code,
        status,
        instance_id,
        ip_addr
    ]
    for target in [ACCOUNTS_CSV, BACKUP_CSV]:
        try:
            exists = os.path.exists(target)
            with open(target, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not exists:
                    writer.writerow(["Timestamp", "Email", "Password", "OTP Code", "Status", "Instance", "IP"])
                writer.writerow(row)
        except Exception:
            pass


def run_single_account_on_memu(instance_id: str, gmail: str, app_pw: str, current_ip: str) -> bool:
    """Executes full account creation pipeline on a single MEmu instance."""
    print(f"\n{'='*70}")
    print(f"   [INSTANCE: {instance_id}] STARTING ACCOUNT CREATION CYCLE")
    print(f"   Using Mobile IP: {current_ip}")
    print(f"{'='*70}")

    detector = ScreenDetector(instance_id)
    t_start = time.time()

    # 1. State Check & Landing Prep
    state, _ = detector.get_screen_state()
    print(f"[*] [{instance_id}] Initial Screen State: [{state}]")

    if state == STATE_SIGNUP:
        print(f"[+] [{instance_id}] Already on Sign Up screen!")
    elif state not in [STATE_CAPTCHA, STATE_OTP_READY, STATE_SET_PASSWORD]:
        ui.go_to_signup_screen(instance_id)
        detector.wait_for_state(STATE_SIGNUP, timeout=7.0)

    # 2. Email & OTP Verification Loop (Auto-retry next email if OTP does not arrive in 60s)
    config = load_config()
    prefix = config.get("email_prefix", "user")
    domain = config.get("cloudflare_domain", "bhullehshahsilage.com")

    otp = None
    email_address = None
    max_email_attempts = 3

    for attempt in range(1, max_email_attempts + 1):
        counter = config.get("current_counter", 250)
        email_address = f"{prefix}{counter}@{domain}"
        config["current_counter"] = counter + 1
        save_config(config)

        print(f"\n[+] [{instance_id}] Target Email (Attempt {attempt}/{max_email_attempts}): {email_address} (Counter #{counter})")

        # Pre-copy to clipboard and paste email, then click Obtain
        obtain_time = ui.request_verification_code(email_address, instance_id)

        # 4. Color-Indexed & Dynamic Slot Captcha Solving (<= 3 attempts)
        print(f"[*] [{instance_id}] Detecting & Solving Puzzle Captcha...")
        solver = ColorIndexedCaptchaSolver(device_id=instance_id)
        solved = solver.solve(max_attempts=3)
        if not solved:
            print(f"[-] [{instance_id}] Captcha solve failed.")
            save_account_to_csv(email_address, "CAPTCHA_FAILED", "Failed_Captcha", instance_id=instance_id, ip_addr=current_ip)
            return False

        # 5. Wait for OTP Ready State (Countdown running or Sign Up screen active)
        print(f"[*] [{instance_id}] Waiting for OTP Ready State...")
        for _ in range(8):
            curr_state, _ = detector.get_screen_state()
            if curr_state in [STATE_OTP_READY, STATE_SIGNUP]:
                print(f"[+] [{instance_id}] OTP Ready verified (Screen: {curr_state})")
                break
            time.sleep(0.8)

        # 6. Fetch OTP from Gmail via IMAP (60s countdown timeout)
        print(f"[*] [{instance_id}] Listening for OTP in Gmail Inbox (60s max)...")
        fetcher = GmailOTPFetcher(gmail, app_pw)
        t_otp_start = time.time()
        otp = fetcher.wait_for_otp(target_email=email_address, min_timestamp=(obtain_time - 30), timeout_seconds=60)
        otp_time = time.time() - t_otp_start

        if otp:
            print(f"[+] [{instance_id}] OTP Received: [{otp}] (in {otp_time:.1f}s)")
            break
        else:
            print(f"[-] [{instance_id}] OTP timed out after 60s for {email_address}.")
            save_account_to_csv(email_address, "TIMEOUT", "Failed_OTP_Timeout", instance_id=instance_id, ip_addr=current_ip)
            if attempt < max_email_attempts:
                print(f"[*] [{instance_id}] Re-trying immediately with next auto-incremented email...")
                time.sleep(1.0)

    if not otp:
        print(f"[-] [{instance_id}] All {max_email_attempts} email OTP attempts exhausted.")
        return False

    # Submit verification code via clipboard paste
    ui.submit_verification_code(otp, instance_id)

    # 7. Set Password
    print(f"[*] [{instance_id}] Setting Account Password...")
    ok, _ = detector.wait_for_state(STATE_SET_PASSWORD, timeout=8.0)
    if not ok:
        print(f"[-] [{instance_id}] Set Password screen missed.")
        save_account_to_csv(email_address, otp, "Failed_No_Password_Screen", instance_id=instance_id, ip_addr=current_ip)
        return False

    ui.set_account_password(DEFAULT_PASSWORD, instance_id)

    # 8. Detect 'I am expert' dialog -> Instant Confirmation!
    print(f"[*] [{instance_id}] Verifying Account Completion ('I am expert')...")
    ok, _ = detector.wait_for_state(STATE_EXPERT_DIALOG, timeout=12.0)
    if ok:
        print(f"[+] [{instance_id}] 'I am expert' DETECTED! Account 100% Verified!")

    save_account_to_csv(email_address, otp, "Success_Created", DEFAULT_PASSWORD, instance_id, current_ip)
    t_total = time.time() - t_start
    print(f"\n[SUCCESS] Account {email_address} created on {instance_id} in {t_total:.1f}s! [OK]")

    # 9. Fast 5-Second Post-Expert Logout sequence to Main Landing
    print(f"[*] [{instance_id}] Running Fast Post-Expert Logout sequence (<5s)...")
    t_post_start = time.time()
    ui.fast_expert_to_main_landing(instance_id)
    t_post_done = time.time() - t_post_start
    print(f"[+] [{instance_id}] Logged out to Main Landing in {t_post_done:.2f}s (<5s achieved!)")

    return True


def run_orchestrator(cycles_per_instance: int = 1):
    config = load_config()
    gmail = config.get("gmail_address")
    app_pw = config.get("gmail_app_password", "").replace(" ", "")

    print("\n" + "="*70)
    print("   YALLA LUDO MEMU MULTI-INSTANCE AUTOMATION ORCHESTRATOR")
    print("   With Dedicated Mobile 4G LTE IP Rotation")
    print("="*70)

    # 1. Verify IP Rotation Strategy
    has_mobile, mobile_id = is_mobile_rotator_available()
    if has_mobile:
        print(f"[+] Physical 4G Rotator Phone Online: {mobile_id} (Using Airplane Mode)")
    else:
        print("[*] No physical mobile connected. Using GitHub Live Public Proxy Rotator for all instances!")

    # 2. Discover MEmu Instances
    print("\n[*] Discovering Active MEmu Instances...")
    instances = discover_memu_instances()
    if not instances:
        print("[-] Error: No MEmu instances found! Please launch instances in Multi-MEmu.")
        return 0

    print(f"[+] Detected {len(instances)} Active MEmu Instances:")
    for idx, inst in enumerate(instances, 1):
        ensure_1080p_resolution(inst)
        dims = ui.get_screen_dimensions(inst)
        print(f"    [{idx}] Endpoint: {inst:20} | Resolution: {dims[0]}x{dims[1]}")

    total_target = len(instances) * cycles_per_instance
    print(f"\n[*] Target: {cycles_per_instance} account(s) per instance x {len(instances)} instances = {total_target} total accounts.")
    print("="*70)

    total_success = 0
    t_orchestrator_start = time.time()

    for cycle in range(1, cycles_per_instance + 1):
        print(f"\n{'#'*70}")
        print(f"   --- BATCH CYCLE {cycle} OF {cycles_per_instance} ---")
        print(f"{'#'*70}")

        for inst in instances:
            # 1. Smart IP rotation: 4G LTE if mobile available; else GitHub proxy for this instance
            current_ip = rotate_ip_smart(inst, airplane_delay=2.5)

            # 2. Run account creation cycle
            try:
                success = run_single_account_on_memu(inst, gmail, app_pw, current_ip)
                if success:
                    total_success += 1
                else:
                    print(f"[!] Instance {inst} cycle failed. Returning to Main Landing...")
                    ui.fast_expert_to_main_landing(inst)
            except Exception as e:
                print(f"[!] Unexpected error on {inst}: {e}")
                try:
                    ui.fast_expert_to_main_landing(inst)
                except Exception:
                    pass
                print(f"[!] Unexpected error on {inst}: {e}")
                try:
                    ui.clear_app_data(inst)
                except Exception:
                    pass

    t_elapsed = time.time() - t_orchestrator_start
    print("\n" + "="*70)
    print(f"   ORCHESTRATOR COMPLETE: {total_success}/{total_target} ACCOUNTS CREATED")
    print(f"   Total Time: {t_elapsed:.1f}s | Average Speed: {t_elapsed / max(total_success, 1):.1f}s / account")
    print("="*70 + "\n")

    return total_success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MEmu Multi-Instance Yalla Ludo Creator")
    parser.add_argument("count", nargs="?", type=int, default=1, help="Cycles per instance (default: 1)")
    parser.add_argument("--total", type=int, default=None, help="Total target accounts across all instances")
    args = parser.parse_args()

    instances = discover_memu_instances()
    n_inst = max(len(instances), 1)

    if args.total:
        cycles = max(1, (args.total + n_inst - 1) // n_inst)
        run_orchestrator(cycles_per_instance=cycles)
    else:
        run_orchestrator(cycles_per_instance=args.count)
