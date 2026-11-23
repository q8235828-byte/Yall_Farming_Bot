import math
import os
import random
import subprocess
import time
import cv2
import numpy as np

from airplane_mode import ADB_BIN, get_device_port


class IntelligentCaptchaSolver:
    """
    Ultra-Fast Intelligent Slider Puzzle Captcha Solver for Yalla Ludo.
    Features:
    - Direct in-memory screencap (Zero disk I/O, under 200ms).
    - Auto-scales to ANY screen resolution (720p, 1080p, etc.).
    - High-speed human-like drag profile (550-700ms).
    - Multi-round strategy (up to 15 attempts).
    """

    def __init__(self, device_id: str = None, max_attempts: int = 15, attempts_per_round: int = 5):
        self.device_id = device_id
        self.max_attempts = max_attempts
        self.attempts_per_round = attempts_per_round

    def capture_screen(self) -> np.ndarray:
        """Captures screencap directly into memory without disk writes."""
        port = get_device_port(self.device_id)
        cmd = [ADB_BIN]
        if port != 5037:
            cmd.extend(["-P", str(port)])
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
        # Fallback to standard
        fallback_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captcha_screen.png")
        cmd2 = [ADB_BIN] + (["-P", str(port)] if port != 5037 else []) + (["-s", self.device_id] if self.device_id else []) + ["shell", "screencap", "-p", "/data/local/tmp/cap_temp.png"]
        subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        cmd3 = [ADB_BIN] + (["-P", str(port)] if port != 5037 else []) + (["-s", self.device_id] if self.device_id else []) + ["pull", "/data/local/tmp/cap_temp.png", fallback_path]
        subprocess.run(cmd3, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return cv2.imread(fallback_path)

    def get_slider_knob_pos(self, img: np.ndarray) -> tuple[int, int, int, int] | None:
        """Dynamically finds the blue slider knob (x, y, w, h) on ANY screen resolution."""
        ih, iw, _ = img.shape
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        blue_lower = np.array([95, 120, 120])
        blue_upper = np.array([135, 255, 255])
        blue_mask = cv2.inRange(hsv, blue_lower, blue_upper)
        contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        min_width = 50 if iw <= 720 else 80
        for c in contours:
            area = cv2.contourArea(c)
            if area > 400:
                x, y, w, h = cv2.boundingRect(c)
                if y > int(ih * 0.48) and w > min_width:
                    return (x + w // 2, y + h // 2, w, h)
        return None

    def is_captcha_present(self, img: np.ndarray = None) -> bool:
        if img is None:
            img = self.capture_screen()
        if img is None:
            return False
        return self.get_slider_knob_pos(img) is not None

    def detect_piece_center(self, canvas: np.ndarray) -> int:
        ch, cw, _ = canvas.shape
        gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 40, 120)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            area = cv2.contourArea(c)
            min_dim = 35 if cw <= 720 else 55
            if x < int(cw * 0.28) and w > min_dim and h > min_dim and area > 1200:
                return x + w // 2
        return int(cw * 0.133)

    def detect_slots(self, canvas: np.ndarray) -> list[int]:
        ch, cw, _ = canvas.shape
        hsv = cv2.cvtColor(canvas, cv2.COLOR_BGR2HSV)
        v_channel = hsv[:, :, 2]
        mean_v = np.mean(v_channel)

        _, dark_mask = cv2.threshold(v_channel, int(mean_v * 0.78), 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        slot_centers = []
        min_area = int(cw * ch * 0.012)
        max_area = int(cw * ch * 0.12)

        for c in contours:
            area = cv2.contourArea(c)
            x, y, cw_box, ch_box = cv2.boundingRect(c)
            center_x = x + cw_box // 2
            if min_area < area < max_area and cw_box > 30 and ch_box > 30 and center_x > int(cw * 0.28):
                slot_centers.append(center_x)

        slot_centers.sort()
        return slot_centers

    def execute_smooth_drag(self, start_x: int, start_y: int, end_x: int, end_y: int):
        duration = random.randint(580, 680) # Ultra-fast human duration
        jitter_y = end_y + random.choice([-1, 0, 1])
        port = get_device_port(self.device_id)
        cmd = [ADB_BIN]
        if port != 5037:
            cmd.extend(["-P", str(port)])
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend([
            "shell", "input", "draganddrop",
            str(start_x), str(start_y),
            str(end_x), str(jitter_y),
            str(duration)
        ])
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def solve(self) -> bool:
        # Priority inverted: Second slider is tried FIRST, first slider is tried SECOND
        strategy_plan = [
            (2, 6), (1, 0), (2, -6), (1, 6), (2, 12),
            (1, -12), (2, 0), (1, -6), (2, 4), (1, -4),
            (2, -4), (1, 8), (2, 8), (1, -8), (2, 2)
        ]

        total_plan = len(strategy_plan)
        current_round = 1

        # Wait for slider puzzle to animate onto screen (up to 6s)
        knob = None
        for _ in range(12):
            time.sleep(0.5)
            img = self.capture_screen()
            knob = self.get_slider_knob_pos(img)
            if knob:
                break

        if not knob:
            print("[-] Captcha was not detected on screen!")
            return False

        for attempt in range(1, self.max_attempts + 1):
            calc_round = ((attempt - 1) // self.attempts_per_round) + 1
            if calc_round > current_round:
                current_round = calc_round
                print(f"[!] Next 5 Attempts (Round {current_round})...")

            # Wait for knob to settle back at start position (left side)
            knob = None
            for _ in range(6):
                img = self.capture_screen()
                knob = self.get_slider_knob_pos(img)
                if knob and knob[0] < int(img.shape[1] * 0.35):
                    break
                time.sleep(0.5)

            if not knob:
                print(f"[SUCCESS] Captcha dialog cleared/solved! [OK]")
                return True

            kx, ky, kw, kh = knob
            iw = img.shape[1]

            canvas_left = max(kx - kw // 2, 15)
            canvas_right = min(iw - canvas_left, iw - 15)
            canvas_bottom = ky - int(kh * 1.1)
            canvas_height = int((canvas_right - canvas_left) * 0.70)
            canvas_top = max(canvas_bottom - canvas_height, 0)

            canvas = img[canvas_top:canvas_bottom, canvas_left:canvas_right]
            if canvas is None or canvas.size == 0:
                time.sleep(0.4)
                continue
            
            cw = canvas.shape[1]
            piece_x = self.detect_piece_center(canvas)
            slots = self.detect_slots(canvas)

            default_slot1_dist = int(cw * 0.414)
            default_slot2_dist = int(cw * 0.708)

            pref_slot, adaptive_offset = strategy_plan[(attempt - 1) % total_plan]

            if len(slots) >= 2:
                slot_idx = 1 if pref_slot == 2 else 0
                chosen_slot = slots[slot_idx]
                raw_dist = chosen_slot - piece_x
            elif len(slots) == 1:
                is_slot_2 = slots[0] > int(cw * 0.55)
                if (pref_slot == 2 and is_slot_2) or (pref_slot == 1 and not is_slot_2):
                    raw_dist = slots[0] - piece_x
                else:
                    raw_dist = default_slot2_dist if pref_slot == 2 else default_slot1_dist
            else:
                raw_dist = default_slot2_dist if pref_slot == 2 else default_slot1_dist

            drag_distance = raw_dist + adaptive_offset
            start_x, start_y = kx, ky
            max_drag = int(iw * 0.88)
            end_x = max(min(start_x + drag_distance, max_drag), start_x + 50)

            self.execute_smooth_drag(start_x, start_y, end_x, start_y)

            # Verification: wait for slide animation and check
            time.sleep(1.4)
            after_img = self.capture_screen()
            if not self.is_captcha_present(after_img):
                time.sleep(0.5)
                confirm_img = self.capture_screen()
                if not self.is_captcha_present(confirm_img):
                    print(f"[SUCCESS] Captcha SOLVED on attempt {attempt}! [OK]")
                    return True

            time.sleep(0.4)

        return False


if __name__ == "__main__":
    solver = IntelligentCaptchaSolver(max_attempts=15)
    solver.solve()
