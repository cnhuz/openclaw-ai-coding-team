[CmdletBinding()]
param(
    [string]$OpenClawHome,
    [string]$ConfigPath,
    [string]$CaptainChannel,
    [string]$CaptainAccountId,
    [switch]$SkipGitInit,
    [switch]$SkipConfigMerge,
    [switch]$SkipAutomation,
    [switch]$SkipIgnite,
    [switch]$SkipQmdInit,
    [switch]$QmdEmbed,
    [string]$AutomationTimezone = "Asia/Shanghai",
    [switch]$DryRun
)

Set-StrictMode -Version 3
$ErrorActionPreference = "Stop"

function Get-DefaultOpenClawHome {
    if ($env:OPENCLAW_HOME) {
        return $env:OPENCLAW_HOME
    }
    if ($env:USERPROFILE) {
        return (Join-Path $env:USERPROFILE ".openclaw")
    }
    return (Join-Path $HOME ".openclaw")
}

function Ensure-Directory {
    param([string]$Path)
    if ($DryRun) {
        return
    }
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Copy-DirectoryContent {
    param(
        [string]$Source,
        [string]$Destination
    )
    Ensure-Directory -Path $Destination
    if ($DryRun) {
        return
    }
    Get-ChildItem -Path $Source -Force | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $Destination -Recurse -Force
    }
}

function Preserve-RuntimeState {
    param(
        [string]$WorkspacePath,
        [string]$StashPath
    )
    foreach ($relativePath in @("MEMORY.md", "memory", "tasks", "specs", "verification-reports", "release-notes", "data/dashboard.md", "data/exec-logs", "data/knowledge-proposals", "data/github-backup-policy.json", "data/execution-target.json", "data/research", "data/skills", "data/kpi", "handoffs")) {
        $sourcePath = Join-Path $WorkspacePath $relativePath
        if (-not (Test-Path $sourcePath)) {
            continue
        }
        $targetPath = Join-Path $StashPath $relativePath
        Ensure-Directory -Path (Split-Path -Parent $targetPath)
        Copy-Item -Path $sourcePath -Destination $targetPath -Recurse -Force
    }
}

function Restore-RuntimeState {
    param(
        [string]$WorkspacePath,
        [string]$StashPath
    )
    foreach ($relativePath in @("MEMORY.md", "memory", "tasks", "specs", "verification-reports", "release-notes", "data/dashboard.md", "data/exec-logs", "data/knowledge-proposals", "data/github-backup-policy.json", "data/execution-target.json", "data/research", "data/skills", "data/kpi", "handoffs")) {
        $sourcePath = Join-Path $StashPath $relativePath
        if (-not (Test-Path $sourcePath)) {
            continue
        }
        $targetPath = Join-Path $WorkspacePath $relativePath
        if (Test-Path $targetPath) {
            Remove-Item -Path $targetPath -Recurse -Force
        }
        Ensure-Directory -Path (Split-Path -Parent $targetPath)
        Copy-Item -Path $sourcePath -Destination $targetPath -Recurse -Force
    }
}

function Remove-RuntimeBootstrap {
    param([string]$WorkspacePath)
    $bootstrapPath = Join-Path $WorkspacePath "BOOTSTRAP.md"
    if ((Test-Path $bootstrapPath) -and -not $DryRun) {
        Remove-Item -Path $bootstrapPath -Force
    }
}

function Ensure-CoreExecLogDirs {
    param([string]$WorkspacePath)
    foreach ($jobName in @("dashboard-refresh", "ambient-discovery", "signal-triage", "opportunity-deep-dive", "opportunity-promotion", "exploration-learning", "planner-intake", "reviewer-gate", "dispatch-approved", "tester-gate", "releaser-gate", "reflect-release", "daily-kpi", "weekly-kpi", "skill-scout", "skill-maintenance", "research-sprint", "build-sprint", "daily-reflection", "daily-curation", "daily-backup", "memory-hourly", "memory-weekly")) {
        Ensure-Directory -Path (Join-Path $WorkspacePath ("data/exec-logs/{0}" -f $jobName))
    }
}

