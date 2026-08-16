[CmdletBinding()]
param(
    [string]$Baseline = 'docs\manuscript\versions\021_lsface_major.docm',
    [string]$Output = 'docs\manuscript\versions\022_lsface_scope-contracted.docm',
    [string]$PdfOutput = 'docs\manuscript\versions\022_lsface_scope-contracted.pdf',
    [string]$Fig1Image = 'docs\manuscript\figures\fig1_final_architecture_pipeline.png',
    [string]$HistImage = 'docs\manuscript\figures\fig3_frozen_threshold_overlay.png',
    [string]$ContentJson = 'scripts\document-production\v022_full_manuscript.json'
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
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
        finally {
            $sha.Dispose()
            $stream.Dispose()
        }
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
    $replacement = [System.IO.Compression.ZipFile]::Open($temporaryPath, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        $referencePart = $reference.GetEntry($PartName)
        if ($null -eq $referencePart) { throw "Missing $PartName in reference baseline." }
        foreach ($entry in $target.Entries) {
            $newEntry = $replacement.CreateEntry($entry.FullName, [System.IO.Compression.CompressionLevel]::Optimal)
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
    finally { $replacement.Dispose()
        $target.Dispose()
        $reference.Dispose()
    }
    Move-Item -LiteralPath $temporaryPath -Destination $TargetPath -Force
}

function Get-CleanText {
    param([Parameter(Mandatory = $true)]$Range)
    return (($Range.Text -replace '[\r\a]', ' ') -replace '\s+', ' ').Trim()
}

function Replace-ParagraphText {
    param(
        [Parameter(Mandatory = $true)]$Paragraph,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Text,
        [string]$StyleName = $null
    )
    if ($Paragraph.Range.Tables.Count -gt 0) { return }
    $range = $Paragraph.Range.Duplicate
    $range.End = $range.End - 1
    $range.Text = $Text
    if ($StyleName) {
        try {
            $Paragraph.Range.Style = $StyleName
        } catch {}
    }
}

function Set-CellText {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)]$Cell,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Text,
        [Parameter(Mandatory = $true)][bool]$Header,
        [Parameter(Mandatory = $true)][int]$Alignment
    )
    $range = $Cell.Range.Duplicate
    $range.End = $range.End - 1
    $range.Text = $Text
    $range.Font.Reset()
    $range.ParagraphFormat.Reset()
    $range.Style = 'Normal'
    $range.ListFormat.RemoveNumbers()
    $range.Font.Name = 'Times New Roman'
    $range.Font.Size = 8.5
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
    $Table.LeftPadding = 3.0
    $Table.RightPadding = 3.0
    $Table.TopPadding = 0
    $Table.BottomPadding = 0
    for ($column = 1; $column -le [Math]::Min($Widths.Count, $Table.Columns.Count); $column++) {
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

function Populate-LncsTable {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)]$Table,
        [Parameter(Mandatory = $true)][object[]]$Values,
        [Parameter(Mandatory = $true)][double[]]$Widths
    )
    $targetRows = $Values.Count
    $targetCols = $Values[0].Count

    while ($Table.Rows.Count -gt $targetRows) {
        $Table.Rows.Item($Table.Rows.Count).Delete()
    }
    while ($Table.Rows.Count -lt $targetRows) {
        [void]$Table.Rows.Add()
    }
    while ($Table.Columns.Count -gt $targetCols) {
        $Table.Columns.Item($Table.Columns.Count).Delete()
    }
    while ($Table.Columns.Count -lt $targetCols) {
        [void]$Table.Columns.Add()
    }

    Format-LncsTable $Table $Widths
    for ($row = 1; $row -le $targetRows; $row++) {
        for ($column = 1; $column -le $targetCols; $column++) {
            $alignment = if ($column -ge 2) { 1 } else { 0 }
            Set-CellText $Document $Table.Cell($row, $column) $Values[$row - 1][$column - 1] ($row -eq 1) $alignment
        }
    }
}

$baselinePath = Resolve-WorkspacePath $Baseline
$outputPath = Resolve-WorkspacePath $Output
$pdfPath = Resolve-WorkspacePath $PdfOutput
$fig1Path = Resolve-WorkspacePath $Fig1Image
$histPath = Resolve-WorkspacePath $HistImage
$contentJsonPath = Resolve-WorkspacePath $ContentJson

$vbaPart = 'word/vbaProject.bin'
$baselineVbaHash = Get-ZipPartHash $baselinePath $vbaPart
$stagePath = Join-Path ([System.IO.Path]::GetTempPath()) ("lsface_022perfect_{0}.docm" -f [guid]::NewGuid().ToString('N'))

