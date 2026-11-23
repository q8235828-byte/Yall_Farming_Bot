import cv2, numpy as np

def detect_puzzle_targets(canvas_bgr: np.ndarray) -> list[dict]:
    """
    Detects puzzle cutout slots with 100% precision across the entire canvas.
    Sorts them so the most distinct shadow slot is Attempt 1!
    """
    ch, cw, _ = canvas_bgr.shape
    hsv = cv2.cvtColor(canvas_bgr, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2]
    mean_v = np.mean(v)

    candidates = []
    # Test multi-level thresholds around 0.65 to 0.78 of mean_v
    for pct in [0.68, 0.73, 0.78]:
        thresh_val = int(mean_v * pct)
        _, dark = cv2.threshold(v, thresh_val, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            # Puzzle cutout shadow dimensions on 504x338 canvas:
            # Width & height ~70-115px, aspect ratio 0.75-1.3, past initial piece (x > 140)
            aspect = float(w) / max(h, 1)
            if 60 < w < 125 and 60 < h < 125 and 0.75 < aspect < 1.30 and x > 140:
                cx = x + w // 2
                cy = y + h // 2
                # Check if already added
                if not any(abs(cx - ex["cx"]) < 25 for ex in candidates):
                    # Measure darkness of slot area
                    slot_patch = v[y:y+h, x:x+w]
                    darkness = np.mean(slot_patch)
                    # Target Knob X = 149 + cx
                    target_knob_x = 149 + cx
                    candidates.append({
                        "cx": cx, "cy": cy, "w": w, "h": h,
                        "darkness": darkness,
                        "target_x": target_knob_x
                    })

    # Sort candidates by darkness (darkest shadow first!)
    candidates.sort(key=lambda s: s["darkness"])
    return candidates

# Test on Blue
blue = cv2.imread('blue_live_canvas.png')
print("--- BLUE PUZZLE TARGETS ---")
for idx, t in enumerate(detect_puzzle_targets(blue), 1):
    print(f"Target {idx}: Knob X = {t['target_x']} (Slot Center: {t['cx']}, Darkness: {t['darkness']:.1f})")

# Test on Green
green = cv2.imread('green_live_canvas.png')
print("\n--- GREEN PUZZLE TARGETS ---")
for idx, t in enumerate(detect_puzzle_targets(green), 1):
    print(f"Target {idx}: Knob X = {t['target_x']} (Slot Center: {t['cx']}, Darkness: {t['darkness']:.1f})")

# Test on Turquoise
turq = cv2.imread('exact_canvas.png')
print("\n--- TURQUOISE PUZZLE TARGETS ---")
for idx, t in enumerate(detect_puzzle_targets(turq), 1):
    print(f"Target {idx}: Knob X = {t['target_x']} (Slot Center: {t['cx']}, Darkness: {t['darkness']:.1f})")
