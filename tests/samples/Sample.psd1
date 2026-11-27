@{
  # Module manifest
  RootModule        = 'Sample.psm1'
  ModuleVersion     = '0.1.0'
  Description       = 'Tag #1'  # a real comment
  ReleaseNotes      = @'
# not a comment
'@
  PowerShellVersion = 7.4
  FunctionsToExport = @('Get-Thing', "Set-Thing")
  PrivateData       = @{ PSData = @{ Prerelease = $null; RequireLicenseAcceptance = $false } }
  Enabled           = $true
}
