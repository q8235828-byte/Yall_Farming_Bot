import cv2
import numpy as np
from captcha_solver import IntelligentCaptchaSolver

img = cv2.imread("live.png")
if img is None:
    print("Could not load live.png")
    exit()

ih, iw, _ = img.shape
print(f"Screen Resolution: {iw}x{ih}")

solver = IntelligentCaptchaSolver(device_id="34558213310005P")
knob = solver.get_slider_knob_pos(img)
is_cap = solver.is_captcha_present(img)
print(f"Captcha Detected: {is_cap}")
print(f"Slider Knob Position: {knob}")

# Also check for text / OCR or common colors
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
# Yellow confirm button check
yellow_mask = cv2.inRange(hsv, np.array([20, 150, 150]), np.array([35, 255, 255]))
yellow_px = cv2.countNonZero(yellow_mask)
print(f"Yellow pixels (Confirm button area): {yellow_px}")

# Green terms check
green_mask = cv2.inRange(hsv, np.array([35, 120, 100]), np.array([85, 255, 255]))
print(f"Green pixels: {cv2.countNonZero(green_mask)}")
