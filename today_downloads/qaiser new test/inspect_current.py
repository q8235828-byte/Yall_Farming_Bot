import sys
import os
import re

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
from screen_detector import get_screen_xml, detect_current_screen

dev = "127.0.0.1:21503"
xml = get_screen_xml(dev)
texts = re.findall(r'text="([^"]*)"', xml)
rids = re.findall(r'resource-id="([^"]*)"', xml)
print("All texts:", [t for t in texts if t])
print("\nResource IDs:")
for r in set([r for r in rids if r]):
    print("  -", r)

print("\nState:", detect_current_screen(dev))
