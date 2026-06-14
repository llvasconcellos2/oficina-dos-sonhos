param([switch]$Confirm)

$dir = "c:\Users\leona\Projects\leonardo\project_archive\oficina-dos-sonhos\rip"

# --- Phase 1a: Rename *.html files (strip &Itemid=XX before .html) ---
$htmlFiles = Get-ChildItem $dir -File | Where-Object { $_.Name -match '&Itemid=\d+\.html$' }
$renames = 0
$skipped = 0

foreach ($f in $htmlFiles) {
    $newName = $f.Name -replace '&Itemid=\d+\.html$', '.html'
    $newPath = Join-Path $f.DirectoryName $newName

    if (Test-Path $newPath) {
        Write-Host "SKIP (collision): $($f.Name)  -->  $newName"
        $skipped++
        continue
    }

    Write-Host "RENAME: $($f.Name)  -->  $newName"
    if ($Confirm) { Rename-Item $f.FullName $newName }
    $renames++
}

# --- Phase 1b: Rename extension-less files ending with &Itemid=XX ---
# These are Joomla format=X downloads (all PDFs in practice).
# Group by would-be target name; keep the lowest Itemid, delete higher duplicates, then rename.
$noExtFiles = Get-ChildItem $dir -File | Where-Object { $_.Name -match '&Itemid=\d+$' }

$pdfGroups = $noExtFiles | Group-Object {
    $fmt = if ($_.Name -match 'format=(\w+)') { $matches[1] } else { 'bin' }
    ($_.Name -replace '&Itemid=\d+$', '') + ".$fmt"
}

foreach ($g in $pdfGroups) {
    $sorted = $g.Group | Sort-Object {
        [int]([regex]::Match($_.Name, '&Itemid=(\d+)$').Groups[1].Value)
    }
    $keeper = $sorted[0]
    $dupes  = $sorted[1..($sorted.Count - 1)]

    foreach ($d in $dupes) {
        Write-Host "  DEL (dup): $($d.Name)"
        if ($Confirm) { Remove-Item $d.FullName -Force }
    }

    $fmt = if ($keeper.Name -match 'format=(\w+)') { $matches[1] } else { 'bin' }
    $newName = ($keeper.Name -replace '&Itemid=\d+$', '') + ".$fmt"
    Write-Host "RENAME: $($keeper.Name)  -->  $newName"
    if ($Confirm) { Rename-Item $keeper.FullName $newName }
    $renames++
}

Write-Host "`nRenames: $renames  Skipped: $skipped"

# --- Phase 2: Patch Itemid references inside all HTML files ---
# .html links:      &amp;Itemid=XX.html  and  &Itemid=XX.html  -> .html
# format=X links:   &amp;Itemid=XX       and  &Itemid=XX       -> .<format>
# The format links appear without .html, so (?!\.html) guards against double-patching.
# Since all remaining non-.html Itemid links are PDFs, .pdf is the correct extension.
$allHtml = Get-ChildItem $dir -Recurse -Filter '*.html'
$patched = 0

foreach ($h in $allHtml) {
    $content = Get-Content $h.FullName -Raw -Encoding UTF8
    $updated = $content `
        -replace '&amp;Itemid=\d+\.html', '.html' `
        -replace '&Itemid=\d+\.html',     '.html' `
        -replace '&amp;Itemid=\d+(?!\.)', '.pdf'  `
        -replace '&Itemid=\d+(?!\.)' ,    '.pdf'

    if ($updated -ne $content) {
        Write-Host "PATCH: $($h.Name)"
        if ($Confirm) { Set-Content $h.FullName $updated -Encoding UTF8 -NoNewline }
        $patched++
    }
}

Write-Host "Patched: $patched HTML files"
if (-not $Confirm) { Write-Host "(dry-run -- pass -Confirm to apply)" }
