[CmdletBinding()]
param(
    [string]$Baseline = 'docs\manuscript\copy\010b_lsface_dl-trio-selection-final-verified.docm',
    [string]$Output = 'docs\manuscript\versions\011_lsface_complementarity-logic-data.docm',
    [string]$PdfOutput = "$env:TEMP\lsface_011_complementarity-logic-data.pdf",
    [int]$MaxPages = 11,
    [switch]$SkipPdfExport
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Resolve-WorkspacePath {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }
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
    if (Test-Path -LiteralPath $temporaryPath) {
        Remove-Item -LiteralPath $temporaryPath -Force
    }
    $reference = [System.IO.Compression.ZipFile]::OpenRead($ReferencePath)
    $target = [System.IO.Compression.ZipFile]::OpenRead($TargetPath)
    $replacement = [System.IO.Compression.ZipFile]::Open(
        $temporaryPath,
        [System.IO.Compression.ZipArchiveMode]::Create
    )
    try {
        $referencePart = $reference.GetEntry($PartName)
        if ($null -eq $referencePart) { throw "Missing $PartName in the named baseline." }
        foreach ($entry in $target.Entries) {
            $newEntry = $replacement.CreateEntry(
                $entry.FullName,
                [System.IO.Compression.CompressionLevel]::Optimal
            )
            $sourceEntry = if ($entry.FullName -eq $PartName) { $referencePart } else { $entry }
            $input = $sourceEntry.Open()
            $outputStream = $newEntry.Open()
            try { $input.CopyTo($outputStream) }
            finally {
                $outputStream.Dispose()
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

    foreach ($paragraph in $Document.Paragraphs) {
        if ((Get-CleanText $paragraph.Range) -eq $Text) { return $paragraph }
    }
    throw "Expected paragraph not found: $Text"
}

function Add-StyledParagraph {
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
    $range.ListFormat.RemoveNumbers()
    $Cursor.Value.SetRange($range.End, $range.End)
    return $range
}

function Replace-Section {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)][string]$StartHeading,
        [Parameter(Mandatory = $true)][string]$EndHeading,
        [Parameter(Mandatory = $true)][scriptblock]$Writer
    )

    $startParagraph = Find-ParagraphExact $Document $StartHeading
    $endParagraph = Find-ParagraphExact $Document $EndHeading
    $start = [int]$startParagraph.Range.Start
    $end = [int]$endParagraph.Range.Start
    if ($end -le $start) { throw "Invalid section order: $StartHeading -> $EndHeading" }
    $range = $Document.Range($start, $end)
    $range.Delete()
    $cursor = $Document.Range($start, $start)
    & $Writer $Document ([ref]$cursor)
}

function Set-CellText {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)]$Cell,
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][bool]$Bold,
        [Parameter(Mandatory = $true)][int]$Alignment
    )

    $range = $Cell.Range.Duplicate
    $range.End = $range.End - 1
    $range.Text = $Text
    $range.Font.Reset()
    $range.ParagraphFormat.Reset()
    $range.Style = $Document.Styles.Item('Normal')
    $range.ListFormat.RemoveNumbers()
    $range.Font.Name = 'Times New Roman'
    $range.Font.Size = 9
    $range.Font.Bold = if ($Bold) { -1 } else { 0 }
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
    $Table.TopPadding = 1.5
    $Table.BottomPadding = 1.5
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
        throw 'Compact complementarity table dimensions do not match recorded values.'
    }
    Format-LncsTable $Table $Widths
    for ($row = 1; $row -le $Table.Rows.Count; $row++) {
        for ($column = 1; $column -le $Table.Columns.Count; $column++) {
            $bold = $row -eq 1 -or $column -eq 1
            $alignment = if ($row -eq 1) { 1 } else { 0 }
            Set-CellText $Document $Table.Cell($row, $column) $Values[$row - 1][$column - 1] $bold $alignment
        }
    }
}

$baselinePath = (Resolve-Path -LiteralPath $Baseline).Path
$outputPath = Resolve-WorkspacePath $Output
$pdfPath = Resolve-WorkspacePath $PdfOutput
if (Test-Path -LiteralPath $outputPath) {
    throw "Refusing to overwrite existing manuscript archive: $outputPath"
}
New-Item -ItemType Directory -Path (Split-Path -Parent $outputPath) -Force | Out-Null
New-Item -ItemType Directory -Path (Split-Path -Parent $pdfPath) -Force | Out-Null

$vbaPart = 'word/vbaProject.bin'
$baselineFileHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $baselinePath).Hash
$baselineVbaHash = Get-ZipPartHash $baselinePath $vbaPart
$stagePath = Join-Path ([System.IO.Path]::GetTempPath()) (
    'lsface_011_{0}.docm' -f [guid]::NewGuid().ToString('N')
)

