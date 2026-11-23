"""
================================================================================
YALLA LUDO HIGH-SPEED CONCURRENT MULTI-DEVICE / MEMU 20-INSTANCE ORCHESTRATOR
================================================================================
Features:
- Automatic MEmu 20-Instance Discovery (Ports 21503 - 21693) + USB ADB Devices.
- Automatic 1080x2400 (DPI 480) Display Calibration across all instances.
- GitHub Live Rotating Proxy Pool (monosans / TheSpeedX / roosterkid).
- Dynamic IP Rotation & Android ID / Device Fingerprint Randomization.
- Concurrent Multi-Worker Execution: Each instance runs in its own worker thread.
- Thread-Safe Atomic Email Counter & CSV Logging.
- Independent IMAP OTP Extraction & Resolution-Adaptive Captcha Solving.
================================================================================
"""

import concurrent.futures
import csv
from datetime import datetime
import json
import os
import subprocess
import sys
import threading
import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from airplane_mode import ADB_BIN, get_device_port, toggle_airplane_mode
from captcha_solver import IntelligentCaptchaSolver
from otp_fetcher import GmailOTPFetcher
from screen_detector import (
    ScreenDetector,
    STATE_MAIN_LANDING,
    STATE_SIGNUP,
    STATE_CAPTCHA,
    STATE_OTP_READY,
    STATE_SET_PASSWORD,
    STATE_EXPERT_DIALOG,
)
import yalla_ui_automator as ui
import yalla_creator_fast as yf

# MEmu & GitHub Rotating Proxy Integrations
from memu_manager import (
    connect_all_memu_instances,
    configure_memu_resolution_1080p,
    randomize_device_identity,
    get_memu_index_from_serial,
)
from github_proxy_rotator import GitHubProxyRotator

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
ACCOUNTS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "created_accounts.csv")
BACKUP_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "created_accounts_backup.csv")
DEFAULT_PASSWORD = "Yalla#2026@Pass"
PACKAGE_NAME = "com.yalla.yallagames"

counter_lock = threading.Lock()
csv_lock = threading.Lock()
print_lock = threading.Lock()

# Initialize global proxy rotator from GitHub sources
proxy_rotator = GitHubProxyRotator(min_pool_size=30)


def log_worker(device_id: str, message: str):
    """Thread-safe clean prefixed worker logging."""
    with print_lock:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{device_id}] {message}", flush=True)


def is_memu_device(device_id: str) -> bool:
    """Returns True if device is a MEmu virtual instance."""
    return "127.0.0.1:" in device_id or "emulator-" in device_id


def rotate_ip_and_identity(device_id: str, air_delay: float):
    """Rotates IP via GitHub live proxy for MEmu or toggles Airplane Mode for mobile."""
    if is_memu_device(device_id):
        log_worker(device_id, "Rotating IP via GitHub Proxy Pool & Randomizing Device Identity...")
        proxy = proxy_rotator.rotate_device_ip(ADB_BIN, device_id)
        randomize_device_identity(device_id)
        return proxy
    else:
        log_worker(device_id, "Rotating IP via Cellular Airplane Mode...")
        toggle_airplane_mode(air_delay, device_id)
        return "mobile_airplane"


def discover_connected_devices() -> list[str]:
    """Scans all MEmu instances (20 ports) and USB ADB ports, calibrating resolution."""
    detected = []

    # 1. Connect and detect all MEmu instances
    memu_devs = connect_all_memu_instances()
    for d in memu_devs:
        if d not in detected:
            detected.append(d)
            configure_memu_resolution_1080p(d)

    # 2. Check standard USB ADB ports (5038, 5037, 5039)
    for port in [5038, 5037, 5039]:
        try:
            res = subprocess.run([ADB_BIN, "-P", str(port), "devices"], stdout=subprocess.PIPE, text=True, timeout=2)
            for line in res.stdout.strip().splitlines()[1:]:
                parts = line.strip().split()
                if len(parts) >= 2 and parts[1] == "device":
                    serial = parts[0]
                    if serial not in detected:
                        detected.append(serial)
        except Exception:
            pass

    return detected


