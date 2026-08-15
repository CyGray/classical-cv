[CmdletBinding()]
param(
    [string]$Baseline = 'docs\manuscript\versions\011_lsface_complementarity-logic-data.docm',
    [string]$Output = 'docs\manuscript\versions\012_lsface_gate-accept-protection-descriptive.docm',
    [string]$CurrentManuscript = 'docs\manuscript\lsface.docm',
    [string]$PdfOutput = 'docs\experiments\manuscript-renders\012_gate_accept_protection\lsface_012_gate_accept_protection_descriptive.pdf',
    [int]$MaxPages = 11
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

function Get-ZipPrefixHashMap {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Prefix
    )

    $hashes = [ordered]@{}
    $archive = [System.IO.Compression.ZipFile]::OpenRead($Path)
    try {
        foreach ($entry in $archive.Entries | Where-Object { $_.FullName.StartsWith($Prefix) } | Sort-Object FullName) {
            $stream = $entry.Open()
            try { $hashes[$entry.FullName] = (Get-FileHash -Algorithm SHA256 -InputStream $stream).Hash }
            finally { $stream.Dispose() }
        }
    }
    finally { $archive.Dispose() }
    return $hashes
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
        if ($null -eq $referencePart) { throw "Missing $PartName in the exact 011 baseline." }
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

function Find-ParagraphStartsWith {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)][string]$Prefix
    )

    $match = $null
    $matchCount = 0
    for ($index = 1; $index -le $Document.Paragraphs.Count; $index++) {
        $paragraph = $Document.Paragraphs.Item($index)
        if ((Get-CleanText $paragraph.Range).StartsWith($Prefix)) {
            $match = $paragraph
            $matchCount++
        }
    }
    if ($matchCount -ne 1) {
        throw "Expected one paragraph beginning '$Prefix'; found $matchCount."
    }
    return $match
}

function Replace-ParagraphText {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)]$Paragraph,
        [Parameter(Mandatory = $true)][string]$Text,
        [string]$StyleName = 'p1a'
    )

    $range = $Paragraph.Range.Duplicate
    $range.End = $range.End - 1
    $range.Text = $Text
    $range.Font.Reset()
    $range.ParagraphFormat.Reset()
    $range.Style = $Document.Styles.Item($StyleName)
    $range.ListFormat.RemoveNumbers()
}

function Set-CellText {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)]$Cell,
        [Parameter(Mandatory = $true)][string]$Text
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
    $range.Font.Bold = 0
    $range.Font.Italic = 0
    $range.ParagraphFormat.Alignment = 0
    $range.ParagraphFormat.SpaceBefore = 0
    $range.ParagraphFormat.SpaceAfter = 0
    $range.ParagraphFormat.LineSpacingRule = 0
}

function Apply-SpringerBodyIndentation {
    param([Parameter(Mandatory = $true)]$Document)

    $flushStyle = $Document.Styles.Item('p1a')
    $indentedStyle = $Document.Styles.Item('Normal')
    $firstLineIndent = [single]$indentedStyle.ParagraphFormat.FirstLineIndent
    $afterHeading = $false
    $flushCount = 0
    $indentCount = 0

    for ($index = 1; $index -le $Document.Paragraphs.Count; $index++) {
        $paragraph = $Document.Paragraphs.Item($index)
        $styleName = [string]$paragraph.Range.Style.NameLocal
        $text = Get-CleanText $paragraph.Range

        if ($styleName -match '^heading[1-4]$') {
            $afterHeading = $true
            continue
        }
        if ($text -eq 'Frozen cascade configuration across databases') {
            # This inherited bold run is a visual subheading in exact 011 even
            # though it uses p1a rather than heading2. Keep it flush and treat
            # the following prose as the opening paragraph.
            $paragraph.Range.Style = $flushStyle
            $paragraph.Range.ParagraphFormat.FirstLineIndent = 0
            $afterHeading = $true
            continue
        }
        if ($text.StartsWith('Overall AR and escalation are means across 41 modifications')) {
            # This is the protocol note directly beneath Table 5, not a body
            # continuation paragraph. Preserve the baseline's flush note form.
            $paragraph.Range.Style = $flushStyle
            $paragraph.Range.ParagraphFormat.FirstLineIndent = 0
            $afterHeading = $false
            continue
        }
        if (-not $text -or $paragraph.Range.Tables.Count -gt 0) { continue }
        if ($styleName -notin @('p1a', 'Normal')) { continue }

        if ($afterHeading) {
            $paragraph.Range.Style = $flushStyle
            $paragraph.Range.ParagraphFormat.FirstLineIndent = 0
            $afterHeading = $false
            $flushCount++
        }
        else {
            $paragraph.Range.Style = $indentedStyle
            $paragraph.Range.ParagraphFormat.FirstLineIndent = $firstLineIndent
            $indentCount++
        }
    }

    return [pscustomobject]@{
        FlushOpeningParagraphs = $flushCount
        IndentedContinuationParagraphs = $indentCount
        FirstLineIndentPt = [double]$firstLineIndent
    }
}

