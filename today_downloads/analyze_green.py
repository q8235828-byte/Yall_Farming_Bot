import cv2, numpy as np

canvas = cv2.imread('green_canvas.png')
ch, cw, _ = canvas.shape
print("Canvas size:", cw, ch)

# Band Y: 59 to 195
band = canvas[59:195, :, :]
hsv_band = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
v = hsv_band[:, :, 2]
mean_v = np.mean(v)
print("Mean V:", mean_v)

for pct in [0.70, 0.75, 0.80]:
    _, dark = cv2.threshold(v, int(mean_v * pct), 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"\n--- Threshold {pct} ---")
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if 40 < w < 130 and 40 < h < 130:
            print(f"Candidate: x={x}, y={y}, w={w}, h={h}, center_x={x + w//2}, Target Knob X: {149 + x + w//2}")

# Also check Color profile for Green in our previous data
from color_indexed_captcha_solver import COLOR_PROFILES_800P
print("\nColor Profile for Green:", COLOR_PROFILES_800P.get("Green"))
