import subprocess, re
from airplane_mode import ADB_BIN

xml = subprocess.check_output([ADB_BIN, '-s', '127.0.0.1:21623', 'shell', 'cat', '/sdcard/after_confirm.xml']).decode('utf-8')
for line in xml.split('><'):
    if 'EditText' in line or 'password' in line.lower() or '952' in line or '186' in line:
        print(line[:140])