function Ensure-RuntimeDefaults {
    param(
        [string]$WorkspacePath,
        [string]$CommonRoot
    )
    foreach ($relativePath in @("data/execution-target.json", "data/research/site_profiles.json", "data/research/tool_profiles.json", "data/skills/README.md", "data/skills/policy.json", "data/skills/dependency_policy.json", "data/skills/catalog.json", "data/kpi/README.md", "data/kpi/rules.v1.json")) {
        $targetPath = Join-Path $WorkspacePath $relativePath
        $sourcePath = Join-Path $CommonRoot $relativePath
        if ((Test-Path $targetPath) -or -not (Test-Path $sourcePath)) {
            continue
        }
        Ensure-Directory -Path (Split-Path -Parent $targetPath)
        if (-not $DryRun) {
            Copy-Item -Path $sourcePath -Destination $targetPath -Recurse -Force
        }
    }
    if (-not $DryRun) {
        $pythonCommand = Get-PythonCommand
        if ($pythonCommand) {
            & $pythonCommand (Join-Path $scriptRoot "merge_runtime_defaults.py") --workspace $WorkspacePath --common-root $CommonRoot | Out-Null
        }
    }
}

function Render-ExecutionTarget {
    param(
        [string]$WorkspacePath,
        [string]$CommonRoot,
        [string]$PackageRoot
    )
    if ($DryRun) {
        return
    }
    $templatePath = Join-Path $CommonRoot "data/execution-target.json"
    if (-not (Test-Path $templatePath)) {
        return
    }
    $targetPath = Join-Path $WorkspacePath "data/execution-target.json"
    $template = Get-Content -Path $templatePath -Raw | ConvertFrom-Json
    $payload = if (Test-Path $targetPath) {
        Get-Content -Path $targetPath -Raw | ConvertFrom-Json
    } else {
        Clone-JsonObject -Value $template
    }
    if (-not $payload.PSObject.Properties["target"]) {
        $payload | Add-Member -NotePropertyName "target" -NotePropertyValue ([pscustomobject]@{})
    }
    $target = $payload.target
    foreach ($prop in $template.target.PSObject.Properties) {
        if (-not $target.PSObject.Properties[$prop.Name]) {
            $target | Add-Member -NotePropertyName $prop.Name -NotePropertyValue $prop.Value
            continue
        }
        if ($target.($prop.Name) -is [System.Collections.IEnumerable] -and -not ($target.($prop.Name) -is [string]) -and $prop.Value -is [System.Collections.IEnumerable] -and -not ($prop.Value -is [string])) {
            $currentItems = @($target.($prop.Name))
            $merged = New-Object System.Collections.ArrayList
            foreach ($item in $currentItems) {
                [void]$merged.Add($item)
            }
            foreach ($item in @($prop.Value)) {
                if ($merged -notcontains $item) {
                    [void]$merged.Add($item)
                }
            }
            $target.($prop.Name) = @($merged.ToArray())
        }
    }
    if (-not $target.repo_root -or $target.repo_root -eq "__PACKAGE_ROOT__") {
        $target.repo_root = $PackageRoot
    }
    if ($null -eq $target.build_entrypoint) { $target.build_entrypoint = "" }
    if ($null -eq $target.release_command) { $target.release_command = "" }
    if ($null -eq $target.rollback_command) { $target.rollback_command = "git revert <commit>" }
    Set-Content -Path $targetPath -Value ($payload | ConvertTo-Json -Depth 30) -Encoding UTF8
}

function Get-PythonCommand {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }
    return $null
}

function Append-IfMissing {
    param(
        [string]$Path,
        [string]$Block
    )
    $existing = ""
    if (Test-Path $Path) {
        $existing = Get-Content -Path $Path -Raw
    }
    $trimmed = $Block.Trim()
    if ($existing.Contains($trimmed)) {
        return
    }
    if ($DryRun) {
        return
    }
    $prefix = ""
    if ($existing -and -not $existing.EndsWith("`n")) {
        $prefix = "`r`n"
    }
    Add-Content -Path $Path -Value ($prefix + $trimmed + "`r`n")
}

function Ensure-TodayDailyLog {
    param(
        [string]$WorkspacePath,
        [string]$DailyTemplatePath
    )
    $today = Get-Date
    $day = $today.ToString("yyyy-MM-dd")
    $weekday = $today.ToString("dddd")
    $dailyPath = Join-Path $WorkspacePath "memory/$day.md"
    if (Test-Path $dailyPath) {
        return $dailyPath
    }
    if ($DryRun) {
        return $dailyPath
    }
    $template = Get-Content -Path $DailyTemplatePath -Raw
    $content = $template.Replace("YYYY-MM-DD", $day).Replace("(Day)", "($weekday)")
    Set-Content -Path $dailyPath -Value $content -Encoding UTF8
    return $dailyPath
}

