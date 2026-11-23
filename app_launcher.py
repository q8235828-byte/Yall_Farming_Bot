import os
import sys
import threading
import time
import webbrowser

# PyInstaller bundle directory handling
if getattr(sys, "frozen", False):
    BUNDLE_DIR = sys._MEIPASS
    APP_DIR = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR = BUNDLE_DIR

sys.path.insert(0, BUNDLE_DIR)
sys.path.insert(0, os.path.join(BUNDLE_DIR, "dashboard"))
sys.path.insert(0, os.path.join(BUNDLE_DIR, "today_downloads", "qaiser new test"))

from dashboard.server import app


def open_ui():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    print("=" * 65)
    print("   🎲 YALLA FARMING STUDIO ENTERPRISE PRO v2.5")
    print("   RankerX-Grade Multi-Instance Engine & HWID Licensing")
    print("=" * 65)
    print("[*] Launching Dashboard on http://127.0.0.1:5000 ...")
    
    threading.Thread(target=open_ui, daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
