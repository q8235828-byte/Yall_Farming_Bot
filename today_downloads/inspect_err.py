import subprocess, re

ADB = 'today_downloads/platform-tools/adb.exe'
dev = '127.0.0.1:21533'
subprocess.run([ADB, '-s', dev, 'shell', 'uiautomator', 'dump', '--compressed', '/sdcard/dump_err.xml'], stdout=subprocess.DEVNULL)
xml = subprocess.check_output([ADB, '-s', dev, 'shell', 'cat', '/sdcard/dump_err.xml']).decode('utf-8', errors='ignore')

for node in xml.split('><'):
    text = re.search(r'text="([^"]+)"', node)
    res = re.search(r'resource-id="([^"]+)"', node)
    t = text.group(1) if text else ''
    r = res.group(1) if res else ''
    if t or any(k in r.lower() for k in ['tv_', 'tip', 'error', 'msg', 'alert', 'dialog', 'btn']):
        print(f"{r:35} | {t}")