function Update-ToolsRuntimeSection {
    param([string]$ToolsPath)
    $block = @(
        "## Installed Runtime Paths",
        "",
        "- `scripts/scan_sessions_incremental.py`：enabled",
        "- `scripts/lockfile.py`：enabled",
        "- `scripts/weekly_gate.py`：enabled",
        "- `scripts/git_backup_health.py`：enabled",
        "- `scripts/validate_task_registry.py`：enabled",
        "- `scripts/query_task_registry.py`：enabled",
        "- `scripts/update_task_registry.py`：enabled",
        "- `scripts/create_handoff.py`：enabled",
        "- `scripts/refresh_dashboard.py`：enabled",
        "- `scripts/execution_target.py`：enabled",
        "- `scripts/verify_worktree_lifecycle.py`：enabled",
        "- `scripts/compute_agent_kpi.py`：enabled",
        "- `scripts/prepare_exploration_batch.py`：enabled",
        "- `scripts/prepare_site_frontier.py`：enabled",
        "- `scripts/prepare_planner_intake.py`：enabled",
        "- `scripts/prepare_builder_intake.py`：enabled",
        "- `scripts/prepare_tester_intake.py`：enabled",
        "- `scripts/prepare_releaser_intake.py`：enabled",
        "- `scripts/prepare_reflector_intake.py`：enabled",
        "- `scripts/validate_reflection_closeout.py`：enabled",
        "- `scripts/record_research_signal.py`：enabled",
        "- `scripts/triage_research_signals.py`：enabled",
        "- `scripts/query_research_opportunities.py`：enabled",
        "- `scripts/promote_research_opportunity.py`：enabled",
        "- `scripts/bridge_ready_review_opportunity.py`：enabled",
        "- `scripts/bridge_approved_task.py`：enabled",
        "- `scripts/exploration_learning.py`：enabled",
        "- `scripts/upsert_site_profile.py`：enabled",
        "- `scripts/plan_tool_route.py`：enabled",
        "- `scripts/record_tool_attempt.py`：enabled",
        "- `scripts/tool_route_learning.py`：enabled",
        "- `scripts/sync_skill_inventory.py`：enabled",
        "- `scripts/register_skill_candidate.py`：enabled",
        "- `scripts/query_skill_catalog.py`：enabled",
        "- `scripts/bootstrap_skill_dependency.py`：enabled",
        "- `scripts/install_skill_candidate.py`：enabled",
        "- `scripts/worktree_lifecycle.py`：enabled",
        "- `AGENTS.md`：merged common + role rules",
        "- `BOOT.md`：optional `boot-md` startup checklist"
    ) -join "`r`n"
    Append-IfMissing -Path $ToolsPath -Block $block
}

function Merge-RoleAgents {
    param(
        [string]$WorkspacePath,
        [string]$RoleAgentsPath,
        [string]$AgentId
    )
    $agentsPath = Join-Path $WorkspacePath "AGENTS.md"
    if (-not (Test-Path $RoleAgentsPath) -or -not (Test-Path $agentsPath)) {
        return
    }
    $startMarker = "<!-- OPENCLAW-ROLE:${AgentId}:BEGIN -->"
    $endMarker = "<!-- OPENCLAW-ROLE:${AgentId}:END -->"
    $existing = Get-Content -Path $agentsPath -Raw
    if ($existing.Contains($startMarker) -or $DryRun) {
        return
    }
    $roleContent = Get-Content -Path $RoleAgentsPath -Raw
    $append = @(
        "",
        $startMarker,
        "",
        $roleContent.Trim(),
        $endMarker,
        ""
    ) -join "`r`n"
    Add-Content -Path $agentsPath -Value $append
}

function Merge-MemorySeed {
    param(
        [string]$WorkspacePath
    )
    $memoryPath = Join-Path $WorkspacePath "MEMORY.md"
    $seedPath = Join-Path $WorkspacePath "MEMORY.seed.md"
    if (-not (Test-Path $seedPath)) {
        return
    }
    $seed = Get-Content -Path $seedPath -Raw
    if (-not $seed.Trim()) {
        return
    }
    Append-IfMissing -Path $memoryPath -Block $seed
}

