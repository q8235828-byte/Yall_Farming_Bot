import subprocess, re
from airplane_mode import ADB_BIN

dev = '127.0.0.1:21623'
print('[*] Tapping Obtain at (607, 675)...')
subprocess.run([ADB_BIN, '-s', dev, 'shell', 'input', 'tap', '607', '675'])
import time; time.sleep(2.0)
subprocess.run([ADB_BIN, '-s', dev, 'shell', 'uiautomator', 'dump', '/sdcard/after_obtain.xml'])

xml = subprocess.check_output([ADB_BIN, '-s', dev, 'shell', 'cat', '/sdcard/after_obtain.xml']).decode('utf-8')
for line in xml.split('><'):
    bounds_m = re.search(r'bounds="([^"]+)"', line)
    text_m = re.search(r'text="([^"]*)"', line)
    t = text_m.group(1) if text_m else ''
    b = bounds_m.group(1) if bounds_m else ''
    if any(k in line.lower() for k in ['puzzle', 'slide', 'refresh', 'close', 'bt_get', 'et_verification', 'toast', 'error']):
        print(f"{b:25} | {line[:130]}")
