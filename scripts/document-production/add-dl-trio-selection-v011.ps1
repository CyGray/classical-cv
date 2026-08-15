[CmdletBinding()]
param(
    [string]$Baseline = 'docs\manuscript\lsface.docm',
    [string]$Before = 'docs\manuscript\versions\010_lsface_before-dl-trio-selection.docm',
    [string]$Output = 'docs\manuscript\versions\011_lsface_dl-trio-selection.docm',
    [string]$CurrentManuscript = 'docs\manuscript\lsface.docm',
    [string]$ReferenceTemplate = 'docs\manuscript\sample\sample.docm',
    [string]$PdfOutput = "$env:TEMP\lsface_011_dl-trio-selection.pdf"
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
        if ($null -eq $referencePart) { throw "Missing $PartName in baseline." }
        foreach ($entry in $target.Entries) {
            $newEntry = $replacement.CreateEntry(
                $entry.FullName,
                [System.IO.Compression.CompressionLevel]::Optimal
            )
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

function Find-ParagraphExact {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)][string]$Text
    )

    for ($index = 1; $index -le $Document.Paragraphs.Count; $index++) {
        $paragraph = $Document.Paragraphs.Item($index)
        if ((Get-CleanText $paragraph.Range) -eq $Text) { return $paragraph }
    }
    throw "Expected paragraph not found: $Text"
}

function Set-ParagraphText {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)]$Paragraph,
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$StyleName
    )

    $range = $Paragraph.Range.Duplicate
    $range.Text = "$Text`r"
    $range.Font.Reset()
    $range.ParagraphFormat.Reset()
    $range.Style = $Document.Styles.Item($StyleName)
    return $range
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
    $range.End = $range.End - 1 # preserve the Word end-of-cell marker
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

function Resize-Table {
    param(
        [Parameter(Mandatory = $true)]$Table,
        [Parameter(Mandatory = $true)][double[]]$Widths
    )

    $Table.AllowAutoFit = $false
    for ($column = 1; $column -le $Widths.Count; $column++) {
        $Table.Columns.Item($column).Width = $Widths[$column - 1]
    }
}

function Reformat-ExistingTable {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)]$Table,
        [Parameter(Mandatory = $true)][double[]]$Widths
    )

    $values = @()
    for ($row = 1; $row -le $Table.Rows.Count; $row++) {
        $rowValues = @()
        for ($column = 1; $column -le $Table.Columns.Count; $column++) {
            $rowValues += Get-CleanText $Table.Cell($row, $column).Range
        }
        $values += ,$rowValues
    }
    Format-LncsTable $Table $Widths
    for ($row = 1; $row -le $Table.Rows.Count; $row++) {
        for ($column = 1; $column -le $Table.Columns.Count; $column++) {
            $alignment = if ($column -eq 1) { 0 } else { 1 }
            Set-CellText $Document $Table.Cell($row, $column) $values[$row - 1][$column - 1] ($row -eq 1) $alignment
        }
    }
}

$baselinePath = (Resolve-Path -LiteralPath $Baseline).Path
$beforePath = Resolve-WorkspacePath $Before
$outputPath = Resolve-WorkspacePath $Output
$currentPath = Resolve-WorkspacePath $CurrentManuscript
$referencePath = (Resolve-Path -LiteralPath $ReferenceTemplate).Path

foreach ($path in @($beforePath, $outputPath)) {
    if (Test-Path -LiteralPath $path) { throw "Refusing to overwrite existing manuscript archive: $path" }
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $beforePath) | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outputPath) | Out-Null
Copy-Item -LiteralPath $baselinePath -Destination $beforePath
Copy-Item -LiteralPath $baselinePath -Destination $outputPath

