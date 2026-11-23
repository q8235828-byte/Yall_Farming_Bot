import email
from email.header import decode_header
import imaplib
import json
import os
import re
import sys
import time

from airplane_mode import run_adb_command
from otp_fetcher import decode_mime_words, extract_otp_from_text

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def copy_to_phone_clipboard(text: str, device_id: str = None):
    """Sends text directly to Android phone's clipboard."""
    try:
        run_adb_command([
            "shell", "am", "broadcast", 
            "-n", "ca.zgrs.clipper/.ClipperReceiver", 
            "-a", "clipper.set", 
            "-e", "text", text
        ], device_id)
        print(f"[PHONE CLIPBOARD] Copied '{text}' to mobile clipboard!")
    except Exception as e:
        print(f"[!] Phone clipboard error: {e}")


def paste_or_type_to_phone(text: str, device_id: str = None):
    """Types the text directly into the phone's focused input box."""
    try:
        run_adb_command(["shell", "input", "text", text], device_id)
        print(f"[PHONE AUTO-INPUT] Typed '{text}' directly on phone screen!")
    except Exception as e:
        print(f"[!] Auto-input error: {e}")


def start_live_gmail_watcher():
    config = load_config()
    gmail_address = config.get("gmail_address")
    app_password = config.get("gmail_app_password", "").replace(" ", "")

    if not gmail_address or app_password == "YOUR_16_DIGIT_APP_PASSWORD":
        print("[ERROR] Please set your 'gmail_address' and 'gmail_app_password' in config.json first!")
        return

    print("=" * 60)
    print("   REAL-TIME GMAIL OTP LISTENER (AUTO-COPY & PASTE TO PHONE)")
    print("=" * 60)
    print(f"[*] Monitoring Gmail: {gmail_address}")
    print("[*] Status: Listening for Yalla Ludo verification emails...")
    print("[*] Press Ctrl + C to stop at any time.\n")

    # Set of already processed message IDs to avoid duplicates
    processed_ids = set()

    # Pre-populate with existing unseen IDs so we only catch NEW ones
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(gmail_address, app_password)
        mail.select("INBOX")
        _, existing = mail.search(None, 'ALL')
        if existing[0]:
            # Remember the latest 10 existing emails so we don't trigger old codes
            for eid in existing[0].split()[-10:]:
                processed_ids.add(eid)
        mail.logout()
    except Exception as e:
        print(f"[!] Initial connection notice: {e}")

    while True:
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            mail.login(gmail_address, app_password)
            mail.select("INBOX")

            # Check UNSEEN first
            status, messages = mail.search(None, 'UNSEEN')
            email_ids = messages[0].split() if (status == "OK" and messages[0]) else []

            # If no unread, also check latest 3 emails (in case marked read)
            if not email_ids:
                status, all_msgs = mail.search(None, 'ALL')
                if status == "OK" and all_msgs[0]:
                    email_ids = all_msgs[0].split()[-3:]

            for e_id in reversed(email_ids):
                if e_id in processed_ids:
                    continue

                _, msg_data = mail.fetch(e_id, '(RFC822)')
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject = decode_mime_words(msg.get("Subject", ""))
                        from_header = decode_mime_words(msg.get("From", ""))
                        to_header = decode_mime_words(msg.get("To", ""))
                        delivered_to = decode_mime_words(msg.get("Delivered-To", ""))
                        
                        if "google" in from_header.lower() and "yalla" not in subject.lower():
                            continue  # Skip Google security alerts

                        all_txt = f"{subject} {from_header} {to_header} {delivered_to}".lower()
                        # Match Yalla or verification keyword
                        is_target = any(k in all_txt for k in ["yalla", "ludo", "verification code"])

                        if is_target:
                            body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_type() in ["text/plain", "text/html"]:
                                        payload = part.get_payload(decode=True)
                                        if payload:
                                            body += payload.decode(errors="ignore") + "\n"
                            else:
                                payload = msg.get_payload(decode=True)
                                if payload:
                                    body = payload.decode(errors="ignore")

                            otp = extract_otp_from_text(subject + " " + body)
                            if otp:
                                print(f"\n[{time.strftime('%H:%M:%S')}] >>> NEW YALLA LUDO OTP DETECTED: {otp} <<<")
                                
                                # 1. Copy to Phone Clipboard
                                copy_to_phone_clipboard(otp)
                                
                                # 2. Direct Type/Paste into active input on phone screen
                                paste_or_type_to_phone(otp)

                                # Mark as processed
                                processed_ids.add(e_id)
                                mail.store(e_id, '+FLAGS', '\\Seen')
                                print("[OK] Successfully sent to Phone! Ready for next email...\n")

            mail.logout()
        except imaplib.IMAP4.error as e:
            print(f"[!] IMAP Auth/Connection Error: {e}")
            time.sleep(5)
        except Exception as e:
            time.sleep(2)

        # Poll interval: fast 1.5 seconds check
        time.sleep(1.5)


if __name__ == "__main__":
    try:
        start_live_gmail_watcher()
    except KeyboardInterrupt:
        print("\n[*] Listener stopped by user.")
