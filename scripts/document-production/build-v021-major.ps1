[CmdletBinding()]
param(
    [string]$Baseline = 'docs\manuscript\versions\020b_lsface_canonical-selfmatch-promoted.docm',
    [string]$Output = 'docs\manuscript\versions\021_lsface_major.docm',
    [string]$PdfOutput = 'docs\manuscript\versions\021_lsface_major.pdf',
    [string]$ContentJson = 'scripts\document-production\v021_content.json'
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
$contentJsonPath = Resolve-WorkspacePath $ContentJson

$vbaPart = 'word/vbaProject.bin'
$baselineVbaHash = Get-ZipPartHash $baselinePath $vbaPart
$stagePath = Join-Path ([System.IO.Path]::GetTempPath()) ("lsface_021_{0}.docm" -f [guid]::NewGuid().ToString('N'))

$content = Get-Content -LiteralPath $contentJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json

Write-Output "================================================================================"
Write-Output " BUILDING VERSION 021_MAJOR MANUSCRIPT (LS-FACE SELECTIVE COMPUTATION)"
Write-Output "================================================================================"
Write-Output "Baseline DOCM: $baselinePath"
Write-Output "Target DOCM:   $outputPath"
Write-Output "Target PDF:    $pdfPath"

try {
    Copy-Item -LiteralPath $baselinePath -Destination $stagePath

    Write-Output "Opening Word Application COM (AutomationSecurity = ForceDisable)..."
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $null

    try {
        $document = $word.Documents.Open($stagePath, $false, $false)

        # -------------------------------------------------------------
        # 1. Update Title, Abstract & Keywords
        # -------------------------------------------------------------
        Write-Output "[1/6] Updating Title, Abstract and Keywords..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range

            if ($p.Range.Style.NameLocal -eq 'papertitle' -or $txt.StartsWith("LS-Face:")) {
                Replace-ParagraphText $p $content.papertitle 'papertitle'
            }
            elseif ($txt.StartsWith("Abstract.")) {
                Replace-ParagraphText $p $content.abstract
                $p.Range.Font.Bold = 0
                $rAbsLead = $p.Range.Duplicate
                $rAbsLead.End = $rAbsLead.Start + 9
                $rAbsLead.Font.Bold = -1
            }
            elseif ($txt.StartsWith("Keywords:")) {
                Replace-ParagraphText $p $content.keywords
                $rKeyLead = $p.Range.Duplicate
                $rKeyLead.End = $rKeyLead.Start + 9
                $rKeyLead.Font.Bold = -1
            }
        }

        # -------------------------------------------------------------
        # 2. Section 3: Methodology & Protocol Updates
        # -------------------------------------------------------------
        Write-Output "[2/6] Updating Section 3 Methodology & Experimental Protocol..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range

            if ($txt.StartsWith("3.1 LS-Face Architecture") -or $txt.StartsWith("3.1 LS-Face Selective")) {
                Replace-ParagraphText $p "3.1 LS-Face Selective-Computation Architecture" 'heading2'
            }
            elseif ($txt.StartsWith("3.2 Recognizer Selection") -or $txt.StartsWith("3.2 Recognizer and Compact")) {
                Replace-ParagraphText $p "3.2 Recognizer and Compact-LBPH Selection" 'heading2'
            }
            elseif ($txt.StartsWith("3.3 Threshold Calibration") -or $txt.StartsWith("3.3 Threshold Calibration and Frozen")) {
                Replace-ParagraphText $p "3.3 Threshold Calibration and Frozen Decision Policy" 'heading2'
            }
            elseif ($txt.StartsWith("3.4 Experimental Protocol")) {
                Replace-ParagraphText $p "3.4 Experimental Protocol" 'heading2'
            }
            elseif ($txt.StartsWith("To evaluate the proposed architecture") -or $txt.StartsWith("To evaluate the cascade")) {
                Replace-ParagraphText $p $content.protocol
            }
        }

        # -------------------------------------------------------------
        # 3. Tables 5 & 6 Update
        # -------------------------------------------------------------
        Write-Output "[3/6] Updating Table 5 (Frozen Thresholds) and Table 6 (LFW Robustness)..."
        if ($document.Tables.Count -ge 5) {
            $t5 = $document.Tables.Item(5)
            $t5Data = @(
                @('Boundary', 'Frozen value', 'Role'),
                @('LBPH accept', '52.3724', 'Early accept (10 ppm FAR on LFW dev)'),
                @('SFace accept', 'L2 <= 1.0313; cosine >= 0.363', 'Escalated accept (10 ppm FAR)'),
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
        # 4. Section 4.2: Corrected LFW Robustness Test
        # -------------------------------------------------------------
        Write-Output "[4/6] Updating Section 4.2 Corrected LFW Robustness Text..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range

            if ($txt.StartsWith("Table 5 reports the controlled self-match") -or $txt.StartsWith("Table 6 reports the controlled self-match") -or $txt.StartsWith("Table 5 reports the corrected controlled") -or $txt.StartsWith("Table 6 reports the corrected controlled")) {
                Replace-ParagraphText $p $content.robustness_lfw
            }
        }

        # -------------------------------------------------------------
        # 5. Section 5 & 6: Discussion & Conclusion
        # -------------------------------------------------------------
        Write-Output "[5/6] Updating Discussion and Conclusion..."
        for ($i = 1; $i -le $document.Paragraphs.Count; $i++) {
            $p = $document.Paragraphs.Item($i)
            $txt = Get-CleanText $p.Range

            if ($txt.StartsWith("5 Discussion")) {
                Replace-ParagraphText $p "5 Discussion" 'heading1'
            }
            elseif ($txt.StartsWith("The experimental results demonstrate four primary findings") -or $txt.StartsWith("The experimental results demonstrate three primary findings")) {
                Replace-ParagraphText $p $content.discussion_intro
            }
            elseif ($txt.StartsWith("6 Conclusion")) {
                Replace-ParagraphText $p "6 Conclusion" 'heading1'
            }
            elseif ($txt.StartsWith("LS-Face demonstrates that hybrid face recognition cascades") -or $txt.StartsWith("This study presented LS-Face")) {
                Replace-ParagraphText $p $content.conclusion
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

    # Restore bit-identical VBA part
    Write-Output "Verifying and restoring bit-identical VBA project part ($vbaPart)..."
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
Write-Output " BUILD COMPLETED: 021_MAJOR MANUSCRIPT READY"
Write-Output " Output DOCM: $outputPath"
Write-Output " Output PDF:  $pdfPath"
Write-Output "================================================================================"
