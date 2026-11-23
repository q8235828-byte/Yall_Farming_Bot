import xml.etree.ElementTree as ET
import glob

print("Scanning XML files...")
for f in sorted(glob.glob("*.xml")):
    try:
        tree = ET.parse(f)
        matches = []
        for node in tree.iter():
            txt = (node.attrib.get('text') or '').strip()
            rid = (node.attrib.get('resource-id') or '').strip()
            bounds = node.attrib.get('bounds', '')
            keywords = ['password', 'confirm', 'expert', 'sign up', 'obtain', 'verification', 'email', 'settings', 'logout', 'log out']
            if any(k in txt.lower() or k in rid.lower() for k in keywords):
                if 'terms' not in txt.lower() and 'yallachat' not in txt.lower() and 'facebook' not in txt.lower():
                    matches.append(f"    id='{rid}' text='{txt}' bounds={bounds}")
        if matches:
            print(f"=== {f} ===")
            for m in matches[:10]:
                print(m)
    except Exception as e:
        pass
