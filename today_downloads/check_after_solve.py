import subprocess, re
from airplane_mode import ADB_BIN

xml = subprocess.check_output([ADB_BIN, '-s', '127.0.0.1:21623', 'shell', 'cat', '/sdcard/after_pwd_set.xml']).decode('utf-8')
for line in xml.split('><'):
    bounds_m = re.search(r'bounds="([^"]+)"', line)
    text_m = re.search(r'text="([^"]*)"', line)
    t = text_m.group(1) if text_m else ''
    b = bounds_m.group(1) if bounds_m else ''
    if t:
        print(f"{b:25} | {t}")
