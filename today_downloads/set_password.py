import time, subprocess
from yalla_ui_automator import copy_to_clipboard, paste_clipboard, tap
from airplane_mode import ADB_BIN

device_id = "127.0.0.1:21623"
password = "LudoPass#2026@"

print(f"[*] Setting password: {password}")
copy_to_clipboard(password, device_id)

# 1. Tap password field at (400, 223)
tap(400, 223, device_id, 0.3)

# 2. Paste password
paste_clipboard(device_id, 0.3)

# 3. Tap Confirm at (400, 1017)
tap(400, 1017, device_id, 1.5)

# 4. Dump UI hierarchy
subprocess.run([ADB_BIN, "-s", device_id, "shell", "uiautomator", "dump", "/sdcard/after_pwd_set.xml"])
xml = subprocess.check_output([ADB_BIN, "-s", device_id, "shell", "cat", "/sdcard/after_pwd_set.xml"]).decode("utf-8")

if "Password Requirements" in xml:
    print("[-] Still on Password dialog. Checking if password was accepted or needs different chars.")
else:
    print("[SUCCESS] Password accepted! Dialog dismissed!")

for line in xml.split("><"):
    if any(k in line for k in ["Account Center", "Bound", "user527", "Settings", "expert", "btn_link"]):
        print("  Found:", line[:120])
