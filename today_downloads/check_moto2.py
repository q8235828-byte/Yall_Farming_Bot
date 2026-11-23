import subprocess

script = """
Get-PnpDevice | Where-Object { $_.Status -eq 'OK' -and $_.InstanceId -like "*22B8*" } | Select-Object FriendlyName, InstanceId | Format-List
"""
res = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True)
print(res.stdout)
