param(
    [string]$Baseline = "docs\manuscript\versions\007_lsface_robustness-results.docm",
    [string]$Output = "docs\manuscript\versions\008_lsface_finalized-results-discussion.docm",
    [string]$CurrentManuscript = "docs\manuscript\lsface.docm",
    [string]$PdfOutput = "$env:TEMP\lsface_008_finalized-results-discussion.pdf"
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
            $input = $sourceEntry.Open(); $output = $newEntry.Open()
            try { $input.CopyTo($output) }
            finally { $output.Dispose(); $input.Dispose() }
        }
    }
    finally { $replacement.Dispose(); $target.Dispose(); $reference.Dispose() }
    Move-Item -LiteralPath $temporaryPath -Destination $TargetPath -Force
}

function Add-Paragraph([object]$Document, [ref]$Cursor, [string]$Text, [string]$StyleName) {
    $range = $Cursor.Value.Duplicate
    $range.Text = "$Text`r"
    $range.Style = $Document.Styles.Item($StyleName)
    $Cursor.Value.SetRange($range.End, $range.End)
    return $range
}

function Set-CellText([object]$Document, [object]$Cell, [string]$Text, [bool]$Header) {
    $Cell.Range.Text = $Text
    $Cell.Range.Style = $Document.Styles.Item('tablecaption')
    $Cell.Range.ListFormat.RemoveNumbers()
    $Cell.Range.Font.Name = 'Times New Roman'
    $Cell.Range.Font.Size = 10
    $Cell.Range.Font.Bold = if ($Header) { -1 } else { 0 }
    $Cell.Range.ParagraphFormat.Alignment = 1
    $Cell.Range.ParagraphFormat.SpaceBefore = 0
    $Cell.Range.ParagraphFormat.SpaceAfter = 0
    $Cell.Range.ParagraphFormat.LineSpacingRule = 0
    foreach ($borderIndex in 1..4) { $Cell.Borders.Item($borderIndex).LineStyle = 0 }
}

function Format-LncsTable([object]$Table, [int[]]$Widths) {
    $Table.Style = 'Table Normal'
    $Table.AllowAutoFit = $false
    $Table.Rows.Alignment = 0
    $Table.Rows.AllowBreakAcrossPages = $false
    $Table.Rows.Item(1).HeadingFormat = -1
    $Table.LeftPadding = 5.4; $Table.RightPadding = 5.4
    $Table.TopPadding = 0; $Table.BottomPadding = 0
    for ($column = 1; $column -le $Widths.Count; $column++) { $Table.Columns.Item($column).Width = $Widths[$column - 1] }
    foreach ($borderIndex in 1..8) { $Table.Borders.Item($borderIndex).LineStyle = 0 }
    $Table.Borders.Item(1).LineStyle = 1; $Table.Borders.Item(1).LineWidth = 12
    $Table.Borders.Item(3).LineStyle = 1; $Table.Borders.Item(3).LineWidth = 12
    for ($column = 1; $column -le $Table.Columns.Count; $column++) {
        $separator = $Table.Cell(1, $column).Borders.Item(3)
        $separator.LineStyle = 1; $separator.LineWidth = 6
    }
}

function Add-Figure([object]$Document, [ref]$Cursor, [string]$Path, [string]$Caption) {
    $paragraph = $Cursor.Value.Duplicate
    $paragraph.Text = "`r"
    $paragraph.ParagraphFormat.Alignment = 1
    $shape = $paragraph.InlineShapes.AddPicture($Path, $false, $true, $paragraph)
    $shape.LockAspectRatio = -1
    $maxWidth = 440
    if ($shape.Width -gt $maxWidth) { $shape.Width = $maxWidth }
    $paragraph.ParagraphFormat.SpaceAfter = 2
    $Cursor.Value.SetRange($paragraph.End, $paragraph.End)
    $captionRange = Add-Paragraph $Document $Cursor $Caption 'figurecaption'
    $captionRange.ParagraphFormat.Alignment = 0
    $captionRange.ParagraphFormat.SpaceAfter = 6
}

$baselinePath = (Resolve-Path -LiteralPath $Baseline).Path
$outputPath = Join-Path (Get-Location) $Output
$currentPath = Join-Path (Get-Location) $CurrentManuscript
$outputDirectory = Split-Path -Parent $outputPath
$assets = Join-Path (Get-Location) 'docs\results\complementarity_test\reruns\lsdb_dl41_2026-08-10'
foreach ($asset in @('recovery_rate.svg', 'gate_competence.svg', 'speed_accuracy_curve.svg')) {
    if (-not (Test-Path -LiteralPath (Join-Path $assets $asset))) { throw "Missing canonical figure: $asset" }
}
if (Test-Path -LiteralPath $outputPath) { throw "Refusing to overwrite existing version: $outputPath" }
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
Copy-Item -LiteralPath $baselinePath -Destination $outputPath

