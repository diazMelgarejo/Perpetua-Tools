#Requires -Version 5.1
<#
.SYNOPSIS
    Invoke-MeshLocalCache.ps1 — Windows companion to install.sh / install.ps1 mesh hooks.

.DESCRIPTION
    Idempotent local mesh prep (GOSSIP_SHARED_SECRET harmonization).
    Mirrors scripts/mesh/ensure_local_mesh_secrets.py calls from install.sh for Win parity.
    PT has no lan_topology_archive.py (orama-only); secrets + optional load-local only.

.PARAMETER RepoRoot
    Perpetua-Tools repository root.

.PARAMETER Python
    Python executable (defaults to .venv\Scripts\python.exe, then python).

.PARAMETER Mode
    Install — ensure secrets (warn on failure).
    LanBind — ensure secrets + fail closed when LAN bind lacks GOSSIP + .env.local.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$RepoRoot,

    [string]$Python = '',

    [ValidateSet('Install', 'LanBind')]
    [string]$Mode = 'Install'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

function Write-MeshWarn([string]$Msg) { Write-Host "  !  $Msg" -ForegroundColor Yellow }
function Write-MeshInfo([string]$Msg) { Write-Host "  [+] $Msg" -ForegroundColor Cyan }
function Write-MeshOK([string]$Msg) { Write-Host "  ✓  $Msg" -ForegroundColor Green }

$MeshDir = Join-Path $RepoRoot 'scripts\mesh'

if (-not $Python) {
    $venvPy = Join-Path $RepoRoot '.venv\Scripts\python.exe'
    if (Test-Path $venvPy) {
        $Python = $venvPy
    } else {
        $Python = 'python'
    }
}

if ($Mode -eq 'Install') {
    Write-MeshInfo 'Local mesh secrets (GOSSIP_SHARED_SECRET harmonization)...'
}

$secrets = Join-Path $MeshDir 'ensure_local_mesh_secrets.py'
if (Test-Path $secrets) {
    if ($Mode -eq 'LanBind') {
        Write-MeshInfo 'Ensuring GOSSIP_SHARED_SECRET for LAN bind...'
    }
    & $Python $secrets 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-MeshWarn 'GOSSIP_SHARED_SECRET not written — run ensure_local_mesh_secrets.py manually'
    }
} else {
    Write-MeshWarn 'scripts\mesh\ensure_local_mesh_secrets.py missing — skip mesh secrets'
}

$loadLocal = Join-Path $RepoRoot 'scripts\env\load-local.ps1'
if (Test-Path $loadLocal) {
    & $loadLocal -RepoRoot $RepoRoot
}

if ($Mode -eq 'LanBind') {
    $secret = ''
    if ($env:GOSSIP_SHARED_SECRET) {
        $secret = $env:GOSSIP_SHARED_SECRET.Trim()
    }
    $envLocal = Join-Path $RepoRoot '.env.local'
    if (-not $secret -and -not (Test-Path $envLocal)) {
        Write-Error 'GOSSIP_SHARED_SECRET required for LAN mesh — run: python scripts/mesh/ensure_local_mesh_secrets.py'
        exit 1
    }
}

if ($Mode -eq 'Install') {
    Write-MeshOK 'Mesh local cache step complete (see .local/mesh.log)'
}
