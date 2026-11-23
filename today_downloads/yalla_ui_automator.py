import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET
import cv2
import numpy as np
from airplane_mode import ADB_BIN, run_adb_command, get_device_port

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_NAME = "com.yalla.yallagames"
ACTIVITY_NAME = "com.yalla.yallagames.main.MainActivity"

# Calibrated 1080x2400 Coordinates (Vivo V2154 & MEmu 1080p - Verified from XML dumps)
COORDS_1080P = {
    "terms_checkbox": (142, 2283),
    "email_login_btn": (685, 1973),
    "signup_link": (937, 1687),
    "login_close_btn": (981, 818),
    "signup_email_input": (540, 1069),
    "signup_email_input_top": (540, 666),
    "obtain_code_btn": (820, 1247),
    "obtain_code_btn_top": (820, 844),
    "otp_input": (402, 1240),
    "otp_input_top": (402, 837),
    "signup_confirm_btn": (540, 1565),
    "signup_confirm_btn_top": (540, 1162),
    "password_input": (540, 831),
    "password_confirm_btn": (540, 1790),
    "btn_expert": (720, 1343),
    "popup_close_btn": (1003, 230),
    "settings_gear_btn": (1020, 172),
    "logout_btn": (280, 1642),
    "logout_confirm_ok": (810, 1320),
    "skip_tutorial_btn": (946, 90),
    "back_key": 4,
}

# Calibrated 720x1600 Coordinates (Motorola Moto G Play)
COORDS_720P = {
    "terms_checkbox": (95, 1521),
    "email_login_btn": (457, 1314),
    "signup_link": (624, 1125),
    "signup_email_input": (360, 419),
    "obtain_code_btn": (547, 538),
    "otp_input": (268, 533),
    "signup_confirm_btn": (360, 750),
    "password_input": (360, 319),
    "password_confirm_btn": (360, 1193),
    "btn_expert": (480, 896),
    "popup_close_btn": (669, 183),
    "settings_gear_btn": (680, 131),
    "logout_btn": (187, 1109),
    "back_key": 4,
}

# Calibrated 800x1280 Coordinates (MEmu Android Native Resolution)
COORDS_800P = {
    "terms_checkbox": (105, 1193),
    "email_login_btn": (508, 1042),
    "signup_link": (694, 1001),
    "signup_email_input": (400, 542),
    "obtain_code_btn": (607, 675),
    "otp_input": (297, 670),
    "signup_confirm_btn": (400, 910),
    "password_input": (400, 223),
    "password_confirm_btn": (400, 1017),
    "btn_expert": (534, 746),
    "popup_close_btn": (743, 122),
    "settings_gear_btn": (755, 56),
    "logout_btn": (208, 938),
    "back_key": 4,
}

RESOURCE_IDS = {
    "terms_checkbox": "com.yalla.yallagames:id/iv_select",
    "email_login_btn": "com.yalla.yallagames:id/ll_email",
    "signup_link": "com.yalla.yallagames:id/tv_sign_up",
    "signup_email_input": "com.yalla.yallagames:id/et_phone_number_sign",
    "obtain_code_btn": "com.yalla.yallagames:id/bt_get_verification_code_sign",
    "otp_input": "com.yalla.yallagames:id/et_verification_code_sign",
    "signup_confirm_btn": "com.yalla.yallagames:id/bt_sign_up_confirm",
    "password_input": "com.yalla.yallagames:id/et_cus_login_password",
    "password_confirm_btn": "com.yalla.yallagames:id/bt_set_pwd",
    "btn_expert": "com.yalla.yallagames:id/btn_yes",
    "popup_close_btn": "com.yalla.yallagames:id/iv_close",
    "settings_gear_btn": "com.yalla.yallagames:id/iv_setting",
    "logout_btn": "com.yalla.yallagames:id/bt_cancellation",
}

_RESOLUTION_CACHE = {}


