import cv2, numpy as np

img = cv2.imread('green_piece_crop.png')
print("piece crop shape:", img.shape)
# Find the piece's bounding box inside the whole canvas
# The piece has a distinct border or transparent background around it
canvas = cv2.imread('green_live_canvas.png')
# Let's inspect the first 120 columns of canvas around row 177 (center of slot)
print("Row 177 BGR profile across first 80 pixels:")
for x in range(0, 80, 5):
    print(f"x={x}: {canvas[177, x]}")
