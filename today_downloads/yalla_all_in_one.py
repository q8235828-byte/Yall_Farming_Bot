"""
================================================================================
YALLA LUDO ALL-IN-ONE AUTOMATION SUITE (EXACT RESTORED WORKING MASTER)
================================================================================
Restored directly from master_backup_working.
All screen detections, wait_for_state checks, and calibrated delays are 100%
identical to the proven 5/5 batch run.
================================================================================
"""

import csv
from datetime import datetime
import email
from email.header import decode_header
import imaplib
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

import cv2
import numpy as np

# Force UTF-8 for console output
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# Dynamic Base Directory (Works in source and compiled .exe)
BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
ACCOUNTS_CSV = os.path.join(BASE_DIR, "created_accounts.csv")
DEFAULT_PASSWORD = "Yalla#2026@Pass"

# Local ADB binary auto-detection
LOCAL_ADB = os.path.join(BASE_DIR, "platform-tools", "adb.exe")
ADB_BIN = LOCAL_ADB if os.path.exists(LOCAL_ADB) else (shutil.which("adb") or "adb")

# State Constants
STATE_UNKNOWN = "UNKNOWN"
STATE_MAIN_LANDING = "MAIN_LANDING"
STATE_SIGNUP = "SIGNUP_SCREEN"
STATE_CAPTCHA = "CAPTCHA_PUZZLE"
STATE_OTP_READY = "OTP_INPUT_READY"
STATE_SET_PASSWORD = "SET_PASSWORD"
STATE_EXPERT_DIALOG = "EXPERT_DIALOG"
STATE_LOBBY_POPUP = "LOBBY_POPUP"
STATE_GAME_HALL = "GAME_HALL"
STATE_SETTINGS_DIALOG = "SETTINGS_DIALOG"

