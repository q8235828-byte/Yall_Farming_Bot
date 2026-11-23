import cv2
import numpy as np

img = cv2.imread('captcha_modal.png')
# Canvas is y=39 to 610, x=25 to 854
canvas = img[39:610, 25:854]
hsv = cv2.cvtColor(canvas, cv2.COLOR_BGR2HSV)
v = hsv[:, :, 2]
mean_v = np.mean(v)
print(f"Mean V: {mean_v}")

# Test multiple dark threshold ratios
for ratio in [0.70, 0.75, 0.78, 0.82, 0.85]:
    _, dark = cv2.threshold(v, int(mean_v * ratio), 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"--- Ratio {ratio} ---")
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = cv2.contourArea(c)
        if 2000 < area < 30000 and 40 < w < 220 and 40 < h < 220:
            # global x on screen = 125 + x
            print(f"  Contour: x={x}, y={y}, w={w}, h={h}, area={area}, screen_cx={125 + x + w//2}")
