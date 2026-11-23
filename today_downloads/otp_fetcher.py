from datetime import datetime, timezone
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import imaplib
import re
import time
import pyperclip


def decode_mime_words(s: str) -> str:
    """Decodes email encoded headers like =?utf-8?B?...?="""
    if not s:
        return ""
    decoded_fragments = decode_header(s)
    result = []
    for text, charset in decoded_fragments:
        if isinstance(text, bytes):
            result.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(str(text))
    return "".join(result)


def extract_otp_from_text(text: str) -> str | None:
    """
    Extracts 4 to 6 digit verification code from email body or subject.
    Strips HTML tags first for clean regex matching.
    """
    clean_text = re.sub(r'<[^>]+>', ' ', text)
    clean_text = re.sub(r'\s+', ' ', clean_text)

    # 1. Look for patterns like 'code: 123456' or 'code: 314108'
    match = re.search(r'(?:code|verification|otp|pin)[^\d]{0,40}(\b\d{4,6}\b)', clean_text, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # 2. Standalone 6 digit numbers
    numbers = re.findall(r'\b\d{6}\b', clean_text)
    if numbers:
        return numbers[0]
    
    numbers_4 = re.findall(r'\b\d{4}\b', clean_text)
    if numbers_4:
        return numbers_4[0]
        
    return None


class GmailOTPFetcher:
    def __init__(self, gmail_address: str, app_password: str):
        self.gmail_address = gmail_address
        self.app_password = app_password.replace(" ", "")

    def connect(self) -> imaplib.IMAP4_SSL:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(self.gmail_address, self.app_password)
        return mail

    def wait_for_otp(
        self, 
        target_email: str = None, 
        min_timestamp: float = None,
        timeout_seconds: int = 90, 
        poll_interval: float = 1.5
    ) -> str | None:
        """
        Polls Gmail inbox for incoming verification code.
        STRICT VALIDATION:
        1. Only considers emails received AFTER min_timestamp (ignoring old emails).
        2. Strictly verifies target_email in email headers or body.
        3. Copies valid code to clipboard immediately.
        """
        print(f"[*] Waiting for OTP in Gmail ({self.gmail_address})...")
        if target_email:
            print(f"[*] Target forwarded address: {target_email}")
        if min_timestamp:
            dt_str = datetime.fromtimestamp(min_timestamp, tz=timezone.utc).strftime('%H:%M:%S UTC')
            print(f"[*] Request Time Barrier: Only accepting emails sent after {dt_str}")
            
        start_time = time.time()
        mail = None
        
        while time.time() - start_time < timeout_seconds:
            try:
                if mail is None:
                    mail = self.connect()
                    mail.select("INBOX")
                else:
                    try:
                        mail.noop()
                    except Exception:
                        mail = self.connect()
                        mail.select("INBOX")
                
                # Always inspect recent 25 emails across all messages (avoids getting stuck on old UNSEEN backlog)
                status, messages = mail.search(None, 'ALL')
                
                if status == "OK" and messages[0]:
                    email_ids = messages[0].split()
                    # Check recent 25 emails in reverse order (newest first)
                    for e_id in reversed(email_ids[-25:]):
                        _, msg_data = mail.fetch(e_id, '(RFC822)')
                        for response_part in msg_data:
                            if isinstance(response_part, tuple):
                                msg = email.message_from_bytes(response_part[1])
                                
                                subject = decode_mime_words(msg.get("Subject", ""))
                                to_header = decode_mime_words(msg.get("To", ""))
                                from_header = decode_mime_words(msg.get("From", ""))
                                delivered_to = decode_mime_words(msg.get("Delivered-To", ""))
                                x_forwarded = decode_mime_words(msg.get("X-Forwarded-To", ""))
                                date_header = msg.get("Date", "")
                                
                                # 1. Strict Timestamp Filter: Reject old emails from previous requests
                                if min_timestamp and date_header:
                                    try:
                                        email_dt = parsedate_to_datetime(date_header)
                                        email_ts = email_dt.timestamp()
                                        # Allow 45s leeway for server clock differences and email delivery latency
                                        if email_ts < (min_timestamp - 45):
                                            # This is an OLD email received before we clicked 'Obtain'
                                            continue
                                    except Exception:
                                        pass

                                # 2. Extract body
                                body = ""
                                if msg.is_multipart():
                                    for part in msg.walk():
                                        content_type = part.get_content_type()
                                        if content_type in ["text/plain", "text/html"]:
                                            payload = part.get_payload(decode=True)
                                            if payload:
                                                body += payload.decode(errors="ignore") + "\n"
                                else:
                                    payload = msg.get_payload(decode=True)
                                    if payload:
                                        body = payload.decode(errors="ignore")

                                all_text = f"{to_header} {delivered_to} {x_forwarded} {from_header} {subject} {body}".lower()

                                # Skip non-Yalla Google alerts
                                if "google" in from_header.lower() and "yalla" not in subject.lower():
                                    continue

                                # 3. Strict Target Email Match: Must match current account email
                                if target_email:
                                    target_prefix = target_email.split("@")[0].lower()
                                    if target_email.lower() not in all_text and target_prefix not in all_text:
                                        # Email is for another account, skip it!
                                        continue
                                elif "yalla" not in all_text and "code" not in subject.lower():
                                    continue

                                # 4. Extract OTP code
                                otp = extract_otp_from_text(subject + " " + body)
                                if otp:
                                    print(f"\n[+] FRESH OTP Code Verified: {otp}")
                                    try:
                                        pyperclip.copy(otp)
                                    except Exception:
                                        pass
                                    
                                    # Mark email as read
                                    try:
                                        mail.store(e_id, '+FLAGS', '\\Seen')
                                    except Exception:
                                        pass
                                    try:
                                        mail.logout()
                                    except Exception:
                                        pass
                                    return otp
                                        
                mail.logout()
            except Exception as e:
                pass
                
            time.sleep(poll_interval)
            elapsed = int(time.time() - start_time)
            print(f"\r[*] Polling Gmail... ({elapsed}s/{timeout_seconds}s)", end="", flush=True)

        print("\n[-] Timeout: No fresh OTP received.")
        return None


if __name__ == "__main__":
    import json
    import os
    
    config_file = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            cfg = json.load(f)
        
        gmail = cfg.get("gmail_address")
        app_pw = cfg.get("gmail_app_password")
        
        if gmail and app_pw and app_pw != "YOUR_APP_PASSWORD_HERE":
            fetcher = GmailOTPFetcher(gmail, app_pw)
            code = fetcher.wait_for_otp()
            print("Extracted code:", code)
