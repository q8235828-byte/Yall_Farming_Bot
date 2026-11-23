import subprocess

script = """
Get-PnpDevice | Where-Object { $_.Status -eq 'OK' -and ($_.Class -match 'Android|WPD|USB' -or $_.FriendlyName -match 'Phone|Mobile') } | Select-Object FriendlyName, Class, InstanceId | Format-Table -AutoSize
"""
res = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print("Error:", res.stderr)