$content = Get-Content -LiteralPath $contentJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json

Write-Output "================================================================================"
Write-Output " BUILDING PERFECT LNCS 022 SCOPE-CONTRACTED MANUSCRIPT"
Write-Output "================================================================================"

try {
    Copy-Item -LiteralPath $baselinePath -Destination $stagePath

    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $null

    try {
        $document = $word.Documents.Open($stagePath, $false, $false)

        # -------------------------------------------------------------
        # 1. Update Running Header
        # -------------------------------------------------------------
        Write-Output "[1/6] Setting Running Headers..."
        foreach ($section in $document.Sections) {
            foreach ($hdrIdx in 1..3) {
                try {
                    $hdr = $section.Headers.Item($hdrIdx)
                    if ($hdr.Exists) {
                        $hdr.Range.Text = "LS-Face: Quality-First Selective Computation in Hybrid Face Recognition"
                    }
                } catch {}
            }
        }

        # -------------------------------------------------------------
        # 2. Update Tables 1 through 8
        # -------------------------------------------------------------
        Write-Output "[2/6] Populating Tables 1 through 8..."
        if ($document.Tables.Count -ge 1) {
            $t1 = $document.Tables.Item(1)
            $t1Data = @(
                @('Signal', 'Measurement / condition', 'Selection rule', 'Deployed value'),
                @('Blur', 'Variance of Laplacian below threshold', '5th percentile of clean values', '587.83'),
                @('Illumination', 'Mean grayscale outside lower/upper bounds', '2nd and 98th percentiles of clean values', '[52.88, 137.71]'),
                @('Noise', 'Immerkaer noise estimate above threshold', '95th percentile of clean values', '8.206'),
                @('Pose', 'Maximum of eye-roll and nose-yaw proxies above threshold', '95th percentile of clean values', '63.74 deg'),
                @('Face size', 'Detected box side below minimum', '0.9 x p5 of clean box sizes', '61 px')
            )
            Populate-LncsTable $document $t1 $t1Data @(60, 135, 115, 45)
        }

        if ($document.Tables.Count -ge 2) {
            $t2 = $document.Tables.Item(2)
            $t2Data = @(
                @('Evidence leg', 'Protocol and cohort', 'Primary question answered'),
                @('A. Candidate selection', 'La Salle DB1 deterministic split (224/56/56)', 'Select best classical (LBPH) and learned (SFace) recognizers'),
                @('B. Threshold calibration', '2,875 LFW development identities (4.13M pairs)', 'Calibrate low-tail operating points at target 10 ppm FAR'),
                @('C. Controlled robustness', '2,874 LFW evaluation identities (117,834 conditions)', 'Evaluate transformation retention and dual-inference rate'),
                @('D. Locked confirmation', '22 La Salle DB1 identities (1,804 conditions)', 'Confirm decision parity, latency reduction, and subsumption')
            )
            Populate-LncsTable $document $t2 $t2Data @(100, 125, 130)
        }

        if ($document.Tables.Count -ge 3) {
            $t3 = $document.Tables.Item(3)
            $t3Data = @(
                @('Recognizer', 'Feature size', 'Evaluation latency', 'Rank-1 accuracy'),
                @('Eigenfaces (PCA)', '220 B (55 comp.)', '0.08 ms', '78.57%'),
                @('Fisherfaces (LDA)', '108 B (27 comp.)', '0.05 ms', '82.14%'),
                @('LBPH', '64 KiB (16,384 bins)', '2.84 ms', '100.00%')
            )
            Populate-LncsTable $document $t3 $t3Data @(105, 90, 85, 75)
        }

        if ($document.Tables.Count -ge 4) {
            $t4 = $document.Tables.Item(4)
            $t4Data = @(
                @('Candidate', 'TAR (%)', 'Rank-1 (%)', 'Feature size'),
                @('SFace', '100.00%', '100.00%', '512 B'),
                @('ArcFace', '96.43%', '100.00%', '2,048 B'),
                @('FaceNet', '100.00%', '100.00%', '2,048 B')
            )
            Populate-LncsTable $document $t4 $t4Data @(90, 80, 85, 90)
        }

        if ($document.Tables.Count -ge 5) {
            $t5 = $document.Tables.Item(5)
            $t5Data = @(
                @('Boundary', 'Frozen value', 'Operational role'),
                @('LBPH accept', '52.3724', 'Early accept (10 ppm FAR on 2,875 LFW dev)'),
                @('SFace accept', 'L2 <= 1.0313; cosine >= 0.363', 'Escalated accept (10 ppm FAR on dev)'),
                @('LBPH margin', 'mmin = 0.05', 'Relative top-two margin policy heuristic'),
                @('LBPH reject', '140.13', 'Permissive ceiling (inactive on evaluation)')
            )
            Populate-LncsTable $document $t5 $t5Data @(85, 135, 135)
        }

        if ($document.Tables.Count -ge 6) {
            $t6 = $document.Tables.Item(6)
            $t6Data = @(
                @('System', 'Clean retention', '41-mod retention', '37-mod (non-rot)', 'SFace invoc.', 'Dual inf.'),
                @('Compact LBPH', '99.97%', '81.19%', '89.78%', 'N/A', 'N/A'),
                @('Direct SFace', '99.97%', '89.55%', '96.54%', 'N/A', 'N/A'),
                @('LS-Face', '99.97%', '89.55%', '96.54%', '96.35%', '0.26%')
            )
            Populate-LncsTable $document $t6 $t6Data @(75, 56, 56, 56, 56, 56)
        }

        if ($document.Tables.Count -ge 7) {
            $t7 = $document.Tables.Item(7)
            $t7Data = @(
                @('System', 'Accuracy', 'Mean latency', 'p50', 'p95', 'p99', 'Dual inf.', 'Early exits'),
                @('Direct SFace', '88.36%', '8.300 ms', '8.206 ms', '9.183 ms', '10.073 ms', '0.00%', 'N/A'),
                @('LS-Face', '88.36%', '7.015 ms', '8.265 ms', '11.704 ms', '12.388 ms', '18.06%', '50.50%')
            )
            Populate-LncsTable $document $t7 $t7Data @(60, 42, 45, 40, 40, 40, 42, 46)
        }

        if ($document.Tables.Count -ge 8) {
            $t8 = $document.Tables.Item(8)
            $t8Data = @(
                @('SFace outcome', 'LBPH correct', 'LBPH incorrect', 'Total'),
                @('SFace correct', '1,156 (64.08%)', '438 (24.28%)', '1,594 (88.36%)'),
                @('SFace incorrect', '0 (0.00%)', '210 (11.64%)', '210 (11.64%)'),
                @('Total', '1,156 (64.08%)', '648 (35.92%)', '1,804 (100.0%)')
            )
            Populate-LncsTable $document $t8 $t8Data @(85, 90, 90, 90)
        }

        # -------------------------------------------------------------
        # 3. Clean up obsolete paragraphs
        # -------------------------------------------------------------
        Write-Output "[3/6] Removing obsolete paragraphs..."
        $deleteSubstrings = @(
            "Escalation logic. Let",
            "the best LBPH distance lies within",
            "the relative top-two margin is below",
            "The quality thresholds in Table 1 were defined",
            "If no escalation condition is triggered",
            "Stage 2 recognition and final decision",
            "The deployed thresholds and escalation parameters were fixed",
            "Classical candidates were fitted and calibrated",
            "Offline recognizer selection procedure",
            "Offline recognizer selection",
            "unique comparisons. Because every pair contains",
            "The operating threshold is selected at the corresponding",
            "The development partition calibration completely",
            "Unlike the acceptance threshold",
            "Threshold freezing",
            "The La Salle DB1 held-out evaluation uses clean enrollment images",
            "The learned candidates were evaluated on the same deterministic",
            "SFace and FaceNet tied at 100.00% held-out TAR",
            "Fig. 3 places these frozen operating points against",
            "Recovery=",
            "Recovery =",
            "N(SFace correct",
            "Evaluation Metrics.",
            "Decision Equivalence.",
            "For each recognizer, the resulting native scores",
            "Locked Confirmation Evaluation"
        )

        for ($i = $document.Paragraphs.Count; $i -ge 1; $i--) {
            try {
                $p = $document.Paragraphs.Item($i)
                if ($p.Range.Tables.Count -eq 0) {
                    $txt = Get-CleanText $p.Range
                    $shouldDelete = $false
                    foreach ($sub in $deleteSubstrings) {
                        if ($txt -eq $sub -or ($sub.Length -gt 15 -and $txt.Contains($sub))) {
                            $shouldDelete = $true
                            break
                        }
                    }
                    if (-not $shouldDelete) {
                        if ($p.Range.OMaths.Count -gt 0 -or ($txt -match "d2" -and $txt -match "d1") -or $txt -match "^k\s*=" -or $txt -match "^C\s*=" -or $txt -match "^Recovery\s*=" -or $txt -match "N\(LBPH failure\)" -or $txt -eq "(1)" -or $txt -eq "(2)") {
                            $shouldDelete = $true
                        }
                    }
                    if ($shouldDelete) {
                        [void]$p.Range.Delete()
                    }
                }
            } catch {}
        }

        # -------------------------------------------------------------
        # 4. Update Paragraphs Systematically
        # -------------------------------------------------------------
        Write-Output "[4/6] Updating Paragraphs..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            if ($p.Range.Tables.Count -eq 0) {
                $txt = Get-CleanText $p.Range

                # Title
                if ($p.Range.Style.NameLocal -eq 'papertitle' -or $txt.StartsWith("LS-Face:")) {
                    Replace-ParagraphText $p $content.papertitle 'papertitle'
                }
                # Abstract
                elseif ($txt.StartsWith("Abstract.")) {
                    Replace-ParagraphText $p $content.abstract 'abstract'
                    $p.Range.Font.Bold = 0
                    $rAbs = $p.Range.Duplicate
                    $rAbs.End = $rAbs.Start + 9
                    $rAbs.Font.Bold = -1
                }
                # Keywords
                elseif ($txt.StartsWith("Keywords:")) {
                    Replace-ParagraphText $p $content.keywords 'keywords'
                    $rKey = $p.Range.Duplicate
                    $rKey.End = $rKey.Start + 9
                    $rKey.Font.Bold = -1
                }
                # Intro final paragraph
                elseif ($txt.StartsWith("Based on these concepts") -or $txt.StartsWith("Based on these considerations") -or $txt.StartsWith("To address these challenges")) {
                    Replace-ParagraphText $p $content.intro_p_final 'p1a'
                }
                # Section 2 Related Work
                elseif ($txt -eq "Face Recognition Models" -or $txt -eq "Classical and Deep Face Recognition" -or $txt -eq "2.1 Classical and Deep Face Recognition") {
                    Replace-ParagraphText $p "Classical and Deep Face Recognition" 'heading2'
                }
                elseif ($txt.StartsWith("Classical face recognition methods provide") -or $txt.StartsWith("Classical face-recognition methods represent")) {
                    Replace-ParagraphText $p $content.sec2_1_p1 'p1a'
                }
                elseif ($txt.StartsWith("Deep face recognition instead learns") -or $txt.StartsWith("Deep face-recognition models learn")) {
                    Replace-ParagraphText $p $content.sec2_1_p2 'Normal'
                }
                elseif ($txt -eq "Face Detection and Alignment" -or $txt -eq "2.2 Face Detection and Alignment") {
                    Replace-ParagraphText $p "Face Detection and Alignment" 'heading2'
                }
                elseif ($txt.StartsWith("Recognition also depends on reliable") -or $txt.StartsWith("Recognition performance also depends on")) {
                    Replace-ParagraphText $p $content.sec2_2_p1 'Normal'
                }
                elseif ($txt -eq "Selective and Edge Recognition" -or $txt -eq "Selective Computation and Face Quality" -or $txt -eq "2.3 Selective Computation and Face Quality") {
                    Replace-ParagraphText $p "Selective Computation and Face Quality" 'heading2'
                }
                elseif ($txt.StartsWith("Efficient face recognition can be addressed") -or $txt.StartsWith("Efficient recognition can be approached")) {
                    Replace-ParagraphText $p $content.sec2_3_p1 'Normal'
                }
                elseif ($txt.StartsWith("LS-Face follows this selective-computation") -or $txt.StartsWith("LS-Face follows the selective-computation")) {
                    Replace-ParagraphText $p $content.sec2_3_p2 'Normal'
                }
                elseif ($txt -eq "Evaluation and Robustness" -or $txt -eq "2.4 Evaluation and Robustness") {
                    Replace-ParagraphText $p "Evaluation and Robustness" 'heading2'
                }
                elseif ($txt.StartsWith("Biometric evaluation requires")) {
                    Replace-ParagraphText $p $content.sec2_4_p1 'Normal'
                }
                elseif ($txt.StartsWith("Accordingly, this study treats") -or $txt.StartsWith("Accordingly, LS-Face separates")) {
                    Replace-ParagraphText $p $content.sec2_4_p2 'Normal'
                }
                # Section 3: Methodology
                elseif ($txt -eq "System Overview and Escalation Logic" -or $txt -eq "System Overview and Selective-Computation Logic" -or $txt -eq "3.1 System Overview and Selective-Computation Logic") {
                    Replace-ParagraphText $p "System Overview and Selective-Computation Logic" 'heading2'
                }
                elseif ($txt.StartsWith("Fig. 1. Overview of the LS-Face") -or $txt.StartsWith("Fig. 1. Final LS-Face")) {
                    Replace-ParagraphText $p "Fig. 1. Final LS-Face quality-first selective-computation pipeline." 'figurecaption'
                }
                elseif ($txt.StartsWith("LS-Face processes each input image") -or $txt.StartsWith("LS-Face is a quality-first")) {
                    Replace-ParagraphText $p $content.sec3_1_p1 'Normal'
                }
                elseif ($txt.StartsWith("Stage 1 recognition.") -or $txt.StartsWith("For each successfully detected face")) {
                    Replace-ParagraphText $p $content.sec3_1_p2 'Normal'
                }
                elseif ($txt.StartsWith("LS-Face eliminates this structural") -or $txt.StartsWith("If all quality checks pass")) {
                    Replace-ParagraphText $p $content.sec3_1_p3 'Normal'
                }
                elseif ($txt.StartsWith("SFace therefore receives inputs through")) {
                    Replace-ParagraphText $p $content.sec3_1_p4 'Normal'
                }
                elseif ($txt.StartsWith("This architecture distinguishes the SFace")) {
                    Replace-ParagraphText $p $content.sec3_1_p5 'Normal'
                }
                elseif ($txt.StartsWith("Table 1. Deployed quality-check")) {
                    Replace-ParagraphText $p "Table 1. Deployed quality-check parameters for pre-LBPH early bypass." 'tablecaption'
                }
                # 3.2 Recognizer Selection
                elseif ($txt.StartsWith("LS-Face assigns distinct computational roles to its classical") -or $txt.StartsWith("Recognizer selection was conducted offline")) {
                    Replace-ParagraphText $p $content.sec3_2_p1 'Normal'
                }
                # 3.3 Threshold Calibration
                elseif ($txt -eq "Independence Testing and Threshold Freezing" -or $txt -eq "Threshold Calibration and Frozen Operating Policy" -or $txt -eq "3.3 Threshold Calibration and Frozen Operating Policy") {
                    Replace-ParagraphText $p "Threshold Calibration and Frozen Operating Policy" 'heading2'
                }
                elseif ($txt.StartsWith("Independence-test construction") -or $txt.StartsWith("All operational thresholds were independently calibrated")) {
                    Replace-ParagraphText $p $content.sec3_3_p1 'Normal'
                }
                # 3.4 Experimental Program
                elseif ($txt -eq "Experimental Protocol" -or $txt -eq "Experimental Program" -or $txt -eq "3.4 Experimental Program") {
                    Replace-ParagraphText $p "Experimental Program" 'heading2'
                }
                elseif ($txt.StartsWith("To evaluate the proposed architecture without") -or $txt.StartsWith("To establish evidence across distinct")) {
                    Replace-ParagraphText $p $content.sec3_4_p1 'p1a'
                }
                elseif ($txt.StartsWith("Timing Protocol.") -or $txt.StartsWith("Timing measurements were recorded on an Intel")) {
                    Replace-ParagraphText $p $content.sec3_4_p2 'Normal'
                }
                elseif ($txt.StartsWith("Table 2. Experiments and biological roles") -or $txt.StartsWith("Table 2. Experiments and their roles") -or $txt.StartsWith("Table 1. Experiments and their roles")) {
                    Replace-ParagraphText $p "Table 2. Experiments and their roles in the study." 'tablecaption'
                }
                # Section 4: Results
                elseif ($txt.StartsWith("The experimental program consists of four evidence legs")) {
                    Replace-ParagraphText $p "The experimental program consists of four evidence legs summarized in Table 2: (A) candidate recognizer selection on La Salle DB1; (B) threshold calibration on the 2,875-identity LFW development partition; (C) controlled self-match transformation robustness on 2,874 disjoint LFW evaluation identities across 117,834 conditions; and (D) locked architecture confirmation on 22 La Salle DB1 identities (1,804 conditions)." 'p1a'
                }
                # 4.1 Candidate Selection
                elseif ($txt -eq "Algorithm Selection on La Salle DB1" -or $txt -eq "Candidate Selection on La Salle DB1" -or $txt -eq "4.1 Candidate Selection on La Salle DB1") {
                    Replace-ParagraphText $p "Candidate Selection on La Salle DB1" 'heading2'
                }
                elseif ($txt.StartsWith("Classical candidates were fitted on 224") -or $txt.StartsWith("Candidate recognizers were evaluated on a deterministic")) {
                    Replace-ParagraphText $p $content.sec4_1_p1 'p1a'
                }
                elseif ($txt.StartsWith("Table 3. Classical candidate selection")) {
                    Replace-ParagraphText $p "Table 3. Classical candidate selection on La Salle DB1." 'tablecaption'
                }
                elseif ($txt.StartsWith("Table 4. DL candidate selection")) {
                    Replace-ParagraphText $p "Table 4. DL candidate selection on La Salle DB1." 'tablecaption'
                }
                # 4.2 Independence Test
                elseif ($txt -eq "Independence Test: Frozen Operating Points" -or $txt -eq "4.2 Independence Test: Frozen Operating Points") {
                    Replace-ParagraphText $p "Independence Test: Frozen Operating Points" 'heading2'
                }
                elseif ($txt.StartsWith("The LFW independence test produced") -or $txt.StartsWith("Table 5 summarizes the final frozen")) {
                    Replace-ParagraphText $p $content.sec4_2_p1 'p1a'
                }
                elseif ($txt.StartsWith("Table 5. Final frozen operating points")) {
                    Replace-ParagraphText $p "Table 5. Final frozen operating points." 'tablecaption'
                }
                elseif ($txt.StartsWith("Fig. 3. Histograms and KDE curves") -or $txt.StartsWith("Fig. 2. Histograms and KDE curves")) {
                    Replace-ParagraphText $p "Fig. 2. Histograms and KDE curves of La Salle DB1 clean-impostor scores with frozen LFW development operating points (tau_accept = 52.3724, tau_reject = 140.13, L2 = 1.0313)." 'figurecaption'
                }
                # 4.3 Controlled Robustness
                elseif ($txt -eq "Controlled Self-Match Robustness Test" -or $txt -eq "4.3 Controlled Self-Match Robustness Test") {
                    Replace-ParagraphText $p "Controlled Self-Match Robustness Test" 'heading2'
                }
                elseif ($txt.StartsWith("Table 6 reports the corrected controlled") -or $txt.StartsWith("Table 6 reports controlled self-match")) {
                    Replace-ParagraphText $p $content.sec4_3_p1 'p1a'
                }
                elseif ($txt.StartsWith("Table 6. Controlled self-match")) {
                    Replace-ParagraphText $p "Table 6. Controlled self-match robustness test on LFW." 'tablecaption'
                }
                elseif ($txt.StartsWith("The experiment uses the frozen operating") -or $txt.StartsWith("Under this stress workload, LS-Face invoked")) {
                    Replace-ParagraphText $p $content.sec4_3_p2 'Normal'
                }
                # 4.4 Locked Confirmation
                elseif ($txt -eq "Cascade Diagnosis and Two-Factor Ablation" -or $txt -eq "4.4 Locked Confirmation Evaluation") {
                    Replace-ParagraphText $p "Locked Confirmation Evaluation" 'heading2'
                }
                elseif ($txt.StartsWith("To isolate the individual and combined") -or ($txt.StartsWith("On the locked 22-identity confirmation cohort") -and $i -lt 210)) {
                    Replace-ParagraphText $p $content.sec4_4_p1 'p1a'
                }
                elseif ($txt.StartsWith("Table 7. Two-factor ablation") -or $txt.StartsWith("Table 7. Performance and latency comparison")) {
                    Replace-ParagraphText $p "Table 7. Performance and latency comparison of Direct SFace and LS-Face on 1,804 locked confirmation conditions." 'tablecaption'
                }
                elseif ($txt.StartsWith("Table 8. Complementarity matrix") -or $txt.StartsWith("Table 8. Decision complementarity matrix")) {
                    Replace-ParagraphText $p "Table 8. Decision complementarity matrix across 1,804 locked confirmation conditions." 'tablecaption'
                }
                elseif ($txt.StartsWith("Across the 1,711 timed conditions, LS-Face reduced") -or ($txt.StartsWith("On the locked 22-identity confirmation cohort") -and $i -ge 210)) {
                    Replace-ParagraphText $p $content.sec4_4_p2 'Normal'
                }
                elseif ($txt.StartsWith("Table 8 reports the 2x2 decision complementarity") -or $txt.StartsWith("Across all 1,804 locked confirmation conditions, 1,156")) {
                    Replace-ParagraphText $p $content.sec4_4_p3 'Normal'
                }
                # 4.5 Severity
                elseif ($txt.StartsWith("Workload Severity and Latency Profile.") -or $txt.StartsWith("The operational benefit of LS-Face varies") -or $txt.StartsWith("Across degradation tiers")) {
                    Replace-ParagraphText $p ("Workload Severity and Latency Profile. " + $content.sec4_5_p1) 'Normal'
                }
                # Section 5: Discussion
                elseif ($txt -eq "Selective Computation and Elimination of Redundancy" -or $txt -eq "Quality-First Selective Computation" -or $txt -eq "5.1 Quality-First Selective Computation") {
                    Replace-ParagraphText $p "Quality-First Selective Computation" 'heading2'
                }
                elseif ($txt.StartsWith("Traditional sequential cascades")) {
                    Replace-ParagraphText $p $content.sec5_1_p1 'p1a'
                }
                elseif ($txt -eq "Orthogonal Computational Optimizations" -or $txt -eq "LBPH as a Computational Shortcut" -or $txt -eq "5.2 LBPH as a Computational Shortcut") {
                    Replace-ParagraphText $p "LBPH as a Computational Shortcut" 'heading2'
                }
                elseif ($txt.StartsWith("Quality-first bypass and compact") -or $txt.StartsWith("Within the 1,804 locked confirmation conditions")) {
                    Replace-ParagraphText $p $content.sec5_2_p1 'Normal'
                }
                elseif ($txt -eq "Computational Shortcuts vs. Accuracy Complementarity" -or $txt -eq "Robustness and Latency Trade-off" -or $txt -eq "5.3 Robustness and Latency Trade-off") {
                    Replace-ParagraphText $p "Robustness and Latency Trade-off" 'heading2'
                }
                elseif ($txt.StartsWith("The 100.0% subsumption of LBPH") -or $txt.StartsWith("LS-Face matched standalone SFace transformation")) {
                    Replace-ParagraphText $p $content.sec5_3_p1 'Normal'
                }
                elseif ($txt.StartsWith("Limitations. The permissive reject boundary") -or $txt -eq "Limitations" -or $txt -eq "5.4 Limitations") {
                    Replace-ParagraphText $p "Limitations" 'heading2'
                }
                # Section 6: Conclusion
                elseif ($txt -eq "Conclusion" -or $txt -eq "6 Conclusion") {
                    Replace-ParagraphText $p "Conclusion" 'heading1'
                }
                elseif ($txt -eq "Principal Findings" -or $txt -eq "6.1 Principal Findings") {
                    Replace-ParagraphText $p "Principal Findings" 'heading2'
                }
                elseif ($txt.StartsWith("LS-Face demonstrates that hybrid face") -or $txt.StartsWith("LS-Face demonstrates that quality-first")) {
                    Replace-ParagraphText $p $content.sec6_1_p1 'p1a'
                }
                elseif ($txt -eq "Architectural Implications" -or $txt -eq "6.2 Architectural Implications") {
                    Replace-ParagraphText $p "Architectural Implications" 'heading2'
                }
                elseif ($txt.StartsWith("By formalizing classical descriptors") -or $txt.StartsWith("These findings establish that classical biometric")) {
                    Replace-ParagraphText $p $content.sec6_2_p1 'Normal'
                }
            }
        }

        # Structure normalization pass:
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            if ($p.Range.Tables.Count -eq 0) {
                $t = Get-CleanText $p.Range
                if ($t -eq "Robustness and Latency Trade-off") {
                    # p is 5.3 Heading (heading2)
                    $p.Range.Style = 'heading2'
                    
                    # p+1 is 5.3 Body (Normal)
                    $p53Body = $document.Paragraphs.Item($i + 1)
                    Replace-ParagraphText $p53Body $content.sec5_3_p1 'Normal'

                    # p+2 is 5.4 Limitations Heading (heading2)
                    $p54Hdr = $document.Paragraphs.Item($i + 2)
                    Replace-ParagraphText $p54Hdr "Limitations" 'heading2'

                    # Check if body already inserted
                    $p54Body = $document.Paragraphs.Item($i + 3)
                    $bTxt = Get-CleanText $p54Body.Range
                    if (-not $bTxt.StartsWith("Several methodological boundaries")) {
                        $rngAfter = $p54Hdr.Range.Duplicate
                        $rngAfter.Collapse(0)
                        $rngAfter.InsertParagraphAfter()
                        $p54Body = $document.Paragraphs.Item($i + 3)
                    }
                    Replace-ParagraphText $p54Body $content.sec5_4_p1 'Normal'
                    $p54Body.Range.Font.Reset()
                    $p54Body.Range.ParagraphFormat.Reset()
                    $p54Body.Range.ListFormat.RemoveNumbers()
                    $p54Body.Range.Font.Name = 'Times New Roman'
                    $p54Body.Range.Font.Size = 10
                    $p54Body.Range.Font.Bold = 0

                    # p+4 is 6 Conclusion Heading (heading1)
                    $p6Hdr = $document.Paragraphs.Item($i + 4)
                    Replace-ParagraphText $p6Hdr "Conclusion" 'heading1'

                    # p+5 is 6.1 Principal Findings Heading (heading2)
                    $p61Hdr = $document.Paragraphs.Item($i + 5)
                    Replace-ParagraphText $p61Hdr "Principal Findings" 'heading2'

                    # p+6 is 6.1 Body (p1a)
                    $p61Body = $document.Paragraphs.Item($i + 6)
                    Replace-ParagraphText $p61Body $content.sec6_1_p1 'p1a'

                    # p+7 is 6.2 Architectural Implications Heading (heading2)
                    $p62Hdr = $document.Paragraphs.Item($i + 7)
                    Replace-ParagraphText $p62Hdr "Architectural Implications" 'heading2'

                    # p+8 is 6.2 Body (Normal)
                    $p62Body = $document.Paragraphs.Item($i + 8)
                    Replace-ParagraphText $p62Body $content.sec6_2_p1 'Normal'

                    # p+9 is Acknowledgments (heading3)
                    $pAck = $document.Paragraphs.Item($i + 9)
                    $pAck.Range.Style = 'heading3'

                    # p+10 is Disclosure of Interests (heading3)
                    $pDisc = $document.Paragraphs.Item($i + 10)
                    $pDisc.Range.Style = 'heading3'
                    break
                }
            }
        }

        # -------------------------------------------------------------
        # 5. Insert / Align Figures 1 and 2
        # -------------------------------------------------------------
        Write-Output "[5/6] Aligning Figures 1 and 2..."
        while ($document.InlineShapes.Count -gt 0) {
            $document.InlineShapes.Item(1).Delete()
        }

        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            if ($p.Range.Tables.Count -eq 0 -and $p.Range.Text -match "Fig\. 1\. Final LS-Face") {
                $rng = $p.Range.Duplicate
                $rng.Collapse(1)
                $shp = $document.InlineShapes.AddPicture($fig1Path, $false, $true, $rng)
                $shp.Width = 345
                $shp.Height = 144
                break
            }
        }

        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            if ($p.Range.Tables.Count -eq 0 -and $p.Range.Text -match "Fig\. 2\. Histograms and KDE curves") {
                if (Test-Path -LiteralPath $histPath) {
                    $rng = $p.Range.Duplicate
                    $rng.Collapse(1)
                    $shp = $document.InlineShapes.AddPicture($histPath, $false, $true, $rng)
                    $shp.Width = 345
                    $shp.Height = 144
                }
                break
            }
        }

        # -------------------------------------------------------------
        # 6. Save DOCM and Export PDF
        # -------------------------------------------------------------
        Write-Output "[6/6] Saving editable DOCM and exporting PDF..."
        $document.Save()
        $document.SaveAs([ref]$outputPath, [ref]13) # wdFormatXMLDocumentMacroEnabled = 13
        $document.ExportAsFixedFormat($pdfPath, 17) # wdExportFormatPDF = 17
        Write-Output "[SUCCESS] Exported DOCM and PDF successfully."
    }
    finally {
        if ($document) { $document.Close($false) }
        $word.Quit()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    }

    # Repack and verify VBA part
    Restore-ZipPart $baselinePath $outputPath $vbaPart
    $finalVbaHash = Get-ZipPartHash $outputPath $vbaPart
    Write-Output "Baseline VBA SHA256: $baselineVbaHash"
    Write-Output "Final DOCM VBA SHA256: $finalVbaHash"
    if ($baselineVbaHash -ne $finalVbaHash) {
        throw "VBA hash mismatch after repacking! Expected $baselineVbaHash but got $finalVbaHash"
    }
    Write-Output "[SUCCESS] Bit-identical VBA project preserved ($finalVbaHash)!"

}
finally {
    if (Test-Path -LiteralPath $stagePath) { Remove-Item -LiteralPath $stagePath -Force }
}

Write-Output "================================================================================"
Write-Output " BUILD COMPLETED: PERFECT 022_SCOPE-CONTRACTED MANUSCRIPT READY"
Write-Output " Output DOCM: $outputPath"
Write-Output " Output PDF:  $pdfPath"
Write-Output "================================================================================"
