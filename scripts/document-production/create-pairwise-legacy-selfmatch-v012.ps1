[CmdletBinding()]
param(
    [string]$BaselinePath,

    [string]$OutputPath,

    [switch]$Force
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($BaselinePath)) {
    $BaselinePath = Join-Path $PSScriptRoot '..\..\docs\manuscript\versions\012_lsface_gate-accept-protection-descriptive.docm'
}
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $PSScriptRoot '..\..\docs\manuscript\versions\pairwise\012p_lsface_legacy-selfmatch-robustness.docm'
}

function Get-VbaProjectBytes {
    param([Parameter(Mandatory = $true)][string]$Path)

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($Path)
    try {
        $entry = $archive.GetEntry('word/vbaProject.bin')
        if (-not $entry) { throw "No word/vbaProject.bin found in $Path" }
        $stream = $entry.Open()
        $memory = [System.IO.MemoryStream]::new()
        try {
            $stream.CopyTo($memory)
            # Keep the byte array as one pipeline object; otherwise PowerShell
            # enumerates it and callers receive an Object[] of individual bytes.
            return ,$memory.ToArray()
        }
        finally {
            $memory.Dispose()
            $stream.Dispose()
        }
    }
    finally {
        $archive.Dispose()
    }
}

function Get-VbaProjectHash {
    param([Parameter(Mandatory = $true)][string]$Path)

    $bytes = Get-VbaProjectBytes -Path $Path
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Restore-VbaProject {
    param(
        [Parameter(Mandatory = $true)][string]$TargetPath,
        [Parameter(Mandatory = $true)][byte[]]$VbaProjectBytes
    )

    $archive = [System.IO.Compression.ZipFile]::Open($TargetPath, [System.IO.Compression.ZipArchiveMode]::Update)
    try {
        $entry = $archive.GetEntry('word/vbaProject.bin')
        if ($entry) { $entry.Delete() }
        $replacement = $archive.CreateEntry('word/vbaProject.bin', [System.IO.Compression.CompressionLevel]::Optimal)
        $stream = $replacement.Open()
        try {
            $stream.Write($VbaProjectBytes, 0, $VbaProjectBytes.Length)
        }
        finally {
            $stream.Dispose()
        }
    }
    finally {
        $archive.Dispose()
    }
}

function Get-ParagraphText {
    param([Parameter(Mandatory = $true)]$Paragraph)
    return (($Paragraph.Range.Text -replace '[\r\a]+', ' ') -replace '\s+', ' ').Trim()
}

function Find-ParagraphByPrefix {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)][string]$Prefix
    )

    foreach ($paragraph in $Document.Paragraphs) {
        if ((Get-ParagraphText -Paragraph $paragraph).StartsWith($Prefix, [System.StringComparison]::Ordinal)) {
            return $paragraph
        }
    }
    throw "Could not find paragraph beginning '$Prefix'."
}

function Set-ParagraphText {
    param(
        [Parameter(Mandatory = $true)]$Paragraph,
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$StyleName,
        [switch]$ClearDirectFormatting
    )

    $content = $Paragraph.Range.Duplicate
    $content.End = $content.End - 1
    $content.Text = $Text

    if ($ClearDirectFormatting) {
        $Paragraph.Range.Font.Reset()
        $Paragraph.Range.ParagraphFormat.Reset()
    }
    $Paragraph.Range.Style = $StyleName
}

function Set-TableCellText {
    param(
        [Parameter(Mandatory = $true)]$Table,
        [Parameter(Mandatory = $true)][int]$Row,
        [Parameter(Mandatory = $true)][int]$Column,
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][int]$Alignment,
        [Parameter(Mandatory = $true)][bool]$Bold
    )

    $cell = $Table.Cell($Row, $Column)
    $content = $cell.Range.Duplicate
    $content.End = $content.End - 1
    $content.Text = $Text
    $content.ListFormat.RemoveNumbers()
    $content.ParagraphFormat.Alignment = $Alignment
    $content.Font.Bold = if ($Bold) { 1 } else { 0 }
}