function Convert-ToMutableList {
    param($Items)
    $list = New-Object System.Collections.ArrayList
    foreach ($item in @($Items)) {
        if ($null -ne $item) {
            [void]$list.Add($item)
        }
    }
    Write-Output -NoEnumerate $list
}

function Clone-JsonObject {
    param($Value)
    if ($null -eq $Value) {
        return $null
    }
    $json = $Value | ConvertTo-Json -Depth 30
    return ($json | ConvertFrom-Json)
}

function Ensure-GitRepo {
    param(
        [string]$WorkspacePath,
        [string]$CommitMessage
    )
    if ($SkipGitInit) {
        return
    }
    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) {
        Write-Warning "git not found; skipping Git init for $WorkspacePath"
        return
    }
    if (-not (Test-Path (Join-Path $WorkspacePath ".git"))) {
        if (-not $DryRun) {
            & git -C $WorkspacePath init | Out-Null
            & git -C $WorkspacePath branch -M main | Out-Null
        }
    }
    if ($DryRun) {
        return
    }
    $userName = (& git -C $WorkspacePath config user.name 2>$null)
    $userEmail = (& git -C $WorkspacePath config user.email 2>$null)
    if (-not $userName -or -not $userEmail) {
        Write-Warning "git user.name / user.email is missing; repo initialized but initial commit skipped for $WorkspacePath"
        return
    }
    & git -C $WorkspacePath add . | Out-Null
    $status = (& git -C $WorkspacePath status --short)
    if ($status) {
        & git -C $WorkspacePath commit -m $CommitMessage | Out-Null
    }
}

function Ensure-Property {
    param(
        [psobject]$Object,
        [string]$Name,
        $Value
    )
    if (-not $Object.PSObject.Properties[$Name]) {
        $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
    }
    return $Object.PSObject.Properties[$Name].Value
}

