import subprocess, re
from run_all_active import get_connected_devices, ADB_BIN

devices = get_connected_devices()
print("Connected:", devices)
for dev in devices:
    try:
        subprocess.run([ADB_BIN, '-s', dev, 'shell', 'uiautomator', 'dump', '--compressed', f'/sdcard/d_{dev[-5:]}.xml'], stdout=subprocess.DEVNULL, timeout=4)
        xml = subprocess.check_output([ADB_BIN, '-s', dev, 'shell', 'cat', f'/sdcard/d_{dev[-5:]}.xml'], timeout=2).decode('utf-8', errors='ignore')
        for node in xml.split('><'):
            if any(k in node for k in ['Don\'t ask', 'Watch', 'Tips', 'Cancel', 'watch']):
                t = re.search(r'text="([^"]*)"', node)
                b = re.search(r'bounds="([^"]*)"', node)
                r = re.search(r'resource-id="([^"]*)"', node)
                print(f"[{dev}] {r.group(1) if r else '':30} | {b.group(1) if b else '':22} | {t.group(1) if t else ''}")
    except Exception as e:
        print(f"[{dev}] Error: {e}")
