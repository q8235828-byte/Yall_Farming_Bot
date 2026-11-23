import subprocess, re

ADB = 'today_downloads/platform-tools/adb.exe'
dev = '127.0.0.1:21613'
subprocess.run([ADB, '-s', dev, 'shell', 'uiautomator', 'dump', '--compressed', '/sdcard/dump.xml'], stdout=subprocess.DEVNULL)
xml = subprocess.check_output([ADB, '-s', dev, 'shell', 'cat', '/sdcard/dump.xml']).decode('utf-8', errors='ignore')

for node in xml.split('><'):
    for kw in ['setting', 'logout', 'cancel', 'main', 'hall', 'iv_', 'bt_', 'btn_']:
        if kw in node.lower():
            res = re.search(r'resource-id="([^"]+)"', node)
            bounds = re.search(r'bounds="([^"]+)"', node)
            text = re.search(r'text="([^"]*)"', node)
            r = res.group(1) if res else ""
            b = bounds.group(1) if bounds else ""
            t = text.group(1) if text else ""
            print(f"{r:40} | {b:22} | {t}")
            break
