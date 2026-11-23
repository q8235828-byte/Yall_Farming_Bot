import subprocess, time, re

ADB = 'today_downloads/platform-tools/adb.exe'
dev = '127.0.0.1:21613'

print("[*] Tapping Log Out at (208, 938)...")
subprocess.run([ADB, '-s', dev, 'shell', 'input', 'tap', '208', '938'])
time.sleep(1.0)

subprocess.run([ADB, '-s', dev, 'shell', 'uiautomator', 'dump', '--compressed', '/sdcard/after_logout_tap.xml'], stdout=subprocess.DEVNULL)
xml = subprocess.check_output([ADB, '-s', dev, 'shell', 'cat', '/sdcard/after_logout_tap.xml']).decode('utf-8', errors='ignore')

for node in xml.split('><'):
    for kw in ['btn', 'button', 'confirm', 'cancel', 'ok', 'yes', 'no', 'tv_', 'message', 'text']:
        if kw in node.lower():
            res = re.search(r'resource-id="([^"]+)"', node)
            bounds = re.search(r'bounds="([^"]+)"', node)
            text = re.search(r'text="([^"]*)"', node)
            r = res.group(1) if res else ""
            b = bounds.group(1) if bounds else ""
            t = text.group(1) if text else ""
            if r or t:
                print(f"{r:40} | {b:22} | {t}")
            break