$resolvedBaseline = (Resolve-Path -LiteralPath $BaselinePath).Path
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $resolvedOutput

if ((Test-Path -LiteralPath $resolvedOutput) -and -not $Force) {
    throw "Refusing to overwrite existing experimental manuscript: $resolvedOutput"
}

New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
$baselineVbaBytes = Get-VbaProjectBytes -Path $resolvedBaseline
$baselineVbaHash = Get-VbaProjectHash -Path $resolvedBaseline
Copy-Item -LiteralPath $resolvedBaseline -Destination $resolvedOutput -Force:$Force

$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $word.Documents.Open($resolvedOutput, $false, $false, $false)

    # Abstract: preserve its existing narrative, then close with the archived
    # result and the protocol boundary that governs its interpretation.
    $abstract = Find-ParagraphByPrefix $document 'Abstract.'
    Set-ParagraphText $abstract 'Abstract. A facial recognition system is a technology capable of identifying or verifying a person from a digital image by comparing facial features with a database and has many applications such as home security and access control, finance, public safety and marketing, etc. Among these, the field of Home Security is particularly important for protecting family safety, preventing property loss, and ensuring psychological stability in daily life. Home security consists of a complex combination of various technologies, among which facial recognition technology requires high accuracy, a low false positive rate, and fast processing speeds as essential requirements. Furthermore, recent advancements in artificial intelligence have significantly improved the performance of facial recognition technology, establishing it as an indispensable core function. However, the reality is that applying face recognition technology in real-world environments is difficult because recognition results vary significantly depending on the diversity of facial images due to environmental changes, differences in facial structures between the East and West, and changes in facial expressions and gaze. Meanwhile, various methods to address these issues have recently been proposed. Representative examples include a hybrid approach combining computer vision and deep neural networks, and independence testing techniques that analyze statistical associations between visual variables, features, or data distributions of face images. In this paper, we proposed a methodology that organically links a hybrid approach combining computer vision and deep neural networks with independence testing and evaluated it using the Labeled Faces in the Wild (LFW) dataset. In an archived same-image transform-sensitivity experiment, augmented probes were derived from each enrolled source image; across 41 legacy transformations, LBPH, SFace, and the hybrid cascade retained the source identity in 86.66%, 98.22%, and 94.69% of cases, respectively. Since this protocol includes neither different-photo probes nor impostor comparisons, the values represent within-image degradation retention rather than recognition accuracy or false-accept performance.' 'abstract' -ClearDirectFormatting
    $abstractLabel = $abstract.Range.Duplicate
    $abstractLabel.End = $abstractLabel.Start + 9
    $abstractLabel.Font.Bold = 1

    # Method: retain the deliberately same-image legacy protocol and call it
    # transform sensitivity rather than an image-disjoint recognition metric.
    Set-ParagraphText (Find-ParagraphByPrefix $document 'Robustness: the 41-modification accuracy ratio') 'Archived same-image transform-sensitivity experiment' 'heading2'
    Set-ParagraphText (Find-ParagraphByPrefix $document 'Every original image receives 41 deterministic') 'This experimental branch retains the original LFW stress-test construction. For each of 5,749 identities, one deterministic source image is enrolled as the sole gallery template and the clean probe plus all 41 legacy augmented probes are derived from that same source image. Before an augmentation is applied, the gallery image and the probe source are therefore identical. The test measures whether re-detection and matching retain the identity of a memorized source under the legacy 41-variant, 12-family transformation suite; it does not test recognition from a different photograph.' 'p1a'

    $equationParagraph = Find-ParagraphByPrefix $document 'AR = K / M'
    Set-ParagraphText $equationParagraph 'R = K / M (3)' 'equation'
    # Word's COM projection on this host does not expose OMath.BuildUp.
    # Retaining the existing equation paragraph style keeps the replacement
    # visually aligned with the surrounding LNCS equation block.

    Set-ParagraphText (Find-ParagraphByPrefix $document 'averaged per modification over its levels') 'where K is the number of retained source-identity decisions among M modified probes. We report the mean of the per-modification retention values. The suite is seeded per (image, modification, level), so CV, DL, and hybrid score bit-identical probes. Because no different-photo genuine probes or impostor probes are scored, R is an archived within-image retention score, not recognition accuracy, pairwise verification accuracy, or an estimate of FAR.' 'Normal'
    Set-ParagraphText (Find-ParagraphByPrefix $document 'Separately tuned values across four databases would show tunability') 'Except for the explicitly labelled archived self-match experiment in Table 5, we freeze one configuration before cross-database evaluation: tau_a = 67.03325520645528 from LFW DB1''s unique-pair LBPH sweep (rank 165; 9.986 ppm); tau_r = 140.13 from the LFW escalation trade-off; m_min = 0.05 is policy-set; and SFace uses its deployed L2 rule, 1.0313. The harness records the threshold-file SHA-256, and the same configuration is applied unchanged across the image-disjoint database legs. Table 5 instead preserves its recorded historical rules and is not reinterpreted as this frozen deployment configuration. Enrollment is otherwise clean originals; only probes are modified. Each database answers one question (Table 1):' 'p1a'

    # Evidence matrix: distinguish the experimental record from the canonical
    # image-disjoint robustness evidence without changing other rows.
    $evidenceMatrix = $document.Tables.Item(1)
    Set-TableCellText $evidenceMatrix 5 1 'LFW (41 legacy modifications, 1 image/id)' 0 $false
    Set-TableCellText $evidenceMatrix 5 2 'archived same-image transform sensitivity' 0 $false
    Set-TableCellText $evidenceMatrix 5 3 'within-image degradation retention only; no FAR or cross-photo recognition claim' 0 $false

    # Keep captions concise; the operating-point detail already appears in
    # the adjacent selection paragraphs, where it remains easier to read.
    Set-ParagraphText (Find-ParagraphByPrefix $document 'Table 2. LSDB classical candidate selection') 'Table 2. Classical candidate selection on LSDB.' 'tablecaption' -ClearDirectFormatting
    Set-ParagraphText (Find-ParagraphByPrefix $document 'Table 3. DL-only candidate selection on LSDB') 'Table 3. DL candidate selection on LSDB.' 'tablecaption' -ClearDirectFormatting
    # The two concise replacements are plain text, so preserve the intended
    # caption sequence explicitly instead of allowing Word's remaining field
    # to renumber Table 4 as if Tables 2 and 3 did not exist.
    Set-ParagraphText (Find-ParagraphByPrefix $document 'Table 4. Final frozen operating points') 'Table 4. Final frozen operating points.' 'tablecaption' -ClearDirectFormatting

    # Results: replace only the current LFW2 image-disjoint table trail with
    # the archived same-image experiment and its historical recorded results.
    Set-ParagraphText (Find-ParagraphByPrefix $document 'LFW2 Robustness Evaluation') 'Archived LFW Same-Image Transform-Sensitivity Experiment' 'heading2'
    Set-ParagraphText (Find-ParagraphByPrefix $document 'Table 5 summarizes gallery/probe-disjoint LFW2 1-to-N identification robustness') 'Table 5 reports the deliberately noncanonical archived LFW stress test. One selected original per identity was enrolled and that same original supplied each clean and augmented probe, so the scores quantify within-image degradation retention only. Across the 41 legacy variants, the archived records show 86.66% LBPH retention, 98.22% SFace retention, and 94.69% cascade retention. The derived FAR entries are historical threshold-basis values from separate impostor calibrations; no impostor pairs were evaluated in this experiment.' 'p1a'
    Set-ParagraphText (Find-ParagraphByPrefix $document 'Table 5. LFW2 1-to-N identification robustness') 'Table 5. Archived same-image LFW transform sensitivity (noncanonical).' 'tablecaption' -ClearDirectFormatting

    # Replacing the previous Table 5 caption removes its automatic sequence
    # field. Keep the immediately following logic-to-data table explicitly
    # numbered as Table 6 so the experimental fork has no duplicate caption.
    $logicCaption = $null
    try {
        $logicCaption = Find-ParagraphByPrefix $document 'Table 6. Logic-to-data audit of SFace rescue and gate routing'
    }
    catch {
        $logicCaption = Find-ParagraphByPrefix $document 'Table 5. Logic-to-data audit of SFace rescue and gate routing'
    }
    Set-ParagraphText $logicCaption 'Table 6. SFace rescue and gate-routing audit on LSDB-DL41.' 'tablecaption' -ClearDirectFormatting

    $resultsTable = $document.Tables.Item(5)
    $rows = @(
        @('Mode', 'Clean self-match (%)', '41-mod retention (%)', 'Derived FAR*', 'Escalation (%)'),
        @('Classical CV (LBPH)', '100.00', '86.66', '~1%', 'N/A'),
        @('Deep Learning (SFace)', '99.67', '98.22', '~10 ppm', 'N/A'),
        @('Hybrid Cascade', '99.93', '94.69', 'N/A', '46.39')
    )
    for ($row = 1; $row -le $rows.Count; $row++) {
        for ($column = 1; $column -le $rows[$row - 1].Count; $column++) {
            $alignment = if ($column -eq 1) { 0 } else { 1 } # wdAlignParagraphLeft / Center
            Set-TableCellText $resultsTable $row $column $rows[$row - 1][$column - 1] $alignment ($row -eq 1)
        }
    }
    $resultsTable.AllowAutoFit = $false
    foreach ($pair in @(
        @(1, 78),
        @(2, 68),
        @(3, 78),
        @(4, 52),
        @(5, 69)
    )) {
        $resultsTable.Columns.Item([int]$pair[0]).Width = [single]$pair[1]
    }

    Set-ParagraphText (Find-ParagraphByPrefix $document 'Overall AR and escalation are means across 41 modifications') 'Each row uses one enrolled source image for each of 5,749 LFW identities and 41 legacy modification variants. The source image is reused to make its own clean and modified probes. The archived run predates the standalone-LBPH acceptance correction: its LBPH-only branch used the then tau_r = 76.85 boundary, while the historical cascade used tau_a = 67.0084 and tau_r = 76.85; SFace used L2 = 1.018 with cosine >= 0.363. *Derived FAR is a historical threshold-basis value from separate LFW impostor calibrations: tau_r = 76.85 is approximately 1% FAR, and the SFace rule is approximately 10 ppm. It is not a FAR measured by this same-image experiment; a cascade FAR cannot be inferred from the separate per-leg values. The run has not been recalibrated to Table 4. This table is intentionally noncanonical.' 'p1a'
    Set-ParagraphText (Find-ParagraphByPrefix $document 'The scope also limits generalization.') 'The scope also limits generalization. The archived LFW experiment in Table 5 transforms the image already enrolled for that identity, so it has no separated gallery/probe images, impostor scores, FAR, or unknown-query FPIR; it is reported only as within-image transform sensitivity. The LSDB-DL41 rows are correlated transformations of 56 known-genuine source probes, 236 no-signal cases are outside the scored gate rates, and no unknown-query FPIR can be measured. The stored timing is recognition-stage arithmetic rather than end-to-end latency. The runtime gate remains unchanged. Open-set identification and target-device testing, including Raspberry Pi 5 measurements, are explicitly outside the present paper''s scope.' 'Normal'

    $document.Fields.Update() | Out-Null
    $document.Save()
}
finally {
    if ($document) {
        $document.Close(0)
        [Runtime.InteropServices.Marshal]::FinalReleaseComObject($document) | Out-Null
    }
    if ($word) {
        $word.Quit()
        [Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) | Out-Null
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

Restore-VbaProject -TargetPath $resolvedOutput -VbaProjectBytes $baselineVbaBytes
$outputVbaHash = Get-VbaProjectHash -Path $resolvedOutput
if ($outputVbaHash -ne $baselineVbaHash) {
    throw "VBA hash mismatch after restore: baseline=$baselineVbaHash output=$outputVbaHash"
}

Write-Output "Created $resolvedOutput"
Write-Output "VBA SHA-256 $outputVbaHash"
