[CmdletBinding()]
param(
    [string]$Baseline = 'docs\manuscript\versions\pairwise\018p_polish_run.docm',
    [string]$Output = 'docs\manuscript\versions\pairwise\019p_lsface_reproducibility-pass.docm',
    [string]$PdfOutput = 'docs\manuscript\versions\pairwise\019p_lsface_reproducibility-pass.pdf'
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

function Replace-ZipFileEntry {
    param(
        [Parameter(Mandatory = $true)][string]$ZipPath,
        [Parameter(Mandatory = $true)][string]$EntryName,
        [Parameter(Mandatory = $true)][string]$SourceFilePath
    )
    $archive = [System.IO.Compression.ZipFile]::Open($ZipPath, [System.IO.Compression.ZipArchiveMode]::Update)
    try {
        $entry = $archive.GetEntry($EntryName)
        if ($null -ne $entry) { $entry.Delete() }
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $SourceFilePath, $EntryName, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
    }
    finally {
        $archive.Dispose()
    }
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
        [Parameter(Mandatory = $true)][string]$Text,
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
            $alignment = if ($column -eq 4) { 1 } else { 0 }
            Set-CellText $Document $Table.Cell($row, $column) $Values[$row - 1][$column - 1] ($row -eq 1) $alignment
        }
    }
}

$baselinePath = Resolve-WorkspacePath $Baseline
$outputPath = Resolve-WorkspacePath $Output
$pdfPath = Resolve-WorkspacePath $PdfOutput

$vbaPart = 'word/vbaProject.bin'
$baselineFileHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $baselinePath).Hash
$baselineVbaHash = Get-ZipPartHash $baselinePath $vbaPart
$stagePath = Join-Path ([System.IO.Path]::GetTempPath()) ("lsface_019p_{0}.docm" -f [guid]::NewGuid().ToString('N'))