function Merge-OpenClawConfig {
    param(
        [string]$TargetConfigPath,
        [string]$ResolvedOpenClawHome,
        [string]$SnippetPath,
        [string]$HooksSnippetPath,
        [string]$MemorySnippetPath,
        [string]$Channel,
        [string]$AccountId
    )
    $snippet = Get-Content -Path $SnippetPath -Raw | ConvertFrom-Json
    $hooksSnippet = if (Test-Path $HooksSnippetPath) {
        Get-Content -Path $HooksSnippetPath -Raw | ConvertFrom-Json
    } else {
        [pscustomobject]@{}
    }
    $memorySnippet = if (Test-Path $MemorySnippetPath) {
        Get-Content -Path $MemorySnippetPath -Raw | ConvertFrom-Json
    } else {
        [pscustomobject]@{}
    }
    $config = if (Test-Path $TargetConfigPath) {
        Get-Content -Path $TargetConfigPath -Raw | ConvertFrom-Json
    } else {
        [pscustomobject]@{}
    }

    $agentsObject = Ensure-Property -Object $config -Name "agents" -Value ([pscustomobject]@{})
    $defaultsObject = Ensure-Property -Object $agentsObject -Name "defaults" -Value ([pscustomobject]@{})
    foreach ($prop in $snippet.agents.defaults.PSObject.Properties) {
        if ($prop.Name -eq "subagents") {
            $subagentsDefaults = Ensure-Property -Object $defaultsObject -Name "subagents" -Value ([pscustomobject]@{})
            if ($subagentsDefaults.PSObject.Properties["maxConcurrent"]) {
                $subagentsDefaults.maxConcurrent = $snippet.agents.defaults.subagents.maxConcurrent
            } else {
                $subagentsDefaults | Add-Member -NotePropertyName "maxConcurrent" -NotePropertyValue $snippet.agents.defaults.subagents.maxConcurrent
            }
            continue
        }
        if ($defaultsObject.PSObject.Properties[$prop.Name]) {
            $defaultsObject.($prop.Name) = $prop.Value
        } else {
            $defaultsObject | Add-Member -NotePropertyName $prop.Name -NotePropertyValue $prop.Value
        }
    }

    $agentItems = $null
    if ($agentsObject.PSObject.Properties["list"]) {
        $agentItems = $agentsObject.list
    }
    $agentList = Convert-ToMutableList -Items $agentItems
    foreach ($agentDef in @($snippet.agents.list)) {
        $newAgent = Clone-JsonObject -Value $agentDef
        $newAgent.workspace = Join-Path $ResolvedOpenClawHome ("workspace-{0}" -f $newAgent.id)
        $newAgent.agentDir = Join-Path (Join-Path $ResolvedOpenClawHome "agents") $newAgent.id
        $matchedIndex = -1
        for ($index = 0; $index -lt $agentList.Count; $index++) {
            if ($agentList[$index].id -eq $newAgent.id) {
                $matchedIndex = $index
                break
            }
        }
        if ($matchedIndex -ge 0) {
            $agentList[$matchedIndex] = $newAgent
        } else {
            [void]$agentList.Add($newAgent)
        }
    }
    if ($agentsObject.PSObject.Properties["list"]) {
        $agentsObject.list = @($agentList.ToArray())
    } else {
        $agentsObject | Add-Member -NotePropertyName "list" -NotePropertyValue @($agentList.ToArray())
    }

    if ($Channel -and $AccountId) {
        $bindingItems = $null
        if ($config.PSObject.Properties["bindings"]) {
            $bindingItems = $config.bindings
        }
        $bindings = Convert-ToMutableList -Items $bindingItems
        $binding = [pscustomobject]@{
            agentId = "aic-captain"
            match = [pscustomobject]@{
                channel = $Channel
                accountId = $AccountId
            }
        }
        $matchedIndex = -1
        for ($index = 0; $index -lt $bindings.Count; $index++) {
            if ($bindings[$index].agentId -eq "aic-captain") {
                $matchedIndex = $index
                break
            }
        }
        if ($matchedIndex -ge 0) {
            $bindings[$matchedIndex] = $binding
        } else {
            [void]$bindings.Add($binding)
        }
        if ($config.PSObject.Properties["bindings"]) {
            $config.bindings = @($bindings.ToArray())
        } else {
            $config | Add-Member -NotePropertyName "bindings" -NotePropertyValue @($bindings.ToArray())
        }
    }

    if ($memorySnippet.PSObject.Properties["memory"]) {
        $configMemory = Ensure-Property -Object $config -Name "memory" -Value ([pscustomobject]@{})
        foreach ($prop in $memorySnippet.memory.PSObject.Properties) {
            if ($prop.Value -is [psobject] -and $configMemory.PSObject.Properties[$prop.Name] -and $configMemory.($prop.Name) -is [psobject]) {
                foreach ($nestedProp in $prop.Value.PSObject.Properties) {
                    if ($configMemory.($prop.Name).PSObject.Properties[$nestedProp.Name]) {
                        $configMemory.($prop.Name).($nestedProp.Name) = $nestedProp.Value
                    } else {
                        $configMemory.($prop.Name) | Add-Member -NotePropertyName $nestedProp.Name -NotePropertyValue $nestedProp.Value
                    }
                }
            } elseif ($configMemory.PSObject.Properties[$prop.Name]) {
                $configMemory.($prop.Name) = $prop.Value
            } else {
                $configMemory | Add-Member -NotePropertyName $prop.Name -NotePropertyValue $prop.Value
            }
        }
    }

    if ($hooksSnippet.PSObject.Properties["hooks"]) {
        $configHooks = Ensure-Property -Object $config -Name "hooks" -Value ([pscustomobject]@{})
        foreach ($scope in $hooksSnippet.hooks.PSObject.Properties) {
            $targetScope = Ensure-Property -Object $configHooks -Name $scope.Name -Value ([pscustomobject]@{})
            if ($scope.Value.PSObject.Properties["enabled"]) {
                if ($targetScope.PSObject.Properties["enabled"]) {
                    $targetScope.enabled = $scope.Value.enabled
                } else {
                    $targetScope | Add-Member -NotePropertyName "enabled" -NotePropertyValue $scope.Value.enabled
                }
            }
            $entriesObject = if ($targetScope.PSObject.Properties["entries"] -and $targetScope.entries -is [psobject]) {
                $targetScope.entries
            } else {
                [pscustomobject]@{}
            }
            foreach ($entryProp in $scope.Value.entries.PSObject.Properties) {
                if ($entriesObject.PSObject.Properties[$entryProp.Name]) {
                    $entriesObject.($entryProp.Name) = $entryProp.Value
                } else {
                    $entriesObject | Add-Member -NotePropertyName $entryProp.Name -NotePropertyValue $entryProp.Value
                }
            }
            if ($targetScope.PSObject.Properties["entries"]) {
                $targetScope.entries = $entriesObject
            } else {
                $targetScope | Add-Member -NotePropertyName "entries" -NotePropertyValue $entriesObject
            }
        }
    }

    if ((Test-Path $TargetConfigPath) -and -not $DryRun) {
        $backupStamp = Get-Date -Format "yyyyMMdd-HHmmss"
        Copy-Item -Path $TargetConfigPath -Destination "$TargetConfigPath.$backupStamp.bak" -Force
    }
    if (-not $DryRun) {
        Ensure-Directory -Path (Split-Path -Parent $TargetConfigPath)
        Set-Content -Path $TargetConfigPath -Value ($config | ConvertTo-Json -Depth 30) -Encoding UTF8
    }
}

