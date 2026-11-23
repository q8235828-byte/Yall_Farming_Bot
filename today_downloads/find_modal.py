import cv2
import numpy as np

img = cv2.imread(r"d:\auto account creatoion\screen.png")
h, w, _ = img.shape

# Let's find white card area (the dialog)
# In BGR, white is > 240
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
_, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)

contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

card_box = None
for c in contours:
    x, y, cw, ch = cv2.boundingRect(c)
    # The modal dialog is large (w > 400, h > 300)
    if cw > 400 and ch > 300:
        card_box = (x, y, cw, ch)
        print(f"Modal Card Box: x={x}, y={y}, w={cw}, h={ch}")
        break

if card_box:
    x, y, cw, ch = card_box
    modal_crop = img[y:y+ch, x:x+cw]
    cv2.imwrite(r"d:\auto account creatoion\modal.png", modal_crop)
    print("Saved modal.png")
