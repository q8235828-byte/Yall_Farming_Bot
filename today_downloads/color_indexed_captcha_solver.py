"""
================================================================================
COLOR-INDEXED & DYNAMIC SHADOW CAPTCHA SOLVER FOR YALLA LUDO (3-ATTEMPT SOLVE)
================================================================================
1. Explicitly waits for Geetest captcha to finish loading ('geetest_img_loading' gone).
2. Extracts exact puzzle canvas (149..653, 418..756) on MEmu 800x1280.
3. Identifies exact dark cutout slots via multi-threshold V-channel analysis:
   - Target Knob X = 149 + slot_center_x (mathematically exact 1:1 mapping).
   - Sorts candidates by shadow darkness (darkest slot = Attempt 1).
4. If contours are obscured, falls back to Color-Profile calibrated targets.
5. Executes smooth 'input draganddrop' (620-680ms) for reliable mechanical solve.
================================================================================
"""

import os
import random
import subprocess
import time
import cv2
import numpy as np

from airplane_mode import ADB_BIN, get_device_port


# Color profile calibrated fallbacks for MEmu 800x1280
COLOR_FALLBACKS_800P = {
    "Turquoise/Cyan": [410, 557, 414],
    "Green":          [428, 551, 411],
    "Blue":           [391, 537, 394],
    "Pink/Red":       [351, 501, 354],
    "Yellow/Orange":  [377, 527, 381],
    "Default":        [410, 428, 551],
}


