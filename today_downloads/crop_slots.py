import cv2

canvas = cv2.imread('exact_canvas.png')

# Piece: [0:135, 59:195]
piece = canvas[59:195, 0:135]
cv2.imwrite('piece_extracted.png', piece)

# Slot 1: around x=261, y=127 -> [77:177, 211:311]
slot1 = canvas[59:195, 212:212+99]
cv2.imwrite('slot1_extracted.png', slot1)

# Slot 2: around x=408, y=127 -> [77:177, 358:458]
slot2 = canvas[59:195, 358:358+101]
cv2.imwrite('slot2_extracted.png', slot2)

print("Saved piece_extracted.png, slot1_extracted.png, slot2_extracted.png")
