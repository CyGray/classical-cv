[CmdletBinding()]
param(
    [string]$Source = 'docs\manuscript\versions\011_lsface_dl-trio-selection.docm',
    [string]$Output = 'docs\manuscript\versions\012_lsface_dl-trio-selection-layout-fixed.docm',
    [string]$CurrentManuscript = 'docs\manuscript\lsface.docm',
    [string]$ReferenceTemplate = 'docs\manuscript\sample\sample.docm',
    [string]$VbaBaseline = 'docs\manuscript\versions\010_lsface_before-dl-trio-selection.docm',
    [string]$PdfOutput = "$env:TEMP\lsface_012_dl-trio-selection.pdf"
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Resolve-WorkspacePath {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) { return [System.IO.Path]::GetFullPath($Path) }
    return [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Path))
}

function Get-ZipPartHash {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$PartName
    )

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

function Restore-ZipPart {
    param(
        [Parameter(Mandatory = $true)][string]$ReferencePath,
        [Parameter(Mandatory = $true)][string]$TargetPath,
        [Parameter(Mandatory = $true)][string]$PartName
    )

    $temporaryPath = "$TargetPath.repacked"
    if (Test-Path -LiteralPath $temporaryPath) { Remove-Item -LiteralPath $temporaryPath -Force }
    $reference = [System.IO.Compression.ZipFile]::OpenRead($ReferencePath)
    $target = [System.IO.Compression.ZipFile]::OpenRead($TargetPath)
    $replacement = [System.IO.Compression.ZipFile]::Open(
        $temporaryPath,
        [System.IO.Compression.ZipArchiveMode]::Create
    )
    try {
        $referencePart = $reference.GetEntry($PartName)
        if ($null -eq $referencePart) { throw "Missing $PartName in VBA baseline." }
        foreach ($entry in $target.Entries) {
            $newEntry = $replacement.CreateEntry($entry.FullName, [System.IO.Compression.CompressionLevel]::Optimal)
            $sourceEntry = if ($entry.FullName -eq $PartName) { $referencePart } else { $entry }
            $input = $sourceEntry.Open()
            $output = $newEntry.Open()
            try { $input.CopyTo($output) }
            finally {
                $output.Dispose()
                $input.Dispose()
            }
        }
    }
    finally {
        $replacement.Dispose()
        $target.Dispose()
        $reference.Dispose()
    }
    Move-Item -LiteralPath $temporaryPath -Destination $TargetPath -Force
}

function Get-CleanText {
    param([Parameter(Mandatory = $true)]$Range)

    return (($Range.Text -replace '[\r\a]', ' ') -replace '\s+', ' ').Trim()
}

function Copy-CaptionStyleDefinition {
    param(
        [Parameter(Mandatory = $true)]$TargetDocument,
        [Parameter(Mandatory = $true)]$ReferenceDocument,
        [Parameter(Mandatory = $true)][string]$StyleName
    )

    $target = $TargetDocument.Styles.Item($StyleName)
    $reference = $ReferenceDocument.Styles.Item($StyleName)
    $target.Font.Name = $reference.Font.Name
    $target.Font.Size = $reference.Font.Size
    $target.Font.Bold = $reference.Font.Bold
    $target.Font.Italic = $reference.Font.Italic
    $target.ParagraphFormat.Alignment = $reference.ParagraphFormat.Alignment
    $target.ParagraphFormat.SpaceBefore = $reference.ParagraphFormat.SpaceBefore
    $target.ParagraphFormat.SpaceAfter = $reference.ParagraphFormat.SpaceAfter
    $target.ParagraphFormat.LineSpacing = $reference.ParagraphFormat.LineSpacing
    $target.ParagraphFormat.KeepWithNext = $reference.ParagraphFormat.KeepWithNext
    $target.ParagraphFormat.KeepTogether = $reference.ParagraphFormat.KeepTogether
    $target.ParagraphFormat.PageBreakBefore = $reference.ParagraphFormat.PageBreakBefore
}

function Insert-Paragraph {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)][ref]$Cursor,
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$StyleName
    )

    $range = $Cursor.Value.Duplicate
    $range.Text = "$Text`r"
    $range.Font.Reset()
    $range.ParagraphFormat.Reset()
    $range.Style = $Document.Styles.Item($StyleName)
    $Cursor.Value.SetRange($range.End, $range.End)
    return $range
}

function Apply-CaptionStyle {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)]$Paragraph,
        [Parameter(Mandatory = $true)][string]$StyleName
    )

    $range = $Paragraph.Range.Duplicate
    $range.Font.Reset()
    $range.ParagraphFormat.Reset()
    $range.Style = $Document.Styles.Item($StyleName)
}