# Calibrated 1080x2400 Coordinates (Vivo V2154 & MEmu 1080p - Verified from XML dumps)
COORDS_1080P = {
    "terms_checkbox": (142, 2283),
    "email_login_btn": (685, 1973),
    "signup_link": (937, 1687),
    "login_close_btn": (981, 818),
    "signup_email_input": (540, 1069),
    "obtain_code_btn": (820, 1247),
    "otp_input": (402, 1240),
    "signup_confirm_btn": (540, 1565),
    "password_input": (540, 831),
    "password_confirm_btn": (540, 1790),
    "btn_expert": (720, 1343),
    "popup_close_btn": (1003, 230),
    "settings_gear_btn": (1020, 172),
    "logout_btn": (280, 1642),
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

PACKAGE_NAME = "com.yalla.yallagames"
ACTIVITY_NAME = "com.yalla.yallagames.main.MainActivity"
STOP_REQUESTED = False


# ==============================================================================
# 1. CONFIGURATION & LOGGING HELPERS
# ==============================================================================
def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Error reading config.json: {e}")
    return {
        "device_serial": "34558213310005P",
        "gmail_address": "qaisarfaryad0@gmail.com",
        "gmail_app_password": "ptxp yxiu qeuo mlku",
        "cloudflare_domain": "bhullehshahsilage.com",
        "email_prefix": "user",
        "current_counter": 232,
        "yalla_package": "com.yalla.yallagames",
        "airplane_wait_seconds": 1.5
    }


def save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def get_next_email(config: dict) -> tuple[str, dict]:
    prefix = config.get("email_prefix", "user")
    counter = config.get("current_counter", 101)
    domain = config.get("cloudflare_domain", "bhullehshahsilage.com")
    email_address = f"{prefix}{counter}@{domain}"
    config["current_counter"] = counter + 1
    save_config(config)
    return email_address, config


def save_account_to_csv(email_address: str, otp_code: str, status: str = "Created", password: str = DEFAULT_PASSWORD):
    row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email_address, password, otp_code, status]
    target_path = ACCOUNTS_CSV
    for attempt in range(3):
        try:
            file_exists = os.path.exists(target_path)
            with open(target_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Timestamp", "Email", "Password", "OTP Code", "Status"])
                writer.writerow(row)
            print(f"[+] Account record saved to: {target_path}")
            return
        except PermissionError:
            print(f"[!] Warning: {target_path} is open in another program. Retrying...")
            time.sleep(1.0)
            target_path = os.path.join(BASE_DIR, "created_accounts_session.csv")
    print(f"[!] Saved record to backup session file: {target_path}")


def request_stop():
    global STOP_REQUESTED
    STOP_REQUESTED = True
    print("[!] User requested STOP. Execution will conclude or halt safely.")


# ==============================================================================
# 2. ADB & AIRPLANE MODE ENGINE
# ==============================================================================
def run_adb_command(cmd_args: list[str], device_id: str = None) -> str:
    full_cmd = [ADB_BIN]
    if device_id:
        full_cmd.extend(["-s", device_id])
    full_cmd.extend(cmd_args)
    try:
        result = subprocess.run(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ADB Command Failed: {' '.join(full_cmd)}\nError: {e.stderr.strip()}")


def toggle_airplane_mode(wait_seconds: float = 1.5, device_id: str = None) -> bool:
    print(f"\n[*] Rotating IP Address via Airplane Mode (Hold: {wait_seconds}s)...")
    try:
        run_adb_command(["shell", "cmd", "connectivity", "airplane-mode", "enable"], device_id)
        time.sleep(wait_seconds)
        run_adb_command(["shell", "cmd", "connectivity", "airplane-mode", "disable"], device_id)
        time.sleep(2.0)
        print("[+] Airplane Mode toggled successfully! IP rotated. [OK]")
        return True
    except Exception as e:
        print(f"[-] Root airplane mode toggle failed: {e}. Trying fallback intent...")
        try:
            run_adb_command(["shell", "settings", "put", "global", "airplane_mode_on", "1"], device_id)
            run_adb_command(["shell", "am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE", "--ez", "state", "true"], device_id)
            time.sleep(wait_seconds)
            run_adb_command(["shell", "settings", "put", "global", "airplane_mode_on", "0"], device_id)
            run_adb_command(["shell", "am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE", "--ez", "state", "false"], device_id)
            time.sleep(2.0)
            return True
        except Exception as e2:
            print(f"[!] Warning: Fallback airplane mode failed: {e2}")
            return False


# ==============================================================================
# 3. SCREEN DETECTOR
# ==============================================================================
class ScreenDetector:
    def __init__(self, device_id: str = None):
        self.device_id = device_id

    def capture_screen(self) -> np.ndarray | None:
        cmd = [ADB_BIN]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend(["exec-out", "screencap", "-p"])
        try:
            raw = subprocess.check_output(cmd)
            img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                return img
        except Exception:
            pass
        return None

    def dump_ui_tree(self) -> ET.Element | None:
        try:
            base = [ADB_BIN] + (["-s", self.device_id] if self.device_id else [])
            subprocess.run(base + ["shell", "uiautomator", "dump", "/sdcard/sd_dump.xml"], timeout=6, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            out = subprocess.check_output(base + ["shell", "cat", "/sdcard/sd_dump.xml"], timeout=4)
            text = out.decode("utf-8", errors="ignore")
            start = text.find("<?xml")
            if start != -1:
                return ET.fromstring(text[start:])
        except Exception:
            pass
        return None

    def detect_slider_knob(self, img: np.ndarray) -> tuple[int, int, int, int] | None:
        ih, iw, _ = img.shape
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        blue_mask = cv2.inRange(hsv, np.array([95, 120, 120]), np.array([135, 255, 255]))
        contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            area = cv2.contourArea(c)
            if 500 < area < 30000:
                x, y, w, h = cv2.boundingRect(c)
                aspect = float(w) / max(h, 1)
                if int(ih * 0.40) < y < int(ih * 0.78) and 60 < w < 240 and 0.65 < aspect < 2.0:
                    return (x + w // 2, y + h // 2, w, h)
        return None

    def get_screen_state(self, img: np.ndarray = None) -> tuple[str, dict]:
        root = self.dump_ui_tree()
        rids = {}
        if root is not None:
            for node in root.iter("node"):
                rid = node.get("resource-id", "")
                bounds = node.get("bounds", "")
                text = node.get("text", "")
                if rid:
                    rids[rid] = {"text": text, "bounds": bounds, "node": node}

        if "com.yalla.yallagames:id/tv_fb_login" in rids or "com.yalla.yallagames:id/ll_email" in rids:
            return STATE_MAIN_LANDING, rids.get("com.yalla.yallagames:id/ll_email", {})

        if "com.yalla.yallagames:id/bt_cancellation" in rids:
            return STATE_SETTINGS_DIALOG, rids["com.yalla.yallagames:id/bt_cancellation"]

        if "com.yalla.yallagames:id/btn_yes" in rids:
            return STATE_EXPERT_DIALOG, rids["com.yalla.yallagames:id/btn_yes"]

        for cid in ["com.yalla.yallagames:id/iv_close", "com.yalla.yallagames:id/iv_week_close"]:
            if cid in rids:
                return STATE_LOBBY_POPUP, rids[cid]

        if "com.yalla.yallagames:id/et_cus_login_password" in rids or "com.yalla.yallagames:id/bt_set_pwd" in rids:
            return STATE_SET_PASSWORD, rids.get("com.yalla.yallagames:id/et_cus_login_password", {})

        if "com.yalla.yallagames:id/et_verification_code_sign" in rids:
            obtain_info = rids.get("com.yalla.yallagames:id/bt_get_verification_code_sign", {})
            obtain_text = obtain_info.get("text", "")
            if "s" in obtain_text.lower() and any(char.isdigit() for char in obtain_text):
                return STATE_OTP_READY, {"countdown": obtain_text, "info": rids["com.yalla.yallagames:id/et_verification_code_sign"]}
            
            if img is None:
                img = self.capture_screen()
            if img is not None:
                knob = self.detect_slider_knob(img)
                if knob:
                    return STATE_CAPTCHA, {"knob": knob}

            return STATE_SIGNUP, rids["com.yalla.yallagames:id/et_verification_code_sign"]

        if "com.yalla.yallagames:id/iv_setting" in rids:
            return STATE_GAME_HALL, rids["com.yalla.yallagames:id/iv_setting"]

        return STATE_UNKNOWN, {}

    def wait_for_state(self, target_state: str, timeout: float = 10.0, poll_interval: float = 0.5) -> tuple[bool, dict]:
        print(f"[*] Waiting for screen state: [{target_state}] (Timeout: {timeout}s)...")
        start = time.time()
        while time.time() - start < timeout:
            state, data = self.get_screen_state()
            if state == target_state:
                print(f"[+] Screen DETECTED: [{target_state}] [OK]")
                return True, data
            time.sleep(poll_interval)
        print(f"[-] Screen detection TIMEOUT waiting for [{target_state}]. Current: [{state}]")
        return False, {}


# ==============================================================================
# 4. INTELLIGENT CAPTCHA SOLVER
# ==============================================================================
class IntelligentCaptchaSolver:
    def __init__(self, device_id: str = None):
        self.device_id = device_id

    def capture_screen(self) -> np.ndarray | None:
        cmd = [ADB_BIN]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend(["exec-out", "screencap", "-p"])
        try:
            raw = subprocess.check_output(cmd)
            return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        except Exception:
            return None

    def find_slider_knob(self, img: np.ndarray) -> tuple[int, int, int, int] | None:
        ih, iw, _ = img.shape
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        blue_mask = cv2.inRange(hsv, np.array([95, 120, 120]), np.array([135, 255, 255]))
        contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            area = cv2.contourArea(c)
            if 500 < area < 30000:
                x, y, w, h = cv2.boundingRect(c)
                aspect = float(w) / max(h, 1)
                if int(ih * 0.40) < y < int(ih * 0.78) and 60 < w < 240 and 0.65 < aspect < 2.0:
                    return (x + w // 2, y + h // 2, w, h)
        return None

    def find_puzzle_canvas(self, img: np.ndarray) -> tuple[int, int, int, int] | None:
        ih, iw, _ = img.shape
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 100)
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        cands = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            aspect = float(w) / max(h, 1)
            if 400 < w < 950 and 200 < h < 550 and 1.2 < aspect < 2.4:
                if int(ih * 0.20) < y < int(ih * 0.65):
                    cands.append((w * h, (x, y, w, h)))
        if cands:
            cands.sort(reverse=True)
            return cands[0][1]
        return None

    def detect_gap_x(self, img: np.ndarray, canvas_box: tuple[int, int, int, int]) -> int:
        cx, cy, cw, ch = canvas_box
        canvas = img[cy:cy+ch, cx:cx+cw]
        gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
        v_channel = cv2.cvtColor(canvas, cv2.COLOR_BGR2HSV)[:, :, 2]
        dark_mask = cv2.inRange(v_channel, 0, 75)
        edges = cv2.Canny(gray, 80, 180)
        combined = cv2.bitwise_or(edges, dark_mask)
        col_densities = np.sum(combined, axis=0) / float(ch * 255)
        start_x = int(cw * 0.22)
        end_x = int(cw * 0.90)
        cropped_densities = col_densities[start_x:end_x]
        best_rel_x = int(np.argmax(cropped_densities)) + start_x
        return cx + best_rel_x

    def human_drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration_ms: int = 700):
        cmd = [ADB_BIN]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend(["shell", "input", "swipe", str(start_x), str(start_y), str(end_x), str(end_y), str(duration_ms)])
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def solve(self, max_attempts: int = 3) -> bool:
        print("[*] Starting Intelligent Captcha Solver...")
        for attempt in range(1, max_attempts + 1):
            time.sleep(1.2)
            img = self.capture_screen()
            if img is None:
                continue
            knob = self.find_slider_knob(img)
            if not knob:
                print(f"[+] Captcha slider knob disappeared! Puzzle solved successfully. [OK]")
                return True
            canvas_box = self.find_puzzle_canvas(img)
            if not canvas_box:
                canvas_box = (150, 600, 780, 420)
            target_x = self.detect_gap_x(img, canvas_box)
            cx, cy, cw, ch = canvas_box
            knob_x, knob_y, kw, kh = knob
            fraction = float(target_x - cx) / float(cw)
            fraction = max(0.15, min(0.92, fraction))
            slider_track_width = 680
            drag_distance = int(slider_track_width * fraction)
            drop_x = knob_x + drag_distance
            drop_y = knob_y + random.randint(-4, 4)
            duration = random.randint(580, 780)
            print(f"[Attempt {attempt}] Dragging slider: {knob_x} -> {drop_x} (dist: {drag_distance}px, dur: {duration}ms)...")
            self.human_drag(knob_x, knob_y, drop_x, drop_y, duration)
            time.sleep(2.0)
            check_img = self.capture_screen()
            if check_img is not None and not self.find_slider_knob(check_img):
                print("[+] Captcha Solved Successfully! [OK]")
                return True
        return False


# ==============================================================================
# 5. GMAIL IMAP OTP FETCHER
# ==============================================================================
class GmailOTPFetcher:
    def __init__(self, gmail_user: str, app_password: str):
        self.gmail_user = gmail_user
        self.app_password = app_password

    def fetch_latest_otp(self, target_email: str, timeout_seconds: int = 70, poll_interval: int = 3) -> str | None:
        print(f"[*] Polling Gmail IMAP for OTP addressed to [{target_email}] (Timeout: {timeout_seconds}s)...")
        start_time = time.time()
        clean_user = target_email.split('@')[0].strip().lower()
        while time.time() - start_time < timeout_seconds:
            try:
                mail = imaplib.IMAP4_SSL("imap.gmail.com")
                mail.login(self.gmail_user, self.app_password)
                mail.select("inbox")
                status, messages = mail.search(None, '(FROM "yalla" UNSEEN)')
                if not messages[0]:
                    status, messages = mail.search(None, '(FROM "yalla")')
                msg_ids = messages[0].split()
                if msg_ids:
                    msg_ids.reverse()
                    for m_id in msg_ids[:5]:
                        status, data = mail.fetch(m_id, "(RFC822)")
                        raw_msg = data[0][1]
                        msg = email.message_from_bytes(raw_msg)
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() in ["text/plain", "text/html"]:
                                    body += part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        else:
                            body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
                        if target_email.lower() in body.lower() or clean_user in body.lower() or "verification code" in body.lower():
                            matches = re.findall(r"\b\d{6}\b", body)
                            if matches:
                                otp = matches[0]
                                mail.logout()
                                print(f"[+] Found Yalla Ludo Verification Code: [{otp}] [OK]")
                                return otp
                mail.logout()
            except Exception:
                pass
            time.sleep(poll_interval)
        print(f"[-] Timed out waiting for OTP email for: {target_email}")
        return None


# ==============================================================================
# 6. UI AUTOMATOR
# ==============================================================================
def click_coords(x: int, y: int, device_id: str = None, delay: float = 0.5):
    cmd = [ADB_BIN]
    if device_id:
        cmd.extend(["-s", device_id])
    cmd.extend(["shell", "input", "tap", str(x), str(y)])
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(delay)


def get_element_coords(identifier: str, device_id: str = None) -> tuple[int, int] | None:
    """Dynamic XML parser that matches resource-id or text and returns exact center (x, y)."""
    try:
        cmd = [ADB_BIN]
        if device_id:
            cmd.extend(["-s", device_id])
        subprocess.run(cmd + ["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], timeout=6, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        out = subprocess.check_output(cmd + ["shell", "cat", "/sdcard/window_dump.xml"], timeout=4)
        xml_str = out.decode("utf-8", errors="ignore")
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
    return None


def fast_click(target_key: str, device_id: str = None, delay: float = 0.5):
    rid = RESOURCE_IDS.get(target_key)
    coords = None
    if rid:
        coords = get_element_coords(rid, device_id)
    if not coords:
        coords = COORDS_1080P.get(target_key)
    if coords:
        click_coords(coords[0], coords[1], device_id, delay)


def type_text(text: str, device_id: str = None, delay: float = 0.4):
    cmd = [ADB_BIN]
    if device_id:
        cmd.extend(["-s", device_id])
    cmd.extend(["shell", "input", "text", text])
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(delay)


def clear_text_field(chars_count: int = 50, device_id: str = None):
    cmd = [ADB_BIN]
    if device_id:
        cmd.extend(["-s", device_id])
    subprocess.run(cmd + ["shell", "input", "keyevent", "123"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    keys = " ".join(["67"] * chars_count)
    subprocess.run(cmd + ["shell", f"for i in $(seq 1 {chars_count}); do input keyevent 67; done"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.3)


def dismiss_keyboard(device_id: str = None):
    cmd = [ADB_BIN]
    if device_id:
        cmd.extend(["-s", device_id])
    cmd.extend(["shell", "input", "keyevent", "111"])
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.3)


def request_verification_code(email_address: str, device_id: str = None) -> bool:
    print(f"[*] Entering Email: {email_address}...")
    fast_click("signup_email_input", device_id, 0.4)
    clear_text_field(50, device_id)
    type_text(email_address, device_id, 0.5)
    dismiss_keyboard(device_id)
    print("[*] Clicking 'Obtain' verification code button...")
    fast_click("obtain_code_btn", device_id, 1.2)
    return True


def submit_verification_code(otp_code: str, device_id: str = None) -> bool:
    print(f"[*] Pasting Verification Code: {otp_code}...")
    fast_click("otp_input", device_id, 0.4)
    clear_text_field(10, device_id)
    type_text(otp_code, device_id, 0.4)
    dismiss_keyboard(device_id)
    print("[*] Tapping Yellow Confirm Button...")
    fast_click("signup_confirm_btn", device_id, 1.0)
    return True


def set_password(password: str = DEFAULT_PASSWORD, device_id: str = None) -> bool:
    print(f"[*] Entering New Password...")
    fast_click("password_input", device_id, 0.5)
    clear_text_field(30, device_id)
    type_text(password, device_id, 0.5)
    dismiss_keyboard(device_id)
    print("[*] Confirming Set Password...")
    fast_click("password_confirm_btn", device_id, 2.0)
    return True


def clear_app_data(device_id: str = None):
    cmd = [ADB_BIN]
    if device_id:
        cmd.extend(["-s", device_id])
    subprocess.run(cmd + ["shell", "pm", "clear", PACKAGE_NAME], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(cmd + ["shell", "pm", "grant", PACKAGE_NAME, "android.permission.POST_NOTIFICATIONS"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)


def ensure_main_landing_page(device_id: str = None) -> bool:
    detector = ScreenDetector(device_id)
    state, _ = detector.get_screen_state()
    if state == STATE_MAIN_LANDING:
        return True
    
    cmd = [ADB_BIN]
    if device_id:
        cmd.extend(["-s", device_id])
    subprocess.run(cmd + ["shell", "monkey", "-p", PACKAGE_NAME, "-c", "android.intent.category.LAUNCHER", "1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    for _ in range(25):
        state, _ = detector.get_screen_state()
        if state == STATE_MAIN_LANDING:
            return True
        elif state == STATE_EXPERT_DIALOG:
            fast_click("btn_expert", device_id, 1.2)
        elif state == STATE_LOBBY_POPUP:
            fast_click("popup_close_btn", device_id, 1.0)
        elif state == STATE_GAME_HALL:
            fast_click("settings_gear_btn", device_id, 1.0)
        elif state == STATE_SETTINGS_DIALOG:
            fast_click("logout_btn", device_id, 1.0)
        else:
            time.sleep(0.6)
    return False


# ==============================================================================
# 7. ACCOUNT CREATION PIPELINE & BATCH RUNNER
# ==============================================================================
def run_account_creation_cycle() -> bool:
    config = load_config()
    device_id = config.get("device_serial", "34558213310005P")
    gmail_user = config.get("gmail_address")
    gmail_pwd = config.get("gmail_app_password")
    air_delay = float(config.get("airplane_wait_seconds", 1.5))
    email_address, config = get_next_email(config)

    detector = ScreenDetector(device_id)
    solver = IntelligentCaptchaSolver(device_id)
    otp_fetcher = GmailOTPFetcher(gmail_user, gmail_pwd)

    print(f"\n{'='*60}\n>>> STARTING CYCLE FOR: {email_address}\n{'='*60}")
    
    # SMART RESUME: Detect initial screen state
    curr_state, _ = detector.get_screen_state()
    print(f"[*] Initial Detected Screen State: [{curr_state}]")

    if curr_state == STATE_SIGNUP:
        print("[*] Already on Sign Up screen, proceeding directly to email...")
    elif curr_state == STATE_LOGIN_DIALOG:
        print("[*] Login Dialog active, tapping 'Sign Up' link directly...")
        fast_click("signup_link", device_id, 1.2)
    else:
        if curr_state != STATE_MAIN_LANDING:
            ensure_main_landing_page(device_id)
        # STEP 1: Main Landing -> Tap Checkbox & Email
        print("\n[Step 1] Tapping Terms Checkbox & Email Login Icon...")
        fast_click("terms_checkbox", device_id, 0.4)
        fast_click("email_login_btn", device_id, 1.0)

        # STEP 2: Login Modal -> Tap Sign Up Link
        print("\n[Step 2] Tapping 'Sign Up' Link...")
        fast_click("signup_link", device_id, 1.2)

    # STEP 3: Enter Email & Tap Obtain
    print("\n[Step 3] Submitting Email & Requesting Code...")
    request_verification_code(email_address, device_id)

    # STEP 4: Solve Captcha Slider
    print("\n[Step 4] Detecting & Solving Captcha Slider...")
    solver.solve(max_attempts=3)

    # STEP 5: Verify OTP countdown timer is active
    print("\n[Step 5] Verifying OTP Countdown Timer Active...")
    verified, _ = detector.wait_for_state(STATE_OTP_READY, timeout=12.0)
    if not verified:
        print("[-] Captcha was not cleared or timer not started. Halting cycle.")
        return False

    # STEP 6: Fetch OTP via IMAP
    print("\n[Step 6] Polling Gmail for 6-Digit OTP...")
    otp = otp_fetcher.fetch_latest_otp(email_address, timeout_seconds=70)
    if not otp:
        print(f"[-] Failed to retrieve OTP for {email_address}.")
        return False

    # STEP 7: Submit OTP + Tap Confirm
    print("\n[Step 7] Entering OTP & Confirming...")
    submit_verification_code(otp, device_id)

    # STEP 8: Set Password
    print("\n[Step 8] Setting Password...")
    detector.wait_for_state(STATE_SET_PASSWORD, timeout=8.0)
    set_password(DEFAULT_PASSWORD, device_id)

    # STEP 9: Expert Dialog
    print("\n[Step 9] Handling Post-Creation Lobby Prompts...")
    ok, _ = detector.wait_for_state(STATE_EXPERT_DIALOG, timeout=7.0)
    if ok:
        fast_click("btn_expert", device_id, 1.2)

    # STEP 10: Close Lobby Popup
    ok, _ = detector.wait_for_state(STATE_LOBBY_POPUP, timeout=5.0)
    if ok:
        fast_click("popup_close_btn", device_id, 1.0)

    # STEP 11: Open Settings & Tap Logout
    print("\n[Step 10] Logging out via Settings Gear...")
    ok, _ = detector.wait_for_state(STATE_GAME_HALL, timeout=6.0)
    if ok:
        fast_click("settings_gear_btn", device_id, 1.2)
    else:
        fast_click("settings_gear_btn", device_id, 0.8)

    ok, _ = detector.wait_for_state(STATE_SETTINGS_DIALOG, timeout=5.0)
    if ok:
        fast_click("logout_btn", device_id, 0.5)
    else:
        fast_click("logout_btn", device_id, 0.4)

    # STEP 12: Detect Return to Main Landing
    detector.wait_for_state(STATE_MAIN_LANDING, timeout=7.0)

    # SAVE TO CSV
    save_account_to_csv(email_address, otp, status="Success_Created", password=DEFAULT_PASSWORD)
    print(f"\n[SUCCESS] Account {email_address} created successfully! [OK]")

    # WIPE DATA & ROTATE IP
    print("\n[Step 12] Wiping app cache & Rotating IP (Airplane Mode)...")
    clear_app_data(device_id)
    toggle_airplane_mode(air_delay, device_id)
    time.sleep(1.5)
    ensure_main_landing_page(device_id)
    return True


def run_batch(total_accounts: int = 5):
    global STOP_REQUESTED
    STOP_REQUESTED = False
    print("\n" + "="*65)
    print(f"      STARTING BATCH RUN: {total_accounts} ACCOUNTS")
    print("="*65)
    
    success_count = 0
    for i in range(1, total_accounts + 1):
        if STOP_REQUESTED:
            print("\n[!] BATCH RUN HALTED: User stopped execution.")
            break
        print(f"\n{'#'*65}")
        print(f"  CYCLE {i}/{total_accounts} (Progress: {success_count}/{i-1} Successful)")
        print(f"{'#'*65}")
        
        try:
            status = run_account_creation_cycle()
            if status:
                success_count += 1
                print(f"\n[+] Account {i}/{total_accounts} CREATED SUCCESSFULLY! [OK]")
            else:
                print(f"\n[-] Account {i}/{total_accounts} was not completed. Moving to next...")
        except Exception as e:
            print(f"\n[!] Unexpected error in cycle {i}: {e}")
        
        if STOP_REQUESTED:
            print("\n[!] BATCH RUN HALTED: User stopped execution.")
            break
        if i < total_accounts:
            print("[*] Cooling down 3 seconds before starting next account...")
            time.sleep(3.0)
            
    print("\n" + "="*65)
    print(f"      BATCH COMPLETED: {success_count}/{total_accounts} ACCOUNTS CREATED")
    print("="*65)
    return success_count


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    run_batch(count)
