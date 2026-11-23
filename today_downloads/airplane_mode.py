import os
import shutil
import subprocess
import sys
import time

# Auto-detect ADB path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_ADB = os.path.join(CURRENT_DIR, "platform-tools", "adb.exe")
ADB_BIN = LOCAL_ADB if os.path.exists(LOCAL_ADB) else (shutil.which("adb") or "adb")

_DEVICE_PORT_CACHE = {}


def get_device_port(device_id: str = None) -> int:
    """Auto-detects whether the device is hosted on port 5038, 5037, or 5039."""
    if not device_id:
        return 5037
    if device_id in _DEVICE_PORT_CACHE:
        return _DEVICE_PORT_CACHE[device_id]

    for port in [5038, 5037, 5039]:
        try:
            res = subprocess.run([ADB_BIN, "-P", str(port), "devices"], stdout=subprocess.PIPE, text=True, timeout=2)
            if device_id in res.stdout:
                _DEVICE_PORT_CACHE[device_id] = port
                return port
        except Exception:
            pass
    _DEVICE_PORT_CACHE[device_id] = 5037
    return 5037


def run_adb_command(cmd_args: list[str], device_id: str = None) -> str:
    """Runs an ADB command and returns stripped output."""
    full_cmd = [ADB_BIN]
    port = get_device_port(device_id)
    if port != 5037:
        full_cmd.extend(["-P", str(port)])
    if device_id:
        full_cmd.extend(["-s", device_id])
    full_cmd.extend(cmd_args)

    try:
        result = subprocess.run(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=True
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ADB Command Failed: {' '.join(full_cmd)}\nError: {e.stderr.strip()}")


def get_airplane_mode(device_id: str = None) -> bool:
    """
    Checks if Airplane Mode is currently enabled.
    Returns True if enabled, False if disabled.
    """
    output = run_adb_command(["shell", "cmd", "connectivity", "airplane-mode"], device_id)
    return "enabled" in output.lower()


def set_airplane_mode(enable: bool, device_id: str = None) -> bool:
    """
    Turns Airplane Mode ON (enable=True) or OFF (enable=False).
    """
    action = "enable" if enable else "disable"
    run_adb_command(["shell", "cmd", "connectivity", "airplane-mode", action], device_id)
    current_status = get_airplane_mode(device_id)
    status_text = "ON" if current_status else "OFF"
    print(f"[+] Airplane mode turned {status_text}.")
    return current_status


def toggle_airplane_mode(wait_seconds: float = 3.0, device_id: str = None):
    """
    Turns Airplane Mode ON, waits for specified seconds, then turns it OFF.
    Very useful for resetting cellular connection / rotating IP.
    """
    print(f"[*] Turning Airplane Mode ON...")
    set_airplane_mode(True, device_id)
    
    print(f"[*] Waiting for {wait_seconds} seconds...")
    time.sleep(wait_seconds)
    
    print(f"[*] Turning Airplane Mode OFF...")
    set_airplane_mode(False, device_id)
    print("[OK] Airplane Mode toggled successfully.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command in ("on", "enable", "1"):
            set_airplane_mode(True)
        elif command in ("off", "disable", "0"):
            set_airplane_mode(False)
        elif command in ("toggle", "cycle"):
            delay = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
            toggle_airplane_mode(delay)
        elif command in ("status", "check"):
            status = get_airplane_mode()
            print(f"Current Airplane Mode: {'ON' if status else 'OFF'}")
        else:
            print("Usage: python airplane_mode.py [on|off|toggle|status] [optional_delay_seconds]")
    else:
        # Default run: toggle test
        current = get_airplane_mode()
        print(f"Initial Status: {'ON' if current else 'OFF'}")
        print("Toggling Airplane Mode (ON -> wait 3s -> OFF)...")
        toggle_airplane_mode(3.0)
