<#
.SYNOPSIS
  VibeMon installer entry point for Windows PowerShell.

.DESCRIPTION
  Locates a usable Python, downloads install.py, verifies it against the
  published manifest.json, and runs it with the arguments given here.

  This wrapper exists because the documented `curl ... | python3` pipe does
  not work on Windows: there is no `python3` on PATH, and Windows PowerShell
  5.1 re-encodes piped text with the console code page, which corrupts the
  UTF-8 source before Python ever parses it. Downloading to a file avoids
  both problems.

.EXAMPLE
  irm https://docs.vibemon.io/install.ps1 | iex

.EXAMPLE
  & ([scriptblock]::Create((irm https://docs.vibemon.io/install.ps1))) --claude --token my_token

.EXAMPLE
  & ([scriptblock]::Create((irm https://docs.vibemon.io/install.ps1))) --uninstall --claude
#>

function Install-VibeMon {
    # Function-scoped so `irm | iex` doesn't leave these behind in the
    # caller's interactive session.
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'

    $docsBaseUrl = 'https://docs.vibemon.io'

    # Windows PowerShell 5.1 still negotiates SSL3/TLS1.0 by default on some
    # builds, which docs.vibemon.io refuses.
    try {
        [Net.ServicePointManager]::SecurityProtocol =
            [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    } catch {
        # PowerShell 7 manages this itself and the property may be read-only.
    }

    $python = Find-VibeMonPython
    if (-not $python) {
        throw @'
Python 3 was not found.

Install it from https://www.python.org/downloads/windows/ (tick
"Add python.exe to PATH"), then run this installer again.

If `python` opens the Microsoft Store instead of running, turn off the
"python.exe" and "python3.exe" App execution aliases in
Settings > Apps > Advanced app settings > App execution aliases.
'@
    }
    Write-Host "  Using Python: $($python.Display)"

    $tempScript = Join-Path ([IO.Path]::GetTempPath()) "vibemon-install-$PID.py"
    try {
        Invoke-WebRequest -Uri "$docsBaseUrl/install.py" -OutFile $tempScript -UseBasicParsing

        $expected = Get-VibeMonInstallerHash -DocsBaseUrl $docsBaseUrl
        if ($expected) {
            $actual = (Get-FileHash -Path $tempScript -Algorithm SHA256).Hash
            if ($actual -ne $expected) {
                throw "install.py failed its integrity check (expected $expected, got $actual). Nothing was run; retry, and if it persists the published file may be corrupt."
            }
            Write-Host '  Installer verified against manifest.json'
        }

        # $args of the *caller* is forwarded by the call at the bottom of this
        # file, so platform flags reach install.py unchanged.
        & $python.Exe @($python.PrefixArgs) $tempScript @args
        if ($LASTEXITCODE -ne 0) {
            throw "VibeMon installer exited with code $LASTEXITCODE."
        }
    } finally {
        Remove-Item -Path $tempScript -Force -ErrorAction SilentlyContinue
    }
}

function Find-VibeMonPython {
    <#
    .SYNOPSIS
      First Python 3 that can actually execute code, or $null.

    .DESCRIPTION
      `py -3` is tried first: the python.org launcher lives at a fixed path
      and keeps resolving after an interpreter upgrade. The bare `python` /
      `python3` names come last because Windows ships App execution alias
      stubs under those names that open the Microsoft Store instead of
      running anything -- probing with real code is what tells them apart.
    #>
    $candidates = @(
        @{ Exe = 'py';      PrefixArgs = @('-3') },
        @{ Exe = 'python';  PrefixArgs = @() },
        @{ Exe = 'python3'; PrefixArgs = @() }
    )

    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.Exe -ErrorAction SilentlyContinue)) { continue }
        try {
            $probe = & $candidate.Exe @($candidate.PrefixArgs) '-c' 'import sys; print(sys.version.split()[0])' 2>$null
        } catch {
            continue
        }
        if ($LASTEXITCODE -eq 0 -and $probe) {
            return [pscustomobject]@{
                Exe        = $candidate.Exe
                PrefixArgs = $candidate.PrefixArgs
                Display    = "$($candidate.Exe) $($candidate.PrefixArgs -join ' ')".Trim() + " (Python $probe)"
            }
        }
    }
    return $null
}

function Get-VibeMonInstallerHash {
    <#
    .SYNOPSIS
      Published sha256 of install.py, or $null when the manifest is unavailable.

    .DESCRIPTION
      Mirrors the Desktop app's check. A missing or malformed manifest is a
      warning rather than a failure so a lagging manifest deploy can't block
      installs; a manifest that *is* present and disagrees is fatal.
    #>
    param([Parameter(Mandatory)][string]$DocsBaseUrl)

    try {
        $manifest = Invoke-RestMethod -Uri "$DocsBaseUrl/manifest.json" -UseBasicParsing
    } catch {
        Write-Host "  ! Could not load manifest.json ($($_.Exception.Message)) - integrity check skipped"
        return $null
    }
    if (-not $manifest.installer) {
        Write-Host '  ! manifest.json has no installer hash - integrity check skipped'
        return $null
    }
    return $manifest.installer.ToUpperInvariant()
}

# Guarded rather than a bare `Install-VibeMon @args`: under `irm | iex` the
# script runs in the caller's scope, where $args can be $null instead of an
# empty array, and splatting that would pass a single $null argument through to
# install.py. `iex` also leaves Install-VibeMon defined afterwards, so it can be
# re-run with different flags without downloading again.
if ($args) { Install-VibeMon @args } else { Install-VibeMon }
