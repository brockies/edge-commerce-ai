param(
    [string]$ProjectName = "medusa-store",
    [string]$TargetRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path,
    [string]$DatabaseUrl = "",
    [switch]$SkipDb,
    [switch]$InstallStorefront
)

$destination = Join-Path $TargetRoot $ProjectName

if (Test-Path -LiteralPath $destination) {
    Write-Error "Destination already exists: $destination"
    exit 1
}

$args = @(
    "create-medusa-app@latest",
    $ProjectName,
    "--no-browser",
    "--directory-path",
    $TargetRoot
)

if ($SkipDb) {
    $args += "--skip-db"
} else {
    if (-not $DatabaseUrl) {
        Write-Error "DatabaseUrl is required unless -SkipDb is set. Example: postgres://<user>:<password>@127.0.0.1:5432/medusa-store"
        exit 1
    }
    $args += @("--db-url", $DatabaseUrl)
}

if ($InstallStorefront) {
    $args += "--with-nextjs-starter"
}

Write-Host "Creating standalone Medusa project at $destination"
Write-Host "npx $($args -join ' ')"

& npx @args
exit $LASTEXITCODE