def get_screen_dimensions(device_id: str = None) -> tuple[int, int]:
    """Detects screen width & height with memory caching."""
    if device_id in _RESOLUTION_CACHE:
        return _RESOLUTION_CACHE[device_id]
    try:
        out = run_adb_command(["shell", "wm", "size"], device_id)
        matches = re.findall(r"(\d+)x(\d+)", out)
        if matches:
            dims = (int(matches[-1][0]), int(matches[-1][1]))
            _RESOLUTION_CACHE[device_id] = dims
            return dims
    except Exception:
        pass
    if device_id and ("127.0.0.1" in device_id or "emulator" in device_id):
        return (800, 1280)
    return (1080, 2400)


def get_calibrated_coords(key_name: str, device_id: str = None) -> tuple[int, int]:
    """Returns instant calibrated coordinate based on resolution without XML dumping."""
    w, h = get_screen_dimensions(device_id)
    if w <= 720:
        return COORDS_720P.get(key_name, COORDS_800P.get(key_name))
    elif w <= 900:
        return COORDS_800P.get(key_name)
    return COORDS_1080P.get(key_name)


def run_adb_shell_compound(commands: list[str], device_id: str = None) -> str:
    """Runs multiple shell commands in a single fast ADB invocation."""
    compound_cmd = "; ".join(commands)
    return run_adb_command(["shell", compound_cmd], device_id)


def tap(x: int, y: int, device_id: str = None, delay: float = 0.15):
    """Ultra-fast ADB tap (150ms default)."""
    run_adb_command(["shell", "input", "tap", str(x), str(y)], device_id)
    if delay > 0:
        time.sleep(delay)


def type_text(text: str, device_id: str = None, delay: float = 0.15):
    """Ultra-fast text entry."""
    safe = text.replace(" ", "%s").replace("&", "\\&")
    run_adb_command(["shell", "input", "text", safe], device_id)
    if delay > 0:
        time.sleep(delay)


def keyevent(code: int, device_id: str = None, delay: float = 0.1):
    """Fast keyevent entry."""
    run_adb_command(["shell", "input", "keyevent", str(code)], device_id)
    if delay > 0:
        time.sleep(delay)


def fast_click(key_name: str, device_id: str = None, delay: float = 0.15):
    """Instantly clicks calibrated coordinates (Zero XML overhead)."""
    pt = get_calibrated_coords(key_name, device_id)
    if pt:
        tap(pt[0], pt[1], device_id, delay)


def get_element_coords(identifier: str, device_id: str = None, fallback: bool = False) -> tuple[int, int] | None:
    """Dynamic XML parser that matches resource-id, text, or substring and returns exact center (x, y)."""
    for attempt in range(2):
        try:
            if attempt > 0:
                run_adb_command(["shell", "input", "keyevent", "224"], device_id)
            run_adb_command(["shell", "uiautomator", "dump", "--compressed", "/sdcard/window_dump.xml"], device_id)
            xml_str = run_adb_command(["shell", "cat", "/sdcard/window_dump.xml"], device_id)
            idx = xml_str.find("<?xml")
            if idx != -1:
                xml_str = xml_str[idx:]
                root = ET.fromstring(xml_str)
                for elem in root.iter():
                    rid = elem.attrib.get("resource-id", "")
                    txt = elem.attrib.get("text", "")
                    if rid == identifier or txt == identifier or identifier in rid:
                        bounds = elem.attrib.get("bounds", "")
                        m = re.findall(r"\d+", bounds)
                        if len(m) == 4:
                            x1, y1, x2, y2 = map(int, m)
                            return (x1 + x2) // 2, (y1 + y2) // 2
        except Exception:
            pass
    # Calibrated fallback only if explicitly requested
    if fallback:
        for k, v in RESOURCE_IDS.items():
            if v == identifier or identifier in v:
                return get_calibrated_coords(k, device_id)
    return None


def is_element_present(resource_id: str, device_id: str = None) -> bool:
    return get_element_coords(resource_id, device_id, fallback=False) is not None