try {
    Copy-Item -LiteralPath $baselinePath -Destination $stagePath
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $null
    try {
        $document = $word.Documents.Open($stagePath, $false, $false)

        Replace-Section $document 'Testing complementarity directly' 'Frozen cascade configuration across databases' {
            param($doc, [ref]$cursor)

            Add-StyledParagraph $doc $cursor 'Testing complementarity directly' 'heading2' | Out-Null
            Add-StyledParagraph $doc $cursor 'Complementarity cannot be inferred from aggregate accuracy alone. We test a three-link argument on the same held-out probes: potential fallback value, routability, and measured utility. First, paired thresholded decisions are counted as both right, LBPH only right, SFace only right, or both wrong. The conditional rescue rate is the share of LBPH failures corrected by SFace. Since 41 deterministic transforms repeat each source image, these row counts are descriptive conditions, not independent trials; no row-level significance claim is made.' 'p1a' | Out-Null
            Add-StyledParagraph $doc $cursor 'Second, the cascade is useful only if LBPH exposes a signal before SFace runs. We therefore score the best distance and negative relative margin against threshold-free LBPH Rank-1 error and report ROC AUC, where 0.5 denotes blind routing. The deployed rule is evaluated separately against thresholded LBPH system failure, with its recall, false-routing rate, and precision reported only for probes that yield a gate signal.' 'p1a' | Out-Null
            Add-StyledParagraph $doc $cursor 'Third, routing must justify its cost. The frozen gate is compared with always-LBPH and always-SFace anchors on thresholded correct-identity acceptance, escalation rate, and recognition-stage time from the same records. A selective cascade should retain the learned tier''s benefit while avoiding enough learned-tier calls to offset the LBPH overhead. If it matches SFace but runs slower, the evidence supports fallback behavior rather than an efficiency advantage.' 'p1a' | Out-Null
        }

        Replace-Section $document 'Complementarity on Held-Out LSDB-DL41 Probes' 'Discussion' {
            param($doc, [ref]$cursor)

            Add-StyledParagraph $doc $cursor 'Complementarity on Held-Out LSDB-DL41 Probes' 'heading2' | Out-Null
            Add-StyledParagraph $doc $cursor 'The evaluation follows the three-link argument above. It uses 56 image-disjoint held-out LSDB source probes, two for each of 28 enrolled identities, and 41 deterministic transformations per source, yielding 2,296 correlated probe conditions. The LFW-derived thresholds and gate were frozen before scoring, and detector failures were handled strictly. Table 6 therefore pairs each number with the exact conclusion it can support.' 'p1a' | Out-Null
            Add-StyledParagraph $doc $cursor 'Table 6. Logic-to-data audit of SFace rescue and gate routing on held-out LSDB-DL41 probes.' 'tablecaption' | Out-Null

            $table = $doc.Tables.Add($cursor.Value.Duplicate, 6, 3)
            Write-LncsTable $doc $table @(
                @('Question', 'Recorded data', 'Supported reading'),
                @('Fallback value', 'Both right 707; LBPH only 0; SFace only 1,296; both wrong 293', 'One-way SFace rescue, not mutual complementarity'),
                @('Rescue magnitude', '1,296 / 1,589 LBPH errors = 81.56%', 'Descriptive across repeated transform conditions'),
                @('Can the gate rank risk?', 'Distance AUC 0.95019; negative-margin AUC 0.95319; 2,060 scored, 444 Rank-1 errors; 236 no signal', 'Strong within-suite failure discrimination'),
                @('Does routing catch scored failures?', '1,353 / 1,353 failures routed; 289 / 707 correct cases also routed; precision 82.40%', 'Full recall of scored failures, with substantial over-routing'),
                @('Accuracy-cost result', 'LBPH 30.79% at 5.25 ms; SFace 87.24% at 8.33 ms; cascade 87.24% at 11.96 ms; escalation 71.52%', 'No accuracy or speed gain over SFace on this workload')
            ) @(82, 166, 97)
            $cursor.Value.SetRange($table.Range.End, $table.Range.End)

            Add-StyledParagraph $doc $cursor 'First, the value of the fallback is asymmetric. SFace corrected 1,296 of the 1,589 thresholded LBPH failures (81.56%), whereas LBPH supplied no thresholded success that SFace lacked. The 293 both-wrong conditions identify the remaining failure region for these two final decisions; they are not a universal ceiling for every possible score-level fusion. Because transformations repeat source images, the paired counts are reported descriptively rather than as 2,296 independent observations.' 'p1a' | Out-Null
            Add-StyledParagraph $doc $cursor 'Second, the gate has a useful risk signal but pays for recall with extra routing. On the 2,060 probes with gate signals, distance and negative margin separated 444 threshold-free LBPH Rank-1 errors with AUCs of 0.95019 and 0.95319. Against the thresholded decision, the deployed rule routed all 1,353 scored LBPH failures, but also routed 289 of 707 scored LBPH-correct cases. The 236 strict no-face cases had no gate signal and are excluded from those routing rates.' 'p1a' | Out-Null
            Add-StyledParagraph $doc $cursor 'Third, the measured cost prevents a speed claim. The cascade and SFace each reached 87.24% thresholded correct-identity acceptance, while the cascade required 11.96 ms per probe versus 8.33 ms for SFace and escalated 71.52% of probes. These single-pass, recognition-stage timings exclude detection and I/O. This campaign therefore demonstrates transparent one-way fallback and failure routing, not a Pareto improvement over always-SFace execution.' 'p1a' | Out-Null
        }

        Replace-Section $document 'Discussion' 'Conclusion' {
            param($doc, [ref]$cursor)

            Add-StyledParagraph $doc $cursor 'Discussion' 'heading1' | Out-Null
            Add-StyledParagraph $doc $cursor 'The experiments support a division of labor with a clear negative boundary. LSDB selection separately retains LBPH as the tested classical fast path and SFace as the compact learned tier. In the held-out DL41 stress test, the 1,296 SFace-only successes and zero LBPH-only successes show one-way rescue, while gate AUCs near 0.95 show that LBPH exposes a usable risk signal. However, the cascade equals SFace acceptance and is slower because most probes escalate. The demonstrated contribution is interpretable risk routing, not mutual accuracy gain or a Pareto-efficient cascade.' 'p1a' | Out-Null
            Add-StyledParagraph $doc $cursor 'The scope also limits generalization. The LSDB-DL41 rows are correlated transformations of 56 source probes, 236 no-signal cases are outside the scored gate rates, and timing is neither end-to-end nor measured on the target device. LFW2 similarly drives 97.51% escalation at the frozen gate. Future evaluation should use independently captured, identity-clustered open-set probes and repeated end-to-end embedded timing before making deployment-level security or efficiency claims.' 'p1a' | Out-Null
        }

        Replace-Section $document 'Conclusion' 'Acknowledgments' {
            param($doc, [ref]$cursor)

            Add-StyledParagraph $doc $cursor 'Conclusion' 'heading1' | Out-Null
            Add-StyledParagraph $doc $cursor 'This paper presented LS-Face, a gated LBPH-to-SFace recognizer whose component selection, threshold calibration, and held-out evaluation are kept as separate evidence stages. On LSDB-DL41, SFace recovered 81.56% of thresholded LBPH failures, and the gate signals ranked LBPH Rank-1 risk with AUCs near 0.95. Yet the cascade matched SFace at 87.24% acceptance and was slower under the recorded recognition-stage timing. The result is therefore an interpretable one-way fallback with measurable routing behavior, not a universal accuracy or latency gain. Larger identity-clustered open-set trials and end-to-end device measurements remain necessary.' 'p1a' | Out-Null
        }

        $lfwHeading = Find-ParagraphExact $document 'LFW2 Robustness Evaluation'
        $lfwHeading.Range.ParagraphFormat.PageBreakBefore = 0

        if ($document.InlineShapes.Count -ne 1) {
            throw "Expected one retained figure after compacting complementarity; found $($document.InlineShapes.Count)."
        }
        $figure = $document.InlineShapes.Item(1)
        $figure.LockAspectRatio = -1
        if ([double]$figure.Width -gt 345.0) { $figure.Width = 345.0 }

        $document.Repaginate()
        $pageCount = [int]$document.ComputeStatistics(2)
        if ($pageCount -gt $MaxPages) {
            throw "Page budget exceeded after revision: $pageCount > $MaxPages."
        }
        $document.Save()
        if (-not $SkipPdfExport) {
            $document.ExportAsFixedFormat($pdfPath, 17)
        }
    }
    finally {
        if ($document) {
            $document.Close(0)
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)
        }
        if ($word) {
            $word.Quit()
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
        }
    }

    Restore-ZipPart -ReferencePath $baselinePath -TargetPath $stagePath -PartName $vbaPart
    if ((Get-ZipPartHash $stagePath $vbaPart) -ne $baselineVbaHash) {
        throw 'VBA project hash differs after restoration.'
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $baselinePath).Hash -ne $baselineFileHash) {
        throw 'Named 010b baseline changed during production.'
    }

    Copy-Item -LiteralPath $stagePath -Destination $outputPath
    if ((Get-ZipPartHash $outputPath $vbaPart) -ne $baselineVbaHash) {
        throw 'Output VBA project hash differs from the exact named baseline.'
    }

    Write-Output "BASELINE_DOCM=$baselinePath"
    Write-Output "DOCM=$outputPath"
    Write-Output "PDF=$(if ($SkipPdfExport) { 'SKIPPED' } else { $pdfPath })"
    Write-Output "PAGES=$pageCount"
    Write-Output "VBA_SHA256=$baselineVbaHash"
}
finally {
    if (Test-Path -LiteralPath $stagePath) {
        Remove-Item -LiteralPath $stagePath -Force
    }
    $repackedStage = "$stagePath.repacked"
    if (Test-Path -LiteralPath $repackedStage) {
        Remove-Item -LiteralPath $repackedStage -Force
    }
}
