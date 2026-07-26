#Requires -Version 5.1
<#
.SYNOPSIS
    install.ps1 — Windows companion to install.sh (Layer-2 middleware bootstrap)

.DESCRIPTION
    Idempotent setup (safe to re-run). Initializes vendor/Claude-Desktop-LLM submodule,
    builds MCPB bundles via bash when available, harmonizes GOSSIP_SHARED_SECRET.

    Run from Perpetua-Tools repo root:
        powershell -ExecutionPolicy Bypass -File .\install.ps1

.NOTES
    MCPB build delegates to scripts/install-claude-desktop-llm.sh (requires Git Bash or bash on PATH).
    Mesh secrets use scripts/mesh/Invoke-MeshLocalCache.ps1 (Win/Mac parity with install.sh).
#>
[CmdletBinding()]
param(
    [switch]$Open,
    [switch]$SkipMcpb,
    [switch]$SkipDesktop,
    [switch]$VendorGuide,
    [switch]$SkipVendorGuide,
    [switch]$SkipHygieneCheck,
    [switch]$SkipEcc,
    [switch]$SkipAgenticStack,
    [switch]$SkipAutoresearch,
    [switch]$NonInteractive,
    [switch]$Help
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'

$RepoRoot = $PSScriptRoot
if (-not $RepoRoot) {
    $RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$env:PERPETUA_TOOLS_PATH = $RepoRoot

function _Step { param([string]$Msg) Write-Host "  [+] $Msg" -ForegroundColor Cyan }
function _OK   { param([string]$Msg) Write-Host "  ✓  $Msg" -ForegroundColor Green }
function _Warn { param([string]$Msg) Write-Host "  !  $Msg" -ForegroundColor Yellow }
function _Err  { param([string]$Msg) Write-Host "  ✗  $Msg" -ForegroundColor Red; exit 1 }

function Resolve-BashExe {
    if ($env:HERMES_GIT_BASH_PATH -and (Test-Path $env:HERMES_GIT_BASH_PATH)) {
        return $env:HERMES_GIT_BASH_PATH
    }
    $cmd = Get-Command bash -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @(
        (Join-Path ${env:ProgramFiles} 'Git\bin\bash.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Git\bin\bash.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Git\bin\bash.exe')
    )
    foreach ($path in $candidates) {
        if ($path -and (Test-Path $path)) { return $path }
    }
    return $null
}

if ($Help) {
    Write-Host @"
Usage: install.ps1 [-Open] [-SkipMcpb] [-SkipDesktop] [-VendorGuide]
                  [-SkipVendorGuide] [-SkipHygieneCheck] [-SkipEcc]
                  [-SkipAgenticStack] [-SkipAutoresearch] [-NonInteractive] [-Help]
  Default: init vendor/Claude-Desktop-LLM and build/stage MCPB bundles.
  -VendorGuide opts into the broader vendor bootstrap (ecc-tools, agentic-stack, autoresearch).
"@
    exit 0
}

if ($SkipVendorGuide) { $script:VendorGuide = $false }

Write-Host ''
Write-Host 'Perpetua-Tools install' -ForegroundColor Cyan
Write-Host '──────────────────────' -ForegroundColor DarkGray
Write-Host ''

_Step 'Initializing vendor/Claude-Desktop-LLM submodule...'
& git -C $RepoRoot submodule update --init --recursive vendor/Claude-Desktop-LLM
if ($LASTEXITCODE -ne 0) {
    _Err 'Failed to init submodule vendor/Claude-Desktop-LLM'
}
_OK 'Submodule ready'

if (-not $SkipMcpb) {
    $bash = Resolve-BashExe
    $desktopScript = Join-Path $RepoRoot 'scripts\install-claude-desktop-llm.sh'
    if (-not $bash) {
        _Warn 'bash not found — skip MCPB build. Install Git for Windows or set HERMES_GIT_BASH_PATH.'
        _Warn "Manual: bash scripts/install-claude-desktop-llm.sh"
    } elseif (-not (Test-Path $desktopScript)) {
        _Warn "Missing $desktopScript — skip MCPB build"
    } else {
        $extra = @()
        if ($Open) { $extra += '--open' }
        if ($SkipDesktop) { $extra += '--skip-desktop' }
        _Step 'Building MCPB bundles (install-claude-desktop-llm.sh)...'
        & $bash $desktopScript @extra
        if ($LASTEXITCODE -ne 0) {
            _Warn "MCPB build exited $LASTEXITCODE — check output above"
        } else {
            _OK 'MCPB bundles staged'
        }
    }
} else {
    Write-Host '  (skipped MCPB build — -SkipMcpb)' -ForegroundColor DarkGray
}

$MeshScript = Join-Path $RepoRoot 'scripts\mesh\Invoke-MeshLocalCache.ps1'
if (Test-Path $MeshScript) {
    $venvPy = Join-Path $RepoRoot '.venv\Scripts\python.exe'
    $pyArg = if (Test-Path $venvPy) { $venvPy } else { 'python' }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $MeshScript -RepoRoot $RepoRoot -Python $pyArg -Mode Install
} else {
    _Warn 'scripts\mesh\Invoke-MeshLocalCache.ps1 missing — skip mesh local cache'
}

if ($VendorGuide) {
    $bash = Resolve-BashExe
    $guideScript = Join-Path $RepoRoot 'scripts\install-vendor-guided.sh'
    if (-not $bash) {
        _Warn 'bash not found — cannot run --vendor-guide'
    } elseif (-not (Test-Path $guideScript)) {
        _Warn "Missing $guideScript — skip vendor guide"
    } else {
        $guideArgs = @()
        if ($SkipHygieneCheck) { $guideArgs += '--skip-hygiene-check' }
        if ($SkipEcc) { $guideArgs += '--skip-ecc' }
        if ($SkipAgenticStack) { $guideArgs += '--skip-agentic-stack' }
        if ($SkipAutoresearch) { $guideArgs += '--skip-autoresearch' }
        if ($NonInteractive) { $guideArgs += '--non-interactive' }
        _Step 'Running guided vendor install...'
        & $bash $guideScript @guideArgs
        if ($LASTEXITCODE -ne 0) {
            _Warn "Vendor guide exited $LASTEXITCODE"
        } else {
            _OK 'Vendor guide complete'
        }
    }
} else {
    Write-Host ''
    Write-Host '  (guided vendor install not requested — use -VendorGuide)' -ForegroundColor DarkGray
}

Write-Host ''
Write-Host 'Done. Claude Code: cd packages/alphaclaw-mcp; npm run build' -ForegroundColor Green
Write-Host '      claude mcp add --transport stdio alphaclaw -- node packages/alphaclaw-mcp/build/index.js'
Write-Host ''
