# YALLA LUDO AUTOMATION ARCHITECTURE & MEMORY REPOSITORY

## 1. Project Overview & Current Working Status
- **Target Application:** Yalla Ludo (`com.yalla.yallagames`, Activity: `com.yalla.yallagames.main.MainActivity`)
- **Primary Devices Tested & Calibrated:**
  - **Device 1 (1080x2400):** Vivo Y55 (`34558213310005P`), Port: 5037 (PTP Mode).
  - **Moto G Play 2024 Cluster (5 Identical Devices, 720x1600, Android 14):**
    1. `ZL8322CK9N`
    2. `ZL8323DXJF`
    3. `ZY22KNB2KW` (Registry `DeviceInterfaceGUID: {F72FE0D4-CBCB-407D-8814-9ED673D0DD6B}` registered)
    4. `ZY22KTR2ZH`
    5. `ZY22KV2D2B`
  - **Ports Routed:** Dynamic across `5037` and `5038`.
- **Concurrent Multi-Device Architecture (`yalla_multi_worker.py`):**
  - **Dynamic Discovery:** Automatically scans ports `5038` and `5037` to discover all active devices.
  - **ThreadPoolExecutor:** Drives all connected mobiles simultaneously in parallel worker threads (`max_workers=len(devices)`).
  - **Thread-Safe Atomic Synchronization:** `threading.Lock()` guarantees conflict-free email increments (`user{N}@domain.com`) and thread-safe CSV append (`created_accounts.csv` + fallback to `created_accounts_backup.csv`).
  - **Independent Verification & IP Rotation:** Each worker independently listens for its target email OTP in IMAP, enters credentials, confirms, and rotates that specific phone's IP via airplane mode toggle.
  - **Robust IMAP Fetching:** Inspects the last 25 emails across `ALL` messages with a 45s clock-skew leeway and thread-safe clipboard handling, eliminating stale `UNSEEN` backlog stalls.
  - **Proven Speed:** 3 accounts created simultaneously in **138.5s (46.2s / account effective speed)**.
- **Auto Multi-Device Resolution Adapter:** All UI interactions and coordinates automatically scale based on `get_screen_dimensions(device_id)`. Works seamlessly on both 1080p and 720p screens.
- **Verification Method:** Cloudflare Catch-All Email Routing (`user{counter}@bhullehshahsilage.com`) forwarded to Master Gmail (`qaisarfaryad0@gmail.com`).
- **OTP Retrieval:** IMAP SSL (`imap.gmail.com:993`) searching subject/body for 6-digit regex `\b\d{6}\b`.
- **Current Proven Status:** 100% Verified End-to-End Success Rate across multi-cycle batch tests (`user227` to `user239`, and newly verified `user244`, `user245`, `user246`, `user249`, `user252`).
- **Optimized Fast Pipeline (`yalla_creator_fast.py`):**
  - **Auto-Increment Email Input:** `user{N}@domain.com` injected atomically.
  - **Instant Expert Wipe:** The moment `STATE_EXPERT_DIALOG` is detected after password confirmation, the account is recorded and `pm clear` is immediately executed (eliminating redundant in-game lobby delays).
  - **Fast Bypass Relaunch (Step 8):** Auto-grants `POST_NOTIFICATIONS` via ADB, launches app, and executes a direct 3-second compound sequence (`I'm expert` -> close popups -> Settings -> Log Out -> Check Terms) landing on `MAIN_LANDING` in ~10s total (eliminating 30+ seconds of slow polling and fallbacks).
- **OTP Retrieval Performance:** 4.6s - 6.4s end-to-end via IMAP SSL (`imap.gmail.com:993`) searching subject/body for 6-digit regex `\b\d{6}\b`.
- **Captcha Solving Performance:** 100% automated resolution via In-Memory frame processing and multi-attempt adaptive strategy. Priority calibrated: Slot 2 (far notch) is targeted FIRST on attempt 1 with +6 offset, followed by Slot 1 on attempt 2, solving most captchas in 1 attempt.

---

## 2. Calibrated Screen States & XML Resource IDs (1080x2400 Vivo)
Every step must be verified by `uiautomator dump` XML hierarchy inspection before action:

