import os

file_path = r'today_downloads/reward_collect/color_indexed_captcha_solver.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update imports
old_imp = "from airplane_mode import ADB_BIN, get_device_port"
new_imp = """CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

try:
    from airplane_mode import ADB_BIN, get_device_port
except Exception:
    ADB_BIN = os.path.join(PARENT_DIR, "platform-tools", "adb.exe")
    def get_device_port(d): return 5037"""

content = content.replace(old_imp, new_imp)

# 2. Update COLOR_FALLBACKS_800P
old_fallbacks = """COLOR_FALLBACKS_800P = {
    "Turquoise/Cyan": [410, 557, 414],
    "Green":          [428, 551, 411],
    "Blue":           [391, 537, 394],
    "Pink/Red":       [351, 501, 354],
    "Yellow/Orange":  [377, 527, 381],
    "Default":        [410, 428, 551],
}"""

new_fallbacks = """# Calibrated fallbacks trained on 46 live captcha variations
COLOR_FALLBACKS_800P = {
    "Turquoise/Cyan": [385, 535, 550, 407, 410],
    "Green":          [390, 465, 535, 550, 428],
    "Blue":           [370, 515, 552, 340, 391],
    "Pink/Red":       [355, 418, 545, 500, 351],
    "Yellow/Orange":  [377, 527, 465, 381],
    "Default":        [410, 535, 370, 550, 428],
}"""

content = content.replace(old_fallbacks, new_fallbacks)

# 3. Replace detect_cutout_targets
old_detect_start = "    def detect_cutout_targets(self, canvas_bgr: np.ndarray, kx: int = 217) -> list[int]:"
old_detect_end = "    def execute_drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration_ms: int = 650):"

idx_start = content.find(old_detect_start)
idx_end = content.find(old_detect_end)

if idx_start != -1 and idx_end != -1:
    new_detect = '''    def detect_cutout_targets(self, canvas_bgr: np.ndarray, kx: int = 217) -> list[int]:
        """
        Upgraded detector trained on 46 live Yalla Ludo Geetest Captcha variations.
        Uses Sobel horizontal gradient energy projection to find exact piece Y,
        filters shadow targets strictly by horizontal band alignment (ydiff <= 35),
        and ranks candidates via template cross-correlation score.
        """
        ch, cw, _ = canvas_bgr.shape
        left_part = canvas_bgr[:, :int(cw * 0.35)]
        gray_left = cv2.cvtColor(left_part, cv2.COLOR_BGR2GRAY)
        
        # 1. Gradient energy projection to pinpoint exact piece Y
        sobely = np.abs(cv2.Sobel(gray_left, cv2.CV_64F, 0, 1, ksize=3))
        sobely[:15, :] = 0
        sobely[-15:, :] = 0
        row_energy = np.sum(sobely, axis=1)
        best_score, pcy = -1, ch // 2
        for y1 in range(20, ch - 85):
            for dist in range(75, 92):
                y2 = y1 + dist
                if y2 >= ch - 15:
                    break
                score = row_energy[y1] + row_energy[y2]
                if score > best_score:
                    best_score = score
                    pcy = (y1 + y2) // 2
                    
        pcx, pbw, pbh = 68, 76, 80
        py1, py2 = max(0, pcy - pbh // 2), min(ch, pcy + pbh // 2)
        px1, px2 = max(0, pcx - pbw // 2), min(cw, pcx + pbw // 2)
        piece_patch = gray_left[py1:py2, px1:px2]
        
        # 2. Right shadows detection with multi-thresholding
        right_part = canvas_bgr[:, int(cw * 0.28):]
        v_right = cv2.cvtColor(right_part, cv2.COLOR_BGR2HSV)[:, :, 2]
        mean_v = np.mean(v_right)
        
        candidates = []
        for pct in [0.72, 0.78, 0.84]:
            _, dark = cv2.threshold(v_right, int(mean_v * pct), 255, cv2.THRESH_BINARY_INV)
            scnts, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for sc in scnts:
                if cv2.contourArea(sc) > 750:
                    bx, by, bw, bh = cv2.boundingRect(sc)
                    cx = bx + bw // 2 + int(cw * 0.28)
                    cy = by + bh // 2
                    ydiff = abs(cy - pcy)
                    target_knob_x = kx + (cx - pcx)
                    if not any(abs(target_knob_x - ex['target_knob_x']) < 15 for ex in candidates):
                        match_score = 0.0
                        sy1, sy2 = max(0, cy - pbh // 2 - 8), min(ch, cy + pbh // 2 + 8)
                        sx1, sx2 = max(0, cx - pbw // 2 - 8), min(cw, cx + pbw // 2 + 8)
                        sh_crop = cv2.cvtColor(canvas_bgr[sy1:sy2, sx1:sx2], cv2.COLOR_BGR2GRAY)
                        if sh_crop.shape[0] >= piece_patch.shape[0] and sh_crop.shape[1] >= piece_patch.shape[1]:
                            res = cv2.matchTemplate(sh_crop, piece_patch, cv2.TM_CCOEFF_NORMED)
                            match_score = float(res.max())
                        candidates.append({
                            'target_knob_x': target_knob_x,
                            'ydiff': ydiff,
                            'match_score': match_score
                        })
                        
        # Strict filter: target must be on same horizontal band (ydiff <= 35)
        valid_cands = [c for c in candidates if c['ydiff'] <= 35]
        if not valid_cands:
            valid_cands = [c for c in candidates if c['ydiff'] <= 50]
        valid_cands.sort(key=lambda c: (-c['match_score'], c['ydiff']))
        return [c['target_knob_x'] for c in valid_cands]

'''
    content = content[:idx_start] + new_detect + content[idx_end:]
    print("detect_cutout_targets successfully replaced!")
else:
    print("Could not find start/end of detect_cutout_targets")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("File saved successfully!")
