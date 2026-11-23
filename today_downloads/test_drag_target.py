import time, subprocess
from airplane_mode import ADB_BIN

device_id = "127.0.0.1:21623"
start_x, start_y = 217, 810
target_x, target_y = 410, 810
duration = 650

print(f"[*] Executing draganddrop from ({start_x}, {start_y}) to ({target_x}, {target_y}) in {duration}ms...")
cmd = [ADB_BIN, "-s", device_id, "shell", "input", "draganddrop", str(start_x), str(start_y), str(target_x), str(target_y), str(duration)]
subprocess.run(cmd)

time.sleep(2)

# Check UI hierarchy to see if captcha closed
res = subprocess.check_output([ADB_BIN, "-s", device_id, "shell", "uiautomator", "dump", "/sdcard/after_solve.xml"])
xml = subprocess.check_output([ADB_BIN, "-s", device_id, "shell", "cat", "/sdcard/after_solve.xml"]).decode("utf-8")

if "Slide to complete the puzzle" in xml:
    print("[-] Puzzle still on screen! Checking status...")
    if "Please try again" in xml:
        print("    Status: 'Please try again'")
    else:
        print("    Status: Puzzle not solved or reset.")
else:
    print("[SUCCESS] Puzzle SOLVED! Captcha dialog closed!")

# Check if countdown timer appeared
import re
for m in re.finditer(r'text="([0-9]+s|Obtain)"', xml):
    print("    Verification button/timer state:", m.group(0))
