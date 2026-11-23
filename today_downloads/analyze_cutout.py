import cv2, numpy as np

with open('test_pull.raw', 'rb') as f:
    raw = f.read()
w = int.from_bytes(raw[0:4], byteorder='little')
h = int.from_bytes(raw[4:8], byteorder='little')
data = np.frombuffer(raw[16:], dtype=np.uint8).reshape((h, w, 4))
bgr = cv2.cvtColor(data, cv2.COLOR_RGBA2BGR)

# Exact puzzle canvas bounds from XML: [149, 418][653, 756]
canvas = bgr[418:756, 149:653]
cv2.imwrite('exact_canvas.png', canvas)

print("Canvas shape:", canvas.shape) # (338, 504, 3)

# Piece bounds in XML: [149, 477][284, 613]
# Inside canvas, piece y is (477-418)=59 to (613-418)=195
# Piece height is 136, width is 135
# Center Y of piece is 59 + 68 = 127 (Absolute Y: 477 + 68 = 545)
print("Piece center Y:", 545, "(Canvas Y: 127)")

# Now, where is the cutout slot?
# The cutout slot MUST be at the SAME Y level as the piece! Y around 59 to 195!
# Let's inspect the horizontal slice between Y=65 and Y=190
slot_band = canvas[59:195, :, :]
cv2.imwrite('slot_band.png', slot_band)

# In this horizontal band, let's find the shadow/cutout!
hsv_band = cv2.cvtColor(slot_band, cv2.COLOR_BGR2HSV)
v = hsv_band[:, :, 2]
mean_v = np.mean(v)
print("Band mean V:", mean_v)

# Find dark regions with width ~80-120px and x > 140
for thresh_pct in [0.65, 0.70, 0.75, 0.80]:
    _, dark = cv2.threshold(v, int(mean_v * thresh_pct), 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"\n--- Threshold {thresh_pct} ---")
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        if cw > 40 and ch > 40 and x > 120:
            print(f"Slot Candidate: x={x}, y={y}, w={cw}, h={ch}, center_x={x + cw//2}")
            # Target absolute X on screen = 149 + x + cw//2 - (piece_offset)
            # Piece at x=0 starts at 149.
            # Slider starts at 217.
            # So if slot center is at x_slot inside canvas, and piece center is at x_piece inside canvas:
            # Shift needed = x_slot - x_piece
            # If piece is [0, 135], piece center inside canvas is 67.5 ~ 68.
            # So shift = (x + cw//2) - 68
            # And Slider Target End X = 217 + shift = 149 + 68 + shift = 149 + (x + cw//2)!
            target_knob_x = 149 + (x + cw // 2)
            print(f"  -> Knob Target End X: {target_knob_x}")