function Compact-FinalEmptyParagraph {
    param([Parameter(Mandatory = $true)]$Document)

    $finalParagraph = $Document.Paragraphs.Item($Document.Paragraphs.Count)
    if (Get-CleanText $finalParagraph.Range) {
        throw 'Expected the inherited final paragraph from 011 to remain empty.'
    }

    # Word must retain the terminal paragraph mark, but after the added gate
    # prose and body indents its default line box can spill onto a header-only
    # page. Keep the paragraph and make only that empty line box compact.
    $finalParagraph.Range.Font.Size = 1
    $finalParagraph.Range.ParagraphFormat.FirstLineIndent = 0
    $finalParagraph.Range.ParagraphFormat.SpaceBefore = 0
    $finalParagraph.Range.ParagraphFormat.SpaceAfter = 0
    $finalParagraph.Range.ParagraphFormat.LineSpacingRule = 4
    $finalParagraph.Range.ParagraphFormat.LineSpacing = 1
    $finalParagraph.Range.ParagraphFormat.KeepWithNext = 0
    $finalParagraph.Range.ParagraphFormat.KeepTogether = 0
    $finalParagraph.Range.ParagraphFormat.PageBreakBefore = 0
}

$baselinePath = (Resolve-Path -LiteralPath $Baseline).Path
$outputPath = Resolve-WorkspacePath $Output
$currentPath = Resolve-WorkspacePath $CurrentManuscript
$pdfPath = Resolve-WorkspacePath $PdfOutput
if (Test-Path -LiteralPath $outputPath) {
    throw "Refusing to overwrite existing corrected 012 archive: $outputPath"
}
New-Item -ItemType Directory -Path (Split-Path -Parent $outputPath) -Force | Out-Null
New-Item -ItemType Directory -Path (Split-Path -Parent $pdfPath) -Force | Out-Null

$vbaPart = 'word/vbaProject.bin'
$baselineFileHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $baselinePath).Hash
$baselineVbaHash = Get-ZipPartHash $baselinePath $vbaPart
$baselineMediaHashes = Get-ZipPrefixHashMap $baselinePath 'word/media/'
if ($baselineMediaHashes.Count -lt 1) {
    throw 'Exact 011 baseline contains no packaged media parts.'
}
$stagePath = Join-Path ([System.IO.Path]::GetTempPath()) (
    'lsface_gate_accept_v012_{0}.docm' -f [guid]::NewGuid().ToString('N')
)
$pageCount = $null