def get_next_email_thread_safe(config: dict) -> str:
    """Atomically increments current_counter in config.json under lock."""
    with counter_lock:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        prefix = cfg.get("email_prefix", "user")
        counter = cfg.get("current_counter", 250)
        domain = cfg.get("cloudflare_domain", "bhullehshahsilage.com")
        email_address = f"{prefix}{counter}@{domain}"
        cfg["current_counter"] = counter + 1
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        return email_address


def save_account_to_csv_thread_safe(email_address: str, otp_code: str, status: str = "Success_Created", password: str = DEFAULT_PASSWORD, device_id: str = "Unknown"):
    """Thread-safe CSV append under lock with fallback."""
    with csv_lock:
        row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email_address, password, otp_code, status, device_id]
        for target_path in [ACCOUNTS_CSV, BACKUP_CSV]:
            try:
                file_exists = os.path.exists(target_path)
                with open(target_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(["Timestamp", "Email", "Password", "OTP Code", "Status", "Device"])
                    writer.writerow(row)
                return
            except PermissionError:
                continue
            except Exception:
                pass


def run_single_account_on_device(device_id: str, gmail: str, app_pw: str, air_delay: float) -> bool:
    """Executes full account creation pipeline on a specific mobile / MEmu device."""
    detector = ScreenDetector(device_id)
    t_start = time.time()

    log_worker(device_id, "Starting account creation cycle...")

    # 1. Zero-Wait Landing Detection & Prep
    state, _ = detector.get_screen_state()
    log_worker(device_id, f"Initial screen state: [{state}]")

    if state not in [STATE_SIGNUP, STATE_CAPTCHA, STATE_OTP_READY, STATE_SET_PASSWORD]:
        yf.ensure_ready_landing_screen(detector, device_id)
        yf.go_to_signup(device_id)
        ok, _ = detector.wait_for_state(STATE_SIGNUP, timeout=7.0)
        if not ok:
            log_worker(device_id, "Could not reach SIGNUP screen. Retrying landing...")
            ui.ensure_main_landing_page(device_id)
            yf.go_to_signup(device_id)
            detector.wait_for_state(STATE_SIGNUP, timeout=6.0)

    # 2. Thread-safe Email Acquisition
    email_address = get_next_email_thread_safe({})
    log_worker(device_id, f"Acquired email: {email_address}")

    # Enter Email & Tap Obtain
    obtain_time = ui.request_verification_code(email_address, device_id)

    # 3. Solve Captcha on this device's screen
    log_worker(device_id, "Detecting & Solving Captcha...")
    solver = IntelligentCaptchaSolver(device_id=device_id, max_attempts=15, attempts_per_round=5)
    if not solver.solve():
        log_worker(device_id, "Captcha resolution failed.")
        save_account_to_csv_thread_safe(email_address, "CAPTCHA_FAILED", status="Failed_Captcha", device_id=device_id)
        return False

    # 4. Wait for OTP Ready Countdown
    log_worker(device_id, "Waiting for OTP input countdown...")
    ok, _ = detector.wait_for_state(STATE_OTP_READY, timeout=10.0)
    if not ok:
        state, _ = detector.get_screen_state()
        if state != STATE_SIGNUP:
            log_worker(device_id, f"OTP Ready countdown did not appear (Current: {state}).")
            save_account_to_csv_thread_safe(email_address, "OTP_NOT_READY", status="Failed_OTP_Not_Ready", device_id=device_id)
            return False
        log_worker(device_id, "Sign up dialog active with OTP box, proceeding to listen for OTP...")

    # 5. Fetch OTP from Gmail
    log_worker(device_id, f"Listening to Gmail for OTP ({email_address})...")
    fetcher = GmailOTPFetcher(gmail, app_pw)
    t_otp_start = time.time()
    otp = fetcher.wait_for_otp(target_email=email_address, min_timestamp=(obtain_time - 30), timeout_seconds=90)
    otp_time = time.time() - t_otp_start
    if not otp:
        log_worker(device_id, "OTP wait timed out.")
        save_account_to_csv_thread_safe(email_address, "TIMEOUT", status="Failed_OTP_Timeout", device_id=device_id)
        return False

    log_worker(device_id, f"Fresh OTP received: {otp} (in {otp_time:.2f}s)")
    ui.submit_verification_code(otp, device_id)

    # 6. Set Password & Keyboard Dismiss
    log_worker(device_id, "Waiting for Set Password screen...")
    ok, _ = detector.wait_for_state(STATE_SET_PASSWORD, timeout=8.0)
    if not ok:
        log_worker(device_id, "Set Password screen was not detected.")
        save_account_to_csv_thread_safe(email_address, otp, status="Failed_No_Password_Screen", device_id=device_id)
        return False

    ui.set_account_password(DEFAULT_PASSWORD, device_id)

    # 7. As soon as 'I am expert' is detected -> Account is 100% verified -> WIPE DATA IMMEDIATELY!
    log_worker(device_id, "Detecting 'I am expert' dialog to trigger direct wipe...")
    ok, _ = detector.wait_for_state(STATE_EXPERT_DIALOG, timeout=12.0)
    if ok:
        log_worker(device_id, "'I am expert' DETECTED! Account 100% confirmed!")

    # Save to CSV immediately
    save_account_to_csv_thread_safe(email_address, otp, status="Success_Created", password=DEFAULT_PASSWORD, device_id=device_id)
    cycle_time = time.time() - t_start
    log_worker(device_id, f"SUCCESS! Account {email_address} created in {cycle_time:.1f}s [OK]")

    # 8. Instant Wipe & IP Rotation (GitHub Proxy for MEmu or Airplane Mode for Phone)
    log_worker(device_id, "Executing data wipe (pm clear) & IP rotation...")
    ui.clear_app_data(device_id)
    rotate_ip_and_identity(device_id, air_delay)

    # 9. Relaunch app & bypass to Main Landing
    log_worker(device_id, "Relaunching app to Main Landing for next cycle...")
    yf.ensure_ready_landing_screen(detector, device_id)
    return True


def worker_device_runner(device_id: str, accounts_per_device: int, gmail: str, app_pw: str, air_delay: float) -> int:
    """Worker thread dedicated to one specific connected mobile / MEmu device."""
    log_worker(device_id, f"Worker thread started. Target: {accounts_per_device} accounts.")
    successful = 0

    # Ensure device is calibrated to 1080x2400
    if is_memu_device(device_id):
        configure_memu_resolution_1080p(device_id)
        rotate_ip_and_identity(device_id, air_delay)

    for i in range(1, accounts_per_device + 1):
        log_worker(device_id, f"--- Cycle {i}/{accounts_per_device} (Completed: {successful}) ---")
        try:
            status = run_single_account_on_device(device_id, gmail, app_pw, air_delay)
            if status:
                successful += 1
                log_worker(device_id, f"Cycle {i}/{accounts_per_device} completed successfully!")
            else:
                log_worker(device_id, f"Cycle {i}/{accounts_per_device} failed. Resetting device state...")
                ui.clear_app_data(device_id)
                rotate_ip_and_identity(device_id, air_delay)
                yf.ensure_ready_landing_screen(ScreenDetector(device_id), device_id)
        except Exception as e:
            log_worker(device_id, f"Unexpected error in cycle {i}: {e}")
            try:
                ui.clear_app_data(device_id)
                rotate_ip_and_identity(device_id, air_delay)
            except Exception:
                pass

    log_worker(device_id, f"Worker finished: {successful}/{accounts_per_device} accounts created.")
    return successful


def run_all_devices_concurrently(accounts_per_device: int = 1):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    gmail = config.get("gmail_address")
    app_pw = config.get("gmail_app_password", "").replace(" ", "")
    air_delay = config.get("airplane_wait_seconds", 1.5)

    print("\n" + "="*70)
    print("   CONCURRENT MULTI-DEVICE / MEMU 20-INSTANCE YALLA CREATOR")
    print("="*70)

    devices = discover_connected_devices()
    print(f"[*] Detected {len(devices)} Connected Devices (MEmu / Mobile):")
    for idx, d in enumerate(devices, 1):
        dims = ui.get_screen_dimensions(d)
        port = get_device_port(d)
        dev_type = "MEmu Instance" if is_memu_device(d) else "Physical Phone"
        print(f"    [{idx}] Serial: {d:18} | Type: {dev_type:14} | Resolution: {dims[0]}x{dims[1]}")

    if not devices:
        print("[-] Error: No active Android or MEmu devices found.")
        print("    -> Tip: Launch your MEmu instances in Multi-MEmu, then re-run!")
        return 0

    # Pre-warm GitHub proxy pool if running on MEmu instances
    has_memu = any(is_memu_device(d) for d in devices)
    if has_memu:
        print("\n[*] Initializing GitHub Live Proxy Pool...")
        proxy_rotator.refresh_working_pool(target_count=max(20, len(devices) * 2))

    total_target = len(devices) * accounts_per_device
    print(f"\n[*] Launching {len(devices)} parallel worker threads ({accounts_per_device} accounts/device). Target Total: {total_target} accounts.")
    print("="*70 + "\n")

    t_batch_start = time.time()
    total_successful = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(devices)) as executor:
        futures = {
            executor.submit(worker_device_runner, dev, accounts_per_device, gmail, app_pw, air_delay): dev
            for dev in devices
        }

        for future in concurrent.futures.as_completed(futures):
            dev = futures[future]
            try:
                count = future.result()
                total_successful += count
            except Exception as e:
                print(f"[!] Worker exception for device {dev}: {e}")

    t_total = time.time() - t_batch_start
    print("\n" + "="*70)
    print(f"   CONCURRENT BATCH FINISHED: {total_successful}/{total_target} ACCOUNTS CREATED")
    print(f"   Total Time: {t_total:.1f}s | Effective Speed: {t_total / max(total_successful, 1):.1f}s / account")
    print("="*70 + "\n")

    # Clean up proxies on exit
    for d in devices:
        if is_memu_device(d):
            proxy_rotator.clear_device_proxy(ADB_BIN, d)

    # Automatically run sheet retry for any failed accounts
    try:
        from retry_failed_accounts import run_sheet_retry
        print("[*] Checking sheet for failed accounts to auto-retry...")
        retried_count = run_sheet_retry()
        if retried_count > 0:
            print(f"[+] Auto-retry complete: Successfully recovered {retried_count} account(s) in sheet!")
    except Exception as e:
        print(f"[!] Warning: Sheet auto-retry encountered an error: {e}")

    return total_successful


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Yalla Ludo Concurrent Multi-Device / MEmu 20-Instance Creator")
    parser.add_argument("count", nargs="?", type=int, default=None, help="Accounts to create (per device or total)")
    parser.add_argument("--total", type=int, default=None, help="Total target accounts across all devices")
    args = parser.parse_args()

    devs = discover_connected_devices()
    num_devs = max(len(devs), 1)

    if args.total:
        per_dev = max(1, (args.total + num_devs - 1) // num_devs)
        print(f"[*] Target Total: {args.total} accounts across {num_devs} devices (~{per_dev} accounts/device)")
        run_all_devices_concurrently(accounts_per_device=per_dev)
    elif args.count:
        if args.count >= 20:
            per_dev = max(1, (args.count + num_devs - 1) // num_devs)
            print(f"[*] Distributing total {args.count} accounts across {num_devs} devices ({per_dev} accounts/device)...")
            run_all_devices_concurrently(accounts_per_device=per_dev)
        else:
            run_all_devices_concurrently(accounts_per_device=args.count)
    else:
        run_all_devices_concurrently(accounts_per_device=1)
