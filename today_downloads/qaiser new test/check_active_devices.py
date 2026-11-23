"""
================================================================================
YALLA LUDO - ACTIVE DEVICES & MEMU INSTANCES CHECKER (check_active_devices.py)
================================================================================
Checks all connected MEmu instances, their connection status, resolution,
and whether Yalla Ludo is currently active.
================================================================================
"""

import os
import subprocess
import sys
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)

ADB_BIN = os.path.join(PARENT_DIR, "platform-tools", "adb.exe")
if not os.path.exists(ADB_BIN):
    ADB_BIN = "adb"


def run_cmd(cmd: list, timeout: float = 5.0) -> str:
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return res.stdout.decode("utf-8", errors="ignore")
    except Exception as e:
        return ""


def get_all_devices():
    out = run_cmd([ADB_BIN, "devices", "-l"])
    lines = out.strip().splitlines()
    
    online = []
    offline = []
    unauthorized = []
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            dev_id = parts[0]
            status = parts[1]
            extra = " ".join(parts[2:]) if len(parts) > 2 else ""
            if status == "device":
                online.append((dev_id, extra))
            elif status == "offline":
                offline.append((dev_id, extra))
            else:
                unauthorized.append((dev_id, status))
                
    return online, offline, unauthorized


def check_instance_details(dev_id: str):
    # Check screen size
    size_out = run_cmd([ADB_BIN, "-s", dev_id, "shell", "wm", "size"], timeout=3.0)
    size = "Unknown"
    for s in size_out.splitlines():
        if "Physical size:" in s:
            size = s.split("Physical size:")[-1].strip()
            break
            
    # Check if Yalla Ludo is in foreground
    focus_out = run_cmd([ADB_BIN, "-s", dev_id, "shell", "dumpsys", "window", "windows"], timeout=3.0)
    yalla_running = False
    if "com.yalla.yallagames" in focus_out:
        yalla_running = True
        
    return {
        "device_id": dev_id,
        "resolution": size,
        "yalla_running": yalla_running
    }


def main():
    print("\n" + "="*75)
    print("      YALLA LUDO AUTOMATION - ACTIVE MEmu INSTANCE CHECKER")
    print(f"      ADB Path: {ADB_BIN}")
    print("="*75)

    online, offline, unauthorized = get_all_devices()
    
    print(f"\n[+] Total Connected Online Instances : {len(online)}")
    print(f"[-] Total Offline Instances          : {len(offline)}")
    if unauthorized:
        print(f"[!] Unauthorized Instances           : {len(unauthorized)}")
    print("-" * 75)

    if not online and not offline:
        print("[!] No devices found. Please make sure MEmu instances are started.")
        print("    Tip: You can start MEmu from Multi-MEmu on your Desktop.")
        print("="*75 + "\n")
        return

    print(f"{'#':<3} | {'Device ID (IP:Port)':<22} | {'Resolution':<12} | {'Yalla Ludo App Status':<20}")
    print("-" * 75)

    for idx, (dev_id, extra) in enumerate(online, 1):
        info = check_instance_details(dev_id)
        yalla_status = "[RUNNING / ACTIVE]" if info["yalla_running"] else "[Not Active / Lobby]"
        res = info["resolution"]
        print(f"{idx:<3} | {dev_id:<22} | {res:<12} | {yalla_status:<20}")

    if offline:
        print("\n" + "-"*75)
        print("OFFLINE INSTANCES (Not ready for ADB commands):")
        for idx, (dev_id, extra) in enumerate(offline, 1):
            print(f"  [-] {idx}. {dev_id} (offline)")

    print("=" * 75)
    print(f"[OK] Ready to run automation across {len(online)} online instance(s)!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