function Prime-QmdMemory {
    param(
        [string]$AgentId,
        [string]$WorkspacePath,
        [string]$RuntimeAgentDir,
        [string]$PrimerPath
    )
    if ($SkipQmdInit) {
        return
    }
    $qmd = Get-Command qmd -ErrorAction SilentlyContinue
    if (-not $qmd) {
        Write-Warning "qmd not found; qmd memory priming skipped for $AgentId"
        return
    }
    $python = Get-PythonCommand
    if (-not $python) {
        Write-Warning "python3/python not found; qmd memory priming skipped for $AgentId"
        return
    }
    $args = @(
        $PrimerPath,
        "--agent-id", $AgentId,
        "--workspace", $WorkspacePath,
        "--agent-dir", $RuntimeAgentDir
    )
    if ($QmdEmbed) {
        $args += "--embed"
    }
    if ($DryRun) {
        $args += "--dry-run"
    }
    & $python @args | Out-Null
}

if (-not $OpenClawHome) {
    $OpenClawHome = Get-DefaultOpenClawHome
}
if (-not $ConfigPath) {
    $ConfigPath = Join-Path $OpenClawHome "openclaw.json"
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Split-Path -Parent $scriptRoot
$commonRoot = Join-Path $packageRoot "templates/common"
$agentsRoot = Join-Path $packageRoot "agents"
$runtimeScriptsRoot = Join-Path $packageRoot "automation/scripts"
$snippetPath = Join-Path $packageRoot "config/openclaw.agents.snippet.json"
$hooksSnippetPath = Join-Path $packageRoot "config/openclaw.hooks.snippet.json"
$memorySnippetPath = Join-Path $packageRoot "config/openclaw.memory.qmd.snippet.json"
$dailyTemplatePath = Join-Path $commonRoot "memory/daily/TEMPLATE.md"
$qmdPrimerPath = Join-Path $scriptRoot "prime_qmd_memory.py"

Ensure-Directory -Path $OpenClawHome

$createdWorkspaces = @()
$agentDirectories = Get-ChildItem -Path $agentsRoot -Directory | Sort-Object Name

foreach ($agentDirectory in $agentDirectories) {
    $agentId = $agentDirectory.Name
    $workspacePath = Join-Path $OpenClawHome ("workspace-{0}" -f $agentId)
    $runtimeAgentDir = Join-Path (Join-Path $OpenClawHome "agents") $agentId
    $workspaceExists = Test-Path $workspacePath
    $stateStashPath = $null

    Ensure-Directory -Path $workspacePath
    Ensure-Directory -Path $runtimeAgentDir
    if ($workspaceExists -and -not $DryRun) {
        $stateStashPath = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString())
        Ensure-Directory -Path $stateStashPath
        Preserve-RuntimeState -WorkspacePath $workspacePath -StashPath $stateStashPath
    }
    Copy-DirectoryContent -Source $commonRoot -Destination $workspacePath
    if ($workspaceExists -and -not $DryRun) {
        Restore-RuntimeState -WorkspacePath $workspacePath -StashPath $stateStashPath
        Remove-Item -Path $stateStashPath -Recurse -Force
    }
    Ensure-RuntimeDefaults -WorkspacePath $workspacePath -CommonRoot $commonRoot
    Render-ExecutionTarget -WorkspacePath $workspacePath -CommonRoot $commonRoot -PackageRoot $packageRoot
    Remove-RuntimeBootstrap -WorkspacePath $workspacePath
    Ensure-CoreExecLogDirs -WorkspacePath $workspacePath

    $roleSource = Join-Path $agentDirectory.FullName "AGENTS.md"
    Merge-RoleAgents -WorkspacePath $workspacePath -RoleAgentsPath $roleSource -AgentId $agentId

    foreach ($roleFile in @("SOUL.md", "IDENTITY.md", "HEARTBEAT.md", "MEMORY.seed.md")) {
        $rolePath = Join-Path $agentDirectory.FullName $roleFile
        if ((Test-Path $rolePath) -and -not $DryRun) {
            Copy-Item -Path $rolePath -Destination (Join-Path $workspacePath $roleFile) -Force
        }
    }

    $workspaceScripts = Join-Path $workspacePath "scripts"
    Ensure-Directory -Path $workspaceScripts
    if (-not $DryRun) {
        Get-ChildItem -Path $runtimeScriptsRoot -Filter "*.py" | ForEach-Object {
            Copy-Item -Path $_.FullName -Destination (Join-Path $workspaceScripts $_.Name) -Force
        }
    }

    Ensure-TodayDailyLog -WorkspacePath $workspacePath -DailyTemplatePath $dailyTemplatePath | Out-Null
    Merge-MemorySeed -WorkspacePath $workspacePath
    Update-ToolsRuntimeSection -ToolsPath (Join-Path $workspacePath "TOOLS.md")
    Ensure-GitRepo -WorkspacePath $workspacePath -CommitMessage ("chore: bootstrap {0} workspace" -f $agentId)
    Prime-QmdMemory -AgentId $agentId -WorkspacePath $workspacePath -RuntimeAgentDir $runtimeAgentDir -PrimerPath $qmdPrimerPath

    $createdWorkspaces += [pscustomobject]@{
        AgentId = $agentId
        Workspace = $workspacePath
    }
}

