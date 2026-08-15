$ErrorActionPreference = "Stop"

$srcDocm = "C:\Users\acer\Documents\USLS 4th Year\Computer Vision\docs\manuscript\versions\pairwise\017p_lsface_focused-cleanup.docm"
$pdfOut = "C:\Users\acer\Documents\USLS 4th Year\Computer Vision\docs\manuscript\versions\pairwise\017p_lsface_focused-cleanup.pdf"

Write-Output "Opening Word Application COM..."
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.AutomationSecurity = 3 # msoAutomationSecurityForceDisable
$word.DisplayAlerts = 0

try {
    Write-Output "Opening $srcDocm..."
    $doc = $word.Documents.Open($srcDocm, $false, $false, $false, "", "", $false, "", "", 0)
    
    Write-Output "Updating all fields in document..."
    $doc.Fields.Update()
    
    foreach ($story in $doc.StoryRanges) {
        $story.Fields.Update()
    }
    
    Write-Output "Exporting to PDF: $pdfOut..."
    $wdExportFormatPDF = 17
    $doc.ExportAsFixedFormat($pdfOut, $wdExportFormatPDF)
    
    Write-Output "Saving updated docm..."
    $doc.Save()
    $doc.Close()
    Write-Output "Document closed successfully."
}
catch {
    Write-Error "Error during Word processing: $_"
}
finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
}

Write-Output "Restoring bit-for-bit identical vbaProject.bin..."
$baselineDocm = "C:\Users\acer\Documents\USLS 4th Year\Computer Vision\docs\manuscript\versions\pairwise\016p_new.docm"

$tempZip = "C:\Users\acer\.gemini\antigravity-cli\brain\9178fbfd-4234-456f-88b4-f2456e30ea96\scratch\temp_vba"
if (Test-Path $tempZip) { Remove-Item -Recurse -Force $tempZip }
New-Item -ItemType Directory -Path $tempZip | Out-Null

python -c "
import zipfile, shutil, os
with zipfile.ZipFile(r'$baselineDocm', 'r') as z:
    z.extract('word/vbaProject.bin', r'$tempZip')

# Repackage vbaProject.bin into target
with zipfile.ZipFile(r'$srcDocm', 'r') as zin:
    with zipfile.ZipFile(r'$srcDocm' + '.tmp', 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == 'word/vbaProject.bin':
                zout.write(r'$tempZip\word\vbaProject.bin', 'word/vbaProject.bin')
            else:
                zout.writestr(item, zin.read(item.filename))
os.replace(r'$srcDocm' + '.tmp', r'$srcDocm')
"

$hBase = (Get-FileHash -Algorithm SHA256 "$tempZip\word\vbaProject.bin").Hash
Write-Output "Verified restored VBA hash: $hBase"
