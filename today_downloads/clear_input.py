import time
from airplane_mode import run_adb_command

dev = "34558213310005P"

# Tap near the far right of the field to place cursor at the end
run_adb_command(["shell", "input", "tap", "900", "666"], dev)
time.sleep(0.3)

# Move cursor to end just in case
run_adb_command(["shell", "input", "keyevent", "123"], dev)
time.sleep(0.3)

# Delete 70 characters
run_adb_command(["shell", "input", "keyevent"] + ["67"] * 70, dev)
time.sleep(0.5)

# Type clean email
run_adb_command(["shell", "input", "text", "user102@bhullehshahsilage.com"], dev)
time.sleep(0.5)

# Hide keyboard
run_adb_command(["shell", "input", "keyevent", "4"], dev)
print("Done clearing and typing!")
