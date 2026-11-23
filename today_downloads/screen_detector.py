"""
================================================================================
YALLA LUDO HIGH SPEED XML & CV SCREEN STATE DETECTOR
================================================================================
Identifies precise UI states in under 200ms using instant hierarchy mapping:
- MAIN_LANDING: Welcome screen (Email Login / Facebook buttons)
- LOGIN_DIALOG: Email/Password login modal with 'Sign Up' link
- SIGNUP_SCREEN: Registration form (Email + Verification Code fields)
- CAPTCHA_PUZZLE: Slider puzzle dialog active
- OTP_INPUT_READY: Countdown active (e.g., 59s, 58s)
- SET_PASSWORD: Set password screen
- EXPERT_DIALOG: "I'm expert" onboarding choice modal
- GAME_HALL: Inside game lobby
- SETTINGS_DIALOG: Settings menu with Logout button
================================================================================
"""

import os
import subprocess
import time
import xml.etree.ElementTree as ET
import cv2
import numpy as np

from airplane_mode import ADB_BIN, get_device_port

STATE_MAIN_LANDING = "MAIN_LANDING"
STATE_LOGIN_DIALOG = "LOGIN_DIALOG"
STATE_SIGNUP = "SIGNUP_SCREEN"
STATE_CAPTCHA = "CAPTCHA_PUZZLE"
STATE_OTP_READY = "OTP_INPUT_READY"
STATE_SET_PASSWORD = "SET_PASSWORD"
STATE_EXPERT_DIALOG = "EXPERT_DIALOG"
STATE_LOBBY_POPUP = "LOBBY_POPUP"
STATE_GAME_HALL = "GAME_HALL"
STATE_SETTINGS_DIALOG = "SETTINGS_DIALOG"
STATE_UNKNOWN = "UNKNOWN"


class ScreenDetector:
    def __init__(self, device_id: str = None):
        self.device_id = device_id

    def dump_ui_tree(self) -> ET.Element | None:
        """Dumps UI hierarchy tree fast using standard XML dump with auto-wakeup."""
        port = get_device_port(self.device_id)
        base = [ADB_BIN]
        if port != 5037:
            base.extend(["-P", str(port)])
        if self.device_id:
            base.extend(["-s", self.device_id])

        dev_tag = self.device_id.replace(":", "_").replace(".", "_") if self.device_id else "def"
        dump_path = f"/sdcard/sd_dump_{dev_tag}.xml"
        for attempt in range(2):
            try:
                if attempt > 0:
                    subprocess.run(base + ["shell", "input", "keyevent", "224"], timeout=2)
                subprocess.run(base + ["shell", "rm", "-f", dump_path], timeout=2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(base + ["shell", "uiautomator", "dump", "--compressed", dump_path],
                               timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                out = subprocess.check_output(base + ["shell", "cat", dump_path], timeout=3)
                text = out.decode("utf-8", errors="ignore")
                start = text.find("<?xml")
                if start != -1:
                    return ET.fromstring(text[start:])
            except Exception:
                time.sleep(0.2)
        return None

    def get_screen_state(self) -> tuple[str, dict]:
        """
        Ultra-fast Unambiguous Screen State Classifier (takes ~200ms).
        Matches resource-ids, texts, and dialog elements.
        """
        root = self.dump_ui_tree()
        rids = {}
        texts = []
        if root is not None:
            for node in root.iter("node"):
                rid = node.get("resource-id", "")
                bounds = node.get("bounds", "")
                text = node.get("text", "")
                if text:
                    texts.append(text)
                if rid:
                    rids[rid] = {"text": text, "bounds": bounds, "node": node}

        # 0. Check for Captcha slider popup
        if any("puzzle" in t.lower() or "slide to" in t.lower() for t in texts):
            return STATE_CAPTCHA, {"text": "puzzle"}

        # 1. Set Password Screen (Highest priority dialog after verification code)
        if "com.yalla.yallagames:id/bt_set_pwd" in rids or "com.yalla.yallagames:id/et_set_password1" in rids or any("Password Requirements" in t or "must meet the following" in t for t in texts):
            return STATE_SET_PASSWORD, rids.get("com.yalla.yallagames:id/bt_set_pwd", {})

        # 2. Sign Up Dialog (Check for OTP countdown or active input)
        if "com.yalla.yallagames:id/et_verification_code_sign" in rids:
            obtain_info = rids.get("com.yalla.yallagames:id/bt_get_verification_code_sign", {})
            obtain_text = obtain_info.get("text", "")
            # Countdown timer running?
            if "s" in obtain_text.lower() and any(char.isdigit() for char in obtain_text):
                return STATE_OTP_READY, {"countdown": obtain_text, "info": rids["com.yalla.yallagames:id/et_verification_code_sign"]}
            return STATE_SIGNUP, rids["com.yalla.yallagames:id/et_verification_code_sign"]

        # 3. Login Dialog (Phone/Password modal with "Sign Up" link)
        if "com.yalla.yallagames:id/tv_sign_up" in rids or "com.yalla.yallagames:id/bt_login" in rids:
            return STATE_LOGIN_DIALOG, rids.get("com.yalla.yallagames:id/tv_sign_up", {})

        # 4. Expert Dialog ("I'm expert" choice after registration)
        if "com.yalla.yallagames:id/btn_yes" in rids or any("expert" in t.lower() for t in texts):
            return STATE_EXPERT_DIALOG, rids.get("com.yalla.yallagames:id/btn_yes", {})

        # 5. Settings Dialog
        if "com.yalla.yallagames:id/bt_cancellation" in rids:
            return STATE_SETTINGS_DIALOG, rids["com.yalla.yallagames:id/bt_cancellation"]

        # 6. Lobby Reward / Daily Popup
        for cid in ["com.yalla.yallagames:id/iv_close", "com.yalla.yallagames:id/iv_week_close"]:
            if cid in rids:
                return STATE_LOBBY_POPUP, rids[cid]

        # 7. Game Hall (In-lobby home screen)
        if "com.yalla.yallagames:id/iv_setting" in rids or "com.yalla.yallagames:id/main_hall" in rids:
            return STATE_GAME_HALL, rids.get("com.yalla.yallagames:id/iv_setting", {})

        # 8. Main Landing Screen (Only if no overlay dialogs are open)
        if "com.yalla.yallagames:id/tv_fb_login" in rids or "com.yalla.yallagames:id/ll_email" in rids or "Login with Facebook" in texts:
            return STATE_MAIN_LANDING, rids.get("com.yalla.yallagames:id/ll_email", {})

        return STATE_UNKNOWN, {}

    def wait_for_state(self, target_state: str, timeout: float = 10.0, poll_interval: float = 0.5) -> tuple[bool, dict]:
        """Polls until screen reaches target state."""
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
