param(
    [string]$SourceUrl = "https://aaban-classic-building-cleaning-llc.odoo.com",
    [string]$SourceDb = "aaban-classic-building-cleaning-llc",
    [string]$SourceUsername = "aabancleaningandpestcontrol@gmail.com",
    [string]$SourceApiKey = $env:AABAAN_SOURCE_ODOO_API_KEY,
    [string]$TargetUrl = "https://core2plus-odoo-aabaan-services.odoo.com",
    [string]$TargetDb = "core2plus-odoo-aabaan-services-main-34150667",
    [string]$TargetUsername = "muhammad.umer@core2plus.com",
    [string]$TargetApiKey = $env:AABAAN_TARGET_ODOO_API_KEY,
    [string]$OutputDir = "outputs\odoo_migration_export",
    [int]$MaxPartners = 0,
    [int]$MaxProducts = 0,
    [int]$MaxEmployees = 0,
    [switch]$ImportToTarget
)

$ErrorActionPreference = "Stop"

function Read-SecretText {
    param([string]$Prompt)
    $secure = Read-Host $Prompt -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

if (-not $SourceApiKey) { $SourceApiKey = Read-SecretText "Source Odoo API key" }
if (-not $TargetApiKey) { $TargetApiKey = Read-SecretText "Target Odoo API key" }

Write-Host "This helper is intentionally secret-free."
Write-Host "Use the local implementation export script in docs/deployment_notes.md as the operational reference."
Write-Host "Source: $SourceUrl / $SourceDb / $SourceUsername"
Write-Host "Target: $TargetUrl / $TargetDb / $TargetUsername"
Write-Host "Dry run mode: $(-not $ImportToTarget)"

# Keep this committed helper small and auditable. The full operational migration script
# should be run from a secure implementation workstation with API keys supplied via
# environment variables or hidden prompts. Do not commit generated CSV exports or keys.
