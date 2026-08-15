[CmdletBinding()]
param(
    [string]$Source = 'docs\manuscript\versions\013_lsface_dl-trio-selection-final.docm',
    [string]$Output = 'docs\manuscript\versions\014_lsface_dl-trio-selection-final-verified.docm',
    [string]$CurrentManuscript = 'docs\manuscript\lsface.docm',
    [string]$VbaBaseline = 'docs\manuscript\versions\010_lsface_before-dl-trio-selection.docm',
    [string]$PdfOutput = "$env:TEMP\lsface_014_dl-trio-selection-final-verified.pdf"
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

$sourcePath = (Resolve-Path -LiteralPath $Source).Path
$outputPath = Resolve-WorkspacePath $Output
$currentPath = Resolve-WorkspacePath $CurrentManuscript
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
try {
    $document = $word.Documents.Open($outputPath, $false, $false)

    $robustnessTable = $document.Tables.Item(5)
    $farCell = $robustnessTable.Cell(4, 4)
    $mojibakeLessOrEqual = ([string][char]0x00E2) + ([string][char]0x2030) + ([string][char]0x00A4) + '0.0020'
    if ((Get-CleanText $farCell.Range) -ne $mojibakeLessOrEqual) {
        throw 'Expected malformed FAR cell was not found.'
    }
    $farRange = $farCell.Range.Duplicate
    $farRange.End = $farRange.End - 1
    $farRange.Text = ([string][char]0x2264) + '0.0020'
    $farRange.Font.Name = 'Times New Roman'
    $farRange.Font.Size = 9
    $farRange.Font.Bold = 0
    $farRange.Font.Italic = 0
    $farRange.ParagraphFormat.Alignment = 1
    $farRange.ParagraphFormat.SpaceBefore = 0
    $farRange.ParagraphFormat.SpaceAfter = 0

    $figureLead = Find-ParagraphExact $document 'Figure 1 shows the frozen boundaries against the fresh LSDB clean-impostor distribution; it is not a re-calibration.'
    $figureLead.Range.ParagraphFormat.KeepWithNext = -1
    $figureLead.Range.ParagraphFormat.KeepTogether = -1
    $figureLead.Range.ParagraphFormat.PageBreakBefore = -1

    $document.Repaginate()
    $pageCount = [int]$document.ComputeStatistics(2)
    $document.Save()
    $document.ExportAsFixedFormat($PdfOutput, 17)
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
