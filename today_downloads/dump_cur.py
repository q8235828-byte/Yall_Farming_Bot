import subprocess, re
ADB = 'today_downloads/platform-tools/adb.exe'
dev = '127.0.0.1:21533'
subprocess.run([ADB, '-s', dev, 'shell', 'rm', '-f', '/sdcard/cur.xml'])
subprocess.run([ADB, '-s', dev, 'shell', 'uiautomator', 'dump', '--compressed', '/sdcard/cur.xml'], timeout=12)
xml = subprocess.check_output([ADB, '-s', dev, 'shell', 'cat', '/sdcard/cur.xml'], timeout=4).decode('utf-8', errors='ignore')
print('XML Length:', len(xml))
for node in xml.split('><'):
    t = re.search(r'text="([^"]*)"', node)
    r = re.search(r'resource-id="([^"]*)"', node)
    b = re.search(r'bounds="([^"]*)"', node)
    text = t.group(1) if t else ''
    res = r.group(1) if r else ''
    bounds = b.group(1) if b else ''
    if text or any(k in res.lower() for k in ['btn', 'iv_', 'tv_', 'cb_', 'check', 'tips', 'watch', 'cancel']):
        print(f"{res:35} | {bounds:22} | {text}")
