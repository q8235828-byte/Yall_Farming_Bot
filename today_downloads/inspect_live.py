import subprocess
import time
import xml.etree.ElementTree as ET
import re
import os

ADB = r"c:\Users\admin\codebase\today_downloads\platform-tools\adb.exe"
DEV = "127.0.0.1:21623"

def get_live_xml(device_id=DEV):
    subprocess.run(f'"{ADB}" -s {device_id} shell "input keyevent 224"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cmd = f'"{ADB}" -s {device_id} shell "uiautomator dump /sdcard/live.xml > /dev/null 2>&1; cat /sdcard/live.xml"'
    raw = subprocess.check_output(cmd, shell=True, text=True, errors="replace")
    idx = raw.find("<?xml")
    if idx == -1:
        return None
    try:
        return ET.fromstring(raw[idx:])
    except Exception as e:
        return None

def analyze_screen(root):
    if root is None:
        return "UNKNOWN_SCREEN", {}
    
    nodes = {}
    for el in root.iter("node"):
        rid = el.attrib.get("resource-id", "")
        txt = el.attrib.get("text", "")
        bounds = el.attrib.get("bounds", "")
        if rid:
            nodes[rid] = {"text": txt, "bounds": bounds}
    
    # 1. Sign Up screen
    if "com.yalla.yallagames:id/et_verification_code_sign" in nodes:
        obtain_txt = nodes.get("com.yalla.yallagames:id/bt_get_verification_code_sign", {}).get("text", "")
        if "s" in obtain_txt.lower() and any(c.isdigit() for c in obtain_txt):
            return "STATE_OTP_READY", nodes
        return "STATE_SIGNUP", nodes
    
    # 2. Login Dialog
    if "com.yalla.yallagames:id/tv_sign_up" in nodes or "com.yalla.yallagames:id/bt_login" in nodes:
        return "STATE_LOGIN_DIALOG", nodes

    # 3. Set Password
    if "com.yalla.yallagames:id/bt_set_pwd" in nodes or "com.yalla.yallagames:id/et_set_password1" in nodes:
        return "STATE_SET_PASSWORD", nodes

    # 4. Expert Dialog
    if "com.yalla.yallagames:id/btn_yes" in nodes:
        return "STATE_EXPERT_DIALOG", nodes

    # 5. Main Landing
    if "com.yalla.yallagames:id/ll_email" in nodes or "com.yalla.yallagames:id/tv_fb_login" in nodes:
        return "STATE_MAIN_LANDING", nodes

    return "STATE_OTHER", nodes

if __name__ == "__main__":
    root = get_live_xml()
    state, nodes = analyze_screen(root)
    print(f"[CURRENT SCREEN DETECTED]: {state}")
    for k, v in nodes.items():
        if "yalla" in k:
            print(f"  {k} -> '{v['text']}' @ {v['bounds']}")