function Set-CellText {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)]$Cell,
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][bool]$Header,
        [Parameter(Mandatory = $true)][int]$Alignment
    )

    $range = $Cell.Range.Duplicate
    $range.End = $range.End - 1 # Preserve the Word end-of-cell marker.
    $range.Text = $Text
    $range.Font.Reset()
    $range.ParagraphFormat.Reset()
    $range.Style = $Document.Styles.Item('Normal')
    $range.ListFormat.RemoveNumbers()
    $range.Font.Name = 'Times New Roman'
    $range.Font.Size = 9
    $range.Font.Bold = if ($Header) { -1 } else { 0 }
    $range.Font.Italic = 0
    $range.ParagraphFormat.Alignment = $Alignment
    $range.ParagraphFormat.SpaceBefore = 0
    $range.ParagraphFormat.SpaceAfter = 0
    $range.ParagraphFormat.LineSpacingRule = 0
}

function Format-LncsTable {
    param(
        [Parameter(Mandatory = $true)]$Table,
        [Parameter(Mandatory = $true)][double[]]$Widths
    )

    $Table.Style = 'Table Normal'
    $Table.AllowAutoFit = $false
    $Table.Rows.Alignment = 0
    $Table.Rows.AllowBreakAcrossPages = $false
    $Table.Rows.Item(1).HeadingFormat = -1
    $Table.LeftPadding = 3.5
    $Table.RightPadding = 3.5
    $Table.TopPadding = 0
    $Table.BottomPadding = 0
    for ($column = 1; $column -le $Widths.Count; $column++) {
        $Table.Columns.Item($column).Width = $Widths[$column - 1]
    }
    foreach ($borderIndex in 1..8) { $Table.Borders.Item($borderIndex).LineStyle = 0 }
    $Table.Borders.Item(1).LineStyle = 1
    $Table.Borders.Item(1).LineWidth = 12
    $Table.Borders.Item(3).LineStyle = 1
    $Table.Borders.Item(3).LineWidth = 12
    for ($column = 1; $column -le $Table.Columns.Count; $column++) {
        $separator = $Table.Cell(1, $column).Borders.Item(3)
        $separator.LineStyle = 1
        $separator.LineWidth = 6
    }
}

function Write-LncsTable {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)]$Table,
        [Parameter(Mandatory = $true)][object[]]$Values,
        [Parameter(Mandatory = $true)][double[]]$Widths
    )

    if ($Table.Rows.Count -ne $Values.Count -or $Table.Columns.Count -ne $Values[0].Count) {
        throw 'Existing table dimensions do not match the recorded values.'
    }
    Format-LncsTable $Table $Widths
    for ($row = 1; $row -le $Table.Rows.Count; $row++) {
        for ($column = 1; $column -le $Table.Columns.Count; $column++) {
            $alignment = if ($column -eq 1) { 0 } else { 1 }
            Set-CellText $Document $Table.Cell($row, $column) $Values[$row - 1][$column - 1] ($row -eq 1) $alignment
        }
    }
}

function Insert-AboveTable {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)]$Table,
        [Parameter(Mandatory = $true)][object[]]$Paragraphs
    )

    $cursor = $Table.Range.Duplicate
    $cursor.Collapse(1) # wdCollapseStart
    foreach ($paragraph in $Paragraphs) {
        Insert-Paragraph $Document ([ref]$cursor) $paragraph.Text $paragraph.Style | Out-Null
    }
}

function Insert-BelowTable {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)]$Table,
        [Parameter(Mandatory = $true)][string]$Text
    )

    $cursor = $Table.Range.Duplicate
    $cursor.Collapse(0) # wdCollapseEnd
    Insert-Paragraph $Document ([ref]$cursor) $Text 'Normal' | Out-Null
}

$sourcePath = (Resolve-Path -LiteralPath $Source).Path
$outputPath = Resolve-WorkspacePath $Output
$currentPath = Resolve-WorkspacePath $CurrentManuscript
$referencePath = (Resolve-Path -LiteralPath $ReferenceTemplate).Path
$vbaBaselinePath = (Resolve-Path -LiteralPath $VbaBaseline).Path
if (Test-Path -LiteralPath $outputPath) { throw "Refusing to overwrite existing manuscript archive: $outputPath" }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outputPath) | Out-Null
Copy-Item -LiteralPath $sourcePath -Destination $outputPath

