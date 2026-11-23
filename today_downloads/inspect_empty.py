import cv2, numpy as np

img = cv2.imread('empty_target_canvas.png')
ch, cw, _ = img.shape
print(f"Canvas size: {cw}x{ch}")

hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
v = hsv[:, :, 2]
mean_v = np.mean(v)
print(f"Mean V: {mean_v}")

# Let's inspect all contours across various thresholds
for pct in [0.60, 0.65, 0.70, 0.75, 0.80, 0.85]:
    thresh_val = int(mean_v * pct)
    _, dark = cv2.threshold(v, thresh_val, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"\n--- Pct {pct} (Thresh {thresh_val}) ---")
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w > 30 and h > 30:
            print(f"x={x}, y={y}, w={w}, h={h}, aspect={w/h:.2f}, center_x={x + w//2}, Target Knob X: {149 + x + w//2}")
