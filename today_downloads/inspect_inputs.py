import subprocess, re, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
xml = subprocess.check_output(['platform-tools\\adb.exe', '-s', '127.0.0.1:21623', 'shell', 'cat', '/sdcard/w_check_email.xml']).decode('utf-8', errors='replace')
for line in xml.split('><'):
    bounds_m = re.search(r'bounds="([^"]+)"', line)
    text_m = re.search(r'text="([^"]*)"', line)
    res_m = re.search(r'resource-id="([^"]*)"', line)
    cls_m = re.search(r'class="([^"]*)"', line)
    t = text_m.group(1) if text_m else ''
    b = bounds_m.group(1) if bounds_m else ''
    r = res_m.group(1) if res_m else ''
    c = cls_m.group(1) if cls_m else ''
    if t or 'EditText' in c or 'et_' in r or 'btn' in r or 'tv_' in r or 'phone' in r or 'email' in r.lower():
        print(f"{b:25} | {c:28} | {r:38} | '{t}'")
