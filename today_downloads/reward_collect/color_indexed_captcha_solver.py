"""
================================================================================
COLOR-INDEXED & UNIVERSAL DYNAMIC GEOMETRIC CAPTCHA SOLVER FOR YALLA LUDO
================================================================================
Handles all GeeTest Captcha variants:
- Classic Jigsaw Puzzle (notches/tabs)
- Triangular / Arrow 3D Geometric Puzzles
- Star Geometric Puzzles (New Canvas with multi-shadow distractors)
- Hexagon / Glass Translucent Shapes

Key Principles:
1. Moving piece on the left is semi-transparent / glass with specular highlights.
   Detected via Canny + Sobel gradient magnitude with morphological closing.
2. The moving piece NEVER moves vertically (its Y coordinate is physically fixed).
   All true matching slots must satisfy |scy - pcy| <= 25px.
3. Shadows (cutouts) are dark regions on the right side.
   Distractors (like top/bottom off-axis shapes) are filtered by Y-alignment and aspect ratio.
4. Target Knob X is constrained to physical slider track (310..525).
5. Drag executed via human-like touch swipe (430-490ms), bypassing GeeTest bot detector.
================================================================================
"""

import os
import sys
import random
import subprocess
import time
import cv2
import numpy as np

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

try:
    from airplane_mode import ADB_BIN, get_device_port
except Exception:
    ADB_BIN = os.path.join(PARENT_DIR, "platform-tools", "adb.exe")
    def get_device_port(d): return 5037


# Color profile calibrated fallbacks for MEmu 800x1280
COLOR_FALLBACKS_800P = {
    "Turquoise/Cyan": [385, 535, 550, 407, 410],
    "Green":          [390, 465, 535, 550, 428],
    "Blue":           [370, 515, 552, 340, 391],
    "Pink/Red":       [355, 418, 545, 500, 351],
    "Yellow/Orange":  [377, 527, 465, 381],
    "Default":        [410, 535, 370, 550, 428],
}


