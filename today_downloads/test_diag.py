import subprocess, time
dev = '127.0.0.1:21623'
import yalla_ui_automator as ui
from screen_detector import ScreenDetector
sd = ScreenDetector(dev)

def clear():
    subprocess.run(['platform-tools/adb.exe', '-s', dev, 'shell', 'input', 'keyevent', '123'])
    subprocess.run(['platform-tools/adb.exe', '-s', dev, 'shell', 'input', 'keyevent'] + ['67'] * 60)
    subprocess.run(['platform-tools/adb.exe', '-s', dev, 'shell', 'input', 'keyevent', '122'])
    subprocess.run(['platform-tools/adb.exe', '-s', dev, 'shell', 'input', 'keyevent'] + ['112'] * 60)

def read_text():
    root = sd.dump_ui_tree()
    for n in root.iter('node'):
        if 'phone_number_sign' in n.attrib.get('resource-id', ''):
            return n.attrib.get('text')

clear()
subprocess.run(['platform-tools/adb.exe', '-s', dev, 'shell', 'input', 'text', 'user'])
print('After typing user:', repr(read_text()))

subprocess.run(['platform-tools/adb.exe', '-s', dev, 'shell', 'input', 'text', '520'])
print('After typing 520:', repr(read_text()))

subprocess.run(['platform-tools/adb.exe', '-s', dev, 'shell', 'input', 'keyevent', '77'])
print('After typing @:', repr(read_text()))

subprocess.run(['platform-tools/adb.exe', '-s', dev, 'shell', 'input', 'text', 'bhul'])
subprocess.run(['platform-tools/adb.exe', '-s', dev, 'shell', 'input', 'text', 'leh'])
print('After bhul + leh:', repr(read_text()))