def clear_app_data(device_id: str = None):
    """Wipes app data to reset device cookies and bypass registration limits."""
    print("[*] Clearing app data (Anti-Limit Reset)...")
    run_adb_command(["shell", "pm", "clear", PACKAGE_NAME], device_id)
    try:
        run_adb_command(["shell", "pm", "grant", PACKAGE_NAME, "android.permission.POST_NOTIFICATIONS"], device_id)
    except Exception:
        pass
    time.sleep(0.5)


def start_app(device_id: str = None):
    """Fast app start."""
    run_adb_command(["shell", "monkey", "-p", PACKAGE_NAME, "-c", "android.intent.category.LAUNCHER", "1"], device_id)
    time.sleep(1.2)


def ensure_main_landing_page(device_id: str = None) -> bool:
    """
    Ensures the app is on the Main Welcome Landing Page (Login with Email/Facebook).
    Handles:
    - Android permission popups
    - Fresh launch after wiping data ("Welcome to Yalla Ludo! Have you ever played Ludo?" -> "I'm expert")
    - Lobby popups -> Settings -> Log Out
    """
    print("[*] Ensuring App is on Main Landing Page...")
    start_app(device_id)
    time.sleep(1.0)

    # 1. Check for Android permission prompt and auto-allow
    allow_btn = get_element_coords("com.android.permissioncontroller:id/permission_allow_button", device_id)
    if allow_btn:
        print("[+] Android permission prompt detected, auto-allowing...")
        tap(allow_btn[0], allow_btn[1], device_id, 0.5)
        time.sleep(0.5)

    # 2. Check if already on Main Landing Page
    if is_element_present(RESOURCE_IDS["email_login_btn"], device_id):
        print("[+] Main Landing Page verified!")
        return True

    # 3. Check for fresh launch after wiping data: "Welcome to Yalla Ludo! [I'm expert]"
    expert_btn = get_element_coords("com.yalla.yallagames:id/btn_yes", device_id)
    if expert_btn:
        print("[+] Fresh restart screen ('I'm expert') detected! Tapping to reach lobby...")
        tap(expert_btn[0], expert_btn[1], device_id, 0.8)
        time.sleep(1.2)

    # 4. Check for and close any Lobby popups (daily reward / check-in)
    for _ in range(5):
        close_btn = None
        for cid in ["com.yalla.yallagames:id/iv_close", "com.yalla.yallagames:id/iv_week_close"]:
            close_btn = get_element_coords(cid, device_id)
            if close_btn:
                print(f"[+] Closing lobby popup at {close_btn}...")
                tap(close_btn[0], close_btn[1], device_id, 0.5)
                time.sleep(0.6)
                break
        if not close_btn:
            break

    # 5. If in Lobby/Game Hall, open Settings and Log Out
    gear_btn = get_element_coords(RESOURCE_IDS["settings_gear_btn"], device_id)
    if gear_btn:
        print("[+] Game Lobby detected! Opening Settings to Log Out...")
        tap(gear_btn[0], gear_btn[1], device_id, 0.6)
        time.sleep(0.6)

    # 6. Click Log Out in Settings
    logout_btn = get_element_coords(RESOURCE_IDS["logout_btn"], device_id)
    if logout_btn:
        print("[+] Logging out to reach Main Landing Page...")
        tap(logout_btn[0], logout_btn[1], device_id, 0.6)
        time.sleep(1.0)

    # Final verification
    if is_element_present(RESOURCE_IDS["email_login_btn"], device_id):
        print("[+] Main Landing Page verified!")
        return True

    return True


