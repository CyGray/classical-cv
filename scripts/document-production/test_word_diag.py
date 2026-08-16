import os
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\acer\Documents\USLS 4th Year\Computer Vision")
src = PROJECT_ROOT / "docs" / "manuscript" / "versions" / "pairwise" / "018p_polish_run.docm"
test_docm = PROJECT_ROOT / "docs" / "manuscript" / "versions" / "pairwise" / "test_word.docm"

with zipfile.ZipFile(src, "r") as zin:
    items = {item.filename: zin.read(item.filename) for item in zin.infolist()}

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("w", W_NS)

root = ET.fromstring(items["word/document.xml"])
body = root.find(f"{{{W_NS}}}body")

# Test 1: Simple text change in Section 3.2
for child in body:
    if child.tag.endswith("p"):
        for t in child.iter():
            if t.tag.endswith("}t") and t.text and "robustness under the 41 image modifications" in t.text:
                t.text = t.text.replace("robustness under the 41 image modifications", "robustness under the 41 image transformations")

items["word/document.xml"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)

with zipfile.ZipFile(test_docm, "w", zipfile.ZIP_DEFLATED) as zout:
    for fname, content in items.items():
        zout.writestr(fname, content)

ps_code = f"""
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {{
    $doc = $word.Documents.Open('{test_docm}', $false, $false, $false, '', '', $false, '', '', 0)
    Write-Output 'Success opening Test 1 docm!'
    $doc.Close()
}} catch {{
    Write-Output "Error: $_"
}} finally {{
    $word.Quit()
}}
"""

res = subprocess.run(["pwsh", "-Command", ps_code], capture_output=True, text=True)
print("STDOUT:", res.stdout)

