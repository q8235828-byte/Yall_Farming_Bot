"""
================================================================================
REWARD COLLECT - CAPTCHA HANDLER
================================================================================
Module: reward_collect/captcha_handler.py
Purpose:
- Integrates the intelligent ColorIndexedCaptchaSolver for Yalla Ludo login.
- Solves Geetest slider puzzle using multi-threshold shadow cutout detection
  and color-profile fallback calibration.
- Verifies post-solve transition into Game Hall / Lobby.
================================================================================
"""

import os
import sys
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

from color_indexed_captcha_solver import ColorIndexedCaptchaSolver


def solve_login_captcha(device_id: str = "127.0.0.1:21613", max_attempts: int = 3) -> bool:
    print("\n" + "="*70)
    print("   REWARD COLLECT -> INTELLIGENT CAPTCHA SOLVER EXECUTION")
    print(f"   Target Device: {device_id}")
    print(f"   Max Attempts: {max_attempts}")
    print("="*70 + "\n")

    solver = ColorIndexedCaptchaSolver(device_id=device_id)

    # Step 1: Execute solve sequence
    print("[*] Running Color-Indexed Captcha Solver...")
    success = solver.solve(max_attempts=max_attempts)

    # Step 2: Verification
    print("\n" + "="*70)
    if success:
        print("   RESULT: Captcha Solved Successfully [OK]!")
    else:
        print("   RESULT: Captcha Solve Failed or Timed Out [FAILED]")
    print("="*70 + "\n")
    return success


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:21613"
    attempts = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    solve_login_captcha(target, attempts)
