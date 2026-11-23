import sys
import xml.etree.ElementTree as ET

xml_file = sys.argv[1] if len(sys.argv) > 1 else "ui_login.xml"
tree = ET.parse(xml_file)
root = tree.getroot()

print(f"{'TEXT':<30} | {'RESOURCE-ID':<40} | {'BOUNDS':<20}")
print("-" * 95)
for elem in root.iter():
    text = elem.attrib.get('text', '')
    res_id = elem.attrib.get('resource-id', '')
    bounds = elem.attrib.get('bounds', '')
    if text or res_id:
        print(f"{text:<30} | {res_id:<40} | {bounds:<20}")
