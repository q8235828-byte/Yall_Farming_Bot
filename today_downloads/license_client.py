import hashlib
import json
import os
import platform
import subprocess
import urllib.request
import uuid

LICENSE_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".license_cache.json")
DEFAULT_CLOUDFLARE_ENDPOINT = "https://yalla-licensing.workers.dev"


def get_machine_hwid() -> str:
    """
    Generates a unique Hardware ID (HWID) bound to this PC.
    Works on Windows 10 & 11 (using PowerShell CIM instance).
    """
    raw_components = []
    
    # Motherboard UUID via PowerShell
    try:
        cmd = 'powershell -NoProfile -Command "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID"'
        uuid_str = subprocess.check_output(cmd, shell=True).decode().strip()
        if uuid_str:
            raw_components.append(uuid_str)
    except Exception:
        pass

    # Processor ID via PowerShell
    try:
        cmd = 'powershell -NoProfile -Command "(Get-CimInstance -ClassName Win32_Processor).ProcessorId"'
        proc_str = subprocess.check_output(cmd, shell=True).decode().strip()
        if proc_str:
            raw_components.append(proc_str)
    except Exception:
        pass

    # MAC Address & Hostname fallback
    raw_components.append(str(uuid.getnode()))
    raw_components.append(platform.node())

    combined_str = "||".join(raw_components)
    sha = hashlib.sha256(combined_str.encode('utf-8')).hexdigest().upper()
    return f"{sha[0:4]}-{sha[4:8]}-{sha[8:12]}-{sha[12:16]}"


def get_realtime_public_ip() -> str:
    """Detects the client PC's real-time public IP address."""
    endpoints = [
        "https://api.ipify.org?format=json",
        "https://api.my-ip.io/v2/ip.json",
        "https://checkip.amazonaws.com"
    ]
    for url in endpoints:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3.5) as response:
                content = response.read().decode('utf-8').strip()
                if "{" in content:
                    data = json.loads(content)
                    return data.get("ip") or data.get("client_ip")
                return content
        except Exception:
            continue
    return "Unknown_IP"


def verify_license_online(license_key: str, worker_url: str = DEFAULT_CLOUDFLARE_ENDPOINT) -> dict:
    """
    Validates license against Cloudflare Worker API.
    Binds the license key to this PC's HWID and logs the real-time IP in Admin Dashboard.
    """
    hwid = get_machine_hwid()
    client_ip = get_realtime_public_ip()
    hostname = platform.node()
    os_info = f"{platform.system()} {platform.release()}"

    payload = {
        "license_key": license_key.strip(),
        "hwid": hwid,
        "hostname": hostname,
        "client_ip": client_ip,
        "os_info": os_info,
        "app_version": "2.4.0"
    }

    try:
        req = urllib.request.Request(
            f"{worker_url}/api/verify",
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'User-Agent': 'YallaStudioClient/2.4'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            res_data = json.loads(resp.read().decode('utf-8'))
            if res_data.get("valid"):
                save_license_cache(license_key, res_data)
            return res_data
    except Exception as e:
        cached = load_license_cache()
        if cached and cached.get("license_key") == license_key and cached.get("hwid") == hwid:
            return {
                "valid": True,
                "offline_mode": True,
                "message": "Valid (Cached Offline Validation)",
                "hwid": hwid
            }
        return {"valid": False, "message": f"License Server Notice: {str(e)}", "hwid": hwid}


def save_license_cache(license_key: str, verify_data: dict):
    data = {
        "license_key": license_key,
        "hwid": get_machine_hwid(),
        "expires_at": verify_data.get("expires_at"),
        "last_verified": verify_data.get("server_time")
    }
    try:
        with open(LICENSE_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def load_license_cache() -> dict | None:
    if os.path.exists(LICENSE_CACHE_FILE):
        try:
            with open(LICENSE_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


if __name__ == "__main__":
    print("="*50)
    print("  CLIENT HARDWARE ID & TELEMETRY DETECTOR")
    print("="*50)
    print(f"Machine HWID:       {get_machine_hwid()}")
    print(f"Realtime Public IP: {get_realtime_public_ip()}")
    print(f"Computer Hostname:  {platform.node()}")
    print(f"Operating System:   {platform.system()} {platform.release()}")
    print("="*50)
