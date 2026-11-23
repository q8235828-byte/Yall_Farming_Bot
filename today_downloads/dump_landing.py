import subprocess, re, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
subprocess.run(['platform-tools\\adb.exe', '-s', '127.0.0.1:21623', 'shell', 'uiautomator', 'dump', '/sdcard/w_landing.xml'])
xml = subprocess.check_output(['platform-tools\\adb.exe', '-s', '127.0.0.1:21623', 'shell', 'cat', '/sdcard/w_landing.xml']).decode('utf-8', errors='replace')
for line in xml.split('><'):
    bounds_m = re.search(r'bounds="([^"]+)"', line)
    text_m = re.search(r'text="([^"]*)"', line)
    res_m = re.search(r'resource-id="([^"]*)"', line)
    chk_m = re.search(r'checked="([^"]*)"', line)
    t = text_m.group(1) if text_m else ''
    b = bounds_m.group(1) if bounds_m else ''
    r = res_m.group(1) if res_m else ''
    c = chk_m.group(1) if chk_m else ''
    if t or "select" in r or "ll_" in r or "iv_" in r or "tv_" in r:
        print(f"{b:25} | {r:38} | chk={c} | {t}")