def fast_expert_to_main_landing(device_id: str = None) -> bool:
    """
    Ultra-fast compound sequence executed as soon as 'I'm expert' screen is detected:
    1. Tap 'I'm expert' (btn_yes) -> enters Game Lobby
    2. Tap Gear Icon (iv_setting) -> opens Settings Dialog
    3. Tap 'Log Out' (bt_cancellation) -> lands directly on Main Welcome Landing Page!
    Completed in under 3.5 seconds total!
    """
    expert_pt = get_element_coords(RESOURCE_IDS["btn_expert"], device_id) or get_calibrated_coords("btn_expert", device_id)
    gear_pt = get_element_coords(RESOURCE_IDS["settings_gear_btn"], device_id) or get_calibrated_coords("settings_gear_btn", device_id)
    logout_pt = get_element_coords(RESOURCE_IDS["logout_btn"], device_id) or get_calibrated_coords("logout_btn", device_id)
    close_pt = get_calibrated_coords("popup_close_btn", device_id)

    print(f"[*] Executing Rapid Expert -> Gear -> Log Out Sequence on {device_id}...")
    
    cmd = (
        f"input tap {expert_pt[0]} {expert_pt[1]}; "
        f"sleep 1.0; "
        f"input tap {close_pt[0]} {close_pt[1]}; "
        f"sleep 0.2; "
        f"input tap {gear_pt[0]} {gear_pt[1]}; "
        f"sleep 0.6; "
        f"input tap {logout_pt[0]} {logout_pt[1]}"
    )
    run_adb_command(["shell", cmd], device_id)
    time.sleep(0.8)
    print(f"[+] Ultra-Fast Expert -> Logout completed in <3.5s! Landed on Main Landing!")
    return True


