import subprocess, re, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
xml = subprocess.check_output(['platform-tools\\adb.exe', '-s', '127.0.0.1:21623', 'shell', 'cat', '/sdcard/c_wait.xml']).decode('utf-8', errors='replace')
for line in xml.split('><'):
    bounds_m = re.search(r'bounds="([^"]+)"', line)
    text_m = re.search(r'text="([^"]*)"', line)
    res_m = re.search(r'resource-id="([^"]*)"', line)
    t = text_m.group(1) if text_m else ''
    b = bounds_m.group(1) if bounds_m else ''
    r = res_m.group(1) if res_m else ''
    if t or "btn" in r or "bt_" in r or "et_" in r:
        print(f"{b:25} | {r:35} | {t}")
