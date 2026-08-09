param([string]$Root = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))

$ErrorActionPreference = 'Stop'
$template = Join-Path $Root 'docs\splnproc2510.docm'
$output = Join-Path $Root 'docs\lsface_hybrid_independence_testing.docm'
$sourcePaper = Join-Path $Root 'classical-cv\docs\PAPER.md'
$sourceDirectory = Split-Path -Parent $sourcePaper
$wdAlertsNone = 0
$msoAutomationSecurityForceDisable = 3
$wdAlignParagraphCenter = 1
$wdBorderTop = -1
$wdBorderBottom = -3
$wdLineStyleNone = 0
$wdLineStyleSingle = 1
$wdLineWidth075pt = 6
$wdLineWidth150pt = 12
$script:firstBodyParagraph = $false

function Get-VbaProjectHash {
    param([string]$Path)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($Path)
    try {
        $entry = $archive.GetEntry('word/vbaProject.bin')
        if ($null -eq $entry) { throw "No VBA project was found in $Path" }
        $stream = $entry.Open()
        try {
            $sha = [System.Security.Cryptography.SHA256]::Create()
            try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '') }
            finally { $sha.Dispose() }
        }
        finally { $stream.Dispose() }
    }
    finally { $archive.Dispose() }
}

function Restore-TemplateVbaProject {
    param([string]$TemplatePath, [string]$OutputPath)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $temporary = "$OutputPath.repack"
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
    $templateArchive = [System.IO.Compression.ZipFile]::OpenRead($TemplatePath)
    $outputArchive = [System.IO.Compression.ZipFile]::OpenRead($OutputPath)
    $newArchive = [System.IO.Compression.ZipFile]::Open($temporary, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        $templateVba = $templateArchive.GetEntry('word/vbaProject.bin')
        if ($null -eq $templateVba) { throw 'The template does not contain word/vbaProject.bin.' }
        foreach ($entry in $outputArchive.Entries) {
            $newEntry = $newArchive.CreateEntry($entry.FullName, [System.IO.Compression.CompressionLevel]::Optimal)
            $sourceEntry = if ($entry.FullName -eq 'word/vbaProject.bin') { $templateVba } else { $entry }
            $source = $sourceEntry.Open()
            $destination = $newEntry.Open()
            try { $source.CopyTo($destination) }
            finally { $destination.Dispose(); $source.Dispose() }
        }
    }
    finally {
        $newArchive.Dispose()
        $outputArchive.Dispose()
        $templateArchive.Dispose()
    }
    Move-Item -LiteralPath $temporary -Destination $OutputPath -Force
}

function Remove-Markdown {
    param([string]$Text)
    $clean = $Text.Trim()
    $clean = $clean -replace '\*\*', ''
    $clean = $clean -replace '`', ''
    $clean = $clean -replace '^\*', ''
    $clean = $clean -replace '\*$', ''
    return $clean.Trim()
}

function Add-Paragraph {
    param([string]$Text, [string]$Style = 'Normal', [int]$Alignment = -1)
    $start = $doc.Content.End - 1
    $insertion = $doc.Range($start, $start)
    $insertion.InsertAfter($Text + "`r")
    $inserted = $doc.Range($start, $start + $Text.Length)
    $paragraph = $inserted.Paragraphs.Item(1)
    $paragraph.Range.Style = $Style
    if ($Alignment -ge 0) { $paragraph.Range.ParagraphFormat.Alignment = $Alignment }
}

function Add-BodyParagraph {
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return }
    $style = if ($script:firstBodyParagraph) { 'p1a' } else { 'Normal' }
    Add-Paragraph $Text $style
    $script:firstBodyParagraph = $false
}

function Add-Heading {
    param([string]$Text, [int]$Level = 1)
    $style = if ($Level -eq 1) { 'heading1' } else { 'heading2' }
    Add-Paragraph $Text $style
    $script:firstBodyParagraph = $true
}

function Add-Figure {
    param([string]$Path, [string]$Caption)
    if (-not (Test-Path -LiteralPath $Path)) {
        Add-BodyParagraph "[Figure source unavailable: $Path]"
        return
    }
    $anchor = $doc.Range($doc.Content.End - 1, $doc.Content.End - 1)
    $shape = $doc.InlineShapes.AddPicture($Path, $false, $true, $anchor)
    if ($shape.Width -gt 380) { $shape.Width = 380 }
    $shape.Range.ParagraphFormat.Alignment = $wdAlignParagraphCenter
    Add-Paragraph $Caption 'figurecaption'
    $script:firstBodyParagraph = $true
}

