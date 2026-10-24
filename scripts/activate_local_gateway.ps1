#Requires -Version 7.0
<#
Preview is the default. -Activate stages an independent runtime and enables the
validated user-level routes. -RollbackReceipt restores checked configuration and
Startup bytes and stops only processes belonging to that exact runtime.
#>
[CmdletBinding(DefaultParameterSetName = 'Plan')]
param(
    [Parameter(Mandatory, ParameterSetName = 'Plan')][string]$SourceRoot,
    [Parameter(Mandatory, ParameterSetName = 'Plan')][string]$UV,
    [Parameter(Mandatory, ParameterSetName = 'Plan')][string]$BasePython,
    [Parameter(Mandatory, ParameterSetName = 'Plan')][string]$RuntimeRoot,
    [Parameter(ParameterSetName = 'Plan')][ValidateRange(1024, 65535)][int]$Port = 43187,
    [Parameter(ParameterSetName = 'Plan')][switch]$Preview,
    [Parameter(ParameterSetName = 'Plan')][switch]$Activate,
    [Parameter(ParameterSetName = 'Plan', ValueFromRemainingArguments = $true)][string[]]$ExtraArgs,
    [Parameter(Mandatory, ParameterSetName = 'Rollback')][string]$RollbackReceipt
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($ExtraArgs) {
    if (@($ExtraArgs | Where-Object { $_ -ne '--preview' }).Count -gt 0) { throw 'Unknown trailing argument.' }
    $Preview = $true
}
$taskUserHome = [Environment]::GetFolderPath('UserProfile')
$taskStartup = Join-Path ([Environment]::GetFolderPath('Startup')) 'TOMC Gateway.lnk'
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)

function Resolve-Full([string]$Path) {
    return [IO.Path]::GetFullPath($Path).TrimEnd([IO.Path]::DirectorySeparatorChar)
}

function Assert-InDirectory([string]$Path, [string]$Directory) {
    $prefix = (Resolve-Full $Directory) + [IO.Path]::DirectorySeparatorChar
    if (-not (Resolve-Full $Path).StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'A managed path escaped its expected directory.'
    }
}

function Assert-NoReparse([string]$Path) {
    $cursor = Resolve-Full $Path
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'Managed installation paths must not traverse symbolic links or junctions.'
            }
        }
        $parent = [IO.Directory]::GetParent($cursor)
        if ($null -eq $parent) { break }
        $cursor = $parent.FullName
    }
}

function Assert-Runtime([string]$Directory) {
    $expectedParent = Resolve-Full (Join-Path $taskUserHome '.codex/tomc')
    if ((Resolve-Full ([IO.Directory]::GetParent($Directory).FullName)) -ne $expectedParent -or
        [IO.Path]::GetFileName($Directory) -notmatch '^gateway-016-\d{8}T\d{6}Z$') {
        throw 'RuntimeRoot must be a new ~/.codex/tomc/gateway-016-YYYYMMDDTHHMMSSZ directory.'
    }
    Assert-NoReparse $Directory
}

function Get-Digest([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw 'Expected a regular file.' }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Save-Receipt($Receipt, [string]$Path) {
    [IO.File]::WriteAllText($Path, ($Receipt | ConvertTo-Json -Depth 12), $utf8NoBom)
}

function Assert-PortFree([int]$Number) {
    # Binding is definitive, unlike a health response from an unrelated old service.
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $Number)
    $listener.Server.ExclusiveAddressUse = $true
    try { $listener.Start() }
    catch { throw "Port $Number is occupied; no service was stopped or reused." }
    finally { $listener.Stop() }
}

