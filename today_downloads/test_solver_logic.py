import cv2
import numpy as np

img = cv2.imread('captcha_screen.png')
h, w, _ = img.shape
roi_bounds = (0.133, 0.405, 0.867, 0.625)
x1 = int(roi_bounds[0] * w)
y1 = int(roi_bounds[1] * h)
x2 = int(roi_bounds[2] * w)
y2 = int(roi_bounds[3] * h)

roi = img[y1:y2, x1:x2]
gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
blurred = cv2.bilateralFilter(gray, 9, 75, 75)
edges = cv2.Canny(blurred, 40, 140)

hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
v_chan = hsv[:, :, 2]
mean_v = np.mean(v_chan)
_, dark_thresh = cv2.threshold(v_chan, int(mean_v * 0.78), 255, cv2.THRESH_BINARY_INV)
combined = cv2.bitwise_or(edges, dark_thresh)
contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

gaps = []
for c in contours:
    area = cv2.contourArea(c)
    cx, cy, cw, ch = cv2.boundingRect(c)
    center_x = x1 + cx + cw // 2
    # Starting piece is around center_x ~ 238
    if center_x > 320 and 40 < cw < 250 and 40 < ch < 250 and area > 1000:
        gaps.append((center_x, area, cw, ch, cx, cy))

gaps.sort(key=lambda x: x[0])
print(f"Found {len(gaps)} candidate gaps:")
for g in gaps:
    print(" ", g)
