param(
    [string]$Baseline = "docs\manuscript\versions\006c_lsface_independence-finalization.docm",
    [string]$Output = "docs\manuscript\versions\007_lsface_robustness-results.docm",
    [string]$CurrentManuscript = "docs\manuscript\lsface.docm",
    [string]$PdfOutput = "$env:TEMP\lsface_007_robustness-results.pdf"
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Get-ZipPartHash([string]$Path, [string]$PartName) {
    $archive = [System.IO.Compression.ZipFile]::OpenRead($Path)
    try {
        $entry = $archive.GetEntry($PartName)
        if ($null -eq $entry) { throw "Missing $PartName in $Path" }
        $stream = $entry.Open()
        try { return (Get-FileHash -Algorithm SHA256 -InputStream $stream).Hash }
        finally { $stream.Dispose() }
    }
    finally { $archive.Dispose() }
}

function Restore-ZipPart([string]$ReferencePath, [string]$TargetPath, [string]$PartName) {
    $temporaryPath = "$TargetPath.repacked"
    if (Test-Path -LiteralPath $temporaryPath) { Remove-Item -LiteralPath $temporaryPath -Force }
    $reference = [System.IO.Compression.ZipFile]::OpenRead($ReferencePath)
    $target = [System.IO.Compression.ZipFile]::OpenRead($TargetPath)
    $replacement = [System.IO.Compression.ZipFile]::Open($temporaryPath, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        $referencePart = $reference.GetEntry($PartName)
        if ($null -eq $referencePart) { throw "Missing $PartName in baseline." }
        foreach ($entry in $target.Entries) {
            $newEntry = $replacement.CreateEntry($entry.FullName, [System.IO.Compression.CompressionLevel]::Optimal)
            $sourceEntry = if ($entry.FullName -eq $PartName) { $referencePart } else { $entry }
            $input = $sourceEntry.Open()
            $output = $newEntry.Open()
            try { $input.CopyTo($output) }
            finally { $output.Dispose(); $input.Dispose() }
        }
    }
    finally { $replacement.Dispose(); $target.Dispose(); $reference.Dispose() }
    Move-Item -LiteralPath $temporaryPath -Destination $TargetPath -Force
}

$baselinePath = (Resolve-Path -LiteralPath $Baseline).Path
$outputPath = Join-Path (Get-Location) $Output
$currentPath = Join-Path (Get-Location) $CurrentManuscript
$pdfPath = $PdfOutput
$outputDirectory = Split-Path -Parent $outputPath

if (Test-Path -LiteralPath $outputPath) { throw "Refusing to overwrite existing version: $outputPath" }
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
Copy-Item -LiteralPath $baselinePath -Destination $outputPath

$vbaPart = 'word/vbaProject.bin'
$baselineVbaHash = Get-ZipPartHash $baselinePath $vbaPart

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$word.AutomationSecurity = 3 # msoAutomationSecurityForceDisable
$document = $null
try {
    $document = $word.Documents.Open($outputPath, $false, $false)

    $referencesParagraph = $null
    for ($index = 1; $index -le $document.Paragraphs.Count; $index++) {
        $paragraph = $document.Paragraphs.Item($index)
        $text = $paragraph.Range.Text.Trim([char]13, [char]7)
        if ($text -eq 'References') { $referencesParagraph = $paragraph; break }
    }
    if ($null -eq $referencesParagraph) { throw 'References heading not found.' }

    $independenceParagraph = $null
    for ($index = 1; $index -le $document.Paragraphs.Count; $index++) {
        $paragraph = $document.Paragraphs.Item($index)
        $text = $paragraph.Range.Text.Trim([char]13, [char]7)
        if ($text -eq 'Independence Test: Frozen Operating Points') { $independenceParagraph = $paragraph; break }
    }
    if ($null -eq $independenceParagraph) { throw 'Independence subsection heading not found.' }
    $independenceParagraph.Range.Style = $document.Styles.Item('heading2')
    $independenceParagraph.Range.ParagraphFormat.PageBreakBefore = 0

    $cursor = $referencesParagraph.Range.Duplicate
    $cursor.Collapse(1) # wdCollapseStart

    function Insert-StyledParagraph([string]$Text, [string]$StyleName) {
        $range = $script:cursor.Duplicate
        $range.Text = "$Text`r"
        $range.Style = $document.Styles.Item($StyleName)
        $script:cursor.SetRange($range.End, $range.End)
        return $range
    }

    $heading = Insert-StyledParagraph 'LFW2 Robustness Evaluation' 'heading2'
    $heading.ParagraphFormat.KeepWithNext = -1
    $heading.ParagraphFormat.PageBreakBefore = -1

    $summary = Insert-StyledParagraph 'Table 4 summarizes gallery/probe-disjoint LFW2 1-to-N identification robustness at the frozen deployment thresholds. Across all 41 modifications, SFace and the cascade retain 80.65% AR, whereas LBPH alone retains 1.41%. The cascade escalates 97.51% of probes to SFace; isolated latency is reported from a 575-identity subset.' 'p1a'
    $summary.ParagraphFormat.KeepWithNext = -1

    $caption = Insert-StyledParagraph 'Table 4. LFW2 1-to-N identification robustness at frozen deployment thresholds.' 'tablecaption'
    $caption.ParagraphFormat.KeepWithNext = -1

    $table = $document.Tables.Add($cursor.Duplicate, 4, 5)
    $table.Style = 'Table Normal'
    $table.AllowAutoFit = $false
    $table.Rows.Alignment = 0 # wdAlignRowCenter
    $table.LeftPadding = 3.6
    $table.RightPadding = 3.6
    $table.TopPadding = 0
    $table.BottomPadding = 0
    $table.Rows.AllowBreakAcrossPages = $false
    $table.Rows.Item(1).HeadingFormat = -1

    $headers = @('Mode', "AR`n(%)", "Latency`n(ms)", "FAR`n(%)", "Escalation`n(%)")
    $rows = @(
        @('Classical CV (LBPH)', '1.41', '72.49', '0.0010', 'N/A'),
        @('Deep Learning (SFace)', '80.65', '84.36', '~0.0010', 'N/A'),
        @('Hybrid Cascade', '80.65', '82.54', (([string][char]0x2264) + '0.0020'), '97.51')
    )
    $widths = @(112, 58, 82, 78, 94)

    for ($column = 1; $column -le 5; $column++) {
        $table.Columns.Item($column).Width = $widths[$column - 1]
    }
    for ($row = 1; $row -le 4; $row++) {
        for ($column = 1; $column -le 5; $column++) {
            $cell = $table.Cell($row, $column)
            $value = if ($row -eq 1) { $headers[$column - 1] } else { $rows[$row - 2][$column - 1] }
            $cell.Range.Text = $value
            $cell.Range.Style = $document.Styles.Item('tablecaption')
            $cell.Range.Font.Name = 'Times New Roman'
            $cell.Range.Font.Size = 9
            $cell.Range.Font.Bold = if ($row -eq 1) { -1 } else { 0 }
            $cell.Range.ParagraphFormat.Alignment = 1 # wdAlignParagraphCenter
            $cell.Range.ParagraphFormat.SpaceBefore = 0
            $cell.Range.ParagraphFormat.SpaceAfter = 0
            foreach ($borderIndex in 1..4) {
                $border = $cell.Borders.Item($borderIndex)
                $border.LineStyle = 0
            }
        }
    }
    foreach ($borderIndex in 1..8) { $table.Borders.Item($borderIndex).LineStyle = 0 }
    $table.Borders.Item(1).LineStyle = 1 # wdBorderTop
    $table.Borders.Item(1).LineWidth = 12 # wdLineWidth150pt
    $table.Borders.Item(3).LineStyle = 1 # wdBorderBottom
    $table.Borders.Item(3).LineWidth = 12
    for ($column = 1; $column -le 5; $column++) {
        $headerBottom = $table.Cell(1, $column).Borders.Item(3)
        $headerBottom.LineStyle = 1
        $headerBottom.LineWidth = 6 # wdLineWidth075pt
    }

    $cursor.SetRange($table.Range.End, $table.Range.End)
    $cascadeFarBound = ([string][char]0x2264) + '0.0020%'
    $noteText = "Overall AR and escalation are means across 41 modifications (5,749 enrolled identities; 1,680 probes; strict no-face policy). Latencies are isolated means from a 575-identity/172-probe subset. Standalone FAR values are LFW1 9.986-ppm calibrations; SFace is approximate at the deployed boundary. Cascade $cascadeFarBound is a conservative union bound, not a measured joint FAR."
    $note = Insert-StyledParagraph $noteText 'p1a'
    $note.Font.Name = 'Times New Roman'
    $note.Font.Size = 8
    $note.ParagraphFormat.SpaceAfter = 6

    $document.Save()
    $document.ExportAsFixedFormat($pdfPath, 17) # wdExportFormatPDF
}
finally {
    if ($null -ne $document) { $document.Close(0); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($document) }
    $word.Quit()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word)
}

Restore-ZipPart $baselinePath $outputPath $vbaPart
$outputVbaHash = Get-ZipPartHash $outputPath $vbaPart
if ($outputVbaHash -ne $baselineVbaHash) { throw 'VBA hash mismatch after restoration.' }
Copy-Item -LiteralPath $outputPath -Destination $currentPath -Force
$currentVbaHash = Get-ZipPartHash $currentPath $vbaPart
if ($currentVbaHash -ne $baselineVbaHash) { throw 'Current manuscript VBA hash mismatch.' }

Write-Output "DOCM=$outputPath"
Write-Output "PDF=$pdfPath"
Write-Output "VBA_SHA256=$outputVbaHash"