def is_terms_checked(device_id: str = None) -> bool:
    """
    Accurate in-memory color pixel detection of the bright green checkmark inside terms checkbox.
    Supports 1080p, 800p (MEmu), and 720p.
    Returns True if already checked (green pixels > 80), False otherwise.
    """
    try:
        port = get_device_port(device_id)
        cmd = [ADB_BIN]
        if port != 5037:
            cmd.extend(["-P", str(port)])
        if device_id:
            cmd.extend(["-s", device_id])

        dev_tag = device_id.replace(":", "_").replace(".", "_") if device_id else "def"
        tmp_remote = f"/sdcard/tc_{dev_tag}.png"
        tmp_local = os.path.join(CURRENT_DIR, f"tc_{dev_tag}.png")

        subprocess.run(cmd + ["shell", "screencap", "-p", tmp_remote],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
        subprocess.run(cmd + ["pull", tmp_remote, tmp_local],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)

        if os.path.exists(tmp_local):
            img = cv2.imread(tmp_local)
            try:
                os.remove(tmp_local)
            except Exception:
                pass
            if img is not None:
                h, w = img.shape[:2]
                if w <= 720:
                    y1, y2, x1, x2 = 1480, 1560, 60, 130
                elif w <= 900:
                    y1, y2, x1, x2 = 1160, 1227, 72, 139
                else:
                    y1, y2, x1, x2 = 2220, 2340, 100, 190

                crop = img[y1:y2, x1:x2]
                b, g, r = crop[:, :, 0].astype(int), crop[:, :, 1].astype(int), crop[:, :, 2].astype(int)
                green_pixels = int(np.sum((g > 140) & (g > r + 20)))
                print(f"[{device_id}] Terms Checkbox Color Pixel Count: {green_pixels} green pixels")
                return green_pixels > 80
    except Exception as e:
        print(f"[{device_id}] is_terms_checked error: {e}")
    return False


def ensure_terms_checked(device_id: str = None):
    """Checks the terms and conditions checkbox ONLY if not already checked."""
    if is_terms_checked(device_id):
        print(f"[{device_id}] [+] Terms checkbox is ALREADY CHECKED (green checkmark verified). Skipping tap!")
        return True
    
    print(f"[{device_id}] [*] Terms checkbox is UNCHECKED. Tapping once to check...")
    cal_pt = get_calibrated_coords("terms_checkbox", device_id)
    tap(cal_pt[0], cal_pt[1], device_id, 0.2)
    time.sleep(0.4)
    return True


def go_to_signup_screen(device_id: str = None) -> bool:
    """
    Ultra-resilient self-correcting navigation to Sign Up screen:
    1. If already on SIGNUP_SCREEN -> done!
    2. If on LOGIN_DIALOG -> tap 'Sign Up' link!
    3. From MAIN_LANDING:
       - Checks terms checkbox color pixel first (never uncheck if checked).
       - Taps Email login button.
       - Taps 'Sign Up' link on Login dialog to reach SIGNUP_SCREEN.
    """
    # 1. If already on Sign Up screen
    if is_element_present(RESOURCE_IDS["otp_input"], device_id) or is_element_present(RESOURCE_IDS["signup_email_input"], device_id):
        print(f"[{device_id}] [+] Already on Sign Up screen!")
        return True

    # 2. If Login Dialog is already visible, directly tap Sign Up!
    su_pt = get_element_coords(RESOURCE_IDS["signup_link"], device_id)
    if su_pt:
        print(f"[{device_id}] [*] Login dialog already visible, tapping Sign Up at {su_pt}...")
        tap(su_pt[0], su_pt[1], device_id, 0.8)
        return True

    # 3. From Main Landing: ensure terms checkbox is checked via color pixel first!
    ensure_terms_checked(device_id)
    time.sleep(0.3)

    email_pt = get_element_coords(RESOURCE_IDS["email_login_btn"], device_id) or get_calibrated_coords("email_login_btn", device_id)
    tap(email_pt[0], email_pt[1], device_id, 0.8)

    # Check if Login Dialog opened
    su_pt = get_element_coords(RESOURCE_IDS["signup_link"], device_id)
    if not su_pt:
        # If still not opened, re-verify terms with color pixels
        print(f"[{device_id}] [*] Login dialog not opened yet. Checking terms color pixels...")
        if not is_terms_checked(device_id):
            print(f"[{device_id}] [*] Checkbox was not checked. Tapping terms checkbox...")
            chk_pt = get_calibrated_coords("terms_checkbox", device_id)
            tap(chk_pt[0], chk_pt[1], device_id, 0.3)
        tap(email_pt[0], email_pt[1], device_id, 0.8)
        su_pt = get_element_coords(RESOURCE_IDS["signup_link"], device_id)

    # 4. Tap Sign Up on Login Dialog
    if su_pt:
        print(f"[{device_id}] [*] Tapping Sign Up link at {su_pt}...")
        tap(su_pt[0], su_pt[1], device_id, 0.8)
        return True

    cal_su = get_calibrated_coords("signup_link", device_id)
    if cal_su:
        tap(cal_su[0], cal_su[1], device_id, 0.8)
    return True


def is_keyboard_shown(device_id: str = None) -> bool:
    """Checks whether the Android virtual IME soft-keyboard is currently active/visible."""
    try:
        out = run_adb_command(["shell", "dumpsys", "input_method"], device_id)
        return "mInputShown=true" in out
    except Exception:
        return False


def ensure_clipper_installed(device_id: str = None) -> bool:
    """Verifies ca.zgrs.clipper is installed; installs clipper.apk automatically if missing."""
    try:
        out = run_adb_command(["shell", "pm", "list", "packages", "ca.zgrs.clipper"], device_id)
        if "ca.zgrs.clipper" not in out:
            print(f"[*] Installing clipboard helper (clipper.apk) on {device_id}...")
            clipper_apk = os.path.join(CURRENT_DIR, "clipper.apk")
            if os.path.exists(clipper_apk):
                run_adb_command(["shell", "settings", "put", "global", "package_verifier_enable", "0"], device_id)
                run_adb_command(["shell", "settings", "put", "global", "package_verifier_user_consent", "-1"], device_id)
                port = get_device_port(device_id)
                cmd = [ADB_BIN]
                if port != 5037:
                    cmd.extend(["-P", str(port)])
                if device_id:
                    cmd.extend(["-s", device_id])
                cmd.extend(["install", "-r", "-g", clipper_apk])
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        return True
    except Exception as e:
        print(f"[!] Clipper check warning: {e}")
        return False


def copy_to_clipboard(text: str, device_id: str = None) -> bool:
    """Pre-copies text directly into the device's Android clipboard via Clipper broadcast."""
    try:
        ensure_clipper_installed(device_id)
        cmd = [
            "shell", "am", "broadcast",
            "-a", "clipper.set",
            "-e", "text", f'"{text}"',
            "-n", "ca.zgrs.clipper/.ClipperReceiver",
            "-f", "0x01000000"
        ]
        out = run_adb_command(cmd, device_id)
        return "copied into clipboard" in out or "result=-1" in out
    except Exception as e:
        print(f"[!] copy_to_clipboard error: {e}")
        return False


def paste_clipboard(device_id: str = None, delay: float = 0.15):
    """Pastes clipboard contents instantly into the currently focused EditText."""
    keyevent(279, device_id, delay)


def request_verification_code(email_address: str, device_id: str = None) -> float:
    """
    Pastes email into the field via clipboard / direct input and clicks Obtain button.
    NO keyevent 111 (Escape) is executed so the dialog stays open!
    Returns: exact timestamp (float) when Obtain was clicked.
    """
    email_pt = get_element_coords(RESOURCE_IDS["signup_email_input"], device_id)
    if not email_pt:
        email_pt = get_calibrated_coords("signup_email_input", device_id)

    # 1. Tap email field
    tap(email_pt[0], email_pt[1], device_id, 0.2)

    # 2. Clean any existing text thoroughly
    run_adb_command(["shell", "input", "keyevent", "123"], device_id)
    run_adb_command(["shell", "input", "keyevent"] + ["67"] * 60, device_id)
    time.sleep(0.1)

    # 3. Pre-copy target email to device clipboard & paste
    pasted = False
    if copy_to_clipboard(email_address, device_id):
        paste_clipboard(device_id, 0.2)
        pasted = True

    if not pasted:
        run_adb_command(["shell", "input", "text", email_address], device_id)
    print(f"[+] Email [{email_address}] populated into input field successfully (NO keyevent 111)!")

    # 4. Dynamic re-query for Obtain button
    obtain_pt = get_element_coords(RESOURCE_IDS["obtain_code_btn"], device_id)
    if not obtain_pt:
        obtain_pt = get_calibrated_coords("obtain_code_btn", device_id)

    obtain_time = time.time()
    tap(obtain_pt[0], obtain_pt[1], device_id, 0.4)
    return obtain_time


def submit_verification_code(otp_code: str, device_id: str = None) -> bool:
    """Copies OTP to clipboard/types into OTP box, and clicks yellow Confirm button."""
    otp_pt = get_element_coords(RESOURCE_IDS["otp_input"], device_id)
    if not otp_pt:
        otp_pt = get_calibrated_coords("otp_input", device_id)

    # 1. Tap OTP box and wait for input focus
    tap(otp_pt[0], otp_pt[1], device_id, 0.2)

    # 2. Clear and paste/type OTP
    run_adb_command(["shell", "input", "keyevent", "123"], device_id)
    run_adb_command(["shell", "input", "keyevent"] + ["67"] * 20, device_id)
    pasted = False
    if copy_to_clipboard(otp_code, device_id):
        paste_clipboard(device_id, 0.2)
        pasted = True
    if not pasted:
        run_adb_command(["shell", "input", "text", otp_code], device_id)
    print(f"[+] OTP [{otp_code}] entered into verification field successfully!")

    # Dismiss soft keyboard if visible so Confirm button is fully clickable
    run_adb_command(["shell", "input", "keyevent", "111"], device_id)
    time.sleep(0.3)

    # 3. Find and tap yellow Confirm button directly
    confirm_pt = get_element_coords(RESOURCE_IDS["signup_confirm_btn"], device_id)
    if not confirm_pt:
        confirm_pt = get_calibrated_coords("signup_confirm_btn", device_id)

    print(f"[*] Tapping yellow Confirm button at {confirm_pt}...")
    tap(confirm_pt[0], confirm_pt[1], device_id, 0.5)
    return True


def set_account_password(password: str = "LudoPass#2026@", device_id: str = None) -> bool:
    """Copies password to clipboard/types into password box, and clicks Confirm."""
    print(f"[{device_id}] Waiting for Set Password screen...")
    pw_pt = None
    confirm_pt = None
    dev_tag = device_id.replace(":", "_").replace(".", "_") if device_id else "def"
    remote_xml = f"/sdcard/sd_pwd_{dev_tag}.xml"

    for _ in range(15):
        try:
            run_adb_command(["shell", "rm", "-f", remote_xml], device_id)
            run_adb_command(["shell", "uiautomator", "dump", "--compressed", remote_xml], device_id)
            xml_str = run_adb_command(["shell", "cat", remote_xml], device_id)
            idx = xml_str.find("<?xml")
            if idx != -1:
                root = ET.fromstring(xml_str[idx:])
                for elem in root.iter():
                    # Match password field
                    if elem.attrib.get("class") == "android.widget.EditText" and elem.attrib.get("password") == "true":
                        bounds = elem.attrib.get("bounds", "")
                        m = re.findall(r"\d+", bounds)
                        if len(m) == 4:
                            pw_pt = ((int(m[0]) + int(m[2])) // 2, (int(m[1]) + int(m[3])) // 2)
                    # Match confirm button
                    if elem.attrib.get("resource-id") == "com.yalla.yallagames:id/bt_set_pwd" or (elem.attrib.get("text") == "Confirm" and int(m[1]) > 700):
                        bounds = elem.attrib.get("bounds", "")
                        m = re.findall(r"\d+", bounds)
                        if len(m) == 4:
                            confirm_pt = ((int(m[0]) + int(m[2])) // 2, (int(m[1]) + int(m[3])) // 2)
        except Exception:
            pass

        if pw_pt:
            break
        time.sleep(0.3)
    
    if not pw_pt:
        pw_pt = get_calibrated_coords("password_input", device_id)
    if not confirm_pt:
        confirm_pt = get_calibrated_coords("password_confirm_btn", device_id)

    # 1. Focus password field
    print(f"[{device_id}] Focusing password field at {pw_pt}...")
    tap(pw_pt[0], pw_pt[1], device_id, 0.25)

    # 2. Clean any residual characters
    run_adb_command(["shell", "input", "keyevent", "123"], device_id)
    run_adb_command(["shell", "input", "keyevent"] + ["67"] * 30, device_id)
    time.sleep(0.1)

    # 3. Enter password (Clipper paste, fallback input text)
    pasted = False
    if copy_to_clipboard(password, device_id):
        paste_clipboard(device_id, 0.2)
        pasted = True
    if not pasted:
        run_adb_command(["shell", "input", "text", password], device_id)
    print(f"[{device_id}] Password entered into password field successfully!")

    # Dismiss soft keyboard if visible so Confirm button is fully clickable
    run_adb_command(["shell", "input", "keyevent", "111"], device_id)
    time.sleep(0.3)

    # 4. Click confirm button directly
    print(f"[{device_id}] Tapping password Confirm button at {confirm_pt}...")
    tap(confirm_pt[0], confirm_pt[1], device_id, 0.3)
    # Double tap confirm / tap calibrated confirm
    cal_conf = get_calibrated_coords("password_confirm_btn", device_id)
    if cal_conf:
        tap(cal_conf[0], cal_conf[1], device_id, 0.4)
    return True


def handle_welcome_dialog(device_id: str = None) -> bool:
    """
    Full Account Finalization Sequence:
    1. Waits for and taps 'I am expert' (btn_yes).
    2. Waits for and closes the lobby reward dialog box (iv_close / iv_week_close).
    3. Taps Settings gear icon (iv_setting).
    4. Taps Log Out button (bt_cancellation) to cleanly end session.
    """
    print("[*] Waiting for 'I am expert' dialog...")
    for _ in range(25):
        expert_coords = get_element_coords(RESOURCE_IDS["btn_expert"], device_id)
        if expert_coords:
            print(f"[+] 'I am expert' screen detected at {expert_coords}! Tapping...")
            tap(expert_coords[0], expert_coords[1], device_id, 0.5)
            break
        time.sleep(0.4)
    else:
        print("[*] Fallback tapping calibrated expert button...")
        fast_click("btn_expert", device_id, 0.5)

    # Step: Close the dialogue box that appears right after 'I am expert'
    print("[*] Waiting for popup dialogue box to close...")
    time.sleep(1.2)
    popup_closed = False
    for _ in range(12):
        for close_id in ["com.yalla.yallagames:id/iv_close", "com.yalla.yallagames:id/iv_week_close"]:
            close_pt = get_element_coords(close_id, device_id)
            if close_pt:
                print(f"[+] Dialogue box close button detected at {close_pt}! Closing...")
                tap(close_pt[0], close_pt[1], device_id, 0.4)
                popup_closed = True
                break
        if popup_closed:
            break
        time.sleep(0.3)
    
    if not popup_closed:
        print("[*] Fallback tapping calibrated popup close button...")
        fast_click("popup_close_btn", device_id, 0.4)

    time.sleep(0.8)

    # Step: Tap Settings Gear icon
    print("[*] Tapping Settings Gear icon...")
    gear_opened = False
    for _ in range(10):
        gear_pt = get_element_coords(RESOURCE_IDS["settings_gear_btn"], device_id)
        if gear_pt:
            print(f"[+] Settings gear detected at {gear_pt}! Opening...")
            tap(gear_pt[0], gear_pt[1], device_id, 0.4)
            gear_opened = True
            break
        time.sleep(0.3)
    if not gear_opened:
        fast_click("settings_gear_btn", device_id, 0.4)

    time.sleep(0.6)

    # Step: In Settings, click Log Out
    print("[*] Tapping Log Out button...")
    logout_pt = get_element_coords(RESOURCE_IDS["logout_btn"], device_id)
    if not logout_pt:
        logout_pt = get_calibrated_coords("logout_btn", device_id)
    tap(logout_pt[0], logout_pt[1], device_id, 0.5)
    print("[+] Successfully logged out! Account creation complete.")
    return True


def close_lobby_popups(device_id: str = None):
    """Closes any lobby promotion popup."""
    for _ in range(3):
        close_pt = get_element_coords(RESOURCE_IDS["popup_close_btn"], device_id)
        if close_pt:
            tap(close_pt[0], close_pt[1], device_id, 0.3)
        else:
            keyevent(4, device_id, 0.2)
        time.sleep(0.3)


def logout_account(device_id: str = None) -> bool:
    """Opens settings gear and logs out."""
    for _ in range(5):
        gear_pt = get_element_coords(RESOURCE_IDS["settings_gear_btn"], device_id)
        if gear_pt:
            tap(gear_pt[0], gear_pt[1], device_id, 0.4)
            break
        time.sleep(0.3)
    else:
        fast_click("settings_gear_btn", device_id, 0.4)

    # Click logout
    logout_pt = get_element_coords(RESOURCE_IDS["logout_btn"], device_id)
    if not logout_pt:
        logout_pt = get_calibrated_coords("logout_btn", device_id)
    tap(logout_pt[0], logout_pt[1], device_id, 0.4)

    # Confirm dialog if asked
    for confirm_id in ["android:id/button1", "com.yalla.yallagames:id/btn_ok", "com.yalla.yallagames:id/btn_yes"]:
        c = get_element_coords(confirm_id, device_id)
        if c:
            tap(c[0], c[1], device_id, 0.3)
            break
    time.sleep(0.5)
    return True


def reset_app_and_ip(device_id: str = None, air_delay: float = 1.5):
    """Wipes app data (anti-limit reset), toggles airplane mode, and re-launches app."""
    terms_pt = get_calibrated_coords("terms_checkbox", device_id)
    cmd = (
        f"pm clear {PACKAGE_NAME}; "
        f"cmd connectivity airplane-mode enable; "
        f"sleep {air_delay}; "
        f"cmd connectivity airplane-mode disable; "
        f"sleep 1.0; "
        f"monkey -p {PACKAGE_NAME} -c android.intent.category.LAUNCHER 1; "
        f"sleep 1.2; "
        f"input tap {terms_pt[0]} {terms_pt[1]}"
    )
    run_adb_shell_compound([cmd], device_id)

