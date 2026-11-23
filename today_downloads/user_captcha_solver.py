import os
import random
import re
import time
from typing import Optional
import cv2
import numpy as np

from airplane_mode import run_adb_command

SCREENSHOT_PATH = r"d:\auto account creatoion\captcha_screen.png"


class VisionDetector:
    """OpenCV contour gap and color analysis for Yalla Ludo captcha."""

    def locate_slider_gap(self, img: np.ndarray, roi_bounds: tuple[float, float, float, float]) -> Optional[int]:
        h, w, _ = img.shape
        x1 = int(roi_bounds[0] * w)
        y1 = int(roi_bounds[1] * h)
        x2 = int(roi_bounds[2] * w)
        y2 = int(roi_bounds[3] * h)

        roi = img[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # Bilateral filter to smooth texture while preserving shadow edges
        blurred = cv2.bilateralFilter(gray, 9, 75, 75)
        edges = cv2.Canny(blurred, 40, 140)

        # Shadow detection using HSV V-channel
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        v_chan = hsv[:, :, 2]
        mean_v = np.mean(v_chan)
        _, dark_thresh = cv2.threshold(v_chan, int(mean_v * 0.78), 255, cv2.THRESH_BINARY_INV)

        combined = cv2.bitwise_or(edges, dark_thresh)
        contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        gap_candidates = []
        for c in contours:
            area = cv2.contourArea(c)
            cx, cy, cw, ch = cv2.boundingRect(c)
            # Filter contours by cutout dimensions
            if 2000 < area < 28000 and 45 < cw < 220 and 45 < ch < 220:
                # The target gap must be past the starting piece
                if cx > int(w * 0.12):
                    center_x = x1 + cx + cw // 2
                    gap_candidates.append((center_x, area, cw, ch))

        if gap_candidates:
            # Sort from left to right
            gap_candidates.sort(key=lambda item: item[0])
            return gap_candidates[0][0]

        return None

    def is_captcha_modal_open(self, img: np.ndarray) -> bool:
        """Checks if the blue slider button is currently visible."""
        if img is None:
            return False
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        blue_mask = cv2.inRange(hsv, np.array([95, 120, 120]), np.array([135, 255, 255]))
        return cv2.countNonZero(blue_mask) > 600


class UserCaptchaSolver:
    """
    Automated Slider Puzzle Captcha Solver for Yalla Ludo.
    Uses OpenCV contour gap analysis, distance projection, and human-like swipe execution.
    """

    def __init__(self, device_id: str = None):
        self.device_id = device_id
        self.vision = VisionDetector()

    def screencap(self) -> np.ndarray:
        run_adb_command(["shell", "screencap", "-p", "/sdcard/cap_temp.png"], self.device_id)
        run_adb_command(["pull", "/sdcard/cap_temp.png", SCREENSHOT_PATH], self.device_id)
        return cv2.imread(SCREENSHOT_PATH)

    def get_screen_dimensions(self) -> tuple[int, int]:
        out = run_adb_command(["shell", "wm", "size"], self.device_id)
        # e.g. "Physical size: 1080x2400"
        m = re.findall(r"(\d+)x(\d+)", out)
        if m:
            return int(m[0][0]), int(m[0][1])
        return 1080, 2400

    def resolve_coord(self, name: str, width: int, height: int) -> tuple[int, int]:
        if name == "captcha_slider_start":
            # Calibrated for normalized slider start (x ~ 21.8%, y ~ 65.3%)
            return int(width * 0.218), int(height * 0.653)
        return int(width * 0.5), int(height * 0.5)

    def smooth_swipe(self, start_x: int, start_y: int, end_x: int, end_y: int, duration_ms: int, delay: float = 2.5):
        run_adb_command([
            "shell", "input", "swipe",
            str(start_x), str(start_y),
            str(end_x), str(end_y),
            str(duration_ms)
        ], self.device_id)
        time.sleep(delay)

    def solve(self, max_retries: int = 5) -> bool:
        """
        Attempts to solve the Yalla Ludo puzzle captcha up to max_retries times.
        Returns True if resolved or dismissed, False if failed.
        """
        print("[*] Inspecting screen for 'Slide to complete the puzzle' captcha...")
        time.sleep(1.5)

        width, height = self.get_screen_dimensions()

        for attempt in range(1, max_retries + 1):
            img = self.screencap()
            if not self.vision.is_captcha_modal_open(img):
                print("[+] Captcha modal is not displayed or already solved!")
                return True

            roi_bounds = (0.133, 0.405, 0.867, 0.625)

            # 1. Locate the matching puzzle cutout notch
            target_gap_x = self.vision.locate_slider_gap(img, roi_bounds)
            if not target_gap_x:
                print(f"[!] Could not locate puzzle gap (attempt {attempt}/{max_retries})")
                time.sleep(1.5)
                continue

            # 2. Determine slider start and track coordinates
            start_x, start_y = self.resolve_coord("captcha_slider_start", width, height)
            
            # The piece starts at calibrated piece origin
            piece_start_x = int(roi_bounds[0] * width) + int(width * 0.065)
            drag_distance = target_gap_x - piece_start_x

            # End slider position
            calibrated_end_x = start_x + drag_distance
            
            # Bound end_x to avoid dragging off screen
            max_drag_x = int(width * 0.82)
            calibrated_end_x = min(max(calibrated_end_x, start_x + 50), max_drag_x)

            print(
                f"[Attempt {attempt}/{max_retries}]: Dragging slider from ({start_x}, {start_y}) "
                f"to ({calibrated_end_x}, {start_y}) [Distance: {drag_distance}px]"
            )

            # 3. Perform realistic drag gesture with subtle Y variation
            duration = random.randint(700, 850)
            jitter_y = start_y + random.choice([-1, 1, 2])
            self.smooth_swipe(start_x, start_y, calibrated_end_x, jitter_y, duration_ms=duration, delay=2.5)

            # 4. Check if captcha was successfully solved
            time.sleep(2.0)
            after_img = self.screencap()
            
            # If the modal closed, captcha succeeded!
            if not self.vision.is_captcha_modal_open(after_img):
                print(f"[SUCCESS] Captcha solved successfully on attempt {attempt}! 🎉")
                return True

            print("[*] Captcha slider reset detected. Retrying with adjusted offset...")
            time.sleep(1.0)

        print("[-] Reached max attempts.")
        return False


if __name__ == "__main__":
    import re
    solver = UserCaptchaSolver(device_id="34558213310005P")
    res = solver.solve(max_retries=5)
    print("Solver Result:", res)