$vbaPart = 'word/vbaProject.bin'
$baselineVbaHash = Get-ZipPartHash $baselinePath $vbaPart
$word = New-Object -ComObject Word.Application
$word.Visible = $false; $word.DisplayAlerts = 0; $word.AutomationSecurity = 3
$document = $null
try {
    $document = $word.Documents.Open($outputPath, $false, $false)
    $referencesParagraph = $null
    for ($index = 1; $index -le $document.Paragraphs.Count; $index++) {
        $paragraph = $document.Paragraphs.Item($index)
        if ($paragraph.Range.Text.Trim([char]13, [char]7) -eq 'References') { $referencesParagraph = $paragraph; break }
    }
    if ($null -eq $referencesParagraph) { throw 'References heading not found.' }
    $cursor = $referencesParagraph.Range.Duplicate
    $cursor.Collapse(1)

    $heading = Add-Paragraph $document ([ref]$cursor) 'Complementarity on Held-Out LSDB-DL41 Probes' 'heading2'
    $heading.ParagraphFormat.KeepWithNext = -1
    $p = Add-Paragraph $document ([ref]$cursor) 'The complementarity battery used 2,296 DL41-transformed probes from the 56-image held-out LSDB split, with the frozen LFW-derived gate and strict detector-failure handling. This is a paired transform-sensitivity analysis, not a new operating-point calibration or an LFW result. At the thresholded correct-identity decision, LBPH was correct on 707 probes, SFace alone recovered 1,296 LBPH failures, and both engines failed on 293 probes.' 'p1a'
    $p.ParagraphFormat.KeepWithNext = -1
    $caption = Add-Paragraph $document ([ref]$cursor) 'Table 5. Paired thresholded correct-identity outcomes on held-out LSDB-DL41 probes (n = 2,296).' 'tablecaption'
    $caption.ParagraphFormat.KeepWithNext = -1
    $table = $document.Tables.Add($cursor.Duplicate, 3, 3)
    $values = @(
        @('LBPH outcome', 'SFace correct', 'SFace wrong'),
        @('LBPH correct', '707', '0'),
        @('LBPH wrong', '1,296', '293')
    )
    for ($row = 1; $row -le 3; $row++) { for ($column = 1; $column -le 3; $column++) { Set-CellText $document $table.Cell($row,$column) $values[$row-1][$column-1] ($row -eq 1) } }
    Format-LncsTable $table @(150, 150, 150)
    $cursor.SetRange($table.Range.End, $table.Range.End)
    $note = Add-Paragraph $document ([ref]$cursor) 'SFace recovered 1,296 of 1,589 LBPH errors: 81.56% (Wilson 95% CI, 79.58–83.39%). Exact two-sided McNemar testing of the discordant cells (LBPH-only right = 0; SFace-only right = 1,296) gave p < 10^-300. These counts establish asymmetric error recovery in this LSDB stress setting; they do not establish error independence on a population-level impostor distribution.' 'p1a'
    $note.Font.Size = 9
    Add-Figure $document ([ref]$cursor) (Join-Path $assets 'recovery_rate.svg') 'Fig. 3. SFace recovery of LBPH thresholded errors by DL41 transformation on the LSDB held-out split. Whiskers show 95% Wilson intervals; all claims are restricted to this transform-sensitivity stress test.'
    $p = Add-Paragraph $document ([ref]$cursor) 'The gate signal separated threshold-free LBPH Rank-1 failures strongly among the 2,060 probes for which a gate signal was available: the LBPH distance yielded ROC AUC 0.95019 and negative relative margin yielded AUC 0.95319, against 444 Rank-1 errors. At the deployed routing rule, the gate recalled all thresholded LBPH system failures, while its false-positive routing rate among thresholded LBPH-correct scored probes was 40.88% and routing precision was 82.40%. The gate therefore captures the relevant failure regime, but deliberately routes many correct LBPH cases to the DL tier.' 'p1a'
    Add-Figure $document ([ref]$cursor) (Join-Path $assets 'gate_competence.svg') 'Fig. 4. Gate competence for threshold-free LBPH Rank-1 errors on scored LSDB-DL41 probes (n = 2,060; 444 errors). Curves evaluate failure discrimination, separate from the thresholded routing outcomes reported in text.'
    $p = Add-Paragraph $document ([ref]$cursor) 'The route sweep shows the cost of that recovery under the recorded recognition-stage timing protocol. The deployed cascade matched SFace at 87.24% thresholded correct-identity acceptance, but used 11.96 ms per probe versus 8.33 ms for SFace-only; it escalated 71.52% of probes. LBPH-only ran at 5.25 ms but reached 30.79%. Thus this run supports recovery and routing evidence, not a selective speed-gain claim.' 'p1a'
    Add-Figure $document ([ref]$cursor) (Join-Path $assets 'speed_accuracy_curve.svg') 'Fig. 5. Recognition-stage timing versus thresholded correct-identity acceptance for held-out LSDB-DL41 probes. Timing is single-pass, model-initialized measurement and is not end-to-end deployment latency.'

    $heading = Add-Paragraph $document ([ref]$cursor) 'Discussion' 'heading1'
    $heading.ParagraphFormat.KeepWithNext = -1
    Add-Paragraph $document ([ref]$cursor) 'Results support a division of labor rather than a claim that the cascade universally improves a stronger learned recognizer. LSDB selection identifies LBPH as the strongest tested classical fast path under its local calibration-only protocol, while SFace is retained as the compact learned tier. The held-out DL41 stress test then shows why the two tiers are operationally useful together: SFace recovers most thresholded LBPH failures and the LBPH distance/margin signals predict rank failures well enough to route them.' 'p1a' | Out-Null
    Add-Paragraph $document ([ref]$cursor) 'The evaluation also exposes an important boundary. On the LSDB-DL41 sweep, the deployed cascade equals SFace-only acceptance but is slower under recorded recognition-stage timing because most probes escalate. On the LFW2 identification evaluation, the cascade likewise closely follows SFace because the frozen LFW gate escalates 97.51% of degraded probes. The practical benefit is therefore a policy-controlled fallback and a transparent failure-routing mechanism, not a demonstrated latency reduction in every domain.' 'p1a' | Out-Null
    Add-Paragraph $document ([ref]$cursor) 'Several limits remain. LSDB candidate selection, LFW threshold calibration, LFW2 robustness, and LSDB-DL41 complementarity answer different protocol questions and must not be merged into one accuracy claim. The LSDB complementarity results use deterministic transformations of a small held-out split; they do not measure open-set recognition, end-to-end device latency, or population-level error independence. Future work should repeat the paired battery with independently captured probes, full end-to-end hardware timing, and a larger open-set impostor corpus.' 'p1a' | Out-Null

    $heading = Add-Paragraph $document ([ref]$cursor) 'Conclusion' 'heading1'
    $heading.ParagraphFormat.KeepWithNext = -1
    Add-Paragraph $document ([ref]$cursor) 'This paper presented LS-Face, a gated hybrid face-recognition system that couples an LBPH fast path with SFace escalation. A provenance-separated evaluation selected LBPH on LSDB, froze the deployment gate from LFW impostor evidence, and evaluated robustness and paired recovery without silently retuning thresholds on test outcomes. On held-out LSDB-DL41 probes, SFace recovered 81.56% of thresholded LBPH errors, while the gate signals discriminated LBPH Rank-1 failures with AUCs near 0.95.' 'p1a' | Out-Null
    Add-Paragraph $document ([ref]$cursor) 'The evidence supports the hybrid as an interpretable routing design: LBPH can provide a low-cost first decision, and SFace supplies a robust fallback when the gate identifies a risky case. It does not support a general claim of lower latency than SFace-only or a universal accuracy gain. Larger independently captured open-set trials and end-to-end embedded measurements are needed before deployment-level performance claims.' 'p1a' | Out-Null

    $heading = Add-Paragraph $document ([ref]$cursor) 'Acknowledgments' 'heading1'
    $heading.ParagraphFormat.KeepWithNext = -1
    Add-Paragraph $document ([ref]$cursor) 'The authors thank the external deep-learning team for providing the candidate-model artifacts used in the offline screening stage.' 'acknowlegments' | Out-Null
    $heading = Add-Paragraph $document ([ref]$cursor) 'Disclosure of Interests' 'heading1'
    $heading.ParagraphFormat.KeepWithNext = -1
    Add-Paragraph $document ([ref]$cursor) 'The authors have no competing interests to declare.' 'p1a' | Out-Null

    $document.Save()
    $document.ExportAsFixedFormat($PdfOutput, 17)
}
finally {
    if ($null -ne $document) { $document.Close(0); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($document) }
    $word.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word)
}

Restore-ZipPart $baselinePath $outputPath $vbaPart
$outputVbaHash = Get-ZipPartHash $outputPath $vbaPart
if ($outputVbaHash -ne $baselineVbaHash) { throw 'VBA hash mismatch after restoration.' }
Copy-Item -LiteralPath $outputPath -Destination $currentPath -Force
$currentVbaHash = Get-ZipPartHash $currentPath $vbaPart
if ($currentVbaHash -ne $baselineVbaHash) { throw 'Current manuscript VBA hash mismatch.' }
Write-Output "DOCM=$outputPath"
Write-Output "PDF=$PdfOutput"
Write-Output "VBA_SHA256=$outputVbaHash"
