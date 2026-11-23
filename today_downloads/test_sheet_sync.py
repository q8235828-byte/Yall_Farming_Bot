import subprocess, json, urllib.request, csv, io

WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbz_0cbU9GjM_FmvtqmVx7o27HLoVXUd_1EtcfvKfnFXvxauE7jvYhQfdCKwvzcaZ128/exec"
SHEET_EXPORT_URL = "https://docs.google.com/spreadsheets/d/1h2y1lr1WF5cOicHEIxd_26k695KZVP-ILCh36ML6Ngs/export?format=csv&gid=1485006795"

payload = {
    "email": "user221@bhullehshahsilage.com",
    "status": "Ready_For_Logout",
    "device_id": "127.0.0.1:21613",
    "golds_chest": "Yes",
    "free_rewards": "6/6",
    "total_coin": "5000"
}

print("[*] Sending POST update to Google Sheet Webhook...")
payload_json = json.dumps(payload)

# Use curl.exe which handles Google Apps Script 302 redirects with post data
cmd = [
    "curl.exe", "-L", "-s",
    "-H", "Content-Type: application/json",
    "-d", payload_json,
    WEBHOOK_URL
]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
print("[+] Webhook Response:", res.stdout.strip())

print("\n[*] Verifying live Google Sheet row for user221...")
req = urllib.request.Request(SHEET_EXPORT_URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as resp:
    data = resp.read().decode("utf-8", errors="ignore")

reader = csv.reader(io.StringIO(data))
rows = list(reader)
header = rows[0]
print("[+] Sheet Header:", header)
for i, r in enumerate(rows):
    if "user221" in str(r):
        print(f"[+] Row {i+1}:", r)