| Screen State | Detection Anchor (XML Node) | Action Taken | Calibrated Coords |
| :--- | :--- | :--- | :--- |
- **Terms & Conditions Verification:**
  - `iv_select` bounds: `[97, 2238][187, 2328]`, center: `(142, 2283)`.
  - In-memory screencap checks the exact 30x30 center region `[cy-15:cy+15, cx-15:cx+15]`:
    - Checked: 460 green checkmark pixels.
    - Unchecked: 0 green pixels.
  - If unchecked: taps `(142, 2283)` before proceeding.
  - If already checked: skips checkbox tap completely to prevent accidental unchecking, directly tapping Email Login (`685, 1973`).
| **SIGNUP_MODAL** | `com.yalla.yallagames:id/et_verification_code_sign` | Click "Sign Up" link, Enter email, Tap Obtain | Sign Up Link: `(937, 1687)`, Input: `(540, 666)`, Obtain: `(820, 1247)` |
| **CAPTCHA_PUZZLE** | Blue Slider Knob Contour (`60 < w < 240`, `0.65 < aspect < 2.0`) | Calculate Canvas Gap (`cv2.Canny` + HSV V-channel), Drag Knob | Knob Center X, Y -> Target Gap X (Distance: `track_width * fraction`) |
| **OTP_INPUT_READY** | `com.yalla.yallagames:id/bt_get_verification_code_sign` with digit countdown `Xs` | Poll IMAP for OTP, type OTP, send Keyevent 111 (hide keyboard), tap Yellow Confirm | OTP Input: `(402, 1240)`, Confirm: `(540, 1565)` |
| **SET_PASSWORD** | `com.yalla.yallagames:id/et_cus_login_password` | Enter Password, send Keyevent 111, Tap Set Password | Password Input: `(540, 478)`, Confirm: `(540, 1422)` |
| **EXPERT_DIALOG** | `com.yalla.yallagames:id/btn_yes` ("I'm expert") | Tap "I'm expert" button | `(720, 1343)` |
| **LOBBY_POPUP** | `com.yalla.yallagames:id/iv_close` or `iv_week_close` | Tap Close Button on Daily Lobby Reward | `(1003, 230)` |
| **GAME_HALL** | `com.yalla.yallagames:id/iv_setting` | Tap Settings Gear in Top Right | `(1020, 172)` |
| **SETTINGS_DIALOG** | `com.yalla.yallagames:id/bt_cancellation` | Tap Log Out Button | `(280, 1642)` |

---

## 3. Critical Rules & Hard Lessons Learned
1. **Never Touch or Break Working Code:**
   - Any modifications or speed improvements must be developed in separate files (`yalla_all_in_one.py` or new version branches).
   - `master_backup_working/` contains the golden master backup. Never overwrite it without explicit verification.
2. **On-Screen Keyboard Obscuring Buttons:**
   - On Moto G Play (720x1600), typing the password opens the virtual keyboard which covers the Confirm button (`y=1193`).
   - For Moto/720p devices (`w <= 720`), the script automatically dispatches `input keyevent 4` (Back key) immediately after typing the password to close the virtual keyboard, exposing the Yellow Confirm button.
   - For Vivo (1080x2400), this behavior remains untouched as its layout already avoids obscuration.
3. **Prevent String Concatenation:**
   - Typing without clearing appends to existing text. Use atomic keyevent clearing: `input keyevent 123` followed by backspaces `input keyevent 67 67 67...`.
4. **Captcha False-Positives Prevention:**
   - If slider knob is not found on screen, never assume captcha is cleared. Verify `STATE_OTP_READY` (countdown timer actively ticking) before proceeding to Gmail polling.
5. **Post-Clear Relaunch Handler:**
   - `pm clear com.yalla.yallagames` causes the app to restart into a guest lobby prompt ("Welcome to Yalla Ludo! Have you ever played Ludo?").
   - Automation must grant `POST_NOTIFICATIONS`, tap "I'm expert", dismiss daily lobby popup, enter settings gear, and tap log out to cleanly arrive at `MAIN_LANDING`.

---

## 4. Multi-Device Scalability Guidelines
When running across multiple connected devices simultaneously:
- Spawn dedicated worker thread/process per device serial: `run_worker(device_serial, account_queue)`.
- Use thread-safe file locking (`fcntl` / `filelock` / retry loop) when writing to `created_accounts.csv`.
- Each device requires its own screen detector and UI automator instance scoped to `-s <device_serial>`.
- If devices share cellular data (USB tethering), stagger airplane mode toggles or use separate proxy/APNs per device.

- **Auto-Retry Integration (Nov 2026):** yalla_multi_worker.py and yalla_creator_fast.py now automatically trigger run_sheet_retry() upon finishing the new-account creation batch to clean up any failed sheet rows in-place.