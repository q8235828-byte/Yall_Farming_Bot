import hashlib
import json
import os
import platform
import subprocess
import sys
import urllib.request
import uuid
from datetime import datetime

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CLOUDFLARE_URL = "https://yalla-licensing.q8235828.workers.dev"
PAGES_DEV_BUY_URL = "https://yalla-farming.pages.dev"
USER_HOME_LICENSE = os.path.join(os.path.expanduser("~"), ".yalla_license.json")


def get_machine_hwid() -> str:
    """Generates a hardware-bound Hardware ID (HWID) based on Motherboard, CPU, MAC."""
    raw = []
    try:
        cmd = 'powershell -NoProfile -Command "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID"'
        out = subprocess.check_output(cmd, shell=True).decode().strip()
        if out:
            raw.append(out)
    except Exception:
        pass

    try:
        cmd = 'powershell -NoProfile -Command "(Get-CimInstance -ClassName Win32_Processor).ProcessorId"'
        out = subprocess.check_output(cmd, shell=True).decode().strip()
        if out:
            raw.append(out)
    except Exception:
        pass

    raw.append(str(uuid.getnode()))
    raw.append(platform.node())
    comb = "||".join(raw)
    sha = hashlib.sha256(comb.encode("utf-8")).hexdigest().upper()
    return f"{sha[0:4]}-{sha[4:8]}-{sha[8:12]}-{sha[12:16]}"


def get_license_file_path() -> str:
    """Returns persistent license path, prioritizing app root directory and user home."""
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, ".license.json")
    return os.path.join(CURRENT_DIR, ".license.json")


def load_saved_license() -> dict:
    paths = [get_license_file_path(), USER_HOME_LICENSE, os.path.join(CURRENT_DIR, ".license.json")]
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data and data.get("license_key"):
                        return data
            except Exception:
                pass
    return {}


def save_license(data: dict):
    # Save to primary location
    primary = get_license_file_path()
    try:
        with open(primary, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

    # Also save to user home as persistent backup across exe moves
    try:
        with open(USER_HOME_LICENSE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def is_activated() -> tuple[bool, dict]:
    saved = load_saved_license()
    if not saved or not saved.get("license_key"):
        return False, {}

    current_hwid = get_machine_hwid()
    if saved.get("hwid") and saved.get("hwid") != current_hwid:
        return False, {"error": "HWID mismatch! Key is locked to another PC."}

    # Check expiry if present
    exp = saved.get("expires_at")
    if exp:
        try:
            if datetime.fromisoformat(exp.replace("Z", "+00:00")) < datetime.now(datetime.timezone.utc):
                return False, {"error": "License has expired. Please renew."}
        except Exception:
            pass

    return True, saved


def verify_and_activate(license_key: str, email: str = "", cloudflare_url: str = DEFAULT_CLOUDFLARE_URL) -> tuple[bool, dict]:
    license_key = license_key.strip()
    hwid = get_machine_hwid()

    # Master Developer / Admin Key
    if license_key.upper().startswith("MASTER-") or license_key == "YALLA-PRO-LIFETIME-2026":
        rec = {
            "license_key": license_key,
            "customer_name": email or "Licensed Pro Owner",
            "email": email,
            "hwid": hwid,
            "plan": "Enterprise Lifetime Pro ($1,000)",
            "activated_at": datetime.now().isoformat(),
            "expires_at": None,
            "status": "active"
        }
        save_license(rec)
        return True, rec

    payload = {
        "license_key": license_key,
        "email": email,
        "hwid": hwid,
        "hostname": platform.node(),
        "os_info": f"{platform.system()} {platform.release()}",
        "app_version": "2.5.0"
    }

    try:
        req = urllib.request.Request(
            f"{cloudflare_url}/api/verify",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "YallaFarmingStudio/2.5"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            if res_data.get("valid"):
                rec = {
                    "license_key": license_key,
                    "customer_name": res_data.get("customer_name") or email or "Valued Client",
                    "email": email,
                    "hwid": hwid,
                    "plan": res_data.get("plan") or "Enterprise Pro ($1,000)",
                    "activated_at": datetime.now().isoformat(),
                    "expires_at": res_data.get("expires_at"),
                    "status": "active"
                }
                save_license(rec)
                return True, rec
            else:
                return False, {"error": res_data.get("message") or "Invalid license key."}
    except Exception as e:
        # Check if already activated locally before network outage
        active, saved = is_activated()
        if active and saved.get("license_key") == license_key:
            return True, saved
        return False, {"error": f"Could not connect to Cloudflare licensing server: {e}"}
