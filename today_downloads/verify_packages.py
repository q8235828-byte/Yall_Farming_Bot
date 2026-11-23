import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import memu_manager

ADB = os.path.join(BASE_DIR, "platform-tools", "adb.exe")
CLIPPER_APK = os.path.join(BASE_DIR, "clipper.apk")

devices = memu_manager.connect_all_memu_instances()
print(f"=== Scanning {len(devices)} Connected Devices for Yalla Ludo & Clipper ===\n")

report = []
for dev in devices:
    # 1. Check Yalla Ludo
    yalla_res = subprocess.run([ADB, "-s", dev, "shell", "pm", "path", "com.yalla.yallagames"], capture_output=True, text=True)
    has_yalla = "package:" in yalla_res.stdout

    # 2. Check Clipper (both possible package names)
    clip_res = subprocess.run([ADB, "-s", dev, "shell", "pm", "path", "ca.zgrs.clipper"], capture_output=True, text=True)
    clip_pkg = "ca.zgrs.clipper" if "package:" in clip_res.stdout else None
    if not clip_pkg:
        clip_res2 = subprocess.run([ADB, "-s", dev, "shell", "pm", "path", "org.rohitst.clipper"], capture_output=True, text=True)
        if "package:" in clip_res2.stdout:
            clip_pkg = "org.rohitst.clipper"

    has_clipper = clip_pkg is not None
    y_str = "INSTALLED" if has_yalla else "MISSING"
    c_str = f"INSTALLED ({clip_pkg})" if has_clipper else "MISSING"
    y_mark = "[OK]" if has_yalla else "[X]"
    c_mark = "[OK]" if has_clipper else "[X]"

    report.append({"device": dev, "yalla": has_yalla, "clipper": has_clipper, "clip_pkg": clip_pkg})
    print(f"Device: {dev:17} | Yalla Ludo: {y_str:9} {y_mark} | Clipper: {c_str:22} {c_mark}")

missing_clipper = [r["device"] for r in report if not r["clipper"]]
missing_yalla = [r["device"] for r in report if not r["yalla"]]

print("\n" + "=" * 65)
print(f"Total Devices Checked: {len(devices)}")
print(f"Missing Yalla Ludo ({len(missing_yalla)}): {missing_yalla}")
print(f"Missing Clipper    ({len(missing_clipper)}): {missing_clipper}")
print("=" * 65)
