#!/usr/bin/env pwsh
# Compatibility entry point for local PowerShell users.
[CmdletBinding()]
param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
$validator = Join-Path $PSScriptRoot "validate-readme.py"
& python $validator --root $Root
exit $LASTEXITCODE
