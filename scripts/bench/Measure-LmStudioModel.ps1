<#
.SYNOPSIS
  Measure one LM Studio chat model on the local GPU node (hardware/SKILL.md, section "Benchmark protocol").

.DESCRIPTION
  Sends the same fixed prompt -Runs times (after one discarded warm-up run) to
  LM Studio's REST API and records generation tokens/s, time to first token and
  wall time per run, plus the GPU name and VRAM in use from nvidia-smi.
  Prefers the stats LM Studio returns from /api/v0/chat/completions; if a run
  has no stats, tokens/s falls back to completion tokens / wall seconds and the
  run is marked "wall_clock".

  The JSON written records the device id, never the endpoint address.
  Windows PowerShell 5.1 compatible.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\bench\Measure-LmStudioModel.ps1 -Model qwen/qwen3.8-27b -Device win-rtx3080 -Runs 5
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$Model,
  [Parameter(Mandatory = $true)][ValidateSet('win-rtx3080', 'win-rtx5080')][string]$Device,
  [string]$Endpoint = '',
  [ValidateRange(1, 50)][int]$Runs = 5,
  [ValidateRange(16, 4096)][int]$MaxTokens = 256,
  [string]$OutFile = ''
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$utf8 = [System.Text.UTF8Encoding]::new($false)

if (-not $Endpoint) {
  if (-not $env:LM_STUDIO_WIN_ENDPOINTS) {
    throw 'Set LM_STUDIO_WIN_ENDPOINTS (or pass -Endpoint), e.g. http://localhost:1234'
  }
  $Endpoint = ($env:LM_STUDIO_WIN_ENDPOINTS -split ',')[0].Trim()
}
$Endpoint = $Endpoint.TrimEnd('/')
# /api/v0 returns LM Studio's own timing stats; older builds only serve /v1.
$script:uri = $Endpoint + '/api/v0/chat/completions'

# Fixed prompt so runs and nodes are comparable.
$prompt = 'Write a Python function that merges two sorted lists into one sorted list, then explain its time complexity in two sentences.'

function Invoke-OneRun {
  $body = @{
    model       = $Model
    messages    = @(@{ role = 'user'; content = $prompt })
    max_tokens  = $MaxTokens
    temperature = 0
    stream      = $false
  } | ConvertTo-Json -Depth 5
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  $resp = Invoke-RestMethod -Method Post -Uri $script:uri -ContentType 'application/json; charset=utf-8' -Body $utf8.GetBytes($body) -TimeoutSec 600
  $sw.Stop()
  $wall = $sw.Elapsed.TotalSeconds
  $completion = 0
  if ($resp.usage -and $resp.usage.completion_tokens) { $completion = [int]$resp.usage.completion_tokens }
  $tps = $null
  $ttft = $null
  $source = 'lmstudio_stats'
  if ($resp.stats -and $resp.stats.tokens_per_second) {
    $tps = [double]$resp.stats.tokens_per_second
    if ($resp.stats.time_to_first_token) { $ttft = [double]$resp.stats.time_to_first_token }
  } else {
    $source = 'wall_clock'
    if ($wall -gt 0) { $tps = $completion / $wall }
  }
  return [pscustomobject]@{
    gen_tokens_per_s  = $tps
    ttft_s            = $ttft
    wall_s            = $wall
    completion_tokens = $completion
    source            = $source
  }
}

function Get-Median($values) {
  # Untyped on purpose: a [double[]] parameter would turn missing values into 0.
  $v = @($values | Where-Object { $_ -ne $null } | ForEach-Object { [double]$_ } | Sort-Object)
  if ($v.Count -eq 0) { return $null }
  $mid = [int][Math]::Floor($v.Count / 2)
  if ($v.Count % 2 -eq 1) { return $v[$mid] }
  return ($v[$mid - 1] + $v[$mid]) / 2
}

Write-Host ("Warm-up run for {0} on {1} ..." -f $Model, $Device)
try {
  [void](Invoke-OneRun)
} catch {
  Write-Host ("/api/v0 unavailable ({0}); falling back to /v1 with wall-clock timing" -f $_.Exception.Message)
  $script:uri = $Endpoint + '/v1/chat/completions'
  [void](Invoke-OneRun)
}

$results = @()
for ($i = 1; $i -le $Runs; $i++) {
  $r = Invoke-OneRun
  Write-Host ("run {0}/{1}: {2:N1} tok/s, ttft {3}, wall {4:N2}s ({5})" -f $i, $Runs, $r.gen_tokens_per_s, $r.ttft_s, $r.wall_s, $r.source)
  $results += $r
}

$gpu = $null
$nvsmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($nvsmi) {
  $line = (& nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader,nounits | Select-Object -First 1)
  if ($line) {
    $parts = $line -split ',\s*'
    $gpu = [pscustomobject]@{
      name         = $parts[0]
      vram_used_gb  = [Math]::Round([double]$parts[1] / 1024, 2)
      vram_total_gb = [Math]::Round([double]$parts[2] / 1024, 2)
    }
  }
}

$summary = [pscustomobject]@{
  model                   = $Model
  device                  = $Device
  measured_on             = (Get-Date -Format 'yyyy-MM-dd')
  runs                    = $Runs
  max_tokens              = $MaxTokens
  gen_tokens_per_s_median = Get-Median ($results | ForEach-Object { $_.gen_tokens_per_s })
  ttft_s_median           = Get-Median ($results | ForEach-Object { $_.ttft_s })
  wall_s_median           = Get-Median ($results | ForEach-Object { $_.wall_s })
  gpu                     = $gpu
  per_run                 = $results
}

if (-not $OutFile) {
  $safeModel = ($Model -replace '[^A-Za-z0-9._-]', '_')
  $OutFile = 'bench-{0}-{1}-{2}.json' -f $safeModel, $Device, (Get-Date -Format 'yyyyMMdd-HHmmss')
}
$json = $summary | ConvertTo-Json -Depth 6
$outPath = $OutFile
if (-not [System.IO.Path]::IsPathRooted($outPath)) { $outPath = Join-Path (Get-Location).Path $outPath }
[System.IO.File]::WriteAllText($outPath, $json, $utf8)
Write-Host ("median {0:N1} tok/s, ttft {1}, wrote {2}" -f $summary.gen_tokens_per_s_median, $summary.ttft_s_median, $outPath)