function Test-OwnedProcess([int]$ProcessId, [string]$Directory, [string]$ConfigPath, [string[]]$AllowedExecutables) {
    if ($ProcessId -le 0) { return $false }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop
    if ($null -eq $process) { return $false }
    $launcher = Join-Path $Directory 'scripts/request_gateway_launcher.pyw'
    $executableMatches = @($AllowedExecutables | Where-Object {
        [string]::Equals([string]$process.ExecutablePath, $_, [StringComparison]::OrdinalIgnoreCase)
    }).Count -gt 0
    return ($executableMatches -and
        ([string]$process.CommandLine).IndexOf($launcher, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        ([string]$process.CommandLine).IndexOf($ConfigPath, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        ([string]$process.CommandLine) -match ('--runtime\s+"?' + [regex]::Escape($Directory) + '"?(?=\s|$)'))
}

function Test-LaunchAncestry([int]$ProcessId, [int]$LaunchId) {
    $cursor = $ProcessId
    for ($depth = 0; $depth -lt 8; $depth++) {
        if ($cursor -eq $LaunchId) { return $true }
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $cursor"
        if ($null -eq $process -or [int]$process.ParentProcessId -le 0) { return $false }
        $cursor = [int]$process.ParentProcessId
    }
    return $false
}

function Stop-OwnedProcesses($Receipt) {
    if ([int]$Receipt.launcher_pid -le 0) { return }
    $directory = [string]$Receipt.runtime
    $configPath = Join-Path $directory 'config.json'
    # Stop our supervisor first so it cannot restart a child during rollback.
    if (Test-OwnedProcess ([int]$Receipt.supervisor_pid) $directory $configPath $Receipt.allowed_executables) {
        Stop-Process -Id ([int]$Receipt.supervisor_pid) -Force
    }
    $candidates = @(Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'")
    # Windows venv launchers may create a base-interpreter process. Both must
    # match the exact runtime/config; never stop unrelated pythonw processes.
    $ordered = @($candidates | Where-Object { ([string]$_.CommandLine) -notmatch '\s--serve(?:\s|$)' }) +
               @($candidates | Where-Object { ([string]$_.CommandLine) -match '\s--serve(?:\s|$)' })
    foreach ($candidate in $ordered) {
        if (Test-OwnedProcess ([int]$candidate.ProcessId) $directory $configPath $Receipt.allowed_executables) {
            Stop-Process -Id ([int]$candidate.ProcessId) -Force
        }
    }
}

function Restore-Activation([string]$Path) {
    $Path = Resolve-Full $Path
    $receipt = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    if ($receipt.format -ne 'tomc-gateway-activation-v1') { throw 'Unknown activation receipt format.' }
    if ($receipt.activation_unverified) { throw 'Client activation outcome is unverified; retain this service until its configuration receipt is recovered.' }
    $directory = Resolve-Full ([string]$receipt.runtime)
    Assert-Runtime $directory
    if ($Path -ne (Join-Path $directory 'activation-receipt.json')) { throw 'Receipt path does not match its runtime.' }
    if ([string]$receipt.startup.target -ne $taskStartup) { throw 'Receipt has an unexpected Startup target.' }
    Assert-NoReparse $taskStartup
    if ($receipt.startup.installed_sha256 -and (Get-Digest $taskStartup) -ne $receipt.startup.installed_sha256) {
        throw 'Startup shortcut changed after activation; rollback will not overwrite it.'
    }
    if ($receipt.config_receipt) {
        $python = Join-Path $directory '.venv/Scripts/python.exe'
        & $python -B (Join-Path $directory 'scripts/install_request_gateway.py') --home $taskUserHome --restore ([string]$receipt.config_receipt)
        if ($LASTEXITCODE -ne 0) { throw 'Client rollback refused; the gateway was left running to preserve access.' }
        $receipt.config_receipt = $null
        Save-Receipt $receipt $Path
    }
    if ($receipt.startup.installed_sha256) {
        if ($receipt.startup.backup) {
            $backup = Resolve-Full ([string]$receipt.startup.backup)
            Assert-InDirectory $backup $directory
            if ((Get-Digest $backup) -ne $receipt.startup.before_sha256) { throw 'Startup backup integrity check failed.' }
            Copy-Item -LiteralPath $backup -Destination $taskStartup -Force
        } else {
            # A single known file, validated above; no recursive file operations.
            Remove-Item -LiteralPath $taskStartup
        }
        $receipt.startup.installed_sha256 = $null
        Save-Receipt $receipt $Path
    }
    Stop-OwnedProcesses $receipt
    $receipt.status = 'restored'
    Save-Receipt $receipt $Path
    return $receipt
}

if ($PSCmdlet.ParameterSetName -eq 'Rollback') {
    $restored = Restore-Activation $RollbackReceipt
    [pscustomobject]@{ status = $restored.status; runtime = $restored.runtime; receipt = $RollbackReceipt } | ConvertTo-Json
    return
}

if ($Activate -and $Preview) { throw 'Choose either -Preview or -Activate.' }
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$UV = (Resolve-Path -LiteralPath $UV).Path
$BasePython = (Resolve-Path -LiteralPath $BasePython).Path
$RuntimeRoot = Resolve-Full $RuntimeRoot
Assert-Runtime $RuntimeRoot
if (Test-Path -LiteralPath $RuntimeRoot) { throw 'RuntimeRoot already exists; choose a new UTC timestamp.' }
Assert-InDirectory $taskStartup $taskUserHome
Assert-NoReparse $taskStartup
Assert-NoReparse (Join-Path $taskUserHome '.tomc/memory.sqlite3')
$stage = Join-Path $SourceRoot 'scripts/stage_request_gateway.py'
$installer = Join-Path $SourceRoot 'scripts/install_request_gateway.py'
foreach ($required in @($stage, $installer, (Join-Path $SourceRoot 'requirements-gateway.txt'))) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw 'Required gateway source is missing.' }
}
Assert-PortFree $Port

$plan = [ordered]@{
    mode = $(if ($Activate) { 'activate' } else { 'preview' })
    runtime = $RuntimeRoot
    port = $Port
    store = (Join-Path $taskUserHome '.tomc/memory.sqlite3')
    upstreams = @{ codex = 'https://chatgpt.com/backend-api/codex'; claude = 'https://api.anthropic.com' }
    startup = $taskStartup
    receipt = (Join-Path $RuntimeRoot 'activation-receipt.json')
    clients_will_be_closed = $false
}
$plan | ConvertTo-Json -Depth 5
if (-not $Activate) {
    # Existing installer preview validates user configuration without changing it.
    & $BasePython -B $installer --home $taskUserHome --runtime $SourceRoot --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Read-only configuration validation failed.' }
    return
}

& $BasePython -B $stage --source $SourceRoot --destination $RuntimeRoot
if ($LASTEXITCODE -ne 0) { throw 'Staging failed; clients were not activated.' }
Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $RuntimeRoot 'scripts/activate_local_gateway.ps1')
$receiptPath = Join-Path $RuntimeRoot 'activation-receipt.json'
$receipt = [ordered]@{
    format = 'tomc-gateway-activation-v1'; status = 'staged'; runtime = $RuntimeRoot; port = $Port
    created_utc = [DateTime]::UtcNow.ToString('o'); source = $SourceRoot
    launcher_pid = 0; supervisor_pid = 0; service_pid = 0; listener_pid = 0; allowed_executables = @()
    config_receipt = $null; activation_unverified = $false
    startup = [ordered]@{ target = $taskStartup; backup = $null; before_sha256 = (Get-Digest $taskStartup); installed_sha256 = $null }
}
Save-Receipt $receipt $receiptPath
try {
    & $UV venv --python $BasePython (Join-Path $RuntimeRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Independent Python environment creation failed.' }
    $python = Join-Path $RuntimeRoot '.venv/Scripts/python.exe'
    $pythonw = Join-Path $RuntimeRoot '.venv/Scripts/pythonw.exe'
    & $UV pip install --python $python -r (Join-Path $RuntimeRoot 'requirements-gateway.txt')
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $pythonw -PathType Leaf)) { throw 'Gateway dependencies are not ready.' }
    $basePythonw = (& $python -B -c 'import pathlib,sys; print(pathlib.Path(sys._base_executable).with_name("pythonw.exe"))').Trim()
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $basePythonw -PathType Leaf)) { throw 'The base pythonw interpreter cannot be verified.' }
    $receipt.allowed_executables = @((Resolve-Full $pythonw), (Resolve-Full $basePythonw)) | Select-Object -Unique
    $configPath = Join-Path $RuntimeRoot 'config.json'
    $configuration = [ordered]@{
        port = $Port; store = $plan.store
        routes = [ordered]@{
            codex = @{ upstream = $plan.upstreams.codex; compression = @{ recent_messages = 6 } }
            claude = @{ upstream = $plan.upstreams.claude; compression = @{ recent_messages = 1 } }
        }
    }
    [IO.File]::WriteAllText($configPath, ($configuration | ConvertTo-Json -Depth 8), $utf8NoBom)
    # Recheck after dependency setup; never adopt an intervening listener.
    Assert-PortFree $Port
    $launcher = Join-Path $RuntimeRoot 'scripts/request_gateway_launcher.pyw'
    $launchArguments = "`"$launcher`" --runtime `"$RuntimeRoot`" --config `"$configPath`""
    $process = Start-Process -FilePath $pythonw -ArgumentList $launchArguments -WorkingDirectory $RuntimeRoot -WindowStyle Hidden -PassThru
    $receipt.launcher_pid = $process.Id
    $receipt.supervisor_pid = $process.Id
    $receipt.status = 'starting'
    Save-Receipt $receipt $receiptPath
    $ready = $false
    $healthCode = 'import json,sys; from urllib.request import ProxyHandler,build_opener; d=json.load(build_opener(ProxyHandler({})).open("http://127.0.0.1:"+sys.argv[1]+"/health",timeout=0.25)); sys.exit(0 if d.get("service")=="tomc-gateway" and d.get("ready") is True else 1)'
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        $statusPath = Join-Path $RuntimeRoot 'config.status.json'
        if (Test-Path -LiteralPath $statusPath -PathType Leaf) {
            $state = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
            if ((Test-LaunchAncestry ([int]$state.supervisor_pid) $process.Id) -and
                (Test-OwnedProcess ([int]$state.supervisor_pid) $RuntimeRoot $configPath $receipt.allowed_executables) -and
                (Test-OwnedProcess ([int]$state.service_pid) $RuntimeRoot $configPath $receipt.allowed_executables)) {
                # The serving interpreter can itself be a child of a venv stub.
                # Verify the actual listening PID too, excluding a port-race with
                # any other old or unrelated service returning the same health JSON.
                $listeners = @(Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
                foreach ($listener in $listeners) {
                    $ownerId = [int]$listener.OwningProcess
                    if ((Test-OwnedProcess $ownerId $RuntimeRoot $configPath $receipt.allowed_executables) -and
                        (Test-LaunchAncestry $ownerId ([int]$state.service_pid))) {
                        & $python -B -c $healthCode ([string]$Port) 2>$null
                        if ($LASTEXITCODE -eq 0 -and (Test-OwnedProcess $ownerId $RuntimeRoot $configPath $receipt.allowed_executables)) {
                            $receipt.service_pid = [int]$state.service_pid
                            $receipt.supervisor_pid = [int]$state.supervisor_pid
                            $receipt.listener_pid = $ownerId
                            $ready = $true
                            break
                        }
                    }
                }
                if ($ready) { break }
            }
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) { throw 'The new runtime did not reach verified loopback health.' }
    $receipt.status = 'service_ready'
    Save-Receipt $receipt $receiptPath
    if ((Get-Digest $taskStartup) -ne $receipt.startup.before_sha256) { throw 'Startup shortcut changed during installation.' }
    if ($receipt.startup.before_sha256) {
        $backupDirectory = Join-Path $RuntimeRoot 'backups'
        [IO.Directory]::CreateDirectory($backupDirectory) | Out-Null
        $receipt.startup.backup = Join-Path $backupDirectory 'TOMC Gateway.lnk'
        Copy-Item -LiteralPath $taskStartup -Destination $receipt.startup.backup
    }
    Save-Receipt $receipt $receiptPath
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($taskStartup)
    $shortcut.TargetPath = $pythonw
    $shortcut.Arguments = $launchArguments
    $shortcut.WorkingDirectory = $RuntimeRoot
    $shortcut.WindowStyle = 7
    $shortcut.Description = 'TOMC local request gateway'
    $shortcut.Save()
    $receipt.startup.installed_sha256 = Get-Digest $taskStartup
    Save-Receipt $receipt $receiptPath
    $receipt.activation_unverified = $true
    Save-Receipt $receipt $receiptPath
    $installOutput = @(& $python -B (Join-Path $RuntimeRoot 'scripts/install_request_gateway.py') --home $taskUserHome --runtime $RuntimeRoot --port $Port --activate)
    $installExitCode = $LASTEXITCODE
    $receiptMatches = [regex]::Matches(($installOutput -join "`n"), '"receipt"\s*:\s*("(?:\\.|[^"\\])*")')
    if ($receiptMatches.Count -gt 0) {
        $receipt.config_receipt = $receiptMatches[$receiptMatches.Count - 1].Groups[1].Value | ConvertFrom-Json
    }
    # Recover an interrupted CLI result from its exact-runtime receipt, never by
    # guessing that configuration was unchanged after a failed subprocess.
    $archiveRoot = Join-Path $taskUserHome '.codex/tomc/archive'
    if (-not $receipt.config_receipt -and (Test-Path -LiteralPath $archiveRoot -PathType Container)) {
        foreach ($archive in (Get-ChildItem -LiteralPath $archiveRoot -Directory -Filter 'session-update-*')) {
            $candidatePath = Join-Path $archive.FullName 'receipt.json'
            if (-not (Test-Path -LiteralPath $candidatePath -PathType Leaf)) { continue }
            $candidate = Get-Content -LiteralPath $candidatePath -Raw | ConvertFrom-Json
            if ([string]$candidate.runtime -eq $RuntimeRoot) {
                if ($candidate.status -eq 'installed') { $receipt.config_receipt = $candidatePath }
                if ($candidate.status -eq 'rolled_back') { $receipt.activation_unverified = $false }
            }
        }
    }
    if ($receipt.config_receipt) { $receipt.activation_unverified = $false }
    Save-Receipt $receipt $receiptPath
    if ($installExitCode -ne 0) { throw 'Client activation failed; inspect its checked rollback receipt.' }
    if (-not $receipt.config_receipt) { throw 'Activation did not return a rollback receipt; the new service is retained for safe recovery.' }
    $receipt.status = 'installed'
    Save-Receipt $receipt $receiptPath
    [pscustomobject]@{ status = 'installed'; receipt = $receiptPath; restart_clients_to_load_routes = $true; clients_closed = $false } | ConvertTo-Json
} catch {
    $receipt.status = 'failed'
    Save-Receipt $receipt $receiptPath
    try { Restore-Activation $receiptPath | Out-Null }
    catch {
        Write-Warning "Automatic rollback needs attention. Keep the receipt: $receiptPath"
        throw
    }
    throw
}
