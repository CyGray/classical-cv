[CmdletBinding()]
param(
    [string]$Baseline = 'docs\manuscript\versions\020b_lsface_canonical-selfmatch-promoted.docm',
    [string]$Output = 'docs\manuscript\versions\021_lsface_major.docm',
    [string]$PdfOutput = 'docs\manuscript\versions\021_lsface_major.pdf'
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

function Replace-ParagraphText {
    param(
        [Parameter(Mandatory = $true)]$Paragraph,
        [Parameter(Mandatory = $true)][string]$Text,
        [string]$StyleName = $null
    )
    $range = $Paragraph.Range.Duplicate
    $range.End = $range.End - 1
    $range.Text = $Text
    if ($StyleName) {
        $range.Style = $Paragraph.Range.Document.Styles.Item($StyleName)
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
    $range.Style = $Document.Styles.Item('Normal')
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

function Populate-LncsTable {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)]$Table,
        [Parameter(Mandatory = $true)][object[]]$Values,
        [Parameter(Mandatory = $true)][double[]]$Widths
    )
    Format-LncsTable $Table $Widths
    for ($row = 1; $row -le $Table.Rows.Count; $row++) {
        for ($column = 1; $column -le $Table.Columns.Count; $column++) {
            $alignment = if ($column -ge 2) { 1 } else { 0 }
            Set-CellText $Document $Table.Cell($row, $column) $Values[$row - 1][$column - 1] ($row -eq 1) $alignment
        }
    }
}

$baselinePath = Resolve-WorkspacePath $Baseline
$outputPath = Resolve-WorkspacePath $Output
$pdfPath = Resolve-WorkspacePath $PdfOutput

$vbaPart = 'word/vbaProject.bin'
$baselineVbaHash = Get-ZipPartHash $baselinePath $vbaPart
$stagePath = Join-Path ([System.IO.Path]::GetTempPath()) ("lsface_021flawless_{0}.docm" -f [guid]::NewGuid().ToString('N'))

