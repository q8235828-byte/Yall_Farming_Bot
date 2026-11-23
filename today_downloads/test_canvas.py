import cv2
import numpy as np

img = cv2.imread(r"d:\auto account creatoion\modal.png")
h, w, _ = img.shape

# The puzzle canvas inside modal (relative coordinates)
# Canvas is roughly y: 90 to 520, x: 20 to 575
canvas = img[90:520, 20:575]
cv2.imwrite(r"d:\auto account creatoion\canvas.png", canvas)

# Convert to HSV to detect the dark silhouette shadows vs bright piece
hsv = cv2.cvtColor(canvas, cv2.COLOR_BGR2HSV)
gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)

# In the pink background, shadows are distinctly darker and lower value (V channel)
v_channel = hsv[:, :, 2]
cv2.imwrite(r"d:\auto account creatoion\v_channel.png", v_channel)

# Find dark regions (thresholding lower 35% of V channel)
mean_v = np.mean(v_channel)
_, dark_mask = cv2.threshold(v_channel, mean_v * 0.75, 255, cv2.THRESH_BINARY_INV)
cv2.imwrite(r"d:\auto account creatoion\dark_mask.png", dark_mask)

# Find contours of the dark shadows (the slots)
contours, _ = cv2.findContours(dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

slots = []
for c in contours:
    area = cv2.contourArea(c)
    x, y, cw, ch = cv2.boundingRect(c)
    # The triangle slots have area between 3000 and 15000, width/height ~ 70-130
    if 2500 < area < 15000 and 50 < cw < 140 and 50 < ch < 140:
        center_x = x + cw // 2
        center_y = y + ch // 2
        slots.append((center_x, center_y, cw, ch, area))
        print(f"Detected Slot: Center=({center_x}, {center_y}), size=({cw}x{ch}), area={area}")

# Find the bright piece on the left
# The piece has high lightness or high saturation with white border
# Let's find contours on edges or white border
edges = cv2.Canny(gray, 40, 120)
cv2.imwrite(r"d:\auto account creatoion\canvas_edges.png", edges)
edge_contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

pieces = []
for c in edge_contours:
    area = cv2.contourArea(c)
    x, y, cw, ch = cv2.boundingRect(c)
    if x < 150 and 2000 < area < 15000 and 50 < cw < 140 and 50 < ch < 140:
        center_x = x + cw // 2
        center_y = y + ch // 2
        pieces.append((center_x, center_y, cw, ch, area))
        print(f"Detected Piece: Center=({center_x}, {center_y}), size=({cw}x{ch}), area={area}")

print("\nSummary:")
print("Pieces:", pieces)
print("Slots:", slots)