$vbaPart = 'word/vbaProject.bin'
$baselineVbaHash = Get-ZipPartHash $baselinePath $vbaPart
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

    $obsoleteFigureCaption = Find-ParagraphExact $document 'Fig. 1. / LSDB held-out thresholded TAR for classical candidate selection.'
    $obsoleteFigureCaption.Range.Delete() # This paragraph contains the redundant Figure 1 inline shape.

    $legacyDlParagraph = Find-ParagraphExact $document 'For the learned candidates, externally supplied LSDB artifacts report SFace with a 128-D (512-byte) embedding, while ArcFace and FaceNet use 512-D (2,048-byte) embeddings. SFace was retained as the deployment-compatible escalation model; these external, model-specific-threshold results are not presented as a same-harness accuracy ranking.'
    Set-ParagraphText $document $legacyDlParagraph 'A fresh DL-only campaign replaced the legacy self-match test. SFace, ArcFace, and FaceNet used the deterministic 224/56/56 LSDB cohort; each model''s rank-15 acceptance edge came only from 1,512 calibration cross-identity scores (realized FAR 0.992%). Native score scales remained model-specific and were not mixed with the classical ranking.' 'Normal' | Out-Null

    $nextHeading = Find-ParagraphExact $document 'Independence Test: Frozen Operating Points'
    $cursor = $nextHeading.Range.Duplicate
    $cursor.Collapse(1) # wdCollapseStart: insert before the next subsection heading.

    $caption = Insert-Paragraph $document ([ref]$cursor) 'Table 3. DL-only candidate selection on LSDB. TAR uses each model''s rank-15 calibration edge (0.992% realized FAR).' 'tablecaption'
    $table = $document.Tables.Add($cursor.Duplicate, 4, 4)
    $values = @(
        @('Candidate', 'TAR (%)', 'Rank-1 (%)', 'Feature'),
        @('SFace', '100.00%', '100.00%', '512 B'),
        @('ArcFace', '96.43%', '100.00%', '2,048 B'),
        @('FaceNet', '100.00%', '100.00%', '2,048 B')
    )
    Format-LncsTable $table @(105, 78, 82, 80)
    for ($row = 1; $row -le 4; $row++) {
        for ($column = 1; $column -le 4; $column++) {
            $alignment = if ($column -eq 1) { 0 } else { 1 }
            Set-CellText $document $table.Cell($row, $column) $values[$row - 1][$column - 1] ($row -eq 1) $alignment
        }
    }
    $cursor.SetRange($table.Range.End, $table.Range.End)
    Insert-Paragraph $document ([ref]$cursor) 'SFace and FaceNet tied at 100.00% held-out TAR and Rank-1; SFace won the recorded feature-size tie-break (512 B versus 2,048 B). ArcFace retained 100.00% Rank-1 but reached 96.43% TAR. Thus, SFace is the learned tier, while LBPH remains the separately selected classical fast path.' 'Normal' | Out-Null

    # Inserting the DL table shifts subsequent table labels by one.
    $captionReplacements = @(
        @('Table 3. Final frozen operating points.', 'Table 4. Final frozen operating points.'),
        @('Table 4. LFW2 1-to-N identification robustness at frozen deployment thresholds.', 'Table 5. LFW2 1-to-N identification robustness at frozen deployment thresholds.'),
        @('Table 5. Paired thresholded correct-identity outcomes on held-out LSDB-DL41 probes (n = 2,296).', 'Table 6. Paired thresholded correct-identity outcomes on held-out LSDB-DL41 probes (n = 2,296).'),
        @('Fig. 2. Histograms and KDE curves for fresh LSDB clean impostor pairs. Long-dotted lines mark frozen LFW operating points.', 'Fig. 1. Histograms and KDE curves for fresh LSDB clean impostor pairs. Long-dotted lines mark frozen LFW operating points.'),
        @('Fig. 3. SFace recovery of LBPH thresholded errors by DL41 transformation on the LSDB held-out split. Whiskers show 95% Wilson intervals; all claims are restricted to this transform-sensitivity stress test.', 'Fig. 2. SFace recovery of LBPH thresholded errors by DL41 transformation on the LSDB held-out split. Whiskers show 95% Wilson intervals; all claims are restricted to this transform-sensitivity stress test.'),
        @('Fig. 4. Gate competence for threshold-free LBPH Rank-1 errors on scored LSDB-DL41 probes (n = 2,060; 444 errors). Curves evaluate failure discrimination, separate from the thresholded routing outcomes reported in text.', 'Fig. 3. Gate competence for threshold-free LBPH Rank-1 errors on scored LSDB-DL41 probes (n = 2,060; 444 errors). Curves evaluate failure discrimination, separate from the thresholded routing outcomes reported in text.'),
        @('Fig. 5. Recognition-stage timing versus thresholded correct-identity acceptance for held-out LSDB-DL41 probes. Timing is single-pass, model-initialized measurement and is not end-to-end deployment latency.', 'Fig. 4. Recognition-stage timing versus thresholded correct-identity acceptance for held-out LSDB-DL41 probes. Timing is single-pass, model-initialized measurement and is not end-to-end deployment latency.')
    )
    foreach ($replacement in $captionReplacements) {
        $paragraph = Find-ParagraphExact $document $replacement[0]
        $styleName = if ($replacement[1] -match '^Table') { 'tablecaption' } else { 'figurecaption' }
        Set-ParagraphText $document $paragraph $replacement[1] $styleName | Out-Null
    }

    $frozenText = Find-ParagraphExact $document 'LFW DB1 fixes the deployed native-score operating points before LSDB evaluation: LBPH tau_accept = 67.0333 (rank 165 of 16,522,626 unique impostor pairs; 9.986 ppm), SFace L2 = 1.0313 with cosine >= 0.363, and tau_reject = 140.13. Figure 2 shows the frozen boundaries against the fresh LSDB clean-impostor distribution; it is not a re-calibration.'
    Set-ParagraphText $document $frozenText 'LFW DB1 fixes the deployed native-score operating points before LSDB evaluation: LBPH tau_accept = 67.0333 (rank 165 of 16,522,626 unique impostor pairs; 9.986 ppm), SFace L2 = 1.0313 with cosine >= 0.363, and tau_reject = 140.13. Figure 1 shows the frozen boundaries against the fresh LSDB clean-impostor distribution; it is not a re-calibration.' 'Normal' | Out-Null

    $robustnessText = Find-ParagraphExact $document 'Table 4 summarizes gallery/probe-disjoint LFW2 1-to-N identification robustness at the frozen deployment thresholds. Across all 41 modifications, SFace and the cascade retain 80.65% AR, whereas LBPH alone retains 1.41%. The cascade escalates 97.51% of probes to SFace; isolated latency is reported from a 575-identity subset.'
    Set-ParagraphText $document $robustnessText 'Table 5 summarizes gallery/probe-disjoint LFW2 1-to-N identification robustness at the frozen deployment thresholds. Across all 41 modifications, SFace and the cascade retain 80.65% AR, whereas LBPH alone retains 1.41%. The cascade escalates 97.51% of probes to SFace; isolated latency is reported from a 575-identity subset.' 'Normal' | Out-Null

    # Restore every caption to the reference style without direct formatting.
    for ($index = 1; $index -le $document.Paragraphs.Count; $index++) {
        $paragraph = $document.Paragraphs.Item($index)
        $text = Get-CleanText $paragraph.Range
        if ($text -match '^Table\s+\d+\.') { Apply-CaptionStyle $document $paragraph 'tablecaption' }
        elseif ($text -match '^Fig\.\s*\d+\.') { Apply-CaptionStyle $document $paragraph 'figurecaption' }
    }

    # Table 2 was the only table below the template's 9 pt minimum and lacked the LNCS rule weights.
    Reformat-ExistingTable $document $document.Tables.Item(2) @(105, 78, 82, 80)
    # Tables 4-6 retain their recorded values but now fit within the manuscript text block.
    Resize-Table $document.Tables.Item(4) @(90, 145, 110)
    Resize-Table $document.Tables.Item(5) @(85, 45, 65, 60, 90)
    Resize-Table $document.Tables.Item(6) @(115, 115, 115)

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

Restore-ZipPart $baselinePath $outputPath $vbaPart
$outputVbaHash = Get-ZipPartHash $outputPath $vbaPart
if ($outputVbaHash -ne $baselineVbaHash) { throw 'VBA hash mismatch after restoration.' }
Copy-Item -LiteralPath $outputPath -Destination $currentPath -Force
$currentVbaHash = Get-ZipPartHash $currentPath $vbaPart
if ($currentVbaHash -ne $baselineVbaHash) { throw 'Current manuscript VBA hash mismatch.' }

Write-Output "BEFORE_DOCM=$beforePath"
Write-Output "DOCM=$outputPath"
Write-Output "CURRENT_DOCM=$currentPath"
Write-Output "PDF=$PdfOutput"
Write-Output "PAGES=$pageCount"
Write-Output "VBA_SHA256=$outputVbaHash"