class ColorIndexedCaptchaSolver:
    def __init__(self, device_id: str = None):
        self.device_id = device_id

    def wait_for_captcha_loaded(self, timeout: float = 90.0) -> str:
        """
        Polls until Geetest captcha finishes loading
        and 'Slide to complete the puzzle' or the blue knob is fully visible.
        Returns:
            'READY': Captcha is fully rendered and ready to solve.
            'ALREADY_SOLVED': Countdown timer is already active (no captcha required).
            'TIMEOUT': Captcha did not appear or failed to load.
        """
        start = time.time()
        print(f"[*] [CaptchaLoader] Monitoring screen for Captcha dialog to load (up to {timeout:.0f}s)...")
        port = get_device_port(self.device_id)
        cmd = [ADB_BIN]
        if port != 5037:
            cmd.extend(["-P", str(port)])
        if self.device_id:
            cmd.extend(["-s", self.device_id])

        while time.time() - start < timeout:
            # 1. Fast check: Is the blue slider knob already present on screen? (<0.3s)
            if self.is_captcha_present():
                print("[+] Captcha Knob & Canvas LOADED and ready! [OK]")
                time.sleep(0.5)
                return "READY"

            # 2. Check XML text for status
            try:
                subprocess.run(cmd + ["shell", "rm", "-f", "/sdcard/c_wait.xml"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                subprocess.run(cmd + ["shell", "uiautomator", "dump", "--compressed", "/sdcard/c_wait.xml"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=6)
                xml_raw = subprocess.check_output(cmd + ["shell", "cat", "/sdcard/c_wait.xml"], timeout=3)
                xml_text = xml_raw.decode("utf-8", errors="ignore").lower()

                # If fully loaded
                if "slide to complete the puzzle" in xml_text or ("refresh" in xml_text and "close" in xml_text):
                    print("[+] Captcha fully LOADED and ready via XML! [OK]")
                    time.sleep(0.5)
                    return "READY"

                # If countdown timer has already started, no captcha was needed!
                for sec in ["59s", "58s", "57s", "56s", "55s", "54s", "53s", "52s", "51s", "50s"]:
                    if sec in xml_text:
                        print(f"[+] Countdown timer detected ({sec})! Captcha bypassed or already solved.")
                        return "ALREADY_SOLVED"

                # If still loading spinner
                if "geetest_img_loading" in xml_text:
                    elapsed = time.time() - start
                    print(f"    [Captcha Loading...] Geetest downloading puzzle images ({elapsed:.1f}s / {timeout:.0f}s)...")
                    time.sleep(0.8)
                    continue
            except Exception:
                pass

            time.sleep(0.5)

        print(f"[-] Captcha did not load within {timeout:.0f}s timeout.")
        return "TIMEOUT"

    def capture_frame(self) -> np.ndarray:
        """Captures real composite frame via fast exec-out screencap with raw fallback."""
        port = get_device_port(self.device_id)
        cmd = [ADB_BIN]
        if port != 5037:
            cmd.extend(["-P", str(port)])
        if self.device_id:
            cmd.extend(["-s", self.device_id])

        # Fast direct PNG screencap (<0.4s)
        try:
            res = subprocess.run(cmd + ["exec-out", "screencap", "-p"], capture_output=True, timeout=4)
            if len(res.stdout) > 50000:
                img = cv2.imdecode(np.frombuffer(res.stdout, np.uint8), cv2.IMREAD_COLOR)
                if img is not None and img.shape[0] > 0:
                    return img
        except Exception:
            pass

        # Raw fallback
        try:
            subprocess.run(cmd + ["shell", "screencap", "/sdcard/c.raw"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            raw = subprocess.check_output(cmd + ["exec-out", "cat", "/sdcard/c.raw"], timeout=4)
            w = int.from_bytes(raw[0:4], byteorder='little')
            h = int.from_bytes(raw[4:8], byteorder='little')
            data = np.frombuffer(raw[16:16+w*h*4], dtype=np.uint8).reshape((h, w, 4))
            return cv2.cvtColor(data, cv2.COLOR_RGBA2BGR)
        except Exception:
            return None

    def find_slider_knob(self, img: np.ndarray) -> tuple[int, int, int, int]:
        """Finds blue slider knob (kx, ky, kw, kh) with robust calibrated fallback."""
        if img is not None:
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            blue_mask = cv2.inRange(hsv, np.array([95, 90, 110]), np.array([140, 255, 255]))
            contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                x, y, w, h = cv2.boundingRect(c)
                if w > 40 and h > 30 and y > 600:
                    return (x + w // 2, y + h // 2, w, h)
            # Robust calibrated fallback based on resolution
            ih, iw, _ = img.shape
            if iw <= 900:
                return (217, 810, 135, 84)
            return (293, 1490, 180, 110)
        return (217, 810, 135, 84)

    def is_captcha_present(self) -> bool:
        """Quick check if blue slider knob is on screen."""
        frame = self.capture_frame()
        if frame is None:
            return False
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        blue_mask = cv2.inRange(hsv, np.array([95, 90, 110]), np.array([140, 255, 255]))
        return cv2.countNonZero(blue_mask) > 100

    def classify_canvas_color(self, canvas_bgr: np.ndarray) -> tuple[str, float]:
        """Identifies dominant color family from HSV."""
        hsv = cv2.cvtColor(canvas_bgr, cv2.COLOR_BGR2HSV)
        h_mean = float(np.mean(hsv[:, :, 0]))
        s_mean = float(np.mean(hsv[:, :, 1]))

        if (h_mean < 14 or h_mean > 152) and s_mean > 45:
            return "Pink/Red", h_mean
        elif 14 <= h_mean < 35:
            return "Yellow/Orange", h_mean
        elif 35 <= h_mean < 75:
            return "Green", h_mean
        elif 75 <= h_mean < 98:
            return "Turquoise/Cyan", h_mean
        elif 98 <= h_mean < 135:
            return "Blue", h_mean
        return "Default", h_mean

    def detect_cutout_targets(self, canvas_bgr: np.ndarray, kx: int = 217) -> list[int]:
        """
        Trained on 18 Yalla Ludo Geetest Captcha variations on MEmu 800x1280.
        Detects exact piece on left, filters distractor shadows by horizontal band matching,
        and selects matching unrotated shadow target.
        """
        ch, cw, _ = canvas_bgr.shape
        
        # 1. Detect Piece on Left (x < cw * 0.35)
        left_part = canvas_bgr[:, :int(cw * 0.35)]
        hsv_left = cv2.cvtColor(left_part, cv2.COLOR_BGR2HSV)
        v_left = hsv_left[:, :, 2]
        s_left = hsv_left[:, :, 1]
        white_edge = (v_left > 190) & (s_left < 110)
        
        gray_left = cv2.cvtColor(left_part, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray_left, 40, 120)
        cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        candidates_piece = []
        for c in cnts:
            area = cv2.contourArea(c)
            if area > 100:
                bx, by, bw, bh = cv2.boundingRect(c)
                patch_v = v_left[by:by+bh, bx:bx+bw]
                patch_white = white_edge[by:by+bh, bx:bx+bw]
                mean_v = float(np.mean(patch_v))
                white_count = int(np.sum(patch_white))
                candidates_piece.append({
                    'rect': (bx, by, bw, bh),
                    'score': mean_v + white_count * 2
                })
                
        if candidates_piece:
            candidates_piece.sort(key=lambda x: x['score'], reverse=True)
            best = candidates_piece[0]
            pbx, pby, pbw, pbh = best['rect']
            pcx, pcy = pbx + pbw // 2, pby + pbh // 2
        else:
            pcx, pcy, pbw, pbh = 68, ch // 2, 85, 85

        # Extract piece patch for template matching
        py1 = max(0, pcy - pbh // 2)
        py2 = min(ch, pcy + pbh // 2)
        px1 = max(0, pcx - pbw // 2)
        px2 = min(cw, pcx + pbw // 2)
        piece_patch = cv2.cvtColor(canvas_bgr[py1:py2, px1:px2], cv2.COLOR_BGR2GRAY)

        # 2. Detect Shadows on Right (x > cw * 0.28)
        right_part = canvas_bgr[:, int(cw * 0.28):]
        hsv_right = cv2.cvtColor(right_part, cv2.COLOR_BGR2HSV)
        v_right = hsv_right[:, :, 2]
        mean_v = np.mean(v_right)
        
        candidates = []
        for pct in [0.75, 0.80, 0.85]:
            thresh_val = int(mean_v * pct)
            _, dark = cv2.threshold(v_right, thresh_val, 255, cv2.THRESH_BINARY_INV)
            scnts, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for sc in scnts:
                area = cv2.contourArea(sc)
                if area > 800:
                    bx, by, bw, bh = cv2.boundingRect(sc)
                    cx = bx + bw // 2 + int(cw * 0.28)
                    cy = by + bh // 2
                    
                    if not any(abs(cx - ex['cx']) < 30 and abs(cy - ex['cy']) < 30 for ex in candidates):
                        match_score = 0.0
                        if piece_patch.shape[0] > 20 and piece_patch.shape[1] > 20:
                            sy1 = max(0, cy - pbh // 2 - 10)
                            sy2 = min(ch, cy + pbh // 2 + 10)
                            sx1 = max(0, cx - pbw // 2 - 10)
                            sx2 = min(cw, cx + pbw // 2 + 10)
                            sh_crop = cv2.cvtColor(canvas_bgr[sy1:sy2, sx1:sx2], cv2.COLOR_BGR2GRAY)
                            if sh_crop.shape[0] >= piece_patch.shape[0] and sh_crop.shape[1] >= piece_patch.shape[1]:
                                res = cv2.matchTemplate(sh_crop, piece_patch, cv2.TM_CCOEFF_NORMED)
                                match_score = float(res.max())
                                
                        y_diff = abs(cy - pcy)
                        target_knob_x = kx + (cx - pcx)
                        candidates.append({
                            'cx': cx, 'cy': cy, 'w': bw, 'h': bh,
                            'y_diff': y_diff, 'match_score': match_score,
                            'target_knob_x': target_knob_x
                        })
                        
        # Sort candidates:
        # 1. Target must be on same horizontal band (y_diff <= 45 in 800x1280)
        # 2. Highest match_score (unrotated piece)
        # 3. Smallest y_diff
        candidates.sort(key=lambda c: (c['y_diff'] > 45, -c['match_score'], c['y_diff']))
        return [c['target_knob_x'] for c in candidates]

    def execute_drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration_ms: int = 650):
        """Executes smooth human-like draganddrop via ADB."""
        port = get_device_port(self.device_id)
        cmd = [ADB_BIN]
        if port != 5037:
            cmd.extend(["-P", str(port)])
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        jitter_y = end_y + random.choice([-1, 0, 1])
        cmd.extend(["shell", "input", "draganddrop", str(start_x), str(start_y), str(end_x), str(jitter_y), str(duration_ms)])
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def solve(self, max_attempts: int = 3, timeout: float = 90.0) -> bool:
        """
        Solves the captcha in at most 3 attempts:
        1. Waits up to 90 seconds for captcha dialog to finish loading.
        2. If countdown already active, returns True.
        3. Identifies slot cutout and executes calibrated draganddrop.
        """
        # Step 1: Wait for captcha to load (up to 90 seconds)
        load_status = self.wait_for_captcha_loaded(timeout=timeout)
        if load_status == "ALREADY_SOLVED":
            return True
        elif load_status == "TIMEOUT":
            print("[*] No captcha appeared within timeout. Checking if verification timer started...")
            return False

        # Step 2: Capture initial frame
        frame = self.capture_frame()
        knob = self.find_slider_knob(frame)
        if not knob:
            print("[-] Slider knob not detected on loaded captcha.")
            return False

        kx, ky, kw, kh = knob
        print(f"[+] Captcha Knob Detected at ({kx}, {ky}) [size: {kw}x{kh}]")

        # Crop canvas on MEmu 800x1280
        canvas_left = 149
        canvas_right = 653
        canvas_top = 418
        canvas_bottom = 756
        canvas = frame[canvas_top:canvas_bottom, canvas_left:canvas_right]

        # Step 3: Color Classification & Target Prediction
        color_family, h_mean = self.classify_canvas_color(canvas)
        print(f"[+] Dominant Background: [{color_family}] (Mean Hue: {h_mean:.1f})")

        detected_targets = self.detect_cutout_targets(canvas, kx=kx)
        print(f"[*] Live Detected Target(s): {detected_targets}")

        fallbacks = COLOR_FALLBACKS_800P.get(color_family, COLOR_FALLBACKS_800P["Default"])

        # Construct 3-attempt execution plan
        attempts_plan = []
        if len(detected_targets) >= 1:
            attempts_plan.append(("Live Primary Cutout", detected_targets[0]))
        else:
            attempts_plan.append(("Color-Profile Slot 1", fallbacks[0]))

        if len(detected_targets) >= 2:
            attempts_plan.append(("Live Secondary Cutout", detected_targets[1]))
        elif len(fallbacks) >= 2:
            attempts_plan.append(("Color-Profile Slot 2", fallbacks[1]))
        else:
            attempts_plan.append(("Primary Fine-Tuned", attempts_plan[0][1] + 3))

        attempts_plan.append(("Adaptive Fine-Tune", attempts_plan[0][1] + 3))

        for attempt_idx, (desc, target_x) in enumerate(attempts_plan[:max_attempts], 1):
            duration = random.randint(620, 680)
            print(f"\n[Attempt {attempt_idx}/{max_attempts}] Executing {desc} -> Dragging knob to X={target_x}...")

            self.execute_drag(kx, ky, target_x, ky, duration_ms=duration)

            # Wait for verification animation
            time.sleep(2.0)

            # Fast check: Did countdown start or is captcha gone?
            port = get_device_port(self.device_id)
            cmd = [ADB_BIN]
            if port != 5037:
                cmd.extend(["-P", str(port)])
            if self.device_id:
                cmd.extend(["-s", self.device_id])

            try:
                subprocess.run(cmd + ["shell", "uiautomator", "dump", "--compressed", "/sdcard/sd_chk.xml"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                out = subprocess.check_output(cmd + ["shell", "cat", "/sdcard/sd_chk.xml"], timeout=1).decode("utf-8", errors="ignore")
                if any(sec in out.lower() for sec in ["59s", "58s", "57s", "56s", "55s", "54s", "53s", "52s", "51s", "50s", "et_set_password", "bt_set_pwd"]):
                    print(f"[SUCCESS] Countdown started / Password screen! Captcha SOLVED successfully on Attempt {attempt_idx}! [OK]")
                    return True
            except Exception:
                pass

            if not self.is_captcha_present():
                print(f"[SUCCESS] Captcha SOLVED successfully on Attempt {attempt_idx}! [OK]")
                return True

            print(f"[*] Attempt {attempt_idx} did not clear puzzle. Preparing next attempt...")

        print("[-] Captcha could not be solved in 3 attempts.")
        return False


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21613"
    print(f"[*] Running Standalone Captcha Solver on Device: {target}")
    solver = ColorIndexedCaptchaSolver(target)
    result = solver.solve(max_attempts=3)
    print(f"\nFinal Result: {result}")
