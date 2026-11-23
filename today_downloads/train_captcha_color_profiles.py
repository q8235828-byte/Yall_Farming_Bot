"""
================================================================================
CAPTCHA COLOR PROFILE COLLECTOR & TRAINER FOR YALLA LUDO
================================================================================
Collects 15 captcha background variations, analyzes their color pixel profile (HSV),
measures exact cutout slot positions, and generates an optimized Color-Indexed Solver.
================================================================================
"""

import json
import os
import random
import subprocess
import time
import cv2
import numpy as np

from airplane_mode import ADB_BIN, get_device_port

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRAIN_DIR = os.path.join(BASE_DIR, "captcha_training")
os.makedirs(TRAIN_DIR, exist_ok=True)
DB_PATH = os.path.join(BASE_DIR, "captcha_color_db.json")


def capture_frame(device_id: str = None) -> np.ndarray:
    """Captures uncorrupted composite frame using uiautomator + raw screencap."""
    port = get_device_port(device_id)
    cmd = [ADB_BIN]
    if port != 5037:
        cmd.extend(["-P", str(port)])
    if device_id:
        cmd.extend(["-s", device_id])

    # Trigger SurfaceFlinger composition via quick accessibility dump
    subprocess.run(cmd + ["shell", "uiautomator", "dump", "/sdcard/comp_tr.xml"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
    subprocess.run(cmd + ["shell", "screencap", "/sdcard/tr.raw"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
    
    raw = subprocess.check_output(cmd + ["exec-out", "cat", "/sdcard/tr.raw"], timeout=4)
    w = int.from_bytes(raw[0:4], byteorder='little')
    h = int.from_bytes(raw[4:8], byteorder='little')
    data = np.frombuffer(raw[16:], dtype=np.uint8).reshape((h, w, 4))
    return cv2.cvtColor(data, cv2.COLOR_RGBA2BGR)


def find_slider_knob(img: np.ndarray) -> tuple[int, int, int, int] | None:
    """Finds blue slider knob on screen."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    blue_mask = cv2.inRange(hsv, np.array([100, 120, 180]), np.array([135, 255, 255]))
    contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w > 60 and h > 40:
            return (x + w // 2, y + h // 2, w, h)
    return None


def classify_color(hsv_crop: np.ndarray) -> tuple[str, tuple[float, float, float]]:
    """Calculates dominant color family and mean HSV."""
    h_mean = float(np.mean(hsv_crop[:, :, 0]))
    s_mean = float(np.mean(hsv_crop[:, :, 1]))
    v_mean = float(np.mean(hsv_crop[:, :, 2]))

    # Color family classifier
    if (h_mean < 12 or h_mean > 155) and s_mean > 50:
        family = "Pink/Red"
    elif 12 <= h_mean < 35:
        family = "Yellow/Orange"
    elif 35 <= h_mean < 75:
        family = "Green"
    elif 75 <= h_mean < 98:
        family = "Turquoise/Cyan"
    elif 98 <= h_mean < 132:
        family = "Blue"
    elif 132 <= h_mean <= 155:
        family = "Purple"
    else:
        family = "Neutral/Gray"

    return family, (round(h_mean, 1), round(s_mean, 1), round(v_mean, 1))


def analyze_canvas(canvas_bgr: np.ndarray) -> dict:
    """Detects piece center and shadow slots in puzzle picture."""
    ch, cw, _ = canvas_bgr.shape
    hsv = cv2.cvtColor(canvas_bgr, cv2.COLOR_BGR2HSV)
    family, (hm, sm, vm) = classify_color(hsv)

    # Detect shadow slots using inverted V-channel threshold
    v_chan = hsv[:, :, 2]
    mean_v = np.mean(v_chan)
    _, dark_thresh = cv2.threshold(v_chan, int(mean_v * 0.74), 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(dark_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    slots = []
    for c in contours:
        area = cv2.contourArea(c)
        cx, cy, w, h = cv2.boundingRect(c)
        # Expected slot cutout dimensions: 40-120px
        if 2000 < area < 16000 and 38 < w < 125 and 38 < h < 125:
            # Must be past starting piece
            if cx > int(cw * 0.28):
                slots.append({
                    "x": cx + w // 2,
                    "y": cy + h // 2,
                    "w": w,
                    "h": h,
                    "area": float(area)
                })

    slots.sort(key=lambda s: s["x"])

    # Piece position is typically around left 15-25% of canvas
    piece_x = int(cw * 0.16)

    dist_slot1 = (slots[0]["x"] - piece_x) if len(slots) >= 1 else int(cw * 0.414)
    dist_slot2 = (slots[1]["x"] - piece_x) if len(slots) >= 2 else (dist_slot1 + int(cw * 0.29))

    return {
        "color_family": family,
        "mean_hsv": [hm, sm, vm],
        "slots_found": len(slots),
        "slot_positions": slots,
        "piece_x": piece_x,
        "dist_slot1": dist_slot1,
        "dist_slot2": dist_slot2,
    }


def perform_swipe(start_x: int, start_y: int, end_x: int, end_y: int, device_id: str = None, duration: int = 650):
    """Executes smooth human swipe via ADB input swipe."""
    port = get_device_port(device_id)
    cmd = [ADB_BIN]
    if port != 5037:
        cmd.extend(["-P", str(port)])
    if device_id:
        cmd.extend(["-s", device_id])
    jitter_y = end_y + random.choice([-1, 0, 1])
    cmd.extend(["shell", "input", "swipe", str(start_x), str(start_y), str(end_x), str(jitter_y), str(duration)])
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def tap_refresh(device_id: str = None):
    """Taps the refresh icon (229, 907) to generate a new captcha background."""
    port = get_device_port(device_id)
    cmd = [ADB_BIN]
    if port != 5037:
        cmd.extend(["-P", str(port)])
    if device_id:
        cmd.extend(["-s", device_id])
    subprocess.run(cmd + ["shell", "input", "tap", "229", "907"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_training(total_samples: int = 15, device_id: str = "127.0.0.1:21623"):
    print("\n" + "="*70)
    print(f"   STARTING CAPTCHA COLOR PROFILE TRAINING ({total_samples} SAMPLES)")
    print("="*70)

    dataset = []

    for i in range(1, total_samples + 1):
        print(f"\n[Sample {i}/{total_samples}] Capturing Frame...")
        frame = capture_frame(device_id)
        knob = find_slider_knob(frame)

        if not knob:
            print("[-] Knob not visible, attempting to tap Bind Email or wake...")
            subprocess.run([ADB_BIN, "-s", device_id, "shell", "input", "tap", "401", "631"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.5)
            frame = capture_frame(device_id)
            knob = find_slider_knob(frame)
            if not knob:
                print("[-] Could not locate knob. Skipping sample.")
                continue

        kx, ky, kw, kh = knob
        print(f"[+] Knob located at: ({kx}, {ky}) [size: {kw}x{kh}]")

        # Crop puzzle canvas
        # Calibrated for MEmu 800x1280:
        canvas_top = ky - 390
        canvas_bottom = ky - 55
        canvas_left = 150
        canvas_right = 652
        canvas = frame[canvas_top:canvas_bottom, canvas_left:canvas_right]

        sample_img_path = os.path.join(TRAIN_DIR, f"sample_{i}.png")
        cv2.imwrite(sample_img_path, canvas)

        # Analyze color and slots
        info = analyze_canvas(canvas)
        info["sample_id"] = i
        info["image_file"] = f"sample_{i}.png"
        info["knob_pos"] = [kx, ky]
        dataset.append(info)

        print(f"    Color Family:   [{info['color_family']}]")
        print(f"    Mean HSV:       {info['mean_hsv']}")
        print(f"    Slots Detected: {info['slots_found']}")
        print(f"    Slot 1 Dist:    {info['dist_slot1']}px -> End X: {kx + info['dist_slot1']}")
        print(f"    Slot 2 Dist:    {info['dist_slot2']}px -> End X: {kx + info['dist_slot2']}")

        # Test dragging or refresh to get next background
        if i % 2 == 1:
            # Test drag Slot 1 with intentional offset to analyze reset
            print("    [*] Performing test drag to Slot 1...")
            end_x = kx + info["dist_slot1"]
            perform_swipe(kx, ky, end_x, ky, device_id, duration=620)
            time.sleep(2.0)
        else:
            # Tap Refresh to force next background image
            print("    [*] Tapping Refresh for next background...")
            tap_refresh(device_id)
            time.sleep(1.8)

    # Save complete dataset
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)

    print("\n" + "="*70)
    print(f"[+] TRAINING COMPLETED: {len(dataset)} Samples Collected & Analyzed!")
    print(f"[+] Dataset saved to: {DB_PATH}")
    print("="*70)
    return dataset


if __name__ == "__main__":
    run_training(15)
