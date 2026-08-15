[CmdletBinding()]
param(
    [string]$Source = 'docs\manuscript\versions\012_lsface_dl-trio-selection-layout-fixed.docm',
    [string]$Output = 'docs\manuscript\versions\013_lsface_dl-trio-selection-final.docm',
    [string]$CurrentManuscript = 'docs\manuscript\lsface.docm',
    [string]$ReferenceTemplate = 'docs\manuscript\sample\sample.docm',
    [string]$VbaBaseline = 'docs\manuscript\versions\010_lsface_before-dl-trio-selection.docm',
    [string]$PdfOutput = "$env:TEMP\lsface_013_dl-trio-selection-final.pdf"
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
        if ($null -eq $referencePart) { throw "Missing $PartName in VBA baseline." }
        foreach ($entry in $target.Entries) {
            $newEntry = $replacement.CreateEntry($entry.FullName, [System.IO.Compression.CompressionLevel]::Optimal)
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

function Apply-ParagraphStyle {
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

function Insert-ExternalParagraphsBeforeTable {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)]$Table,
        [Parameter(Mandatory = $true)][object[]]$Paragraphs
    )

    # Table.Range.Start is inside its first cell. The character immediately
    # preceding it is the terminating paragraph mark of the preceding body
    # paragraph. A leading paragraph mark splits that paragraph, leaving the
    # inserted text as true body paragraphs rather than table-cell content.
    $insertion = $Document.Range($Table.Range.Start - 1, $Table.Range.Start - 1)
    $text = ''
    foreach ($paragraph in $Paragraphs) { $text += "`r$($paragraph.Text)" }
    $insertion.Text = $text
    foreach ($paragraph in $Paragraphs) {
        Apply-ParagraphStyle $Document (Find-ParagraphExact $Document $paragraph.Text) $paragraph.Style
    }
}

$sourcePath = (Resolve-Path -LiteralPath $Source).Path
$outputPath = Resolve-WorkspacePath $Output
$currentPath = Resolve-WorkspacePath $CurrentManuscript
$referencePath = (Resolve-Path -LiteralPath $ReferenceTemplate).Path
$vbaBaselinePath = (Resolve-Path -LiteralPath $VbaBaseline).Path
if (Test-Path -LiteralPath $outputPath) { throw "Refusing to overwrite existing manuscript archive: $outputPath" }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outputPath) | Out-Null
Copy-Item -LiteralPath $sourcePath -Destination $outputPath

$vbaPart = 'word/vbaProject.bin'
$baselineVbaHash = Get-ZipPartHash $vbaBaselinePath $vbaPart
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

    $frozenTable = $document.Tables.Item(4)
    if ((Get-CleanText $frozenTable.Cell(1, 1).Range) -ne 'Boundary') {
        throw 'Expected frozen-point header cell was not found.'
    }
    Insert-ExternalParagraphsBeforeTable $document $frozenTable @(
        [pscustomobject]@{
            Text = 'LFW DB1 fixes the deployed native-score operating points before LSDB evaluation: LBPH tau_accept = 67.0333 (rank 165 of 16,522,626 unique impostor pairs; 9.986 ppm), SFace L2 = 1.0313 with cosine >= 0.363, and tau_reject = 140.13.'
            Style = 'Normal'
        },
        [pscustomobject]@{
            Text = 'Table 4. Final frozen operating points.'
            Style = 'tablecaption'
        }
    )

    $robustnessTable = $document.Tables.Item(5)
    if ((Get-CleanText $robustnessTable.Cell(1, 1).Range) -ne 'Mode') {
        throw 'Expected robustness header cell was not found.'
    }
    Insert-ExternalParagraphsBeforeTable $document $robustnessTable @(
        [pscustomobject]@{
            Text = 'Table 5 summarizes gallery/probe-disjoint LFW2 1-to-N identification robustness at the frozen deployment thresholds. Across all 41 modifications, SFace and the cascade retain 80.65% AR, whereas LBPH alone retains 1.41%. The cascade escalates 97.51% of probes to SFace; isolated latency is reported from a 575-identity subset.'
            Style = 'Normal'
        },
        [pscustomobject]@{
            Text = 'Table 5. LFW2 1-to-N identification robustness at frozen deployment thresholds.'
            Style = 'tablecaption'
        }
    )

    $pairedTable = $document.Tables.Item(6)
    if ((Get-CleanText $pairedTable.Cell(1, 1).Range) -ne 'LBPH outcome') {
        throw 'Expected paired-outcome header cell was not found.'
    }
    Insert-ExternalParagraphsBeforeTable $document $pairedTable @(
        [pscustomobject]@{
            Text = 'Table 6. Paired thresholded correct-identity outcomes on held-out LSDB-DL41 probes (n = 2,296).'
            Style = 'tablecaption'
        }
    )

    for ($index = 1; $index -le $document.Paragraphs.Count; $index++) {
        $paragraph = $document.Paragraphs.Item($index)
        $text = Get-CleanText $paragraph.Range
        if ($text -match '^Table\s+\d+\.') { Apply-ParagraphStyle $document $paragraph 'tablecaption' }
        elseif ($text -match '^Fig\.\s*\d+\.') { Apply-ParagraphStyle $document $paragraph 'figurecaption' }
    }

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

Restore-ZipPart $vbaBaselinePath $outputPath $vbaPart
$outputVbaHash = Get-ZipPartHash $outputPath $vbaPart
if ($outputVbaHash -ne $baselineVbaHash) { throw 'VBA hash mismatch after restoration.' }
Copy-Item -LiteralPath $outputPath -Destination $currentPath -Force
$currentVbaHash = Get-ZipPartHash $currentPath $vbaPart
if ($currentVbaHash -ne $baselineVbaHash) { throw 'Current manuscript VBA hash mismatch.' }

Write-Output "SOURCE_DOCM=$sourcePath"
Write-Output "DOCM=$outputPath"
Write-Output "CURRENT_DOCM=$currentPath"
Write-Output "PDF=$PdfOutput"
Write-Output "PAGES=$pageCount"
Write-Output "VBA_SHA256=$outputVbaHash"
