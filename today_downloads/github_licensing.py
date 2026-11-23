import json
import os
import platform
import urllib.request
from license_client import get_machine_hwid, get_realtime_public_ip

# Configuration for GitHub-based licensing fallback
GITHUB_OWNER = "qaisarfaryad" # Replace with your GitHub Username
GITHUB_REPO = "yalla-license-db" # Replace with your private/public GitHub Repo
GITHUB_BRANCH = "main"
GITHUB_TOKEN = "" # Optional: GitHub Personal Access Token (for writing telemetry back)


def verify_license_github(license_key: str) -> dict:
    """
    Validates license directly against a GitHub Raw JSON repository.
    URL format: https://raw.githubusercontent.com/{owner}/{repo}/{branch}/licenses.json
    """
    hwid = get_machine_hwid()
    client_ip = get_realtime_public_ip()
    hostname = platform.node()

    url = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/licenses.json"

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'YallaStudioGithubClient/2.4'})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            licenses = data.get("licenses", {})

            if license_key not in licenses:
                return {"valid": False, "message": "License key not found in GitHub registry.", "hwid": hwid}

            rec = licenses[license_key]
            if rec.get("status") != "active":
                return {"valid": False, "message": f"License is {rec.get('status')}.", "hwid": hwid}

            bound = rec.get("bound_hwid")
            if bound and bound != hwid:
                return {
                    "valid": False,
                    "message": "HWID Mismatch! Key is bound to another laptop.",
                    "hwid": hwid
                }

            # Optional: Log Realtime IP to GitHub Telemetry Issue/Webhook
            report_telemetry_to_github(license_key, hwid, client_ip, hostname)

            return {
                "valid": True,
                "customer_name": rec.get("customer", "Customer"),
                "expires_at": rec.get("expires_at"),
                "bound_hwid": bound or hwid,
                "client_ip": client_ip,
                "message": "License verified via GitHub Cloud."
            }
    except Exception as e:
        return {"valid": False, "message": f"GitHub Registry Notice: {str(e)}", "hwid": hwid}


def report_telemetry_to_github(license_key: str, hwid: str, client_ip: str, hostname: str):
    """
    Posts client telemetry (real-time IP, hostname, HWID) to a GitHub Repo Issue or Webhook.
    """
    if not GITHUB_TOKEN:
        return # Skip if token not configured

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues"
    body = {
        "title": f"Telemetry: {hostname} ({client_ip})",
        "body": f"**License Key:** `{license_key}`\n**Client IP:** `{client_ip}`\n**Machine HWID:** `{hwid}`\n**OS Hostname:** `{hostname}`"
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode('utf-8'),
            headers={
                'Authorization': f'token {GITHUB_TOKEN}',
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'YallaTelemetryReporter'
            },
            method='POST'
        )
        urllib.request.urlopen(req, timeout=3.0)
    except Exception:
        pass
