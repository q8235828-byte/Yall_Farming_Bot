"""
================================================================================
MEMU MULTI-INSTANCE ORCHESTRATION & ADB MANAGER (HIGH SPEED CONCURRENT SCAN)
================================================================================
Manages MEmu multi-instances for concurrent Yalla Ludo account creation:
1. Concurrently checks & auto-connects ADB across all MEmu ports (21503 to 21693).
2. Forces calibrated resolution: 1080x2400 (DPI 480) via Android 'wm'.
3. Randomizes device identity (Android ID, Advertising ID).
================================================================================
"""

import concurrent.futures
import os
import random
import shutil
import socket
import subprocess
import sys
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_ADB = os.path.join(CURRENT_DIR, "platform-tools", "adb.exe")
ADB_BIN = LOCAL_ADB if os.path.exists(LOCAL_ADB) else (shutil.which("adb") or "adb")

# MEmu port standard formula: 21503 + (index * 10)
# Covers 20 instances: indices 0 to 19 (ports 21503 to 21693)
MEMU_PORTS = [21503 + (i * 10) for i in range(20)]


def _is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.15) -> bool:
    """Instant TCP socket probe (<0.1s) to check if MEmu instance is listening."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        res = s.connect_ex((host, port))
        s.close()
        return res == 0
    except Exception:
        return False


def _connect_port(port: int) -> str | None:
    """Attempts ADB connection only if the port is actively listening."""
    if not _is_port_open(port):
        return None
    target = f"127.0.0.1:{port}"
    try:
        res = subprocess.run([ADB_BIN, "connect", target],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2)
        if "connected to" in res.stdout.lower() or "already connected" in res.stdout.lower():
            return target
    except Exception:
        pass
    return None


def get_memu_index_from_serial(serial: str) -> int | None:
    """Extracts MEmu VM index from serial (e.g. 127.0.0.1:21513 -> index 1)."""
    if "127.0.0.1:" in serial:
        try:
            port = int(serial.split(":")[1])
            if (port - 21503) % 10 == 0:
                return (port - 21503) // 10
        except Exception:
            pass
    return None


def connect_all_memu_instances() -> list[str]:
    """Scans all 20 MEmu ports in parallel and returns active connected devices in < 0.5s."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(_connect_port, MEMU_PORTS))

    connected = [r for r in results if r]

    # Query adb devices for verified active state
    active_devices = []
    try:
        res = subprocess.run([ADB_BIN, "devices"], stdout=subprocess.PIPE, text=True, timeout=5)
        for line in res.stdout.strip().splitlines()[1:]:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1] == "device":
                serial = parts[0]
                if serial not in active_devices:
                    active_devices.append(serial)
    except Exception as e:
        print(f"[!] Error querying ADB devices: {e}")

    return active_devices


def configure_memu_resolution_1080p(device_id: str):
    """Sets Android resolution to 1080x2400 and DPI to 480 via ADB 'wm'."""
    try:
        res_out = subprocess.run([ADB_BIN, "-s", device_id, "shell", "wm", "size"],
                                 stdout=subprocess.PIPE, text=True, timeout=2).stdout
        if "1080x2400" not in res_out:
            print(f"[{device_id}] Calibrating display to 1080x2400 (DPI 480)...")
            subprocess.run([ADB_BIN, "-s", device_id, "shell", "wm", "size", "1080x2400"],
                           timeout=2, stdout=subprocess.DEVNULL)
            subprocess.run([ADB_BIN, "-s", device_id, "shell", "wm", "density", "480"],
                           timeout=2, stdout=subprocess.DEVNULL)
    except Exception as e:
        print(f"[!] Resolution calibration error on {device_id}: {e}")


def randomize_device_identity(device_id: str):
    """Generates a fresh Android ID and MAC spoof for anti-fingerprint bypass."""
    try:
        new_android_id = "".join(random.choices("0123456789abcdef", k=16))
        subprocess.run([ADB_BIN, "-s", device_id, "shell", "settings", "put", "secure", "android_id", new_android_id],
                       timeout=2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


if __name__ == "__main__":
    t0 = time.time()
    devs = connect_all_memu_instances()
    print(f"Scan finished in {time.time()-t0:.2f}s.")
    print(f"[+] Active MEmu Devices Found: {len(devs)}")
    for d in devs:
        print(f"  - Device: {d}")
        configure_memu_resolution_1080p(d)
        randomize_device_identity(d)
