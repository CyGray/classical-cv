[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$DocumentPath,

    [string]$BaselinePath,

    [int[]]$Pages = @(),

    [int]$MaxPages = 13,

    [string]$ReferenceTemplatePath = (Join-Path $PSScriptRoot '..\..\docs\manuscript\sample\sample.docm'),

    [bool]$RequireCaptionStyleCompliance = $true,

    [string]$OutputDirectory = (Join-Path $env:TEMP "word-layout-inspection")
)

$ErrorActionPreference = 'Stop'

function Get-VbaHash {
    param([Parameter(Mandatory = $true)][string]$Path)

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($Path)
    try {
        $entry = $archive.GetEntry('word/vbaProject.bin')
        if (-not $entry) { return $null }
        $stream = $entry.Open()
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
        }
        finally {
            $sha.Dispose()
            $stream.Dispose()
        }
    }
    finally {
        $archive.Dispose()
    }
}

function Get-StyleName {
    param([Parameter(Mandatory = $true)]$Range)

    try { return [string]$Range.Style.NameLocal }
    catch { return [string]$Range.Style }
}

function Get-StyleSnapshot {
    param([Parameter(Mandatory = $true)]$Style)

    return [ordered]@{
        FontName = [string]$Style.Font.Name
        FontSize = [double]$Style.Font.Size
        Bold = [int]$Style.Font.Bold
        Italic = [int]$Style.Font.Italic
        Alignment = [int]$Style.ParagraphFormat.Alignment
        SpaceBefore = [double]$Style.ParagraphFormat.SpaceBefore
        SpaceAfter = [double]$Style.ParagraphFormat.SpaceAfter
        LineSpacing = [double]$Style.ParagraphFormat.LineSpacing
        KeepWithNext = [int]$Style.ParagraphFormat.KeepWithNext
        KeepTogether = [int]$Style.ParagraphFormat.KeepTogether
        PageBreakBefore = [int]$Style.ParagraphFormat.PageBreakBefore
    }
}

function Get-RangeFormattingSnapshot {
    param([Parameter(Mandatory = $true)]$Range)

    return [ordered]@{
        FontName = [string]$Range.Font.Name
        FontSize = [double]$Range.Font.Size
        Bold = [int]$Range.Font.Bold
        Italic = [int]$Range.Font.Italic
        Alignment = [int]$Range.ParagraphFormat.Alignment
        SpaceBefore = [double]$Range.ParagraphFormat.SpaceBefore
        SpaceAfter = [double]$Range.ParagraphFormat.SpaceAfter
        LineSpacing = [double]$Range.ParagraphFormat.LineSpacing
        KeepWithNext = [int]$Range.ParagraphFormat.KeepWithNext
        KeepTogether = [int]$Range.ParagraphFormat.KeepTogether
        PageBreakBefore = [int]$Range.ParagraphFormat.PageBreakBefore
    }
}

function Compare-Formatting {
    param(
        [Parameter(Mandatory = $true)]$Actual,
        [Parameter(Mandatory = $true)]$Expected
    )

    $mismatches = @()
    foreach ($name in @('FontName', 'Bold', 'Italic', 'Alignment', 'KeepWithNext', 'KeepTogether', 'PageBreakBefore')) {
        if ([string]$Actual[$name] -ne [string]$Expected[$name]) { $mismatches += $name }
    }
    foreach ($name in @('FontSize', 'SpaceBefore', 'SpaceAfter', 'LineSpacing')) {
        if ([Math]::Abs(([double]$Actual[$name]) - ([double]$Expected[$name])) -gt 0.05) { $mismatches += $name }
    }
    return ,$mismatches
}

function Get-NearestFollowingTable {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)][int]$Position
    )

    $match = $null
    foreach ($table in $Document.Tables) {
        if ($table.Range.Start -ge $Position -and ($null -eq $match -or $table.Range.Start -lt $match.Range.Start)) { $match = $table }
    }
    return $match
}

function Get-NearestPrecedingInlineShape {
    param(
        [Parameter(Mandatory = $true)]$Document,
        [Parameter(Mandatory = $true)][int]$Position
    )

    $match = $null
    foreach ($shape in $Document.InlineShapes) {
        if ($shape.Range.End -le $Position -and ($null -eq $match -or $shape.Range.End -gt $match.Range.End)) { $match = $shape }
    }
    return $match
}

