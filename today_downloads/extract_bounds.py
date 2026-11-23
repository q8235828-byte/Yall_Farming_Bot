import subprocess, re
from airplane_mode import ADB_BIN

xml_text = subprocess.check_output([ADB_BIN, '-s', '127.0.0.1:21623', 'shell', 'cat', '/sdcard/t.xml']).decode('utf-8')
for line in xml_text.split('><'):
    bounds_m = re.search(r'bounds="([^"]+)"', line)
    text_m = re.search(r'text="([^"]*)"', line)
    cls_m = re.search(r'class="([^"]+)"', line)
    b = bounds_m.group(1) if bounds_m else ""
    t = text_m.group(1) if text_m else ""
    c = cls_m.group(1) if cls_m else ""
    if t or "149" in b or "Button" in c:
        print(f"{b:25} | {c:28} | '{t}'")
