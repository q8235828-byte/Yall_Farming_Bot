import subprocess

script = """
Get-PnpDevice | Where-Object { $_.InstanceId -like "*22B8*" } | Select-Object FriendlyName, Status, ConfigManagerErrorCode, Class, Problem | Format-Table -AutoSize
"""
res = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print("Error:", res.stderr)