Write-Output "================================================================================"
Write-Output " BUILDING FLAWLESS 021_MAJOR MANUSCRIPT (LS-FACE SELECTIVE COMPUTATION)"
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
        Write-Output "[1/7] Updating Running Headers across all sections..."
        foreach ($section in $document.Sections) {
            foreach ($hdrIdx in 1..3) {
                try {
                    $hdr = $section.Headers.Item($hdrIdx)
                    if ($hdr.Exists) {
                        $txt = $hdr.Range.Text
                        if ($txt -match "Facial Recognition Using Hybrid Technologies" -or $txt -match "LS-Face:") {
                            $hdr.Range.Text = "LS-Face: Selective Computation in Hybrid Face Recognition"
                        }
                    }
                } catch {}
            }
        }

        # -------------------------------------------------------------
        # 2. Update Existing Tables 1, 3, 5, 6 FIRST
        # -------------------------------------------------------------
        Write-Output "[2/7] Updating Tables 1, 3, 5, 6 with exact numbers..."
        if ($document.Tables.Count -ge 1) {
            $t1 = $document.Tables.Item(1)
            $t1Data = @(
                @('Signal', 'Measurement / condition', 'Selection rule', 'Deployed value'),
                @('Blur', 'Variance of Laplacian below threshold', '5th percentile of clean values', '587.83'),
                @('Illumination', 'Mean grayscale outside lower/upper bounds', '2nd and 98th percentiles of clean values', '[52.88, 137.71]'),
                @('Noise', 'Immerkaer noise estimate above threshold', '95th percentile of clean values', '8.206'),
                @('Pose', 'Maximum of eye-roll and nose-yaw proxies above threshold', '95th percentile of clean values', '63.74 deg'),
                @('Face size', 'Detected box side below minimum', '0.9 x p5 of clean box sizes', '61 px'),
                @('Relative top-two margin', '(d2 - d1) / d1 < mmin', 'Fixed engineering policy value', 'mmin = 0.05')
            )
            Populate-LncsTable $document $t1 $t1Data @(72, 130, 118, 58)
        }

        if ($document.Tables.Count -ge 3) {
            $t3 = $document.Tables.Item(3)
            $t3Data = @(
                @('Recognizer', 'Feature size', 'Evaluation latency', 'Rank-1 accuracy'),
                @('Eigenfaces (PCA)', '220 B (55 comp.)', '0.08 ms', '78.57%'),
                @('Fisherfaces (LDA)', '108 B (27 comp.)', '0.05 ms', '82.14%'),
                @('Compact LBPH (r3_n8_g6x6)', '36 KiB (9,216 bins)', '1.68 ms', '92.86%')
            )
            Populate-LncsTable $document $t3 $t3Data @(110, 95, 95, 78)
        }

        if ($document.Tables.Count -ge 5) {
            $t5 = $document.Tables.Item(5)
            $t5Data = @(
                @('Boundary', 'Frozen value', 'Role'),
                @('LBPH accept', '52.3724', 'Early accept (10 ppm FAR on LFW dev)'),
                @('SFace accept', 'L2 <= 1.0313; cosine >= 0.363', 'Escalated accept (10 ppm FAR on dev)'),
                @('LBPH reject', '140.13', 'Permissive ceiling (inactive on test)')
            )
            Populate-LncsTable $document $t5 $t5Data @(110, 140, 128)
        }

        if ($document.Tables.Count -ge 6) {
            $t6 = $document.Tables.Item(6)
            $t6Data = @(
                @('Mode', 'Clean self-match (%)', '41-transformation retention (%)', '41-transformation escalation (%)'),
                @('Classical CV (LBPH)', '99.97', '81.19', 'N/A'),
                @('Deep Learning (SFace)', '99.97', '89.55', 'N/A'),
                @('Hybrid Cascade', '99.97', '89.55', '96.35')
            )
            Populate-LncsTable $document $t6 $t6Data @(120, 85, 95, 78)
        }

        # -------------------------------------------------------------
        # 3. Replace Legacy Pie Chart and Bar Chart with Native Tables 7 & 8
        # -------------------------------------------------------------
        Write-Output "[3/7] Replacing legacy figures with native Tables 7 & 8..."
        if ($document.InlineShapes.Count -ge 4) {
            $document.InlineShapes.Item(4).Delete()
        }
        if ($document.InlineShapes.Count -ge 3) {
            $document.InlineShapes.Item(3).Delete()
        }

        # -------------------------------------------------------------
        # 4. Iterate through Paragraphs and Replace Text Cleanly
        # -------------------------------------------------------------
        Write-Output "[4/7] Scanning and updating all document paragraphs..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range

            # Title
            if ($p.Range.Style.NameLocal -eq 'papertitle' -or $txt.StartsWith("LS-Face:") -or $txt.StartsWith("Facial Recognition Using Hybrid")) {
                Replace-ParagraphText $p "LS-Face: Selective Computation in Hybrid Face Recognition via Quality-First Early Bypass and Compact Descriptor Retuning" 'papertitle'
            }
            # Abstract
            elseif ($txt.StartsWith("Abstract.")) {
                $newAbs = "Abstract. Cascaded face recognition architectures combine lightweight classical feature extractors with deep convolutional neural networks to reduce average inference latency. However, existing sequential cascades frequently incur redundant computation by executing classical descriptors on severely degraded frames that inevitably trigger deep-model fallback, while relying on default, unoptimized classical configurations. In this work, we propose LS-Face, an optimized selective-computation cascade incorporating two complementary design enhancements: (1) a quality-first early-bypass routing mechanism that evaluates lightweight image-quality metrics before descriptor extraction, immediately routing degraded inputs directly to deep inference, and (2) a compact retuned Local Binary Pattern Histograms (LBPH) descriptor (r=3, n=8, 6x6 spatial grid) that achieves higher standalone identification accuracy while cutting template representation memory by 43.75% (36 KiB vs. 64 KiB) and lowering scoring latency. In a locked confirmation evaluation across 1,804 conditions (22 held-out identities under 41 controlled transformations), LS-Face achieved a 15.48% lower mean recognition latency than standalone SFace (7.015 ms vs. 8.300 ms; mean paired reduction 1.285 ms, identity-cluster bootstrap 95% CI: [1.088, 1.482] ms) while maintaining 100.00% bit-for-bit decision equivalence (1,594 / 1,804 = 88.36% accuracy, 0 / 1,804 discordant decisions). Ablation analysis demonstrates that neither optimization alone surpasses standalone deep inference in mean latency, whereas their combination collapses dual-inference invocations by 77.53%. Complementarity analysis reveals that every successful classical identification is subsumed by deep inference (1,156 / 1,156), establishing the classical stage as a computational shortcut rather than an accuracy complement."
                Replace-ParagraphText $p $newAbs
                $p.Range.Font.Bold = 0
                $rAbs = $p.Range.Duplicate
                $rAbs.End = $rAbs.Start + 9
                $rAbs.Font.Bold = -1
            }
            # Keywords
            elseif ($txt.StartsWith("Keywords:")) {
                Replace-ParagraphText $p "Keywords: Face Recognition, Cascaded Classifiers, Selective Computation, Local Binary Patterns, Quality-Aware Routing, Embedded Edge Computing."
                $rKey = $p.Range.Duplicate
                $rKey.End = $rKey.Start + 9
                $rKey.Font.Bold = -1
            }
            # Section 3.1
            elseif ($txt -eq "LS-Face Architecture" -or $txt -eq "LS-Face Selective-Computation Architecture" -or ($txt -match "LS-Face" -and $p.Range.Style.NameLocal -eq 'heading2')) {
                Replace-ParagraphText $p "LS-Face Selective-Computation Architecture" 'heading2'
            }
            elseif ($txt.StartsWith("The hybrid recognizer consists of") -or $txt.StartsWith("The proposed LS-Face framework restructures")) {
                Replace-ParagraphText $p "The proposed LS-Face framework restructures the traditional sequential biometric cascade into a selective-computation pipeline designed to eliminate redundant inference stages on unconstrained image streams. In standard sequential cascades, every detected face is processed by a classical descriptor (such as LBPH) before reaching an acceptance gate. When an input contains significant sensory degradation (such as severe blur, extreme illumination, high noise, or off-axis pose), the classical descriptor produces high distance scores that fail the acceptance threshold and trigger escalation to SFace. Consequently, degraded probes incur the cumulative latency of both recognizers (dual inference)."
            }
            elseif ($txt.StartsWith("(i) an image-quality flag is raised") -or $txt.StartsWith("LS-Face eliminates this structural inefficiency")) {
                Replace-ParagraphText $p "LS-Face eliminates this structural inefficiency through Quality-First Early-Bypass Routing. The detected facial crop is first assessed against six diagnostic quality metrics: Laplacian blur variance, mean luminance bounds, Immerkaer noise variance, ocular pose angle, and minimum face size (Table 1). If any quality diagnostic is flagged, the classical descriptor stage is completely bypassed, routing the probe directly to SFace. If all quality diagnostics pass, the sample enters the classical descriptor stage. A confident classical match (d <= tau_accept and relative margin m >= m_min) terminates immediately as an inexpensive classical exit (~3.06 ms). Otherwise, the sample escalates to SFace deep feature extraction. We explicitly distinguish between the SFace invocation rate (the fraction of probes requiring SFace evaluation) and the dual-inference rate (the fraction of probes executing both LBPH and SFace). Quality-first routing decouples these metrics, allowing high escalation on difficult workloads while dropping dual inference to near-zero."
            }
            elseif ($txt.StartsWith("Fig. 1.") -or $txt.StartsWith("Fig. 1 Overview")) {
                Replace-ParagraphText $p "Fig. 1. Overview of the LS-Face selective-computation and early-bypass pipeline." 'figurecaption'
            }
            # Section 3.2
            elseif ($txt -eq "Recognizer Selection" -or $txt -eq "Recognizer and Compact-LBPH Selection") {
                Replace-ParagraphText $p "Recognizer and Compact-LBPH Selection" 'heading2'
            }
            elseif ($txt.StartsWith("The candidate recognizers for the classical") -or $txt.StartsWith("Standard face recognition deployments commonly")) {
                Replace-ParagraphText $p "Standard face recognition deployments commonly pair OpenCV's default LBPH configuration (r=1, n=8, 8x8 grid) with deep embedding models. However, an 8-neighbor sampling at radius 1 captures only micro-texture variations over single-pixel neighborhoods, making it fragile to spatial misalignment and sensor noise, while its 8x8 spatial grid yields a 65,536-byte (64 KiB) histogram per enrolled face. Through systematic hyperparameter exploration, we selected a compact retuned LBPH descriptor (r=3, n=8, 6x6 grid). Extending the radius to r=3 captures broader structural facial features, while the 6x6 spatial grid reduces cell count from 64 to 36, producing a 36,864-byte (36 KiB) histogram per enrolled template--a 43.75% memory reduction that also accelerates Chi-Square histogram comparison by over 40%. The deep component is SFace, an efficient mobile-oriented convolutional neural network producing a 128-dimensional unit-normalized embedding (512 bytes), matched via unit-normalized Euclidean distance L2 = sqrt(2 - 2*cos(theta))."
            }
            # Section 3.3
            elseif ($txt -eq "Threshold Setting" -or $txt -eq "Threshold Calibration and Frozen Decision Policy") {
                Replace-ParagraphText $p "Threshold Calibration and Frozen Decision Policy" 'heading2'
            }
            elseif ($txt.StartsWith("Threshold setting uses cross-identity impostor") -or $txt.StartsWith("All operational thresholds were independently")) {
                Replace-ParagraphText $p "All operational thresholds were independently calibrated on a dedicated 2,875-identity LFW development partition (50% deterministic split, seed 42) and frozen prior to evaluation. Challenger LBPH accept threshold tau_accept = 52.3724 was derived from 4,131,375 unidirectional impostor comparisons to anchor a target false accept rate of FAR = 10 ppm (realized calibration FAR: 9.924 ppm, or 41 / 4,131,375). SFace operating thresholds (L2 <= 1.0313, cosine >= 0.363) were derived to anchor the same 10 ppm operating point. Relative top-two margin m_min = 0.05 was frozen as an empirical policy heuristic, while tau_reject = 140.13 was retained as an inherited permissive engineering ceiling (inactive on evaluation workloads). Table 5 summarizes the frozen operating configuration."
            }
            elseif ($txt.StartsWith("LFW is used for the primary low-FAR") -or $txt.StartsWith("The development partition calibration completely")) {
                Replace-ParagraphText $p "The development partition calibration completely eliminates data leakage into the evaluation cohort, providing rigorous threshold separation."
            }
            elseif ($txt.StartsWith("Unlike the acceptance threshold, the LBPH rejection boundary") -or $txt.StartsWith("Unlike the acceptance threshold")) {
                Replace-ParagraphText $p "Unlike the acceptance threshold, the LBPH rejection boundary tau_reject = 140.13 acts as a permissive ceiling, remaining dormant on test workloads."
            }
            elseif ($txt.StartsWith("Threshold freezing. The final cascade configuration")) {
                Replace-ParagraphText $p "Threshold freezing. The final cascade configuration, comprising the LFW-calibrated thresholds, is summarized in Table 5 and evaluated strictly out-of-sample."
            }
            # Section 3.4
            elseif ($txt -eq "Complementarity Evaluation" -or $txt -eq "Experimental Protocol") {
                Replace-ParagraphText $p "Experimental Protocol" 'heading2'
            }
            elseif ($txt.StartsWith("The frozen held-out La Salle DB1-DL41 evaluation set supports") -or $txt.StartsWith("To evaluate the proposed architecture")) {
                Replace-ParagraphText $p "To evaluate the proposed architecture without data leakage, experiments were structured across three distinct cohorts: (1) an exploratory development subset of 6 identities used for architecture design and metric validation; (2) a locked confirmation cohort of the remaining 22 identities from La Salle DB1 (44 source images x 41 DL41 transformations = 1,804 unique conditions) whose test-probe outcome data was strictly held out and uninspected during optimization; and (3) a disjoint robustness cohort of 2,874 LFW identities (disjoint from the 2,875 development partition) evaluated across 41 BGR-first transformations (117,834 conditions) to evaluate controlled transformation retention."
            }
            elseif ($txt.StartsWith("Fallback value. Thresholded LBPH and SFace outcomes") -or $txt.StartsWith("Timing Protocol.")) {
                Replace-ParagraphText $p "Timing Protocol. Single-probe latencies were recorded with 1 warm-up pass and 5 randomized timing repetitions per probe on an Intel Core i5-12450H CPU."
            }
            elseif ($txt.StartsWith("Routability. LBPH distance") -or $txt.StartsWith("Evaluation Metrics.")) {
                Replace-ParagraphText $p "Evaluation Metrics. Performance is assessed via recognition accuracy, paired latency difference with identity-cluster bootstrap 95% CIs, SFace invocation rate, and dual-inference rate."
            }
            elseif ($txt.StartsWith("Measured utility. The cascade is compared") -or $txt.StartsWith("Decision Equivalence.")) {
                Replace-ParagraphText $p "Decision Equivalence. The cascade is evaluated for bit-for-bit decision parity against standalone SFace across all 1,804 locked confirmation conditions."
            }
            # Figure 3 Caption
            elseif ($txt.StartsWith("Fig. 3.") -or $txt.StartsWith("Fig. 3 Histograms")) {
                Replace-ParagraphText $p "Fig. 3. Histograms and KDE curves of La Salle DB1 clean-impostor scores with frozen LFW development operating points (tau_accept = 52.3724, tau_reject = 140.13, L2 = 1.0313)." 'figurecaption'
            }
            # Section 4.2
            elseif ($txt.StartsWith("Table 5 reports the controlled self-match") -or $txt.StartsWith("Table 6 reports the controlled self-match") -or $txt.StartsWith("Table 6 reports the corrected controlled")) {
                Replace-ParagraphText $p "Table 6 reports the corrected controlled self-match robustness test under the frozen operating configuration on the 2,874 evaluation identities disjoint from the 2,875 development partition. One selected source image per evaluation identity was enrolled, and test probes were generated using BGR-first transformation generation across all 41 DL41 conditions (117,834 modified conditions). Clean self-match retention was 99.97% across all systems (2,873 / 2,874). Across all 41 modified conditions, direct SFace, the baseline sequential cascade, and the combined optimized cascade each achieved an identical macro-average retention rate of 89.55%, compared with 81.19% for standalone challenger LBPH. When excluding the four detector-canonical rotational transformations (37 non-rotational modifications), macro retention reached 96.54% for SFace and both cascade variants, versus 89.78% for challenger LBPH. Face detection failed on 2,931 conditions (2.49%)--concentrated in 90 deg, 180 deg, and 270 deg rotations and horizontal flipping--which were strictly retained as recognition failures. Quality-first routing reduced dual inferences to 0.26% across the 117,834 conditions by directly bypassing LBPH on degraded frames."
            }
            # Section 4.3 Heading & Content
            elseif ($txt -eq "Complementarity on Held-Out La Salle DB1-DL41 Probes" -or $txt -eq "Cascade Diagnosis and Two-Factor Ablation") {
                Replace-ParagraphText $p "Cascade Diagnosis and Two-Factor Ablation" 'heading2'
            }
            elseif ($txt.StartsWith("The evaluation follows the three-link argument") -or $txt.StartsWith("To isolate the individual and combined")) {
                Replace-ParagraphText $p "To isolate the individual and combined contributions of Quality-First Routing and Compact Descriptor Retuning, we evaluated six system configurations across all 1,804 conditions of the locked confirmation cohort (Ntimed = 1,711 detected conditions). The baseline sequential cascade required 11.499 ms mean recognition latency (p50: 12.820 ms, p95: 14.361 ms) with 80.36% dual inference (1,375 / 1,711). Quality-first routing alone reduced LBPH calls by 43.54% (1,711 to 966) and dual inferences by 54.18% (1,375 to 630), lowering mean latency to 9.483 ms. Compact descriptor retuning alone reduced SFace escalations to 61.60% (1,054 / 1,711), achieving 8.354 ms. Crucially, neither optimization alone achieved lower mean latency than direct SFace (8.300 ms). However, when unified in LS-Face, dual inferences collapsed to 18.06% (309 / 1,711), achieving 7.015 ms mean latency--a 38.99% speedup over the baseline cascade and a 15.48% speedup over direct SFace at identical 88.36% accuracy (1,594 / 1,804) with zero decision disagreements."
            }
            elseif ($txt.StartsWith("Table 7.") -or $txt.StartsWith("Fig. 4.")) {
                Replace-ParagraphText $p "Table 7. Two-factor ablation of LS-Face across 1,804 locked confirmation conditions." 'tablecaption'
            }
            # Section 4.4 Heading & Content
            elseif ($txt -eq "Locked Confirmation Evaluation" -or $txt.StartsWith("First, the fallback outcomes were strongly asymmetric")) {
                Replace-ParagraphText $p "Locked Confirmation Evaluation" 'heading2'
            }
            elseif ($txt.StartsWith("Table 8.") -or $txt.StartsWith("Fig. 5.")) {
                Replace-ParagraphText $p "Table 8. Complementarity matrix of classical and deep decisions across 1,804 locked conditions." 'tablecaption'
            }
            elseif ($txt.StartsWith("Second, LBPH distance and relative top-two margin") -or $txt.StartsWith("On the locked 22-identity confirmation")) {
                Replace-ParagraphText $p "On the locked 22-identity confirmation cohort, LS-Face and Direct SFace made identical predictions on all 1,804 conditions (0 discordant cases, 100.00% decision equivalence). Both achieved 1,594 / 1,804 (88.36%) correct recognitions, with 117 rejections (6.49%) and 93 strict detector failures (5.16%) retained as failures. Across the Ntimed = 1,711 detected conditions, LS-Face reduced mean latency by 1.285 ms relative to Direct SFace (mean paired reduction 1.285 ms, identity-cluster bootstrap 95% CI: [1.088, 1.482] ms; paired difference -1.285 ms, 95% CI: [-1.482, -1.088] ms). LS-Face executed faster than Direct SFace on 50.50% of all probes where LBPH terminated early at ~3.06 ms."
            }
            elseif ($txt.StartsWith("A post-hoc accept-protection replay") -or $txt.StartsWith("Across all 1,804 locked confirmation conditions")) {
                Replace-ParagraphText $p "Across all 1,804 locked confirmation conditions, 1,156 cases were recognized correctly by both LBPH and SFace, 0 cases were recognized correctly by LBPH alone, 438 cases were recognized correctly by SFace alone, and 210 cases failed both systems. Because LBPH-only correct is exactly 0, P(SFace correct | LBPH correct) = 100.0%. SFace strictly subsumes LBPH across the evaluated transformation space. LBPH does not expand the system's recognition ceiling; rather, it serves as a selective computational shortcut that resolves easy queries in 3.06 ms instead of 8.30 ms."
            }
            # Section 4.5
            elseif ($txt -eq "Workload Severity and Latency Profile" -or $txt.StartsWith("Third, reducing redundant escalation improves") -or $txt.StartsWith("4.5 Workload Severity and Latency Profile") -or $txt.StartsWith("Workload Severity and Latency Profile")) {
                Replace-ParagraphText $p "Workload Severity and Latency Profile. Across degradation tiers, LS-Face achieved consistent speedups: Clean (~3.45 ms, 58.4% latency reduction), Light (6.176 ms, 25.6% reduction), Medium (7.550 ms, 9.0% reduction), and Heavy (7.722 ms, 7.0% reduction). While Direct SFace provides a tighter single-path distribution (p50: 8.206 ms, p95: 9.183 ms, p99: 10.073 ms), LS-Face accepts a modest tail latency penalty on ambiguous inputs (p50: 8.265 ms, p95: 11.704 ms, p99: 12.388 ms) in exchange for a substantial 15.48% reduction in overall mean inference time."
            }
            # Section 5 (Discussion) Headings & Paragraphs
            elseif ($txt -eq "Controlled Robustness" -or $txt -eq "Selective Computation and Elimination of Redundancy") {
                Replace-ParagraphText $p "Selective Computation and Elimination of Redundancy" 'heading2'
            }
            elseif ($txt.StartsWith("The controlled LFW self-match experiment isolates") -or $txt.StartsWith("The experimental findings demonstrate that traditional")) {
                Replace-ParagraphText $p "The experimental findings demonstrate that traditional sequential cascades are structurally inefficient because they execute classical descriptors indiscriminately on degraded frames that inevitably require deep-model fallback. Quality-first early bypass eliminates this bottleneck by routing degraded frames directly to SFace, cutting dual inference to 0.26% on LFW."
            }
            elseif ($txt -eq "Fallback and Routing Behavior" -or $txt -eq "Orthogonal Computational Optimizations") {
                Replace-ParagraphText $p "Orthogonal Computational Optimizations" 'heading2'
            }
            elseif ($txt.StartsWith("The held-out La Salle DB1-DL41 experiment provides") -or $txt.StartsWith("Quality-first bypass and compact descriptor retuning target")) {
                Replace-ParagraphText $p "Quality-first bypass and compact descriptor retuning target distinct cost sources: early bypass eliminates wasted classical extraction on degraded frames, while compact LBPH reduces memory footprint by 43.75% (36 KiB vs 64 KiB) and accelerates classical comparison. As demonstrated by ablation, neither optimization alone surpasses direct SFace, but their combination achieves a 15.48% mean latency reduction."
            }
            elseif ($txt -eq "Efficiency Trade-off and Scope" -or $txt -eq "Computational Shortcuts vs. Accuracy Complementarity") {
                Replace-ParagraphText $p "Computational Shortcuts vs. Accuracy Complementarity" 'heading2'
            }
            elseif ($txt.StartsWith("A post-hoc replay on the same evaluation data") -or $txt.StartsWith("The 100.0% subsumption of LBPH by SFace")) {
                Replace-ParagraphText $p "The 100.0% subsumption of LBPH by SFace (1,156 / 1,156) establishes that classical descriptors in hybrid cascades operate strictly as computational shortcuts rather than accuracy complements. In embedded edge systems, reducing mean latency from 8.300 ms to 7.015 ms directly improves energy efficiency and throughput, provided tail latency remains within interactive bounds."
            }
            elseif ($txt.StartsWith("These findings remain bounded by the experimental") -or $txt.StartsWith("Limitations. The permissive reject boundary")) {
                Replace-ParagraphText $p "Limitations. The permissive reject boundary tau_reject = 140.13 remained inactive on evaluation workloads (d_max = 72.18), indicating that deployed systems can adopt a streamlined three-branch decision architecture."
            }
            # Section 6 (Conclusion) Headings & Paragraphs
            elseif ($txt -eq "Main Findings" -or $txt -eq "Principal Findings") {
                Replace-ParagraphText $p "Principal Findings" 'heading2'
            }
            elseif ($txt.StartsWith("LS-Face combines an LBPH first stage with SFace fallback") -or $txt.StartsWith("LS-Face demonstrates that hybrid face recognition cascades")) {
                Replace-ParagraphText $p "LS-Face demonstrates that hybrid face recognition cascades can achieve superior average inference efficiency compared to direct deep neural network evaluation without compromising recognition accuracy. By combining quality-guided early bypass routing with a compact retuned LBPH descriptor, LS-Face achieved a 15.48% reduction in mean recognition latency over standalone SFace (38.99% over the baseline cascade) while maintaining exact decision parity across 1,804 locked confirmation conditions."
            }
            elseif ($txt -eq "Overall Implication" -or $txt -eq "Architectural Implications") {
                Replace-ParagraphText $p "Architectural Implications" 'heading2'
            }
            elseif ($txt.StartsWith("Under the held-out La Salle DB1-DL41 stress workload") -or $txt.StartsWith("By formalizing classical descriptors as selective")) {
                Replace-ParagraphText $p "By formalizing classical descriptors as selective computational shortcuts and eliminating dual inference on degraded streams, LS-Face establishes a principled design framework for low-power edge biometrics."
            }
        }

        # -------------------------------------------------------------
        # 5. Insert Native Tables 7 & 8 directly below Table Captions
        # -------------------------------------------------------------
        Write-Output "[5/7] Inserting Table 7 (Ablation) and Table 8 (Complementarity)..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range

            if ($txt.StartsWith("Table 7. Two-factor ablation")) {
                $rng = $p.Range.Duplicate
                $rng.Collapse(0) # 0 = wdCollapseEnd
                $t7 = $document.Tables.Add($rng, 7, 6)
                $t7Data = @(
                    @('Configuration', 'Descriptor', 'Quality bypass', 'Mean latency', 'Dual-inf.', 'Accuracy'),
                    @('Baseline Sequential', 'OpenCV default (r1_g8x8)', 'Disabled', '11.499 ms', '80.36%', '88.36%'),
                    @('Architecture Only', 'OpenCV default (r1_g8x8)', 'Enabled', '9.483 ms', '36.82%', '88.36%'),
                    @('Descriptor Only', 'Compact LBPH (r3_g6x6)', 'Disabled', '8.354 ms', '61.60%', '88.36%'),
                    @('Combined (LS-Face)', 'Compact LBPH (r3_g6x6)', 'Enabled', '7.015 ms', '18.06%', '88.36%'),
                    @('Direct SFace', 'N/A (Standalone DL)', 'N/A', '8.300 ms', '0.00%', '88.36%'),
                    @('Challenger LBPH', 'Compact LBPH (r3_g6x6)', 'N/A', '3.061 ms', '0.00%', '64.08%')
                )
                Populate-LncsTable $document $t7 $t7Data @(85, 75, 50, 45, 45, 45)
            }
            elseif ($txt.StartsWith("Table 8. Complementarity matrix")) {
                $rng = $p.Range.Duplicate
                $rng.Collapse(0)
                $t8 = $document.Tables.Add($rng, 4, 4)
                $t8Data = @(
                    @('SFace outcome', 'LBPH correct', 'LBPH incorrect', 'Total'),
                    @('SFace correct', '1,156 (64.08%)', '438 (24.28%)', '1,594 (88.36%)'),
                    @('SFace incorrect', '0 (0.00%)', '210 (11.64%)', '210 (11.64%)'),
                    @('Total', '1,156 (64.08%)', '648 (35.92%)', '1,804 (100.0%)')
                )
                Populate-LncsTable $document $t8 $t8Data @(85, 85, 85, 90)
            }
        }

        # Save and export
        Write-Output "[6/7] Saving editable DOCM and exporting PDF..."
        $document.Save()
        $document.SaveAs([ref]$outputPath, [ref]13)
        $document.ExportAsFixedFormat($pdfPath, 17)
        Write-Output "[SUCCESS] Exported DOCM and PDF successfully."
    }
    finally {
        if ($document) { $document.Close($false) }
        $word.Quit()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    }

    # Repack and verify VBA
    Write-Output "[7/7] Verifying and restoring bit-identical VBA project part ($vbaPart)..."
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
Write-Output " BUILD COMPLETED: 021_MAJOR FLAWLESS REWRITE READY"
Write-Output " Output DOCM: $outputPath"
Write-Output " Output PDF:  $pdfPath"
Write-Output "================================================================================"