$resolvedDocument = (Resolve-Path -LiteralPath $DocumentPath).Path
if ($BaselinePath) { $resolvedBaseline = (Resolve-Path -LiteralPath $BaselinePath).Path }
if ($RequireCaptionStyleCompliance) { $resolvedReferenceTemplate = (Resolve-Path -LiteralPath $ReferenceTemplatePath).Path }

if ($Pages.Count -gt 0) {
    Add-Type -AssemblyName System.Drawing
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class WordLayoutInspectionWindow {
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll", SetLastError = true)] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint flags);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
'@
    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
}

$word = New-Object -ComObject Word.Application
$document = $null
$referenceDocument = $null
try {
    # Do not run document VBA while inspecting it.
    $word.AutomationSecurity = 3
    $word.Visible = $Pages.Count -gt 0
    if ($word.Visible) { $word.WindowState = 1 }
    $document = $word.Documents.Open($resolvedDocument, $false, $true)
    if ($RequireCaptionStyleCompliance) { $referenceDocument = $word.Documents.Open($resolvedReferenceTemplate, $false, $true) }
    # Opening the reference template makes it the active Word window. Reactivate
    # the requested document before either paginating or capturing it.
    $document.Activate()
    if ($word.ActiveDocument.FullName -ne $resolvedDocument) { throw "Word did not activate the requested document for inspection: $resolvedDocument" }
    $document.Repaginate()

    $pageSetup = $document.Sections.Item(1).PageSetup
    $usableWidth = [Math]::Round(
        ([double]$pageSetup.PageWidth - [double]$pageSetup.LeftMargin - [double]$pageSetup.RightMargin - [double]$pageSetup.Gutter), 1)
    $tableChecks = @()
    $tableNumber = 0
    foreach ($table in $document.Tables) {
        $tableNumber++
        $tableWidth = 0.0
        foreach ($column in $table.Columns) { $tableWidth += [double]$column.Width }
        $tableWidth = [Math]::Round($tableWidth, 1)
        $tableChecks += [pscustomobject]@{
            Table = $tableNumber
            WidthPt = $tableWidth
            UsableWidthPt = $usableWidth
            FitsTextBlock = $tableWidth -le $usableWidth
        }
    }

    $captionChecks = @()
    $captionStyleDefinitions = @()
    if ($RequireCaptionStyleCompliance) {
        foreach ($styleName in @('tablecaption', 'figurecaption')) {
            $actualStyle = Get-StyleSnapshot $document.Styles.Item($styleName)
            $expectedStyle = Get-StyleSnapshot $referenceDocument.Styles.Item($styleName)
            $mismatches = Compare-Formatting $actualStyle $expectedStyle
            $captionStyleDefinitions += [pscustomobject]@{
                Style = $styleName
                MatchesReference = $mismatches.Count -eq 0
                Mismatches = @($mismatches)
                Actual = $actualStyle
                Expected = $expectedStyle
            }
        }

        foreach ($paragraph in $document.Paragraphs) {
            $captionText = (($paragraph.Range.Text -replace '[\r\a]', ' ') -replace '\s+', ' ').Trim()
            $kind = $null
            $number = $null
            $expectedStyleName = $null
            if ($captionText -match '^Table\s+(\d+)\.') {
                $kind = 'Table'; $number = [int]$matches[1]; $expectedStyleName = 'tablecaption'
            }
            elseif ($captionText -match '^Fig\.\s*(\d+)\.') {
                $kind = 'Figure'; $number = [int]$matches[1]; $expectedStyleName = 'figurecaption'
            }
            if (-not $expectedStyleName) { continue }

            $actualStyleName = Get-StyleName $paragraph.Range
            $actualFormatting = Get-RangeFormattingSnapshot $paragraph.Range
            $expectedFormatting = Get-StyleSnapshot $referenceDocument.Styles.Item($expectedStyleName)
            $formatMismatches = Compare-Formatting $actualFormatting $expectedFormatting
            if ($kind -eq 'Table') {
                $object = Get-NearestFollowingTable $document $paragraph.Range.End
                $placementPass = $null -ne $object
            }
            else {
                $object = Get-NearestPrecedingInlineShape $document $paragraph.Range.Start
                $placementPass = $null -ne $object
            }
            $captionChecks += [pscustomobject]@{
                Caption = "$kind $number"
                Page = [int]$paragraph.Range.Information(3)
                Style = $actualStyleName
                ExpectedStyle = $expectedStyleName
                StyleMatches = $actualStyleName -eq $expectedStyleName
                EffectiveFormattingMatchesReference = $formatMismatches.Count -eq 0
                FormattingMismatches = @($formatMismatches)
                CorrectRelativeObject = $placementPass
                Text = $captionText
            }
        }
    }

    $captures = @()
    if ($Pages.Count -gt 0) {
        $document.Activate()
        if ($word.ActiveDocument.FullName -ne $resolvedDocument) { throw "Word changed active document before layout capture: $resolvedDocument" }
        $word.ActiveWindow.View.Type = 3 # wdPrintView
        $word.ActiveWindow.View.Zoom.Percentage = 115
        foreach ($page in $Pages) {
            $word.Selection.GoTo(1, 1, $page) | Out-Null # wdGoToPage, wdGoToAbsolute
            Start-Sleep -Milliseconds 750
            $window = [IntPtr]$word.ActiveWindow.Hwnd
            $path = Join-Path $OutputDirectory ("page-{0}.png" -f $page)
            $captured = $false
            foreach ($attempt in 1..3) {
                [WordLayoutInspectionWindow]::SetForegroundWindow($window) | Out-Null
                Start-Sleep -Milliseconds 300
                [WordLayoutInspectionWindow+RECT]$rect = New-Object WordLayoutInspectionWindow+RECT
                [WordLayoutInspectionWindow]::GetWindowRect($window, [ref]$rect) | Out-Null
                $bitmap = New-Object System.Drawing.Bitmap ($rect.Right - $rect.Left), ($rect.Bottom - $rect.Top)
                $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
                try {
                    $graphicsHdc = $graphics.GetHdc()
                    try { $printed = [WordLayoutInspectionWindow]::PrintWindow($window, $graphicsHdc, 0) }
                    finally { $graphics.ReleaseHdc($graphicsHdc) }
                    if (-not $printed) { continue }
                    $bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
                    $captured = $true
                }
                finally {
                    $graphics.Dispose()
                    $bitmap.Dispose()
                }
                break
            }
            if (-not $captured) { throw "Could not foreground the Word window to capture page $page." }
            $captures += $path
        }
    }

    $result = [pscustomobject]@{
        Document = $resolvedDocument
        Pages = [int]$document.ComputeStatistics(2) # wdStatisticPages
        MaxPages = $MaxPages
        TableChecks = @($tableChecks)
        MacroHashMatchesBaseline = if ($BaselinePath) { (Get-VbaHash $resolvedDocument) -eq (Get-VbaHash $resolvedBaseline) } else { $null }
        CaptionStyleDefinitions = @($captionStyleDefinitions)
        CaptionChecks = @($captionChecks)
        Captures = @($captures)
    }
    $result | ConvertTo-Json -Depth 4

    if ($result.Pages -gt $MaxPages) { throw "Page budget exceeded: $($result.Pages) > $MaxPages." }
    if ($tableChecks | Where-Object { -not $_.FitsTextBlock }) { throw 'One or more tables exceed the usable text width.' }
    if ($BaselinePath -and -not $result.MacroHashMatchesBaseline) { throw 'VBA project hash differs from baseline.' }
    if ($RequireCaptionStyleCompliance -and (($captionStyleDefinitions | Where-Object { -not $_.MatchesReference }) -or ($captionChecks | Where-Object { -not $_.StyleMatches -or -not $_.EffectiveFormattingMatchesReference -or -not $_.CorrectRelativeObject }))) {
        throw 'Caption-style validation failed: use the reference tablecaption/figurecaption styles without direct-format overrides and keep each caption on its correct side of its object.'
    }
}
finally {
    if ($referenceDocument) {
        $referenceDocument.Close(0)
        [Runtime.InteropServices.Marshal]::FinalReleaseComObject($referenceDocument) | Out-Null
    }
    if ($document) {
        $document.Close(0)
        [Runtime.InteropServices.Marshal]::FinalReleaseComObject($document) | Out-Null
    }
    if ($word) {
        $word.Quit()
        [Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) | Out-Null
    }
}