try {
    Copy-Item -LiteralPath $baselinePath -Destination $stagePath
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $null
    try {
        $document = $word.Documents.Open($stagePath, $false, $false)
        $baselineParagraphCount = [int]$document.Paragraphs.Count
        $baselineTableCount = [int]$document.Tables.Count
        $baselineInlineShapeCount = [int]$document.InlineShapes.Count
        if ($baselineTableCount -ne 6 -or $baselineInlineShapeCount -ne 1) {
            throw "Exact 011 object contract failed: tables=$baselineTableCount, figures=$baselineInlineShapeCount."
        }

        $complementarityTable = $document.Tables.Item(6)
        if ((Get-CleanText $complementarityTable.Cell(6, 1).Range) -ne 'Accuracy-cost result') {
            throw 'Expected the accuracy-cost row in Table 6.'
        }
        Set-CellText $document $complementarityTable.Cell(2, 3) 'One-way rescue; not mutual'
        Set-CellText $document $complementarityTable.Cell(3, 3) 'Descriptive correlated transforms'
        Set-CellText $document $complementarityTable.Cell(4, 3) 'Strong within-suite discrimination'
        Set-CellText $document $complementarityTable.Cell(5, 3) 'Full failure recall; substantial over-routing'
        Set-CellText $document $complementarityTable.Cell(6, 2) (
            'Deployed: 87.24% AR, 71.52% escalated, 11.96 ms; ' +
            'candidate: 87.24%, 59.23%, 10.81 ms; SFace: 87.24%, 8.33 ms'
        )
        Set-CellText $document $complementarityTable.Cell(6, 3) (
            'Less redundant routing; direct SFace remains faster'
        )

        $gateParagraph = Find-ParagraphStartsWith $document 'Second, the gate has a useful risk signal'
        Replace-ParagraphText $document $gateParagraph (
            'Second, the gate exposes a useful risk signal, but its accept-side quality overrides cause redundant routing on this battery. ' +
            'Among 2,060 probes with gate signals, distance and negative margin separated 444 threshold-free LBPH Rank-1 errors with AUCs of 0.95019 and 0.95319. ' +
            'The deployed rule routed all 1,353 scored LBPH failures and 289 of 707 scored LBPH-correct cases. ' +
            'A post-hoc accept-protection replay kept the deployed low-margin trigger and every rule above tau_accept unchanged while treating accept-side quality flags as telemetry; it reduced those correct-case escalations to 7 of 707. ' +
            'Because the same transformed probes motivated and evaluated the candidate, this is a canonical descriptive ablation rather than independent policy validation.'
        )

        $costParagraph = Find-ParagraphStartsWith $document 'Third, the measured cost prevents a speed claim.'
        Replace-ParagraphText $document $costParagraph (
            'Third, accept protection improves the deployed route without establishing a speed advantage over SFace. ' +
            'The replay preserved 87.24% thresholded correct-identity acceptance while reducing escalation from 71.52% to 59.23% and the stored recognition-stage arithmetic mean from 11.96 to 10.81 ms. ' +
            'Direct SFace still reached the same acceptance at 8.33 ms, and LBPH-only reached 30.79% at 5.25 ms. ' +
            'These single-pass stored-stage timings exclude detection and I/O; the result supports simpler routing, not a Pareto improvement or a runtime gate change.'
        )

        $discussion = Find-ParagraphStartsWith $document 'The experiments support a division of labor with a clear negative boundary.'
        Replace-ParagraphText $document $discussion (
            'The experiments support a division of labor with a clear negative boundary. ' +
            'LSDB selection retains LBPH as the tested classical fast path and SFace as the compact learned tier; the held-out DL41 stress test shows one-way SFace rescue and gate AUCs near 0.95. ' +
            'The descriptive accept-protection replay then isolates the main source of redundant routing: preventing quality flags from overriding an LBPH decision already inside tau_accept preserves 87.24% AR while reducing escalation to 59.23%. ' +
            'However, the resulting 10.81 ms arithmetic mean remains slower than direct SFace. The contribution is therefore interpretable fallback and a simpler candidate rule, not mutual accuracy gain or a Pareto-efficient cascade.'
        )

        $limits = Find-ParagraphStartsWith $document 'The scope also limits generalization.'
        Replace-ParagraphText $document $limits (
            'The scope also limits generalization. The LSDB-DL41 rows are correlated transformations of 56 known-genuine source probes, 236 no-signal cases are outside the scored gate rates, and no unknown-query FPIR can be measured. ' +
            'The stored timing is recognition-stage arithmetic rather than end-to-end latency, while LFW2 drives 97.51% escalation at the frozen gate. ' +
            'The runtime gate remains unchanged. Open-set identification and target-device testing, including Raspberry Pi 5 measurements, are explicitly outside the present paper''s scope.'
        )

        $conclusion = Find-ParagraphStartsWith $document 'This paper presented LS-Face, a gated LBPH-to-SFace recognizer'
        Replace-ParagraphText $document $conclusion (
            'This paper presented LS-Face, a gated LBPH-to-SFace recognizer whose component selection, threshold calibration, and held-out evaluation remain separate evidence stages. ' +
            'On LSDB-DL41, SFace recovered 81.56% of thresholded LBPH failures and gate signals ranked LBPH Rank-1 risk with AUCs near 0.95. ' +
            'A canonical descriptive accept-protection replay preserved 87.24% AR while reducing escalation from 71.52% to 59.23% and the stored arithmetic mean from 11.96 to 10.81 ms; direct SFace remained faster. ' +
            'The runtime gate is unchanged, and the result is a same-data routing observation rather than independently validated deployment evidence. Open-set and target-device measurements are outside scope.'
        )

        $indentationSummary = Apply-SpringerBodyIndentation $document
        if ($indentationSummary.IndentedContinuationParagraphs -lt 1) {
            throw 'No continuation paragraphs received the Springer first-line indent.'
        }
        Compact-FinalEmptyParagraph $document

        if ([int]$document.Tables.Count -ne $baselineTableCount) {
            throw 'Table count changed during the 011-based gate revision.'
        }
        if ([int]$document.InlineShapes.Count -ne $baselineInlineShapeCount) {
            throw 'Figure count changed during the 011-based gate revision.'
        }
        if ([int]$document.Paragraphs.Count -ne $baselineParagraphCount) {
            throw 'Paragraph count changed during the replacement-only gate revision.'
        }

        $document.Repaginate()
        $pageCount = [int]$document.ComputeStatistics(2)
        if ($pageCount -gt $MaxPages) {
            throw "Page budget exceeded after revision: $pageCount > $MaxPages."
        }
        $document.Save()
        $document.ExportAsFixedFormat($pdfPath, 17)
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
    $stageMediaHashes = Get-ZipPrefixHashMap $stagePath 'word/media/'
    if (($stageMediaHashes | ConvertTo-Json -Compress) -ne ($baselineMediaHashes | ConvertTo-Json -Compress)) {
        throw 'Media parts differ from exact 011; the figure set was not preserved.'
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $baselinePath).Hash -ne $baselineFileHash) {
        throw 'Exact 011 baseline changed during production.'
    }

    Copy-Item -LiteralPath $stagePath -Destination $outputPath
    Copy-Item -LiteralPath $outputPath -Destination $currentPath -Force
    if ((Get-ZipPartHash $outputPath $vbaPart) -ne $baselineVbaHash -or
        (Get-ZipPartHash $currentPath $vbaPart) -ne $baselineVbaHash) {
        throw 'Final/current VBA project hash differs from exact 011.'
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $outputPath).Hash -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath $currentPath).Hash) {
        throw 'Current manuscript is not byte-identical to corrected 012.'
    }

    Write-Output "BASELINE_DOCM=$baselinePath"
    Write-Output "DOCM=$outputPath"
    Write-Output "CURRENT_DOCM=$currentPath"
    Write-Output "PDF=$pdfPath"
    Write-Output "PAGES=$pageCount"
    Write-Output "TABLES=6"
    Write-Output "INLINE_FIGURES=1"
    Write-Output "INDENTED_CONTINUATION_PARAGRAPHS=$($indentationSummary.IndentedContinuationParagraphs)"
    Write-Output "FLUSH_OPENING_PARAGRAPHS=$($indentationSummary.FlushOpeningParagraphs)"
    Write-Output "FIRST_LINE_INDENT_PT=$($indentationSummary.FirstLineIndentPt)"
    Write-Output "VBA_SHA256=$baselineVbaHash"
}
finally {
    if (Test-Path -LiteralPath $stagePath) { Remove-Item -LiteralPath $stagePath -Force }
    $repackedStage = "$stagePath.repacked"
    if (Test-Path -LiteralPath $repackedStage) { Remove-Item -LiteralPath $repackedStage -Force }
}
