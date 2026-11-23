import time, subprocess
import yalla_ui_automator as ui
from airplane_mode import ADB_BIN

device_id = "127.0.0.1:21623"
otp = "149800"
password = "LudoPass#2026@"

print(f"[*] Submitting verification code: {otp}...")
ui.submit_verification_code(otp, device_id)

time.sleep(2.0)

# Check if Password screen appeared
print(f"[*] Setting password: {password}...")
ui.set_account_password(password, device_id)

time.sleep(2.0)

# Now on Game Lobby / Expert screen -> Execute 5-second Logout!
t_logout = time.time()
print("[*] Executing Fast Expert -> Gear -> Log Out sequence...")
ui.fast_expert_to_main_landing(device_id)
print(f"[SUCCESS] 5-Second Logout completed in {time.time() - t_logout:.2f}s!")

# Save to CSV
import datetime
ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
row = f"{ts},user530@bhullehshahsilage.com,{password},{otp},Success_Created,127.0.0.1:21623,Broadband\n"
with open("created_accounts.csv", "a", encoding="utf-8") as f:
    f.write(row)
print("[+] Recorded user530 in created_accounts.csv!")
