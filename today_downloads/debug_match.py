import yalla_ui_automator as ui
import xml.etree.ElementTree as ET

xml_str = ui.run_adb_command(["shell", "cat", "/sdcard/window_dump.xml"], "127.0.0.1:21623")
root = ET.fromstring(xml_str)
identifier = ui.RESOURCE_IDS['otp_input']
print("Looking for identifier:", identifier)
for elem in root.iter():
    rid = elem.attrib.get("resource-id", "")
    txt = elem.attrib.get("text", "")
    if rid == identifier or txt == identifier or identifier in rid:
        print("MATCHED:", elem.attrib)
