import cv2, numpy as np

img = cv2.imread('blue_live_canvas.png')
ch, cw, _ = img.shape
print(f"Canvas size: {cw}x{ch}")

hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
v = hsv[:, :, 2]
mean_v = np.mean(v)
print(f"Mean V: {mean_v}")

for thresh in [int(mean_v * 0.65), int(mean_v * 0.72), int(mean_v * 0.78)]:
    _, dark = cv2.threshold(v, thresh, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"\n--- Threshold {thresh} ---")
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if 40 < w < 140 and 40 < h < 140 and x > 100:
            print(f"Contour: x={x}, y={y}, w={w}, h={h}, center=({x + w//2}, {y + h//2}), Target Knob X: {149 + x + w//2}")
