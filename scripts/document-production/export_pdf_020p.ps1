
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$docPath = "C:\Users\acer\Documents\USLS 4th Year\Computer Vision\docs\manuscript\versions\020p_lsface_canonical-selfmatch-promoted.docm"
$pdfOut = "C:\Users\acer\Documents\USLS 4th Year\Computer Vision\docs\manuscript\versions\020p_lsface_canonical-selfmatch-promoted.pdf"
$doc = $word.Documents.Open($docPath, $false, $false)
$doc.Fields.Update()
foreach ($story in $doc.StoryRanges) { $story.Fields.Update() }
$doc.Repaginate()
$pageCount = [int]$doc.ComputeStatistics(2)
Write-Output ("Document page count: " + $pageCount)
$doc.Save()
$doc.ExportAsFixedFormat($pdfOut, 17)
$doc.Close(0)
$word.Quit()
[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc)
[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