$vbaPart = 'word/vbaProject.bin'
$baselineVbaHash = Get-ZipPartHash $vbaBaselinePath $vbaPart
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$word.AutomationSecurity = 3
$document = $null
$referenceDocument = $null
try {
    $document = $word.Documents.Open($outputPath, $false, $false)
    $referenceDocument = $word.Documents.Open($referencePath, $false, $true)
    foreach ($styleName in @('tablecaption', 'figurecaption')) {
        Copy-CaptionStyleDefinition $document $referenceDocument $styleName
    }
    $referenceDocument.Close(0)
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($referenceDocument)
    $referenceDocument = $null

    $frozenIntro = 'LFW DB1 fixes the deployed native-score operating points before LSDB evaluation: LBPH tau_accept = 67.0333 (rank 165 of 16,522,626 unique impostor pairs; 9.986 ppm), SFace L2 = 1.0313 with cosine >= 0.363, and tau_reject = 140.13.'
    $frozenFigureLead = 'Figure 1 shows the frozen boundaries against the fresh LSDB clean-impostor distribution; it is not a re-calibration.'
    $frozenCaption = 'Table 4. Final frozen operating points.'
    $frozenTable = $document.Tables.Item(4)
    if ((Get-CleanText $frozenTable.Cell(1, 1).Range) -notmatch '^LFW DB1 fixes') {
        throw 'Expected malformed frozen-operating-point table structure was not found.'
    }
    Insert-AboveTable $document $frozenTable @(
        [pscustomobject]@{ Text = $frozenIntro; Style = 'Normal' },
        [pscustomobject]@{ Text = $frozenCaption; Style = 'tablecaption' }
    )
    Write-LncsTable $document $frozenTable @(
        @('Boundary', 'Source / native scale', 'Role'),
        @('LBPH tau_accept', 'LFW; predict_collect', 'accept'),
        @('SFace L2', 'LFW; SFace L2', 'escalated accept'),
        @('LBPH tau_reject', 'LFW trade-off; predict_collect', 'permissive reject edge')
    ) @(90, 145, 110)
    Insert-BelowTable $document $frozenTable $frozenFigureLead

    $robustnessIntro = 'Table 5 summarizes gallery/probe-disjoint LFW2 1-to-N identification robustness at the frozen deployment thresholds. Across all 41 modifications, SFace and the cascade retain 80.65% AR, whereas LBPH alone retains 1.41%. The cascade escalates 97.51% of probes to SFace; isolated latency is reported from a 575-identity subset.'
    $robustnessCaption = 'Table 5. LFW2 1-to-N identification robustness at frozen deployment thresholds.'
    $robustnessTable = $document.Tables.Item(5)
    if ((Get-CleanText $robustnessTable.Cell(1, 1).Range) -notmatch '^Table 5 summarizes') {
        throw 'Expected malformed robustness table structure was not found.'
    }
    Insert-AboveTable $document $robustnessTable @(
        [pscustomobject]@{ Text = $robustnessIntro; Style = 'Normal' },
        [pscustomobject]@{ Text = $robustnessCaption; Style = 'tablecaption' }
    )
    Write-LncsTable $document $robustnessTable @(
        @('Mode', 'AR (%)', 'Latency (ms)', 'FAR (%)', 'Escalation (%)'),
        @('Classical CV (LBPH)', '1.41', '72.49', '0.0010', 'N/A'),
        @('Deep Learning (SFace)', '80.65', '84.36', '~0.0010', 'N/A'),
        @('Hybrid Cascade', '80.65', '82.54', '≤0.0020', '97.51')
    ) @(85, 45, 65, 60, 90)

    $pairedCaption = 'Table 6. Paired thresholded correct-identity outcomes on held-out LSDB-DL41 probes (n = 2,296).'
    $pairedTable = $document.Tables.Item(6)
    if ((Get-CleanText $pairedTable.Cell(1, 1).Range) -notmatch '^Table 6\. Paired') {
        throw 'Expected malformed paired-outcome table structure was not found.'
    }
    Insert-AboveTable $document $pairedTable @(
        [pscustomobject]@{ Text = $pairedCaption; Style = 'tablecaption' }
    )
    Write-LncsTable $document $pairedTable @(
        @('LBPH outcome', 'SFace correct', 'SFace wrong'),
        @('LBPH correct', '707', '0'),
        @('LBPH wrong', '1,296', '293')
    ) @(115, 115, 115)

    for ($index = 1; $index -le $document.Paragraphs.Count; $index++) {
        $paragraph = $document.Paragraphs.Item($index)
        $text = Get-CleanText $paragraph.Range
        if ($text -match '^Table\s+\d+\.') { Apply-CaptionStyle $document $paragraph 'tablecaption' }
        elseif ($text -match '^Fig\.\s*\d+\.') { Apply-CaptionStyle $document $paragraph 'figurecaption' }
    }

    $document.Repaginate()
    $pageCount = [int]$document.ComputeStatistics(2)
    $document.Save()
    $document.ExportAsFixedFormat($PdfOutput, 17)
}
finally {
    if ($referenceDocument) {
        $referenceDocument.Close(0)
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($referenceDocument)
    }
    if ($document) {
        $document.Close(0)
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)
    }
    if ($word) {
        $word.Quit()
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
    }
}

Restore-ZipPart $vbaBaselinePath $outputPath $vbaPart
$outputVbaHash = Get-ZipPartHash $outputPath $vbaPart
if ($outputVbaHash -ne $baselineVbaHash) { throw 'VBA hash mismatch after restoration.' }
Copy-Item -LiteralPath $outputPath -Destination $currentPath -Force
$currentVbaHash = Get-ZipPartHash $currentPath $vbaPart
if ($currentVbaHash -ne $baselineVbaHash) { throw 'Current manuscript VBA hash mismatch.' }

Write-Output "SOURCE_DOCM=$sourcePath"
Write-Output "DOCM=$outputPath"
Write-Output "CURRENT_DOCM=$currentPath"
Write-Output "PDF=$PdfOutput"
Write-Output "PAGES=$pageCount"
Write-Output "VBA_SHA256=$outputVbaHash"
