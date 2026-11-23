import cv2
import numpy as np

img = cv2.imread(r"d:\auto account creatoion\captcha_screen.png")
if img is not None:
    h, w, _ = img.shape
    print(f"Shape: {w}x{h}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        if cw > 500 and ch > 500:
            print(f"1080p Modal Box: x={x}, y={y}, w={cw}, h={ch}")
            crop = img[y:y+ch, x:x+cw]
            cv2.imwrite(r"d:\auto account creatoion\1080p_modal.png", crop)
            break