function Add-Table {
    param([string]$Caption, [string[]]$Lines)
    if ($Lines.Count -lt 2) { return }
    $rows = @()
    foreach ($line in $Lines) {
        if ($line -match '^\|?\s*:?-{3,}') { continue }
        $cells = $line.Trim().Trim('|').Split('|') | ForEach-Object { Remove-Markdown $_ }
        $rows += ,@($cells)
    }
    if ($rows.Count -lt 2) { return }
    if ($Caption) { Add-Paragraph $Caption 'tablecaption' }
    $columnCount = $rows[0].Count
    $anchor = $doc.Range($doc.Content.End - 1, $doc.Content.End - 1)
    $table = $doc.Tables.Add($anchor, $rows.Count, $columnCount)
    $table.Rows.Item(1).Range.Font.Bold = 1
    for ($r = 0; $r -lt $rows.Count; $r++) {
        for ($c = 0; $c -lt $columnCount; $c++) {
            $value = if ($c -lt $rows[$r].Count) { [string]$rows[$r][$c] } else { '' }
            $table.Cell($r + 1, $c + 1).Range.Text = $value
        }
    }
    # LNCS sample table design: rules only at the table top, below the header,
    # and at the table bottom. Keep all vertical and internal body borders off.
    $table.Borders.Enable = $wdLineStyleNone
    $header = $table.Rows.Item(1).Range
    $header.Borders.Item($wdBorderTop).LineStyle = $wdLineStyleSingle
    $header.Borders.Item($wdBorderTop).LineWidth = $wdLineWidth150pt
    $header.Borders.Item($wdBorderBottom).LineStyle = $wdLineStyleSingle
    $header.Borders.Item($wdBorderBottom).LineWidth = $wdLineWidth075pt
    $lastRow = $table.Rows.Item($table.Rows.Count).Range
    $lastRow.Borders.Item($wdBorderBottom).LineStyle = $wdLineStyleSingle
    $lastRow.Borders.Item($wdBorderBottom).LineWidth = $wdLineWidth150pt
    $doc.Range($doc.Content.End - 1, $doc.Content.End - 1).InsertAfter("`r")
    $script:firstBodyParagraph = $true
}

function Flush-SourceParagraph {
    param([System.Collections.Generic.List[string]]$Lines)
    if ($Lines.Count -eq 0) { return }
    $text = Remove-Markdown (($Lines | ForEach-Object { $_.Trim() }) -join ' ')
    $Lines.Clear()
    if ($text -match '^[A-Za-z][A-Za-z0-9_]*\s*=.*\(\d+\)$') {
        Add-Paragraph $text 'equation' $wdAlignParagraphCenter
        $script:firstBodyParagraph = $true
    } else {
        Add-BodyParagraph $text
    }
}

if (-not (Test-Path -LiteralPath $template)) { throw "Template not found: $template" }
if (-not (Test-Path -LiteralPath $sourcePaper)) { throw "Source paper not found: $sourcePaper" }
if (Test-Path -LiteralPath $output) { Remove-Item -LiteralPath $output -Force }
$templateVbaHash = Get-VbaProjectHash $template
Copy-Item -LiteralPath $template -Destination $output

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = $wdAlertsNone
$word.AutomationSecurity = $msoAutomationSecurityForceDisable