try {
    Copy-Item -LiteralPath $baselinePath -Destination $stagePath

    # 1. Update embedded Figure 5 assets in package
    Write-Output "Updating Figure 5 SVG and PNG in document package..."
    $fig5Svg = Resolve-WorkspacePath "docs\manuscript\figures\fig_gate_competence_stacked_bars.svg"
    $fig5Png = Resolve-WorkspacePath "docs\manuscript\figures\fig_gate_competence_stacked_bars.png"
    if ((Test-Path -LiteralPath $fig5Svg) -and (Test-Path -LiteralPath $fig5Png)) {
        Replace-ZipFileEntry -ZipPath $stagePath -EntryName "word/media/image10.svg" -SourceFilePath $fig5Svg
        Replace-ZipFileEntry -ZipPath $stagePath -EntryName "word/media/image9.png" -SourceFilePath $fig5Png
    }

    Write-Output "Opening Word Application COM..."
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $null

    try {
        $document = $word.Documents.Open($stagePath, $false, $false)

        # -------------------------------------------------------------
        # Abstract & Keywords Updates (Self-match sentence untouched)
        # -------------------------------------------------------------
        Write-Output "Applying Abstract & Keywords updates..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range

            if ($txt.StartsWith("Abstract. Face recognition for access-control systems")) {
                $newAbstract = "Abstract. Face recognition for access-control systems must remain reliable under changing image conditions without using more computation than necessary. This study presents LS-Face, a two-stage recognizer that uses LBPH first and sends uncertain or poor-quality cases to SFace. The experiments were divided into four parts: recognizer selection, threshold setting, controlled robustness testing, and held-out cascade testing. LBPH and SFace were chosen from three classical and three deep-learning candidates using La Salle DB1. The acceptance thresholds were then set using cross-identity comparisons on LFW. For LBPH, 16,522,626 impostor comparisons produced a calibration false-accept rate of 9.986 ppm at the selected threshold. In the controlled self-match robustness test, augmented versions of the enrolled images were matched back to their source identities. Across 41 transformations, LBPH, SFace, and the cascade retained an accuracy of 86.66%, 98.22%, and 94.69%, respectively, with 46.70% of cases escalated to SFace. In a separate held-out La Salle DB1-DL41 test using different enrollment and probe photographs, SFace recovered 81.56% of thresholded LBPH failures. LBPH distance and the separation between its top two matches were also strong indicators of LBPH failure, with AUCs of 0.950 and 0.953. A post-hoc replay on the same evaluation data reduced escalation from 71.52% to 59.23% while preserving the same 87.24% thresholded correct-identity acceptance. However, the cascade still required 10.81 ms on average compared with 8.33 ms for direct SFace. These results show that SFace provides an effective fallback for difficult LBPH cases and that LBPH scores can help decide when fallback is needed, but the current cascade does not provide a runtime advantage over direct SFace under the tested stress conditions. Open-set identification and end-to-end target-device performance were not evaluated."
                Replace-ParagraphText $p $newAbstract
                $p.Range.Font.Bold = 0
                $rAbsLead = $p.Range.Duplicate
                $rAbsLead.End = $rAbsLead.Start + 9
                $rAbsLead.Font.Bold = -1
            }
            elseif ($txt.StartsWith("Keywords: Home Security, Facial Recognition")) {
                $newKeywords = "Keywords: Face Recognition, Home Security, Hybrid Recognition, Selective Computation, Independence Testing"
                Replace-ParagraphText $p $newKeywords
                $p.Range.Font.Bold = 0
                $rKwLead = $p.Range.Duplicate
                $rKwLead.End = $rKwLead.Start + 9
                $rKwLead.Font.Bold = -1
            }
            elseif ($txt.StartsWith("Based on these concepts, this paper presents LS-Face")) {
                Replace-ParagraphText $p ($txt -replace "on LSDB-DL41", "on La Salle DB1-DL41")
            }
        }

        # -------------------------------------------------------------
        # Section 3.1: Detection & OpenCV [10] Citation, Table 1, Provenance
        # -------------------------------------------------------------
        Write-Output "Applying Section 3.1 modifications..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range
            if ($txt.StartsWith("LS-Face processes each input image through the two-stage recognition pipeline shown in Fig. 1. YuNet first detects the face")) {
                $newDetText = "LS-Face processes each input image through the two-stage recognition pipeline shown in Fig. 1. The YuNet detector [7] implemented in OpenCV [10] first detects the face and provides detection confidence and facial landmarks. If no valid face is detected, recognition stops and the sample is treated as a detection failure."
                Replace-ParagraphText $p $newDetText
                Write-Output "Cited YuNet [7] and OpenCV [10] in Section 3.1"
                break
            }
        }

        $pMemorization = $null
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range
            if ($txt.StartsWith("The margin is expressed relative to d") -or $txt.StartsWith("The quality thresholds in Table 1 were defined")) {
                $pMemorization = $p
                break
            }
        }
        if ($null -eq $pMemorization) { throw "Could not find memorization paragraph in Section 3.1" }

        $newP31Text = "The quality thresholds in Table 1 were defined from the empirical distribution edges of 279 clean facial crops detected across a 280-image reference collection (10 clean frontal and pose images per identity across 28 identities, with one detector miss excluded), rather than optimized on the 41-transformation evaluation set or fitted to a measured LBPH-to-SFace performance crossover. The relative top-two margin expresses the separation between the two highest-ranked candidates relative to the best-match distance; m_min = 0.05 was chosen as a fixed engineering policy value rather than statistically optimized. The quality condition is evaluated independently of the LBPH score, allowing quality-flagged inputs to be escalated even when the first-stage distance appears confident."
        Replace-ParagraphText $pMemorization $newP31Text

        # Insert Table 1 caption and Table 1 right before this paragraph
        $rInsert = $pMemorization.Range.Duplicate
        $rInsert.Collapse(1)

        $captionText = "Table 1. Deployed quality-check and candidate-separation parameters for Stage 1 escalation.`n"
        $rInsert.Text = $captionText
        $rInsert.Style = $document.Styles.Item('tablecaption')
        $rInsert.Collapse(0)

        $table1 = $document.Tables.Add($rInsert, 7, 4)
        $table1Data = @(
            @('Signal', 'Measurement / condition', 'Selection rule', 'Deployed value'),
            @('Blur', 'Variance of Laplacian below threshold', '5th percentile of clean values', '587.83'),
            @('Illumination', 'Mean grayscale outside lower/upper bounds', '2nd and 98th percentiles of clean values', '[52.88, 137.71]'),
            @('Noise', 'Immerkaer noise estimate above threshold', '95th percentile of clean values', '8.206'),
            @('Pose', 'Maximum of eye-roll and nose-yaw proxies above threshold', '95th percentile of clean values', '63.74'),
            @('Face size', 'Detected box side below minimum', 'floor(0.9 × p₅) of clean box sizes', '61 px'),
            @('Relative top-two margin', '(d₂ − d₁) / d₁ < m_min', 'Fixed engineering policy value', 'm_min = 0.05')
        )
        Populate-LncsTable $document $table1 $table1Data @(72, 130, 118, 58)

        # Update final sentence of Section 3.1 (P066)
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range
            if ($txt.StartsWith("The recognition thresholds and escalation parameters are fixed before evaluation") -or $txt.StartsWith("The deployed thresholds and escalation parameters were fixed")) {
                $newSec31End = "The deployed thresholds and escalation parameters were fixed before the held-out La Salle DB1-DL41 cascade evaluation and were not adjusted using individual test outcomes."
                Replace-ParagraphText $p $newSec31End
                Write-Output "Updated final sentence of Section 3.1"
                break
            }
        }

        # -------------------------------------------------------------
        # Section 3.2: 41 image transformations
        # -------------------------------------------------------------
        Write-Output "Applying Section 3.2 consistency patch..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range
            if ($txt -match "robustness under the 41 image modifications") {
                Replace-ParagraphText $p ($txt -replace "robustness under the 41 image modifications", "robustness under the 41 image transformations")
                break
            }
        }

        # -------------------------------------------------------------
        # Section 3.3: LFW Calibration, LBPH Reject Boundary, Threshold Freezing
        # -------------------------------------------------------------
        Write-Output "Applying Section 3.3 modifications..."
        $pLfw1 = $null
        $pFreezing = $null
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range
            if ($txt.StartsWith("LFW 1 is used for the primary low-FAR independence test") -or $txt.StartsWith("LFW is used for the primary low-FAR independence test")) {
                $pLfw1 = $p
            }
            elseif ($txt.StartsWith("Threshold freezing.")) {
                $pFreezing = $p
            }
        }
        if ($null -eq $pLfw1 -or $null -eq $pFreezing) { throw "Could not find Section 3.3 paragraphs" }

        $newLfw1Text = "LFW is used for the primary low-FAR independence test because its 5,749 identities yield 16,522,626 unique cross-identity comparisons, enabling resolution on the order of 10 ppm (rank 165 yields 9.986 ppm). Applying the rank-165 operating rule separately to the LBPH and SFace impostor-score distributions yielded their respective acceptance boundaries: τ_accept = 67.0333 for LBPH and L₂ ≤ 1.0313 for SFace. The cosine threshold of 0.363 was retained from the existing SFace decision policy rather than independently fitted at this operating point; because normalized embeddings satisfy L₂ = √(2 − 2 cos θ), L₂ ≤ 1.0313 already implies cos θ ≥ 0.4682, rendering the 0.363 cosine constraint non-binding at the deployed L2 boundary."
        Replace-ParagraphText $pLfw1 $newLfw1Text
        $pLfw1.Range.Font.Bold = 0

        $rReject = $pFreezing.Range.Duplicate
        $rReject.Collapse(1)
        $rejectText = "Unlike the acceptance threshold, the LBPH rejection boundary τ_reject = 140.13 was not derived from rank-based low-FAR impostor calibration. Instead, a trade-off sweep across candidate values from 70 to 170 was conducted using 70,560 genuine and 70,560 designated-impostor rows from the image-disjoint LFW verification run (where the designated-impostor count serves as a 1:1 proxy rather than a 1:N FPIR measurement). Because no clear separation-favorable knee emerged on unconstrained LFW, 140.13 was selected as a deliberately permissive engineering boundary corresponding to the 99th percentile of genuine LBPH distances under heavy image degradations, limiting irreversible genuine rejections before SFace fallback.`n"
        $rReject.Text = $rejectText
        $rReject.Font.Bold = 0

        $newFreezingText = "Threshold freezing. The final cascade configuration—comprising the LFW-calibrated LBPH acceptance threshold, the permissive LBPH rejection boundary, the fixed relative top-two margin rule, the clean-distribution quality thresholds, and the deployed SFace acceptance policy—was frozen before conducting the held-out La Salle DB1-DL41 cascade evaluation. The evaluation harness records the configuration SHA-256, and no parameters were retuned using the held-out evaluation outcomes. The final numerical operating points are summarized in Section 4.2."
        Replace-ParagraphText $pFreezing $newFreezingText
        $pFreezing.Range.Font.Bold = 0
        $rFrzLead = $pFreezing.Range.Duplicate
        $rFrzLead.End = $rFrzLead.Start + 19
        $rFrzLead.Font.Bold = -1

        # -------------------------------------------------------------
        # Section 3.4: Merged Opening Paragraph (Cohort -> Evaluation Set)
        # -------------------------------------------------------------
        Write-Output "Applying Section 3.4 merged opening..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range
            if ($txt.StartsWith("The same frozen held-out") -or $txt.StartsWith("The frozen held-out La Salle DB1-DL41 evaluation set")) {
                $newSec34Opening = "The frozen held-out La Salle DB1-DL41 evaluation set supports three parallel analyses of fallback value, routability, and selective utility. The evaluation set contains 56 image-disjoint test images, two for each of 28 identities, with 41 deterministic transformations per image, yielding 2,296 correlated test conditions. Thresholds and routing rules were frozen before scoring, and detector failures were retained as failures."
                Replace-ParagraphText $p $newSec34Opening

                $pNext = $document.Paragraphs.Item($i + 1)
                $nextTxt = Get-CleanText $pNext.Range
                if ($nextTxt.StartsWith("Complementarity Evaluation. There are three analyses")) {
                    $pNext.Range.Delete()
                }
                break
            }
        }

        # -------------------------------------------------------------
        # Section 4 & 4.1: Selection Polish & Table 2, 3, 4
        # -------------------------------------------------------------
        Write-Output "Applying Section 4 & 4.1 selection language polish..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range

            if ($txt.StartsWith("The experimental program consists of four evidence legs")) {
                Replace-ParagraphText $p "The experimental program consists of four evidence legs summarized in Table 2. Each leg has a distinct role in the study: recognizer selection, independence testing and operating-point determination, controlled self-match robustness analysis, or held-out cascade evaluation. Results from one leg are not interpreted as measurements of outcomes that its protocol does not directly evaluate."
            }
            elseif ($txt.StartsWith("The LSDB held-out evaluation") -or $txt.StartsWith("The La Salle DB1 held-out evaluation")) {
                Replace-ParagraphText $p "The La Salle DB1 held-out evaluation uses clean enrollment images and image-disjoint probes from the same 28 enrolled identities, but each probe is transformed across 41 deterministic conditions. It evaluates the complementary rescue provided by SFace on LBPH failures, the discriminative capacity of the first-stage routing signals, and the overall accuracy and computational trade-offs of selective escalation."
            }
            elseif ($txt.StartsWith("Classical candidates were fitted on 224 images, calibrated on 56 disjoint images, and evaluated once on 56 untouched")) {
                $newClassicalText = "Classical candidates were fitted on 224 images, calibrated on 56 disjoint images, and evaluated once on 56 untouched La Salle DB1 probes. The calibration set supplied 1,512 cross-identity scores; the rank-15 impostor score yielded a realized FAR of 0.992%. LBPH achieved the highest test TAR (96.43%) and Rank-1 accuracy (100.00%) and was selected as the classical fast path."
                Replace-ParagraphText $p $newClassicalText
            }
            elseif ($txt.StartsWith("The learned candidates were evaluated on the same deterministic 224/56/56")) {
                $newDlText1 = "The learned candidates were evaluated on the same deterministic 224/56/56 La Salle DB1 split. Each model's rank-15 acceptance edge was derived from the 1,512 calibration cross-identity scores, yielding a realized FAR of 0.992%."
                Replace-ParagraphText $p $newDlText1
            }
            elseif ($txt.StartsWith("SFace and FaceNet tied at 100.00% held-out TAR and Rank-1; SFace")) {
                $newDlText2 = "SFace and FaceNet tied at 100.00% held-out TAR and Rank-1; SFace was selected using feature size as the deployment tie-break (512 B versus 2,048 B). ArcFace retained 100.00% Rank-1 but reached 96.43% TAR. Thus, SFace was selected as the learned tier, while LBPH remained the separately selected classical fast path."
                Replace-ParagraphText $p $newDlText2
            }
        }

        # -------------------------------------------------------------
        # Section 4.2: Unambiguous Rank-165 Operating Points Description
        # -------------------------------------------------------------
        Write-Output "Applying Section 4.2 updates..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range

            if ($txt.StartsWith("The LFW DB1 independence test produced the frozen operating points") -or $txt.StartsWith("The LFW independence test produced the frozen operating points")) {
                $new42Prose = "The LFW independence test produced the frozen operating points summarized in Table 5. Applying the rank-165 operating rule separately to each recognizer's 16,522,626-comparison impostor-score distribution yielded an empirical LBPH acceptance boundary of 67.0333 (realized FAR of 9.986 ppm) and an SFace L2 threshold of 1.0313. The SFace cosine condition (cosine ≥ 0.363) is inherited from the existing SFace decision policy and is non-binding at the deployed L2 boundary."
                Replace-ParagraphText $p $new42Prose
            }
            elseif ($txt.StartsWith("Figure 4 places these frozen operating points") -or $txt.StartsWith("Fig. 3 places these frozen operating points")) {
                $newFig3Callout = "Fig. 3 places these frozen operating points against the separately computed La Salle DB1 clean-impostor score distributions. The La Salle DB1 scores are shown only to visualize cross-database transfer and were not used to recalibrate the thresholds."
                Replace-ParagraphText $p $newFig3Callout
            }
        }

        # -------------------------------------------------------------
        # Section 4.4: Complementarity Results Literal Reporting
        # -------------------------------------------------------------
        Write-Output "Applying Section 4.4 literal results reporting..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range

            if ($txt.StartsWith("The evaluation follows the three-link argument described above. It uses 56 image-disjoint")) {
                $new44Intro = "The evaluation follows the three-link argument described above. It uses 56 image-disjoint held-out La Salle DB1 source probes, two for each of 28 enrolled identities, and 41 deterministic transformations per source, yielding 2,296 correlated probe conditions. The LFW-derived thresholds and routing rule were frozen before scoring, and detector failures were handled strictly. Figures 4 and 5 summarize the two main complementarity findings: whether SFace can recover LBPH failures and whether the routing rule can distinguish cases that should be escalated."
                Replace-ParagraphText $p $new44Intro
            }
            elseif ($txt.StartsWith("First, the fallback outcomes were strongly asymmetric.") -or $txt.StartsWith("First, the fallback value is strongly asymmetric.")) {
                $newFallbackText = "First, the fallback outcomes were strongly asymmetric. As shown in Fig. 4, SFace recovered 1,296 of the 1,589 thresholded LBPH failures, corresponding to a recovery rate of 81.56%. The remaining 293 cases (18.44%) were not recovered by either final decision. Conversely, LBPH supplied no thresholded success that SFace lacked. The observed complementarity is therefore one-way: SFace provides substantial rescue for LBPH failures, rather than the two recognizers mutually recovering each other's errors. Because the 41 transformations are repeated conditions derived from the same source images, these counts are interpreted descriptively rather than as 2,296 independent observations."
                Replace-ParagraphText $p $newFallbackText
            }
            elseif ($txt.StartsWith("Second, LBPH distance and relative top-two margin") -or $txt.StartsWith("Second, the routing rule exposes a useful LBPH risk signal")) {
                $newRoutingText = "Second, LBPH distance and relative top-two margin provided strong discrimination of LBPH Rank-1 errors. Of the 1,589 thresholded LBPH failures, 1,353 had the LBPH signals required for routing analysis; the remaining 236 conditions were excluded from signal-based routing metrics. Among the 2,060 probes with available routing signals, LBPH distance and negative relative top-two margin separated 444 threshold-free LBPH Rank-1 errors with AUCs of 0.95019 and 0.95319, respectively. As shown in Fig. 5, the deployed rule escalated all 1,353 thresholded LBPH failures, giving 100.0% failure-routing recall. However, it also escalated 289 of the 707 LBPH-correct cases (40.88%), while the remaining 418 cases (59.12%) were correctly retained at the LBPH stage. Thus, the rule captured all signal-available thresholded LBPH failures but also escalated 40.88% of LBPH-correct cases."
                Replace-ParagraphText $p $newRoutingText
            }
            elseif ($txt.StartsWith("A post-hoc accept-protection replay examined whether this redundant routing")) {
                $newReplayText = "A post-hoc accept-protection replay examined whether this redundant routing could be reduced. The replay preserved the deployed low-margin trigger and all conditions above tau_accept, while treating accept-side quality flags as telemetry rather than escalation triggers. Under this replay, unnecessary escalations among LBPH-correct cases fell from 289 to 7 of 707. Because the same transformed probes motivated and evaluated this candidate policy, however, the result is treated only as a descriptive ablation and not as independent validation of an improved routing rule."
                Replace-ParagraphText $p $newReplayText
            }
            elseif ($txt.StartsWith("Third, reducing redundant escalation improves the deployed route")) {
                $newCostText = "Third, reducing redundant escalation improves the deployed route without establishing a speed advantage over direct SFace. The candidate replay preserved the same 87.24% thresholded correct-identity acceptance while reducing escalation from 71.52% to 59.23% and lowering mean recognition-stage time from 11.96 ms to 10.81 ms. Direct SFace nevertheless achieved the same 87.24% acceptance at 8.33 ms, while LBPH-only reached 30.79% at 5.25 ms. These timings represent single-pass stored recognition-stage measurements and exclude detection and I/O. The result therefore suggests that simplifying the routing logic could reduce redundant escalation, but it does not demonstrate a Pareto or runtime advantage over direct SFace."
                Replace-ParagraphText $p $newCostText
            }
        }

        # -------------------------------------------------------------
        # Section 5.2, 5.3, 6.2, Acknowledgments
        # -------------------------------------------------------------
        Write-Output "Applying Section 5 & 6 terminology updates..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range

            if ($txt.StartsWith("The held-out LSDB-DL41 experiment provides separate image-disjoint evidence.") -or $txt.StartsWith("The held-out La Salle DB1-DL41 experiment provides")) {
                $new52 = "The held-out La Salle DB1-DL41 experiment provides separate image-disjoint evidence. SFace recovered 81.56% of thresholded LBPH failures, while LBPH produced no thresholded success that SFace lacked, showing strongly one-way fallback value. LBPH distance and relative top-two margin also discriminated failure risk well, with AUCs near 0.95. However, useful risk signals did not automatically produce an efficient cascade: among conditions with routing signals, the deployed rule captured all 1,353 thresholded LBPH failures but also escalated 40.88% of LBPH-correct cases."
                Replace-ParagraphText $p $new52
            }
            elseif ($txt.StartsWith("These findings remain bounded by the experimental protocols. The LSDB-DL41 conditions are correlated") -or $txt.StartsWith("These findings remain bounded by the experimental protocols. The La Salle DB1-DL41 conditions")) {
                $new53 = "These findings remain bounded by the experimental protocols. The La Salle DB1-DL41 conditions are correlated transformations of 56 source probes, 236 conditions lacked the signals required for routing-score analysis, and timing excludes detection and external I/O. The study therefore does not claim open-set identification performance or end-to-end target-device efficiency."
                Replace-ParagraphText $p $new53
            }
            elseif ($txt.StartsWith("Under the held-out LSDB-DL41 stress workload, however") -or $txt.StartsWith("Under the held-out La Salle DB1-DL41 stress workload")) {
                $new62 = "Under the held-out La Salle DB1-DL41 stress workload, however, the cascade did not outperform direct SFace in the recognition-performance/runtime trade-off. The study therefore supports SFace fallback and LBPH-based routing as useful mechanisms while defining a clear efficiency limit of the current architecture. Open-set identification and end-to-end target-device evaluation remain outside the present scope."
                Replace-ParagraphText $p $new62
            }
            elseif ($txt.StartsWith("Acknowledgments. The authors gratefully acknowledge")) {
                $newAck = "Acknowledgments. The authors gratefully acknowledge the Department of Computer Science, University of St. La Salle–Bacolod, for its institutional support throughout this research. The authors also thank the 10 additional group members who contributed to the study and the 28 student volunteers whose participation made the construction of the La Salle DB1 dataset possible."
                Replace-ParagraphText $p $newAck
                $p.Range.Font.Bold = 0
                $rAckLead = $p.Range.Duplicate
                $rAckLead.End = $rAckLead.Start + 16
                $rAckLead.Font.Bold = -1
            }
        }

        # -------------------------------------------------------------
        # Table Captions & Figure Captions Standardization
        # -------------------------------------------------------------
        Write-Output "Standardizing table captions and figure captions..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range

            if ($txt -match "^Table 1\. Experiments and their roles in the study\.$" -or $txt -match "^Table 2\. Experiments and their roles in the study\.$") {
                Replace-ParagraphText $p "Table 2. Experiments and their roles in the study." "tablecaption"
            }
            elseif ($txt -match "^Table 2\. Classical candidate selection on LSDB\.$" -or $txt -match "^Table 3\. Classical candidate selection on") {
                Replace-ParagraphText $p "Table 3. Classical candidate selection on La Salle DB1." "tablecaption"
            }
            elseif ($txt -match "^Table 3\. DL candidate selection on LSDB\.$" -or $txt -match "^Table 4\. DL candidate selection on") {
                Replace-ParagraphText $p "Table 4. DL candidate selection on La Salle DB1." "tablecaption"
            }
            elseif ($txt.StartsWith("Complementarity on Held-Out")) {
                Replace-ParagraphText $p "Complementarity on Held-Out La Salle DB1-DL41 Probes" "heading2"
            }
            elseif ($txt -match "^Table 4\. Final frozen operating points\.$" -or $txt -match "^Table 5\. Final frozen operating points\.$") {
                Replace-ParagraphText $p "Table 5. Final frozen operating points." "tablecaption"
            }
            elseif ($txt -match "^Fig\. 3\. Histograms and KDE curves of") {
                $find = $p.Range.Find
                $find.ClearFormatting()
                $find.Replacement.ClearFormatting()
                $find.MatchCase = $true
                [void]$find.Execute("LSDB", $true, $true, $false, $false, $false, $true, 1, $false, "La Salle DB1", 2)
            }
            elseif ($txt -match "^Fig\. 5\. Gate Competence Escalation" -or $txt -match "^Fig\. 4\. Gate Competence Escalation" -or $txt -match "Gate Competence Escalation") {
                $find = $p.Range.Find
                $find.ClearFormatting()
                $find.Replacement.ClearFormatting()
                [void]$find.Execute("Gate Competence Escalation", $false, $true, $false, $false, $false, $true, 1, $false, "Escalation behavior by LBPH outcome", 2)
            }
        }

        # Standardize Table 3 and Table 4 headers
        if ($document.Tables.Count -ge 6) {
            Set-CellText $document $document.Tables.Item(3).Cell(1, 4) "Feature size" $true 1
            Set-CellText $document $document.Tables.Item(4).Cell(1, 4) "Feature size" $true 1
            Set-CellText $document $document.Tables.Item(2).Cell(2, 1) "La Salle DB1 recognizer selection" $false 0
            Set-CellText $document $document.Tables.Item(2).Cell(2, 2) "Select the classical and learned recognizers using fixed La Salle DB1 subsets." $false 0
            Set-CellText $document $document.Tables.Item(2).Cell(3, 1) "LFW independence test (Sec. 4.2)" $false 0
            Set-CellText $document $document.Tables.Item(2).Cell(5, 1) "La Salle DB1-DL41 held-out evaluation (Sec. 4.4)" $false 0
        }

        # Update all fields in document
        Write-Output "Updating fields and repaginating..."
        $document.Fields.Update()
        foreach ($story in $document.StoryRanges) {
            $story.Fields.Update()
        }
        $document.Repaginate()

        $pageCount = [int]$document.ComputeStatistics(2)
        Write-Output "Document page count: $pageCount"

        Write-Output "Saving modified document..."
        $document.Save()
        
        Write-Output "Exporting to PDF: $pdfPath..."
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

    Write-Output "Restoring bit-for-bit identical VBA project..."
    Restore-ZipPart -ReferencePath $baselinePath -TargetPath $stagePath -PartName $vbaPart
    if ((Get-ZipPartHash $stagePath $vbaPart) -ne $baselineVbaHash) { throw "VBA project hash differs after restoration." }

    # Also restore the updated media files into the final output
    Copy-Item -LiteralPath $stagePath -Destination $outputPath -Force
    if ((Test-Path -LiteralPath $fig5Svg) -and (Test-Path -LiteralPath $fig5Png)) {
        Replace-ZipFileEntry -ZipPath $outputPath -EntryName "word/media/image10.svg" -SourceFilePath $fig5Svg
        Replace-ZipFileEntry -ZipPath $outputPath -EntryName "word/media/image9.png" -SourceFilePath $fig5Png
    }

    if ((Get-ZipPartHash $outputPath $vbaPart) -ne $baselineVbaHash) { throw "Output VBA project hash differs from baseline." }

    Write-Output "SUCCESS: Created $outputPath and $pdfPath"
    Write-Output "VBA SHA256: $baselineVbaHash"
}
finally {
    if (Test-Path -LiteralPath $stagePath) { Remove-Item -LiteralPath $stagePath -Force }
    $repackedStage = "$stagePath.repacked"
    if (Test-Path -LiteralPath $repackedStage) { Remove-Item -LiteralPath $repackedStage -Force }
}
