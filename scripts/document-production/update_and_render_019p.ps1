$ErrorActionPreference = "Stop"

$srcDocm = "C:\Users\acer\Documents\USLS 4th Year\Computer Vision\docs\manuscript\versions\pairwise\019p_lsface_reproducibility-pass.docm"
$pdfOut = "C:\Users\acer\Documents\USLS 4th Year\Computer Vision\docs\manuscript\versions\pairwise\019p_lsface_reproducibility-pass.pdf"
$baselineDocm = "C:\Users\acer\Documents\USLS 4th Year\Computer Vision\docs\manuscript\versions\pairwise\018p_polish_run.docm"

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
$tempZip = "C:\Users\acer\.gemini\antigravity-cli\brain\9fa30ac3-4dd1-44b7-ba43-1aa936eef803\scratch\temp_vba"
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
$hTarget = (Get-FileHash -Algorithm SHA256 "$srcDocm").Hash
$hTargetVba = python -c "
import zipfile, hashlib
with zipfile.ZipFile(r'$srcDocm', 'r') as z:
    print(hashlib.sha256(z.read('word/vbaProject.bin')).hexdigest().upper())
"

Write-Output "Baseline VBA hash: $hBase"
Write-Output "Restored VBA hash: $hTargetVba"
if ($hBase -ne $hTargetVba) {
    Write-Error "VBA hash mismatch after restore!"
} else {
    Write-Output "VBA project bit-for-bit verified identical!"
}