try {
    $doc = $word.Documents.Open($output, $false, $false)
    $doc.Content.Delete()

    Add-Paragraph 'Facial Recognition Using Hybrid Technologies Based on Independence Testing' 'papertitle' $wdAlignParagraphCenter
    Add-Paragraph 'Andrew P. Eroyla*, Kyle Yuan L. Uy*, John Roland L. Octavio*, Jim Jonathan C. Decripito*, Loreto B. Damasco*, and Weon Geon Oh*+' 'author' $wdAlignParagraphCenter
    Add-Paragraph '*Computer Science Department, College of Computing Studies, University of St. La Salle - Bacolod, Bacolod City, Philippines' 'address' $wdAlignParagraphCenter
    Add-Paragraph '+THINKforBL, Korea' 'address' $wdAlignParagraphCenter
    Add-Paragraph 'Abstract. [Reserved for Doc Oh.]' 'abstract'
    Add-Paragraph 'Keywords: face recognition, independence testing, threshold determination, hybrid method, classical computer vision, edge deployment' 'keywords'
    Add-Heading 'Introduction'
    Add-Paragraph '[Reserved for Doc Oh.]' 'p1a'

    $lines = Get-Content -LiteralPath $sourcePaper -Encoding UTF8
    $paragraphLines = [System.Collections.Generic.List[string]]::new()
    $tableLines = [System.Collections.Generic.List[string]]::new()
    $inSourceBody = $false
    $inReferences = $false
    $pendingTableCaption = $null
    $pendingFigureCaption = $null

    foreach ($rawLine in $lines) {
        $line = $rawLine.TrimEnd()
        if ($line -match '^##\s+2\.\s+Related Work') { $inSourceBody = $true }
        if (-not $inSourceBody) { continue }

        if ($line -match '^\|') {
            Flush-SourceParagraph $paragraphLines
            $tableLines.Add($line)
            continue
        }
        if ($tableLines.Count -gt 0) {
            Add-Table $pendingTableCaption $tableLines.ToArray()
            $tableLines.Clear()
            $pendingTableCaption = $null
        }

        if ([string]::IsNullOrWhiteSpace($line)) {
            Flush-SourceParagraph $paragraphLines
            continue
        }
        if ($line -eq '---') { continue }
        if ($line -match '^\*\*Table\s+\d+\.\s*(.+)\*\*$') {
            Flush-SourceParagraph $paragraphLines
            $pendingTableCaption = "Table $($line -replace '^\*\*Table\s+(\d+\.)\s*', '$1 ' -replace '\*\*$', '')"
            continue
        }
        if ($line -match '^\*Fig\.\s+\d+\.\s*(.+)\*$') {
            Flush-SourceParagraph $paragraphLines
            $pendingFigureCaption = Remove-Markdown $line
            continue
        }
        if ($line -match '^!\[[^\]]*\]\(([^)]+)\)$') {
            Flush-SourceParagraph $paragraphLines
            $relative = $matches[1]
            $figurePath = [System.IO.Path]::GetFullPath((Join-Path $sourceDirectory $relative))
            $caption = if ($pendingFigureCaption) { $pendingFigureCaption } else { "Figure: $(Remove-Markdown $line)" }
            Add-Figure $figurePath $caption
            $pendingFigureCaption = $null
            continue
        }
        if ($line -match '^##\s+(.+)$') {
            Flush-SourceParagraph $paragraphLines
            $heading = $matches[1] -replace '^\d+\.\s*', ''
            if ($heading -eq 'Introduction') { continue }
            Add-Heading (Remove-Markdown $heading) 1
            $inReferences = ($heading -eq 'References')
            continue
        }
        if ($line -match '^###\s+(.+)$') {
            Flush-SourceParagraph $paragraphLines
            $heading = $matches[1] -replace '^\d+(\.\d+)+\s*', ''
            Add-Heading (Remove-Markdown $heading) 2
            continue
        }
        if ($inReferences -and $line -match '^\[\d+\]\s+(.+)$') {
            Flush-SourceParagraph $paragraphLines
            Add-Paragraph (Remove-Markdown $matches[1]) 'referenceitem'
            continue
        }
        $paragraphLines.Add($line)
    }
    Flush-SourceParagraph $paragraphLines
    if ($tableLines.Count -gt 0) { Add-Table $pendingTableCaption $tableLines.ToArray() }

    $doc.Save()
    $doc.Close($false)
    $word.Quit()
    Restore-TemplateVbaProject $template $output
    $outputVbaHash = Get-VbaProjectHash $output
    if ($templateVbaHash -ne $outputVbaHash) { throw 'The template VBA project was not preserved.' }
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc)
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    Write-Output "Created $output from PAPER.md with the original VBA project preserved."
}
catch {
    if ($doc) { try { $doc.Close($false) } catch {} }
    if ($word) { try { $word.Quit() } catch {} }
    throw
}
