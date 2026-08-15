[CmdletBinding()]
param(
    [string]$Baseline = 'docs\manuscript\versions\010_lsface_dl-trio-selection-final-verified.docm',
    [string]$Output = 'docs\manuscript\versions\010b_lsface_dl-trio-selection-final-verified.docm'
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

function Find-ParagraphMatching {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)][string]$Pattern
    )

    foreach ($paragraph in $Document.Paragraphs) {
        if ((Get-CleanText $paragraph.Range) -match $Pattern) { return $paragraph }
    }
    throw "Could not find paragraph matching: $Pattern"
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
    $range.End = $range.End - 1 # Preserve Word's end-of-cell marker.
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

function Write-LncsTable {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)]$Table,
        [Parameter(Mandatory = $true)][object[]]$Values,
        [Parameter(Mandatory = $true)][double[]]$Widths
    )

    if ($Table.Rows.Count -ne $Values.Count -or $Table.Columns.Count -ne $Values[0].Count) {
        throw 'Table 4 dimensions do not match recorded values.'
    }
    Format-LncsTable $Table $Widths
    for ($row = 1; $row -le $Table.Rows.Count; $row++) {
        for ($column = 1; $column -le $Table.Columns.Count; $column++) {
            $alignment = if ($column -eq 1) { 0 } else { 1 }
            Set-CellText $Document $Table.Cell($row, $column) $Values[$row - 1][$column - 1] ($row -eq 1) $alignment
        }
    }
}

$baselinePath = (Resolve-Path -LiteralPath $Baseline).Path
$outputPath = Resolve-WorkspacePath $Output
if (Test-Path -LiteralPath $outputPath) { throw "Refusing to overwrite existing manuscript archive: $outputPath" }

$vbaPart = 'word/vbaProject.bin'
$baselineFileHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $baselinePath).Hash
$baselineVbaHash = Get-ZipPartHash $baselinePath $vbaPart
$stagePath = Join-Path ([System.IO.Path]::GetTempPath()) ("lsface_010b_{0}.docm" -f [guid]::NewGuid().ToString('N'))

try {
    Copy-Item -LiteralPath $baselinePath -Destination $stagePath

    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $null
    try {
        $document = $word.Documents.Open($stagePath, $false, $false)
        $table = $document.Tables.Item(4)
        if ($table.Rows.Count -ne 4 -or $table.Columns.Count -ne 3 -or (Get-CleanText $table.Cell(1, 1).Range) -ne 'Boundary') {
            throw 'Expected Table 4 frozen-operating-point layout was not found.'
        }
        $caption = Find-ParagraphMatching $document '^Table 4\. Final frozen operating points\.$'
        if ($caption.Range.End -gt $table.Range.Start) { throw 'Table 4 caption no longer precedes the expected table.' }

        $table.Columns.Add($table.Columns.Item(3)) | Out-Null
        Write-LncsTable $document $table @(
            @('Boundary', 'Source / native scale', 'Current threshold', 'Role'),
            @('LBPH tau_accept', 'LFW; predict_collect', '<= 67.03325520645528', 'accept'),
            @('SFace L2', 'LFW; SFace L2', '<= 1.0313; cosine >= 0.363', 'escalated accept'),
            @('LBPH tau_reject', 'LFW trade-off; predict_collect', '>= 140.13', 'permissive reject edge')
        ) @(75, 85, 105, 80)
        $document.Repaginate()
        $document.Save()
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
    if ((Get-ZipPartHash $stagePath $vbaPart) -ne $baselineVbaHash) { throw 'VBA project hash differs after restoration.' }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $baselinePath).Hash -ne $baselineFileHash) { throw 'Named baseline changed during production.' }

    Copy-Item -LiteralPath $stagePath -Destination $outputPath
    if ((Get-ZipPartHash $outputPath $vbaPart) -ne $baselineVbaHash) { throw 'Output VBA project hash differs from named baseline.' }
    Write-Output "Created $outputPath"
    Write-Output "VBA SHA256 $baselineVbaHash"
}
finally {
    if (Test-Path -LiteralPath $stagePath) { Remove-Item -LiteralPath $stagePath -Force }
    $repackedStage = "$stagePath.repacked"
    if (Test-Path -LiteralPath $repackedStage) { Remove-Item -LiteralPath $repackedStage -Force }
}
