import cv2
import numpy as np

canvas = cv2.imread(r"d:\auto account creatoion\canvas.png")
gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)

# In the canvas, the piece has a bright white glowing border
# Threshold for bright pixels
_, bright = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
cv2.imwrite(r"d:\auto account creatoion\bright.png", bright)

contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
for c in contours:
    x, y, w, h = cv2.boundingRect(c)
    print(f"Bright contour: x={x}, y={y}, w={w}, h={h}, area={cv2.contourArea(c)}")
