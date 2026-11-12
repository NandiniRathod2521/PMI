$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$ghentRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot 'data/raw/ghent'))
$ghentPrefix = $ghentRoot + [IO.Path]::DirectorySeparatorChar
$inventoryPath = Join-Path $projectRoot 'data/processed/external_inventory/ghent_projects_for_review.csv'
$projects = @(Import-Csv -LiteralPath $inventoryPath)
$buildings = @($projects | Where-Object { $_.sector -in @(
    'Construction (residential building)', 'Construction (commercial building)',
    'Construction (institutional building)') })
if ($buildings.Count -eq 0) { throw 'No building projects identified; nothing deleted.' }
$keepCodes = @{}
foreach ($project in $buildings) { $keepCodes[$project.project_code] = $true }
$knownCodes = @{}
foreach ($project in $projects) { $knownCodes[$project.project_code] = $true }
$toDelete = @()
foreach ($file in @(Get-ChildItem -LiteralPath $ghentRoot -Recurse -File -Force)) {
    $resolved = [IO.Path]::GetFullPath($file.FullName)
    if (-not $resolved.StartsWith($ghentPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path outside Ghent workspace: $resolved"
    }
    $reason = $null
    if ($file.Name -eq 'DSLIB3.4.zip') { $reason = 'Mixed-sector archive; recoverable from official release' }
    elseif ($file.Name -eq '.DS_Store' -or $resolved -match '[\\/]__MACOSX[\\/]') { $reason = 'Mac metadata' }
    elseif ($file.Name -match '^(C\d{4})-(\d{1,2})(?:\D|$)') {
        $code = '{0}-{1:D2}' -f $Matches[1], [int]$Matches[2]
        if (-not $knownCodes.ContainsKey($code)) { throw "Unknown project code $code" }
        if (-not $keepCodes.ContainsKey($code)) { $reason = "Excluded sector: $code" }
    }
    elseif ($file.Name -notin @('release.json', 'DSLIB_Analysis_Sheet.xlsx', 'Readme.rtf', 'BUILDINGS_ONLY.md')) {
        throw "Unrecognized file; review before deletion: $resolved"
    }
    if ($reason) { $toDelete += [PSCustomObject]@{ path = $resolved; reason = $reason } }
}
$buildings | Export-Csv -LiteralPath (Join-Path $projectRoot 'data/processed/external_inventory/ghent_buildings.csv') -NoTypeInformation -Encoding UTF8
if ($toDelete.Count -gt 0) {
    $toDelete | Export-Csv -LiteralPath (Join-Path $projectRoot 'data/processed/external_inventory/ghent_removed_files.csv') -NoTypeInformation -Encoding UTF8
    foreach ($item in $toDelete) { Remove-Item -LiteralPath $item.path -Force }
}
# Remove empty directories only; each resolved target stays inside the checked root.
$directories = @(Get-ChildItem -LiteralPath $ghentRoot -Directory -Recurse -Force | Sort-Object { $_.FullName.Length } -Descending)
foreach ($directory in $directories) {
    $resolved = [IO.Path]::GetFullPath($directory.FullName)
    if (-not $resolved.StartsWith($ghentPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe directory' }
    if (@(Get-ChildItem -LiteralPath $resolved -Force).Count -eq 0) { Remove-Item -LiteralPath $resolved -Force }
}
Write-Output "Kept $($buildings.Count) building projects; removed $($toDelete.Count) unrelated or metadata files."
