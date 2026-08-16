[CmdletBinding()]
param(
    [string]$Baseline = 'docs\manuscript\versions\pairwise\019p_lsface_reproducibility-pass.docm',
    [string]$Output = 'docs\manuscript\versions\020p_lsface_canonical-selfmatch-promoted.docm',
    [string]$PdfOutput = 'docs\manuscript\versions\020p_lsface_canonical-selfmatch-promoted.pdf'
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
            $alignment = if ($column -ge 2) { 1 } else { 0 }
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
$stagePath = Join-Path ([System.IO.Path]::GetTempPath()) ("lsface_020p_{0}.docm" -f [guid]::NewGuid().ToString('N'))

try {
    Copy-Item -LiteralPath $baselinePath -Destination $stagePath

    Write-Output "Opening Word Application COM..."
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $null

    try {
        $document = $word.Documents.Open($stagePath, $false, $false)

        # -------------------------------------------------------------
        # 1. Abstract Self-Match Update
        # -------------------------------------------------------------
        Write-Output "Updating Abstract with canonical self-match results..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range

            if ($txt.StartsWith("Abstract. Face recognition for access-control systems")) {
                $newAbstract = "Abstract. Face recognition for access-control systems must remain reliable under changing image conditions without using more computation than necessary. This study presents LS-Face, a two-stage recognizer that uses LBPH first and sends uncertain or poor-quality cases to SFace. The experiments were divided into four parts: recognizer selection, threshold setting, controlled robustness testing, and held-out cascade testing. LBPH and SFace were chosen from three classical and three deep-learning candidates using La Salle DB1. The acceptance thresholds were then set using cross-identity comparisons on LFW. For LBPH, 16,522,626 impostor comparisons produced a calibration false-accept rate of 9.986 ppm at the selected threshold. In the controlled self-match robustness test, transformed versions of the enrolled images were matched back to their source identities. Across 41 transformations, LBPH, SFace, and the cascade achieved retention rates of 77.02%, 88.90%, and 88.91%, respectively, with 92.45% of modified conditions escalated to SFace. In a separate held-out La Salle DB1-DL41 test using different enrollment and probe photographs, SFace recovered 81.56% of thresholded LBPH failures. LBPH distance and the separation between its top two matches were also strong indicators of LBPH failure, with AUCs of 0.950 and 0.953. A post-hoc replay on the same evaluation data reduced escalation from 71.52% to 59.23% while preserving the same 87.24% thresholded correct-identity acceptance. However, the cascade still required 10.81 ms on average compared with 8.33 ms for direct SFace. These results show that SFace provides an effective fallback for difficult LBPH cases and that LBPH scores can help decide when fallback is needed, but the current cascade does not provide a runtime advantage over direct SFace under the tested stress conditions. Open-set identification and end-to-end target-device performance were not evaluated."
                Replace-ParagraphText $p $newAbstract
                $p.Range.Font.Bold = 0
                $rAbsLead = $p.Range.Duplicate
                $rAbsLead.End = $rAbsLead.Start + 9
                $rAbsLead.Font.Bold = -1
                break
            }
        }

        # -------------------------------------------------------------
        # 2. Section 3.1: Quality trigger text, Table 1, and m_min formatting
        # -------------------------------------------------------------
        Write-Output "Updating Section 3.1 quality triggers and Table 1..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range

            if ($txt.StartsWith("(i) an image-quality flag is raised because of blur")) {
                $newP30 = "(i) an image-quality flag is raised because of blur, illumination outside the calibrated range, sensor noise, off-pose presentation, or insufficient face size;"
                Replace-ParagraphText $p $newP30
            }
            elseif ($txt.StartsWith("The quality thresholds in Table 1 were defined")) {
                $newP63 = "The quality thresholds in Table 1 were defined from the empirical distribution edges of 279 clean facial crops detected across a 280-image reference collection (10 clean frontal and pose images per identity across 28 identities, with one detector miss excluded), rather than optimized on the 41-transformation evaluation set or fitted to a measured LBPH-to-SFace performance crossover. The relative top-two margin expresses the separation between the two highest-ranked candidates relative to the best-match distance; mmin = 0.05 was chosen as a fixed engineering policy value rather than statistically optimized. The quality condition is evaluated independently of the LBPH score, allowing quality-flagged inputs to be escalated even when the first-stage distance appears confident."
                Replace-ParagraphText $p $newP63
                # Format mmin as italic m with subscript min
                $findM = $p.Range.Find
                $findM.ClearFormatting()
                if ($findM.Execute("mmin")) {
                    $found = $findM.Parent
                    $mR = $document.Range($found.Start, $found.Start + 1)
                    $mR.Font.Italic = -1
                    $mR.Font.Subscript = 0
                    $minR = $document.Range($found.Start + 1, $found.Start + 4)
                    $minR.Font.Subscript = -1
                    $minR.Font.Italic = 0
                }
            }
        }

        # Format Table 1
        if ($document.Tables.Count -ge 1) {
            $table1 = $document.Tables.Item(1)
            $table1Data = @(
                @('Signal', 'Measurement / condition', 'Selection rule', 'Deployed value'),
                @('Blur', 'Variance of Laplacian below threshold', '5th percentile of clean values', '587.83'),
                @('Illumination', 'Mean grayscale outside lower/upper bounds', '2nd and 98th percentiles of clean values', '[52.88, 137.71]'),
                @('Noise', 'Immerkaer noise estimate above threshold', '95th percentile of clean values', '8.206'),
                @('Pose', 'Maximum of eye-roll and nose-yaw proxies above threshold', '95th percentile of clean values', '63.74'),
                @('Face size', 'Detected box side below minimum', '⌊0.9 × p5⌋ of clean box sizes', '61 px'),
                @('Relative top-two margin', '(d₂ − d₁) / d₁ < mmin', 'Fixed engineering policy value', 'mmin = 0.05')
            )
            Populate-LncsTable $document $table1 $table1Data @(72, 130, 118, 58)

            # Format p5 in face size row
            $rFaceSize = $table1.Cell(6, 3).Range
            $findP5 = $rFaceSize.Find
            $findP5.ClearFormatting()
            if ($findP5.Execute("p5")) {
                $f = $findP5.Parent
                $pR = $document.Range($f.Start, $f.Start + 1)
                $pR.Font.Italic = -1
                $pR.Font.Subscript = 0
                $fiveR = $document.Range($f.Start + 1, $f.Start + 2)
                $fiveR.Font.Subscript = -1
                $fiveR.Font.Italic = 0
            }

            # Format mmin in Table 1 row 7
            $rM1 = $table1.Cell(7, 2).Range
            $findM1 = $rM1.Find
            $findM1.ClearFormatting()
            if ($findM1.Execute("mmin")) {
                $f = $findM1.Parent
                $mR = $document.Range($f.Start, $f.Start + 1)
                $mR.Font.Italic = -1
                $mR.Font.Subscript = 0
                $minR = $document.Range($f.Start + 1, $f.Start + 4)
                $minR.Font.Subscript = -1
                $minR.Font.Italic = 0
            }

            $rM2 = $table1.Cell(7, 4).Range
            $findM2 = $rM2.Find
            $findM2.ClearFormatting()
            if ($findM2.Execute("mmin")) {
                $f = $findM2.Parent
                $mR = $document.Range($f.Start, $f.Start + 1)
                $mR.Font.Italic = -1
                $mR.Font.Subscript = 0
                $minR = $document.Range($f.Start + 1, $f.Start + 4)
                $minR.Font.Subscript = -1
                $minR.Font.Italic = 0
            }
        }

        # -------------------------------------------------------------
        # 3. Section 4.3: Controlled Self-Match Robustness Test & Table 6
        # -------------------------------------------------------------
        Write-Output "Updating Section 4.3 and Table 6..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range

            if ($txt.StartsWith("Table 5 reports the controlled self-match") -or $txt.StartsWith("Table 6 reports the controlled self-match")) {
                $new43ProseText = "Table 6 reports the controlled self-match robustness test under the same frozen operating configuration summarized in Table 5. One selected source image for each of 5,749 LFW identities was enrolled, and the clean and transformed test images were derived from that same source. The experiment therefore measures within-image transformation retention rather than image-disjoint identification, and no FAR is measured because no impostor comparisons are performed. Across the 235,709 modified conditions (41 transformations × 5,749 source images), LBPH, SFace, and the hybrid cascade achieved retention rates of 77.02%, 88.90%, and 88.91%, respectively. The cascade escalated 217,917 of the 235,709 modified conditions (92.45% pooled escalation), essentially matching SFace retention (88.91% versus 88.90%). Under the strict detector-failure policy, 15,083 modified conditions (6.40%) failed face detection—concentrated in 90°, 180°, and 270° rotations and horizontal flipping—and were retained as failures. No modified condition terminated through the LBPH hard-reject branch at τreject = 140.13, consistent with the boundary's deliberately permissive role on this workload."
                Replace-ParagraphText $p $new43ProseText

                # Format τreject with subscript
                $findTau = $p.Range.Find
                $findTau.ClearFormatting()
                if ($findTau.Execute("τreject")) {
                    $f = $findTau.Parent
                    $tauR = $document.Range($f.Start, $f.Start + 1)
                    $tauR.Font.Italic = -1
                    $tauR.Font.Subscript = 0
                    $rejR = $document.Range($f.Start + 1, $f.Start + 7)
                    $rejR.Font.Subscript = -1
                    $rejR.Font.Italic = 0
                }
            }
            elseif ($txt.StartsWith("Each row uses one enrolled source image for each of 5,749 LFW identities") -or $txt.StartsWith("The experiment uses the frozen operating configuration summarized in Table 5")) {
                $newFootnoteText = "The experiment uses the frozen operating configuration summarized in Table 5; detector failures are retained as failures."
                Replace-ParagraphText $p $newFootnoteText
                $p.Range.Font.Size = 9
                $p.Range.Font.Italic = 0
            }
        }

        # Update Table 6 caption
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range
            if ($txt -match "^Table \d+\. Controlled Self-Match Robustness Test on LFW" -or $txt -match "^Table \d+\. Controlled self-match robustness test on LFW") {
                Replace-ParagraphText $p "Table 6. Controlled self-match robustness test on LFW." "tablecaption"
                break
            }
        }

        # Update Table 6 contents (Table 6 is the 6th table in the document)
        if ($document.Tables.Count -ge 6) {
            $table6 = $document.Tables.Item(6)
            if ($table6.Columns.Count -eq 5) {
                $table6.Columns.Item(5).Delete()
            }
            $table6Data = @(
                @('Mode', 'Clean self-match (%)', '41-transformation retention (%)', '41-transformation escalation (%)'),
                @('Classical CV (LBPH)', '99.22', '77.02', 'N/A'),
                @('Deep Learning (SFace)', '99.53', '88.90', 'N/A'),
                @('Hybrid Cascade', '99.53', '88.91', '92.45')
            )
            Populate-LncsTable $document $table6 $table6Data @(108, 70, 95, 75)
        }

        # -------------------------------------------------------------
        # 4. Section 4.4: Terminology updates and τ_accept formatting
        # -------------------------------------------------------------
        Write-Output "Updating Section 4.4 terminology and math formatting..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range

            if ($txt.StartsWith("The evaluation follows the three-link argument described above.")) {
                $new44Intro = "The evaluation follows the three-link argument described above. It uses 56 image-disjoint held-out La Salle DB1 source test images, two for each of 28 enrolled identities, and 41 deterministic transformations per source, yielding 2,296 correlated test conditions. The LFW-derived thresholds and routing rule were frozen before scoring, and detector failures were handled strictly. Figures 4 and 5 summarize the two main complementarity findings: whether SFace can recover LBPH failures and whether the routing rule can distinguish cases that should be escalated."
                Replace-ParagraphText $p $new44Intro
            }
            elseif ($txt.StartsWith("Second, LBPH distance and relative top-two margin provided strong discrimination")) {
                $new44Routing = "Second, LBPH distance and relative top-two margin provided strong discrimination of LBPH Rank-1 errors. Of the 1,589 thresholded LBPH failures, 1,353 had the LBPH signals required for routing analysis; the remaining 236 conditions were excluded from signal-based routing metrics. Among the 2,060 test conditions with available routing signals, LBPH distance and negative relative top-two margin separated 444 threshold-free LBPH Rank-1 errors with AUCs of 0.95019 and 0.95319, respectively. As shown in Fig. 5, the deployed rule escalated all 1,353 thresholded LBPH failures, giving 100.0% failure-routing recall. However, it also escalated 289 of the 707 LBPH-correct cases (40.88%), while the remaining 418 cases (59.12%) were correctly retained at the LBPH stage. Thus, the rule captured all signal-available thresholded LBPH failures but also escalated 40.88% of LBPH-correct cases."
                Replace-ParagraphText $p $new44Routing
            }
            elseif ($txt.StartsWith("A post-hoc accept-protection replay examined whether this redundant routing")) {
                $new44Replay = "A post-hoc accept-protection replay examined whether this redundant routing could be reduced. The replay preserved the deployed low-margin trigger and all conditions above τaccept, while treating accept-side quality flags as telemetry rather than escalation triggers. Under this replay, unnecessary escalations among LBPH-correct cases fell from 289 to 7 of 707. Because the same transformed probes motivated and evaluated this candidate policy, however, the result is treated only as a descriptive ablation and not as independent validation of an improved routing rule."
                Replace-ParagraphText $p $new44Replay

                # Format τaccept with subscript
                $findTauAcc = $p.Range.Find
                $findTauAcc.ClearFormatting()
                if ($findTauAcc.Execute("τaccept")) {
                    $f = $findTauAcc.Parent
                    $tauR = $document.Range($f.Start, $f.Start + 1)
                    $tauR.Font.Italic = -1
                    $tauR.Font.Subscript = 0
                    $accR = $document.Range($f.Start + 1, $f.Start + 7)
                    $accR.Font.Subscript = -1
                    $accR.Font.Italic = 0
                }
            }
        }

        # -------------------------------------------------------------
        # 5. Discussion 5.1: Controlled Robustness
        # -------------------------------------------------------------
        Write-Output "Updating Discussion 5.1..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range

            if ($txt.StartsWith("The controlled LFW self-match experiment isolates sensitivity to known image transformations")) {
                $new51Text = "The controlled LFW self-match experiment isolates sensitivity to known image transformations by deriving each test image from its enrolled source. Under this constrained protocol, LBPH, SFace, and the cascade achieved 77.02%, 88.90%, and 88.91% retention across 235,709 modified conditions, with 15,083 strict detector failures (6.40%) retained as failures. The cascade essentially matched SFace retention under the tested transformations, but its 92.45% pooled escalation rate shows that the current routing policy provided little selectivity on this stress workload. Therefore, this self-match workload provides evidence of SFace robustness rather than substantial selective-computation savings. Because transformed test images derive from their enrolled source, the experiment remains a controlled transformation-sensitivity test rather than image-disjoint identification or FAR measurement."
                Replace-ParagraphText $p $new51Text
                break
            }
        }

        # -------------------------------------------------------------
        # 6. Conclusion 6.1 & 6.2 Updates
        # -------------------------------------------------------------
        Write-Output "Updating Conclusion 6.1 & 6.2..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range

            if ($txt.StartsWith("LS-Face combines an LBPH first stage with SFace fallback and was evaluated through separate selection")) {
                $new61Text = "LS-Face combines an LBPH first stage with SFace fallback and was evaluated through separate selection, calibration, controlled-robustness, and held-out cascade experiments. The controlled self-match rerun showed that SFace showed higher retention than LBPH under the tested transformations, while the cascade essentially matched SFace retention with high escalation. The held-out La Salle DB1-DL41 experiment separately showed substantial SFace recovery of LBPH failures and useful first-stage risk signals."
                Replace-ParagraphText $p $new61Text
            }
            elseif ($txt.StartsWith("Under the held-out La Salle DB1-DL41 stress workload, however")) {
                $new62Text = "Under the held-out La Salle DB1-DL41 stress workload, however, the cascade did not outperform direct SFace in the recognition-performance/runtime trade-off. The study therefore supports SFace as an effective fallback and LBPH scores as informative routing signals, while defining a clear efficiency limit of the current architecture. Open-set identification and end-to-end target-device evaluation remain outside the present scope."
                Replace-ParagraphText $p $new62Text
            }
        }

        # -------------------------------------------------------------
        # 7. Global Table Numbering Audit & Re-pagination
        # -------------------------------------------------------------
        Write-Output "Auditing table captions and updating all fields..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range

            if ($txt -match "^Table \d+\. Deployed quality-check") {
                Replace-ParagraphText $p "Table 1. Deployed quality-check and candidate-separation parameters for Stage 1 escalation." "tablecaption"
            }
            elseif ($txt -match "^Table \d+\. Experiments and their roles") {
                Replace-ParagraphText $p "Table 2. Experiments and their roles in the study." "tablecaption"
            }
            elseif ($txt -match "^Table \d+\. Classical candidate selection on") {
                Replace-ParagraphText $p "Table 3. Classical candidate selection on La Salle DB1." "tablecaption"
            }
            elseif ($txt -match "^Table \d+\. DL candidate selection on") {
                Replace-ParagraphText $p "Table 4. DL candidate selection on La Salle DB1." "tablecaption"
            }
            elseif ($txt -match "^Table \d+\. Final frozen operating points") {
                Replace-ParagraphText $p "Table 5. Final frozen operating points." "tablecaption"
            }
            elseif ($txt -match "^Table \d+\. Controlled self-match robustness") {
                Replace-ParagraphText $p "Table 6. Controlled self-match robustness test on LFW." "tablecaption"
            }
        }

        $document.Fields.Update()
        foreach ($story in $document.StoryRanges) {
            $story.Fields.Update()
        }
        $document.Repaginate()

        $pageCount = [int]$document.ComputeStatistics(2)
        Write-Output "Document page count: $pageCount"

        Write-Output "Saving 020p document..."
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

    Copy-Item -LiteralPath $stagePath -Destination $outputPath -Force
    if ((Get-ZipPartHash $outputPath $vbaPart) -ne $baselineVbaHash) { throw "Output VBA project hash differs from baseline." }

    Write-Output "SUCCESS: Created $outputPath and $pdfPath"
    Write-Output "VBA SHA256: $baselineVbaHash"
}
finally {
    if (Test-Path -LiteralPath $stagePath) { Remove-Item -LiteralPath $stagePath -Force }
    $repackedStage = "$stagePath.repacked"
    if (Test-Path -LiteralPath $repackedStage) { Remove-Item -LiteralPath $repackedStage -Force }
}
