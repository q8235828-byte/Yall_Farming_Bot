# 🎲 Yalla Farming Bot — Autonomous Multi-Instance Engine

Ultra-fast, autonomous reward farming and account cycling bot for **Yalla Ludo** with real-time **Google Sheet live synchronization** and parallel **Multi-Instance MEmu** support.

---

## ⚡ Key Capabilities & Architecture

- **High-Speed In-Memory Detection:** Replaced slow disk dumps with sub-30ms in-memory UI hierarchy (`uiautomator2`).
- **Real-Time Ad Watcher:**
  - Auto-skips 2-segment ads using instant probing (`(740, 36)`).
  - Auto-exits reward-granted screens (`(762, 39)`).
  - Collects all 6/6 Free Rewards video ads without human intervention.
- **🛡️ AppGuard Auto-Recovery:** If an ad opens Chrome, Play Store, or external apps, AppGuard immediately detects it, force-stops the external app, and brings Yalla Ludo back to front within 0.5s.
- **📊 Real-Time Google Sheet Sync:**
  - Automatically reads credentials and status.
  - Updates `Status: Success_Completed`, `Total_Coin` (Lobby coins), `Free_Rewards: 6/6`, and `Latest_Update`.
  - Enforces a 24-hour completion cooldown so finished accounts are not re-processed prematurely.
- **🔄 Auto-Updater Launcher (`run_bot.bat`):** Pulls the latest code directly from GitHub on every execution before running.

---

## 📋 Prerequisites & Setup

### 1. Requirements
- **Python 3.10+**
- **MEmu Emulator** (or any Android Emulator / Physical Device)
  - Recommended Resolution: `800 x 1280` (Tablet / Custom)
  - DPI: `266`
  - ADB Port examples: `127.0.0.1:21503`, `127.0.0.1:21513`, `127.0.0.1:21523`

### 2. Installation
Open PowerShell / Command Prompt and install required libraries:
```powershell
pip install uiautomator2 opencv-python numpy
```

---

## 🚀 How to Run (Usage Guide)

Always run from the repository root directory:
```powershell
cd "C:\Users\wc\OneDrive\Desktop\codebase"
```

### Method 1: Using the Auto-Updater Launcher (Recommended)
`run_bot.bat` will automatically pull the latest code updates from GitHub first, then run the automation:

#### 🔹 Single Instance:
```powershell
.\run_bot.bat 127.0.0.1:21503 10 233
```
- Argument 1: Emulator Device Port (`127.0.0.1:21503`)
- Argument 2: Max Accounts to process in this run (`10`)
- Argument 3: Minimum User ID number (`233` = starts from `user233`)

---

### Method 2: Multi-Instance Parallel Execution (Multiple Terminals)
Open **3 separate Terminal windows** and run each emulator with its own dedicated account slice for maximum speed with **zero collisions**:

#### 💻 Terminal 1 (Instance 1 — Port 21503):
```powershell
.\run_bot.bat 127.0.0.1:21503 10 233 245
```
*(Processes accounts `user233` to `user245`)*

#### 💻 Terminal 2 (Instance 2 — Port 21513):
```powershell
.\run_bot.bat 127.0.0.1:21513 10 246 258
```
*(Processes accounts `user246` to `user258`)*

#### 💻 Terminal 3 (Instance 3 — Port 21523):
```powershell
.\run_bot.bat 127.0.0.1:21523 10 259 270
```
*(Processes accounts `user259` to `user270`)*

---

### Method 3: Sheet Device Matching
If you assign specific Device IDs in Column F of your Google Sheet, use `--match-device` so each emulator only picks its assigned accounts:
```powershell
.\run_bot.bat 127.0.0.1:21503 10 228 --match-device
```

---

## 📊 Google Sheet Column Mapping

| Column | Name | Description |
|---|---|---|
| **A** | `Timestamp` | Date & time of the record |
| **B** | `Email` | Account login email (`userXXX@...`) |
| **C** | `Password` | Account password |
| **E** | `Status` | `Processing`, `Success_Completed`, or failure status |
| **F** | `Device_ID` | Assigned emulator port (e.g. `127.0.0.1:21503`) |
| **H** | `Free_Rewards`| Updated to `6/6` upon ad completion |
| **I** | `Total_Coin` | Extracted lobby coins (e.g. `12.0K`) |
| **J** | `Latest_Update`| Real-time timestamp of when the account ran |

---

## 📁 Project Structure

```text
Yall_Farming_Bot/
│
├── run_bot.bat                     # Auto-pulls latest GitHub code & starts pipeline
├── README.md                       # Complete documentation & usage guide
├── .gitignore                      # Prevents committing temporary cache & dump files
│
└── today_downloads/
    └── qaiser new test/
        ├── master_pipeline.py          # Master orchestrator & multi-instance batch manager
        ├── main_login_page.py          # Terms checkbox verification & email button tap
        ├── login_form_handler.py       # Credential entry & login transition verification
        ├── free_reward_ad_watcher.py   # High-speed ad playback & skip state machine
        ├── lobby_navigator.py          # Reads lobby coins/diamonds & handles popups
        ├── screen_detector.py          # Screen state detector (Lobby, Landing, etc.)
        ├── fast_screen_engine.py       # Template matching & visual recognition
        ├── google_sheet_sync.py        # Webhook API caller & 24h history cooldown manager
        └── logout_handler.py           # Clean logout back to Landing Page
```

---

## 💡 Tips & Best Practices

1. **Keep Emulators Active:** Ensure MEmu emulator windows are not minimized or locked.
2. **Network Connection:** A stable internet connection ensures video ads load within 3-5 seconds.
3. **Pushing Changes:** Any code improvements pushed to this repository will be instantly downloaded by all running machines on their next `run_bot.bat` run.
