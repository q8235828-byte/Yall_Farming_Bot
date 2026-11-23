import cv2
import numpy as np

# Load the saved screenshot
img = cv2.imread(r"d:\auto account creatoion\screen.png")
h, w, _ = img.shape
print(f"Image shape: {w}x{h}")

# The puzzle image box is roughly in the middle
# In 720x1600:
# y: 400 to 630, x: 90 to 630
roi = img[400:630, 90:630]
cv2.imwrite(r"d:\auto account creatoion\roi.png", roi)
print(f"ROI shape: {roi.shape}")

# Convert to grayscale
gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

# Find edges
edges = cv2.Canny(gray, 50, 150)
cv2.imwrite(r"d:\auto account creatoion\edges.png", edges)

# Find contours
contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

candidates = []
for c in contours:
    area = cv2.contourArea(c)
    x, y, cw, ch = cv2.boundingRect(c)
    # The triangle/puzzle piece has area roughly 2000 - 8000
    if 1000 < area < 15000 and 40 < cw < 120 and 40 < ch < 120:
        candidates.append((x, y, cw, ch, area))
        print(f"Candidate: x={x}, y={y}, w={cw}, h={ch}, area={area}")

# Sort candidates by x
candidates.sort(key=lambda item: item[0])
print("Sorted candidates:", candidates)
