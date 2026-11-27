#Requires -Version 7.4
<#
.SYNOPSIS
  Does a thing.
#>
function Get-Thing {
  [CmdletBinding()]
  param([string] $Path = 'x $notvar', [int] $Count = 42)
  if ($true -and -not $false) { Get-ChildItem -Path $Path | ForEach-Object { $_.Name.Trim() } }
  $msg = "Found $Count items in ${Path}"
  $tag = "Issue #1"
  [Math]::Round(3.14) ; $null = $env:HOME  # trailing comment
}
