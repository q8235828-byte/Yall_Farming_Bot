import os, sys, time
from datetime import datetime, timedelta

sys.path.insert(0, r"C:\Users\admin\codebase")
from today_downloads.reward_collect.google_sheet_sync import (
    record_account_completed,
    check_account_cooldown,
    is_account_eligible_to_process,
    get_next_accounts_to_process,
    load_24h_history,
    save_24h_history
)

print("="*70)
print("UNIT TEST: 24-HOUR COOLDOWN & ELIGIBILITY VERIFICATION")
print("="*70)

# Test 1: Just completed account (0 hours ago)
test_email_1 = "test_cooldown_active@example.com"
record_account_completed(test_email_1, free_rewards="6/6", golds_chest="Yes", status="Success_Completed")

acc_1 = {
    "Email": test_email_1,
    "Status": "Success_Completed",
    "Free_Rewards": "6/6",
    "Golds_Chest": "Yes",
    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}
is_cd_1, rem_1, reason_1 = check_account_cooldown(acc_1)
print(f"\n[Test 1] Just Completed Account: {test_email_1}")
print(f"  - Is On Cooldown: {is_cd_1} (Expected: True)")
print(f"  - Hours Remaining: {rem_1:.2f}h")
print(f"  - Reason: {reason_1}")
print(f"  - Eligible to Process: {is_account_eligible_to_process(acc_1)} (Expected: False)")
assert is_cd_1 == True, "Failed: Should be on cooldown!"
assert is_account_eligible_to_process(acc_1) == False, "Failed: Should NOT be eligible!"

# Test 2: Account completed 25 hours ago (> 24h passed)
test_email_2 = "test_25h_expired@example.com"
history = load_24h_history()
ts_25h_ago = time.time() - (25 * 3600)
dt_25h_ago = datetime.fromtimestamp(ts_25h_ago).strftime("%Y-%m-%d %H:%M:%S")
history[test_email_2] = {
    "email": test_email_2,
    "completed_at_timestamp": ts_25h_ago,
    "completed_at_datetime": dt_25h_ago,
    "free_rewards": "6/6",
    "golds_chest": "Yes",
    "status": "Success_Completed"
}
save_24h_history(history)

acc_2 = {
    "Email": test_email_2,
    "Status": "Success_Completed",
    "Free_Rewards": "6/6",
    "Golds_Chest": "Yes",
    "Timestamp": dt_25h_ago
}
is_cd_2, rem_2, reason_2 = check_account_cooldown(acc_2)
print(f"\n[Test 2] Account Completed 25h Ago: {test_email_2}")
print(f"  - Is On Cooldown: {is_cd_2} (Expected: False)")
print(f"  - Hours Remaining: {rem_2:.2f}h")
print(f"  - Reason: {reason_2}")
print(f"  - Eligible to Process: {is_account_eligible_to_process(acc_2)} (Expected: True)")
assert is_cd_2 == False, "Failed: Cooldown should be expired!"
assert is_account_eligible_to_process(acc_2) == True, "Failed: Should be eligible for daily refresh!"

# Test 3: Account with incomplete rewards (e.g. 3/6 ads, Golds Chest No)
acc_3 = {
    "Email": "test_incomplete@example.com",
    "Status": "Processing",
    "Free_Rewards": "3/6",
    "Golds_Chest": "No",
    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}
is_cd_3, rem_3, reason_3 = check_account_cooldown(acc_3)
print(f"\n[Test 3] Incomplete Account (3/6 ads):")
print(f"  - Is On Cooldown: {is_cd_3} (Expected: False)")
print(f"  - Eligible to Process: {is_account_eligible_to_process(acc_3)} (Expected: True)")
assert is_cd_3 == False, "Failed: Incomplete account should NOT be on cooldown!"
assert is_account_eligible_to_process(acc_3) == True, "Failed: Incomplete account should be eligible!"

# Cleanup test records from history
history = load_24h_history()
history.pop(test_email_1, None)
history.pop(test_email_2, None)
save_24h_history(history)

print("\n" + "="*70)
print("ALL UNIT TESTS PASSED SUCCESSFULLY! 24-HOUR RULE FULLY VERIFIED [OK]")
print("="*70)