if (-not $SkipConfigMerge) {
    Merge-OpenClawConfig -TargetConfigPath $ConfigPath -ResolvedOpenClawHome $OpenClawHome -SnippetPath $snippetPath -HooksSnippetPath $hooksSnippetPath -MemorySnippetPath $memorySnippetPath -Channel $CaptainChannel -AccountId $CaptainAccountId
}

$automationStatus = "skipped"
if (-not $SkipAutomation) {
    $openclawCommand = Get-Command openclaw -ErrorAction SilentlyContinue
    if ($openclawCommand) {
        $automationScript = Join-Path $scriptRoot "install-openclaw-automation.ps1"
        $automationArgs = @(
            "-OpenClawHome", $OpenClawHome,
            "-Timezone", $AutomationTimezone
        )
        if ($SkipIgnite) {
            $automationArgs += "-SkipIgnite"
        }
        if ($DryRun) {
            $automationArgs += "-DryRun"
        }
        & $automationScript @automationArgs
        $automationStatus = if ($SkipIgnite) { "installed" } else { "installed + ignited" }
    } else {
        Write-Warning "openclaw not found; skipping automation install"
        $automationStatus = "skipped (openclaw missing)"
    }
}

Write-Host ""
Write-Host "OpenClaw AI Coding Team install result:" -ForegroundColor Green
foreach ($workspaceInfo in $createdWorkspaces) {
    Write-Host ("- {0} -> {1}" -f $workspaceInfo.AgentId, $workspaceInfo.Workspace)
}
if ($SkipConfigMerge) {
    Write-Host "- openclaw.json merge skipped" -ForegroundColor Yellow
} else {
    Write-Host ("- config updated: {0}" -f $ConfigPath)
}
if ($CaptainChannel -and $CaptainAccountId) {
    Write-Host ("- captain binding configured: {0} / {1}" -f $CaptainChannel, $CaptainAccountId)
} else {
    Write-Host "- captain binding not provided; keeping existing binding or leaving it empty" -ForegroundColor Yellow
}
Write-Host ("- automation: {0}" -f $automationStatus)
if ($SkipGitInit) {
    Write-Host "- workspace Git init skipped" -ForegroundColor Yellow
}
if ($SkipQmdInit) {
    Write-Host "- qmd memory priming skipped" -ForegroundColor Yellow
} elseif ($QmdEmbed) {
    Write-Host "- qmd memory primed with embed"
} else {
    Write-Host "- qmd memory primed (BM25/update only)"
}
if ($DryRun) {
    Write-Host "- dry-run mode: no files were written" -ForegroundColor Yellow
}