class ColorIndexedCaptchaSolver:
    def __init__(self, device_id: str = None):
        self.device_id = device_id

    def wait_for_captcha_loaded(self, timeout: float = 90.0) -> str:
        """
        Polls until Geetest captcha finishes loading
        and 'Slide to complete the puzzle' or the blue knob is fully visible.
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
            # 1. Fast check: Is blue knob on screen?
            if self.is_captcha_present():
                print("[+] Captcha Knob & Canvas LOADED and ready! [OK]")
                time.sleep(0.5)
                return "READY"

            # 2. Check XML text
            try:
                subprocess.run(cmd + ["shell", "rm", "-f", "/sdcard/c_wait.xml"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                subprocess.run(cmd + ["shell", "uiautomator", "dump", "--compressed", "/sdcard/c_wait.xml"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=6)
                xml_raw = subprocess.check_output(cmd + ["shell", "cat", "/sdcard/c_wait.xml"], timeout=3)
                xml_text = xml_raw.decode("utf-8", errors="ignore").lower()

                if "slide to complete the puzzle" in xml_text or ("refresh" in xml_text and "close" in xml_text):
                    print("[+] Captcha fully LOADED and ready via XML! [OK]")
                    time.sleep(0.5)
                    return "READY"

                for sec in ["59s", "58s", "57s", "56s", "55s", "54s", "53s", "52s", "51s", "50s"]:
                    if sec in xml_text:
                        print(f"[+] Countdown timer detected ({sec})! Captcha bypassed or already solved.")
                        return "ALREADY_SOLVED"

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
        """Captures composite frame via fast exec-out screencap with raw fallback."""
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
        Universal Intelligent Cutout Detector for all GeeTest Captcha variants:
        - Classic Jigsaw Puzzles
        - Triangular / Arrow Geometric Puzzles
        - Star Geometric Puzzles (New Canvas with multi-shadow distractors)
        - Hexagon / Glass 3D Geometric Puzzles
        """
        ch, cw, _ = canvas_bgr.shape

        # Step 1: Dynamically find piece on left (supports glass & translucent shapes)
        left = canvas_bgr[:, :int(cw * 0.35)]
        gray_left = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)

        # Multi-scale Canny with morphological closing
        edges_left = cv2.Canny(gray_left, 30, 120)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        closed_edges = cv2.morphologyEx(edges_left, cv2.MORPH_CLOSE, kernel)
        dilated_edges = cv2.dilate(closed_edges, kernel, iterations=1)

        # Sobel gradient magnitude for specular glass highlights
        grad_x = cv2.Sobel(gray_left, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray_left, cv2.CV_32F, 0, 1, ksize=3)
        grad_mag = cv2.magnitude(grad_x, grad_y)
        grad_mag = cv2.normalize(grad_mag, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        _, thresh_grad = cv2.threshold(grad_mag, 35, 255, cv2.THRESH_BINARY)
        combined_left = cv2.bitwise_or(dilated_edges, thresh_grad)
        combined_left = cv2.morphologyEx(combined_left, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7)))

        cnts_left, _ = cv2.findContours(combined_left, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best_piece = None
        best_piece_score = -1
        pcx, pcy = int(cw * 0.14), ch // 2
        max_piece_area = 4000

        for sc in cnts_left:
            area = cv2.contourArea(sc)
            px, py, pw, ph = cv2.boundingRect(sc)
            if 30 <= pw <= 120 and 30 <= ph <= 120 and area > 400:
                aspect = pw / max(ph, 1)
                if 0.55 <= aspect <= 1.80 and (px + pw // 2) < cw * 0.30:
                    score = area - abs(1.0 - aspect) * 1000
                    if score > best_piece_score:
                        best_piece_score = score
                        best_piece = sc
                        pcx = px + pw // 2
                        pcy = py + ph // 2
                        max_piece_area = area

        if best_piece is not None:
            print(f"[+] Moving Piece Detected: Center=({pcx}, {pcy}), Area={max_piece_area:.0f}")
        else:
            print(f"[*] Piece edge faint, defaulting left center to ({pcx}, {pcy})")

        # Step 2: Multi-threshold search on right for dark cutout shadows
        v = cv2.cvtColor(canvas_bgr, cv2.COLOR_BGR2HSV)[:, :, 2]
        gray = cv2.cvtColor(canvas_bgr, cv2.COLOR_BGR2GRAY)
        mean_v = np.mean(v)
        mean_g = np.mean(gray)

        candidates = []
        for pct in [0.50, 0.58, 0.66, 0.74, 0.82, 0.90]:
            _, dark_v = cv2.threshold(v, int(mean_v * pct), 255, cv2.THRESH_BINARY_INV)
            _, dark_g = cv2.threshold(gray, int(mean_g * pct), 255, cv2.THRESH_BINARY_INV)
            dark = cv2.bitwise_or(dark_v, dark_g)
            dark_clean = cv2.morphologyEx(dark, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
            cnts_right, _ = cv2.findContours(dark_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for sc in cnts_right:
                area = cv2.contourArea(sc)
                if 500 < area < 16000:
                    sx, sy, sw, sh = cv2.boundingRect(sc)
                    # Filter out non-compact shapes (platforms, ledges, borders)
                    aspect = sw / max(sh, 1)
                    if not (0.50 <= aspect <= 1.85):
                        continue
                    if not (30 <= sw <= 125 and 30 <= sh <= 125):
                        continue
                    if sx <= cw * 0.20:
                        continue  # Must be on right side

                    scx, scy = sx + sw // 2, sy + sh // 2
                    ydiff = abs(scy - pcy)

                    # Sliding match: must align horizontally with moving piece
                    if ydiff <= 25:
                        delta_x = scx - pcx
                        target_knob_x = kx + delta_x

                        if 310 <= target_knob_x <= 525:
                            if not any(abs(target_knob_x - ex['target_knob_x']) < 10 for ex in candidates):
                                area_ratio = abs(area - max_piece_area) / max(max_piece_area, 1)
                                shape_score = 0.0
                                if best_piece is not None:
                                    try:
                                        shape_score = cv2.matchShapes(best_piece, sc, cv2.CONTOURS_MATCH_I1, 0.0) * 10.0
                                    except Exception:
                                        shape_score = 0.0

                                score = (ydiff * 3.5) + (area_ratio * 12.0) + shape_score
                                candidates.append({
                                    'target_knob_x': target_knob_x,
                                    'score': score,
                                    'ydiff': ydiff,
                                    'area': area
                                })

        # Dynamic relaxation fallback if no strict candidate found
        if not candidates:
            for pct in [0.65, 0.75, 0.85]:
                _, dark = cv2.threshold(v, int(mean_v * pct), 255, cv2.THRESH_BINARY_INV)
                cnts_right, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for sc in cnts_right:
                    area = cv2.contourArea(sc)
                    if 500 < area < 16000:
                        sx, sy, sw, sh = cv2.boundingRect(sc)
                        aspect = sw / max(sh, 1)
                        if 0.50 <= aspect <= 1.85 and sx > cw * 0.20:
                            scx, scy = sx + sw // 2, sy + sh // 2
                            ydiff = abs(scy - pcy)
                            delta_x = scx - pcx
                            target_knob_x = kx + delta_x
                            if 310 <= target_knob_x <= 525:
                                if not any(abs(target_knob_x - ex['target_knob_x']) < 10 for ex in candidates):
                                    candidates.append({
                                        'target_knob_x': target_knob_x,
                                        'score': ydiff * 3.0,
                                        'ydiff': ydiff,
                                        'area': area
                                    })

        candidates.sort(key=lambda c: (c['score'], c['ydiff']))
        targets = [c['target_knob_x'] for c in candidates]
        return targets

    def execute_drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration_ms: int = 650):
        """Executes smooth human-like draganddrop via ADB."""
        port = get_device_port(self.device_id)
        cmd = [ADB_BIN]
        if port != 5037:
            cmd.extend(["-P", str(port)])
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        jitter_y = end_y + random.choice([-1, 0, 1])
        cmd.extend(["shell", "input", "swipe", str(start_x), str(start_y), str(end_x), str(jitter_y), str(duration_ms)])
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def solve(self, max_attempts: int = 3, timeout: float = 90.0) -> bool:
        """
        Solves the captcha in at most 3 attempts:
        1. Waits up to 90 seconds for captcha dialog to finish loading.
        2. If countdown already active, returns True.
        3. Identifies slot cutout and executes calibrated touch swipe.
        """
        load_status = self.wait_for_captcha_loaded(timeout=timeout)
        if load_status == "ALREADY_SOLVED":
            return True
        elif load_status == "TIMEOUT":
            print("[*] No captcha appeared within timeout. Checking if verification timer started...")
            return False

        # Capture initial frame
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

        # Color Classification & Target Prediction
        color_family, h_mean = self.classify_canvas_color(canvas)
        print(f"[+] Dominant Background: [{color_family}] (Mean Hue: {h_mean:.1f})")

        detected_targets = self.detect_cutout_targets(canvas, kx=kx)
        print(f"[*] Live Detected Target(s): {detected_targets}")

        fallbacks = COLOR_FALLBACKS_800P.get(color_family, COLOR_FALLBACKS_800P["Default"])

        # Construct execution plan: try all live detected targets in order of confidence
        attempts_plan = []
        for i, target in enumerate(detected_targets):
            attempts_plan.append((f"Live Candidate {i+1}", target))

        # Add fine-tuned offsets if room allows
        if attempts_plan and len(attempts_plan) < max_attempts:
            best_x = attempts_plan[0][1]
            attempts_plan.append(("Fine-Tune (+3px)", best_x + 3))
            attempts_plan.append(("Fine-Tune (-3px)", best_x - 3))

        # Fallback to color profile if no candidates detected
        if not attempts_plan:
            for i, fb in enumerate(fallbacks[:max_attempts]):
                attempts_plan.append((f"Color-Profile Slot {i+1}", fb))

        for attempt_idx, (desc, target_x) in enumerate(attempts_plan[:max_attempts], 1):
            duration = random.randint(430, 490)
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
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21613"
    print(f"[*] Running Standalone Captcha Solver on Device: {target}")
    solver = ColorIndexedCaptchaSolver(target)
    result = solver.solve(max_attempts=3)
    print(f"\nFinal Result: {result}")
