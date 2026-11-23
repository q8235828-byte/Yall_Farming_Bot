import cv2
import numpy as np

img = cv2.imread(r"d:\auto account creatoion\captcha_screen.png")
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# Blue knob mask
blue_lower = np.array([95, 120, 120])
blue_upper = np.array([135, 255, 255])
blue_mask = cv2.inRange(hsv, blue_lower, blue_upper)

contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
knob = None
for c in contours:
    if cv2.contourArea(c) > 800:
        x, y, w, h = cv2.boundingRect(c)
        knob = (x + w // 2, y + h // 2, w, h)
        print(f"Blue Knob: center=({knob[0]}, {knob[1]}), size=({w}x{h})")
        break

if knob:
    kx, ky, kw, kh = knob
    iw = img.shape[1]
    
    # Canvas bounds derived directly from knob position
    canvas_left = kx - kw // 2
    canvas_right = iw - canvas_left
    canvas_bottom = ky - int(kh * 1.2)
    canvas_height = int((canvas_right - canvas_left) * 0.72)
    canvas_top = canvas_bottom - canvas_height
    
    print(f"Calculated Canvas: Left={canvas_left}, Right={canvas_right}, Top={canvas_top}, Bottom={canvas_bottom}")
    
    canvas = img[canvas_top:canvas_bottom, canvas_left:canvas_right]
    cv2.imwrite(r"d:\auto account creatoion\perfect_canvas.png", canvas)
    print("Saved perfect_canvas.png!")
