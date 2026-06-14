param([switch]$Confirm)

$dir = Join-Path $PSScriptRoot "..\rip"
$files = Get-ChildItem $dir -File | Where-Object { $_.Name -match '&Itemid=(\d+)\.html$' }

$groups = $files |
    Group-Object { $_.Name -replace '&Itemid=\d+\.html$', '' } |
    Where-Object { $_.Count -gt 1 }

$toDelete = @()

foreach ($g in $groups) {
    $sorted = $g.Group | Sort-Object {
        [int]([regex]::Match($_.Name, '&Itemid=(\d+)\.html$').Groups[1].Value)
    }
    $keeper = $sorted[0]
    $dupes  = $sorted[1..($sorted.Count - 1)]

    Write-Host "KEEP: $($keeper.Name)"
    foreach ($d in $dupes) {
        Write-Host "  DEL: $($d.Name)"
        $toDelete += $d
    }
}

Write-Host "`nTotal to delete: $($toDelete.Count)"

if ($Confirm) {
    $toDelete | Remove-Item -Force
    Write-Host "Done."
} else {
    Write-Host "(dry-run -- pass -Confirm to delete)"
}
