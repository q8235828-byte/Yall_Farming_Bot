import subprocess
from airplane_mode import ADB_BIN

try:
    devices = subprocess.check_output([ADB_BIN, "devices"]).decode("utf-8")
    print("ADB Devices:\n", devices)
except Exception as e:
    print("Error getting devices:", e)
