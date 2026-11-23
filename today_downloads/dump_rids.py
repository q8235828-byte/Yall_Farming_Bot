import subprocess
import re
import os

ADB = r"c:\Users\admin\codebase\today_downloads\platform-tools\adb.exe"
DEV = "127.0.0.1:21623"

subprocess.run([ADB, "-s", DEV, "shell", "input", "keyevent", "224"])
subprocess.run([ADB, "-s", DEV, "shell", "uiautomator", "dump", "/sdcard/t.xml"], timeout=8)
out = subprocess.check_output([ADB, "-s", DEV, "shell", "cat", "/sdcard/t.xml"], text=True, errors="replace")
rids = re.findall(r'resource-id="([^"]+)"', out)
texts = re.findall(r'text="([^"]+)"', out)
bounds = re.findall(r'bounds="([^"]+)"', out)
print("Unique RIDs:")
for r in sorted(set(rids)):
    if "yalla" in r:
        print(" ", r)

print("Texts:")
for t in texts:
    if t.strip():
        print("  text:", t)
