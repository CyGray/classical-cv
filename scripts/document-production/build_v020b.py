"""Build 020b manuscript with updated Figure 3 and verify VBA integrity."""

import hashlib
import io
import os
import shutil
import subprocess
import sys
import zipfile
from PIL import Image

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = r"C:\Users\acer\Documents\USLS 4th Year\Computer Vision"
BASELINE_DOCM = os.path.join(ROOT, r"docs\manuscript\versions\020p_lsface_canonical-selfmatch-promoted.docm")
OUTPUT_DOCM = os.path.join(ROOT, r"docs\manuscript\versions\020b_lsface_canonical-selfmatch-promoted.docm")
OUTPUT_PDF = os.path.join(ROOT, r"docs\manuscript\versions\020b_lsface_canonical-selfmatch-promoted.pdf")

FIG3_SVG = os.path.join(ROOT, r"docs\manuscript\figures\fig3_frozen_threshold_overlay.svg")
FIG3_PNG = os.path.join(ROOT, r"docs\manuscript\figures\fig3_frozen_threshold_overlay.png")

def get_vba_hash(path):
    with zipfile.ZipFile(path, "r") as z:
        return hashlib.sha256(z.read("word/vbaProject.bin")).hexdigest()

def main():
    print(f"Starting build of 020b from {BASELINE_DOCM}...")
    baseline_vba = get_vba_hash(BASELINE_DOCM)
    print(f"Baseline VBA Hash: {baseline_vba}")

    # Measure PNG aspect ratio
    with Image.open(FIG3_PNG) as img:
        w_px, h_px = img.size
    aspect_ratio = h_px / w_px
    print(f"Fig 3 image size: {w_px}x{h_px}, aspect ratio: {aspect_ratio:.5f}")

    # Standard LNCS text column width in EMU
    cx = 4381500 # ~ 4.791666 inches
    cy = int(round(cx * aspect_ratio))
    print(f"Setting Word drawing extent: cx={cx}, cy={cy}")

    with zipfile.ZipFile(BASELINE_DOCM, "r") as z:
        xml_text = z.read("word/document.xml").decode("utf-8")

    # Target exact replacement of Fig 3 cy extent around rId13
    old_target = '<wp:extent cx="4381500" cy="1485876"/>'
    new_target = f'<wp:extent cx="4381500" cy="{cy}"/>'
    assert old_target in xml_text, "Could not find wp:extent in document.xml"
    xml_text = xml_text.replace(old_target, new_target, 1)

    old_ext = '<a:ext cx="4381500" cy="1485876"/>'
    new_ext = f'<a:ext cx="4381500" cy="{cy}"/>'
    assert old_ext in xml_text, "Could not find a:ext in document.xml"
    xml_text = xml_text.replace(old_ext, new_ext, 1)
    print("Updated Fig 3 drawing extent via clean string substitution.")

    with open(FIG3_PNG, "rb") as f:
        png_bytes = f.read()
    with open(FIG3_SVG, "rb") as f:
        svg_bytes = f.read()

    # Create new docm
    temp_docm = OUTPUT_DOCM + ".temp"
    with zipfile.ZipFile(BASELINE_DOCM, "r") as zin:
        with zipfile.ZipFile(temp_docm, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == "word/document.xml":
                    zout.writestr(item.filename, xml_text.encode("utf-8"))
                elif item.filename == "word/media/image5.png":
                    zout.writestr(item.filename, png_bytes)
                elif item.filename == "word/media/image6.svg":
                    zout.writestr(item.filename, svg_bytes)
                else:
                    zout.writestr(item.filename, zin.read(item.filename))

    shutil.move(temp_docm, OUTPUT_DOCM)
    print(f"Created {OUTPUT_DOCM}")

    # Export PDF via Word COM
    ps_export = f"""
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$docPath = "{OUTPUT_DOCM}"
$pdfOut = "{OUTPUT_PDF}"
$doc = $word.Documents.Open($docPath, $false, $false)
$doc.Fields.Update()
foreach ($story in $doc.StoryRanges) {{ $story.Fields.Update() }}
$doc.Repaginate()
$pageCount = [int]$doc.ComputeStatistics(2)
Write-Output ("Document page count: " + $pageCount)
$doc.Save()
$doc.ExportAsFixedFormat($pdfOut, 17)
$doc.Close(0)
$word.Quit()
[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc)
[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
"""
    ps_script_path = os.path.join(ROOT, r"scripts\document-production\export_pdf_020b.ps1")
    with open(ps_script_path, "w", encoding="utf-8") as f:
        f.write(ps_export)

    print("Running Word COM PDF export...")
    subprocess.run(["pwsh", "-ExecutionPolicy", "Bypass", "-File", ps_script_path], check=True)
    print(f"Exported PDF: {OUTPUT_PDF}")

    # Restore bit-for-bit VBA binary
    with zipfile.ZipFile(BASELINE_DOCM, "r") as z_base:
        vba_bytes = z_base.read("word/vbaProject.bin")

    temp_docm_vba = OUTPUT_DOCM + ".vba_restore"
    with zipfile.ZipFile(OUTPUT_DOCM, "r") as zin:
        with zipfile.ZipFile(temp_docm_vba, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == "word/vbaProject.bin":
                    zout.writestr(item.filename, vba_bytes)
                else:
                    zout.writestr(item.filename, zin.read(item.filename))

    shutil.move(temp_docm_vba, OUTPUT_DOCM)
    final_vba = get_vba_hash(OUTPUT_DOCM)
    print(f"Final 020b VBA Hash: {final_vba}")
    assert final_vba == baseline_vba, f"VBA mismatch: {final_vba} != {baseline_vba}"
    print("VBA integrity VERIFIED.")

    # Render PDF pages to PNG for visual inspection
    import fitz
    render_dir = os.path.join(ROOT, r"docs\manuscript\versions\_page_renders_020b")
    os.makedirs(render_dir, exist_ok=True)
    doc = fitz.open(OUTPUT_PDF)
    print(f"PDF has {len(doc)} pages.")
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=200)
        page_png = os.path.join(render_dir, f"page_{i+1:02d}.png")
        pix.save(page_png)
    print(f"Rendered all {len(doc)} pages to {render_dir}")


if __name__ == "__main__":
    main()
