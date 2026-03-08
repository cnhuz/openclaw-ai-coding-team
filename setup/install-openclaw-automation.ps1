[CmdletBinding()]
param(
    [string]$OpenClawHome,
    [string]$Timezone = "Asia/Shanghai",
    [string]$ResearchEvery = "1h",
    [string]$BuildEvery = "15m",
    [string]$DashboardEvery = "10m",
    [string]$AmbientEvery = "30m",
    [string]$TriageEvery = "45m",
    [string]$DeepDiveEvery = "2h",
    [string]$PromotionEvery = "4h",
    [string]$ExploreLearnEvery = "6h",
    [string]$PlannerIntakeEvery = "10m",
    [string]$ReviewerGateEvery = "15m",
    [string]$DispatchApprovedEvery = "10m",
    [string]$TesterGateEvery = "15m",
    [string]$ReleaserGateEvery = "20m",
    [string]$ReflectReleaseEvery = "30m",
    [string]$SkillScoutEvery = "12h",
    [string]$SkillMaintenanceEvery = "24h",
    [string]$MemoryHourlyEvery = "1h",
    [string]$MemoryAgents = "aic-captain,aic-planner,aic-dispatcher",
    [switch]$SkipIgnite,
    [switch]$DryRun
)

Set-StrictMode -Version 3
$ErrorActionPreference = "Stop"

$TeamAgents = @(
    "aic-captain",
    "aic-planner",
    "aic-reviewer",
    "aic-dispatcher",
    "aic-researcher",
    "aic-builder",
    "aic-tester",
    "aic-releaser",
    "aic-curator",
    "aic-reflector"
)

$MemoryAgentList = @($MemoryAgents.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })

function Get-DefaultOpenClawHome {
    if ($env:OPENCLAW_HOME) {
        return $env:OPENCLAW_HOME
    }
    if ($env:USERPROFILE) {
        return (Join-Path $env:USERPROFILE ".openclaw")
    }
    return (Join-Path $HOME ".openclaw")
}

function Get-JobIdsByName {
    param([string]$Name)
    $payload = openclaw cron list --json | ConvertFrom-Json
    foreach ($job in @($payload.jobs)) {
        if ($job.name -eq $Name -and $job.id) {
            $job.id
        }
    }
}

function Get-RenderedPrompt {
    param(
        [string]$PromptPath,
        [string]$AgentId
    )
    $text = Get-Content -Path $PromptPath -Raw
    $text = $text.Replace("__AGENT_ID__", $AgentId)
    $text = $text.Replace("__TIMEZONE__", $Timezone)
    $text = $text.Replace("__OPENCLAW_HOME__", $OpenClawHome)
    return $text
}

function Remove-ExistingJobs {
    param([string]$Name)
    foreach ($jobId in @(Get-JobIdsByName -Name $Name)) {
        if (-not $jobId) {
            continue
        }
        if ($DryRun) {
            Write-Host ("DRY-RUN remove cron job: {0} ({1})" -f $Name, $jobId)
            continue
        }
        openclaw cron remove $jobId | Out-Null
    }
}

function Install-IntervalJob {
    param(
        [string]$Name,
        [string]$AgentId,
        [string]$Every,
        [string]$PromptPath,
        [string]$Description
    )
    $message = Get-RenderedPrompt -PromptPath $PromptPath -AgentId $AgentId
    Remove-ExistingJobs -Name $Name
    if ($DryRun) {
        Write-Host ("DRY-RUN add interval cron: {0} agent={1} every={2}" -f $Name, $AgentId, $Every)
        return
    }
    openclaw cron add `
        --name $Name `
        --description $Description `
        --agent $AgentId `
        --session isolated `
        --light-context `
        --no-deliver `
        --timeout-seconds 1800 `
        --every $Every `
        --message $message | Out-Null
}

function Install-DailyJob {
    param(
        [string]$Name,
        [string]$AgentId,
        [string]$CronExpr,
        [string]$PromptPath,
        [string]$Description
    )
    $message = Get-RenderedPrompt -PromptPath $PromptPath -AgentId $AgentId
    Remove-ExistingJobs -Name $Name
    if ($DryRun) {
        Write-Host ("DRY-RUN add daily cron: {0} agent={1} cron={2} tz={3}" -f $Name, $AgentId, $CronExpr, $Timezone)
        return
    }
    openclaw cron add `
        --name $Name `
        --description $Description `
        --agent $AgentId `
        --session isolated `
        --light-context `
        --no-deliver `
        --timeout-seconds 1800 `
        --cron $CronExpr `
        --tz $Timezone `
        --exact `
        --message $message | Out-Null
}

if (-not $OpenClawHome) {
    $OpenClawHome = Get-DefaultOpenClawHome
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Split-Path -Parent $scriptRoot
$promptRoot = Join-Path $packageRoot "automation/cron-prompts"

Install-IntervalJob -Name "dashboard-refresh" -AgentId "aic-captain" -Every $DashboardEvery -PromptPath (Join-Path $promptRoot "dashboard-refresh.md") -Description "Refresh the captain dashboard and expose ignition gaps."
Install-IntervalJob -Name "ambient-discovery" -AgentId "aic-researcher" -Every $AmbientEvery -PromptPath (Join-Path $promptRoot "ambient-discovery.md") -Description "Continuously scan public channels for new external signals."
Install-IntervalJob -Name "signal-triage" -AgentId "aic-researcher" -Every $TriageEvery -PromptPath (Join-Path $promptRoot "signal-triage.md") -Description "Aggregate discovery signals into ranked opportunities."
Install-IntervalJob -Name "opportunity-deep-dive" -AgentId "aic-researcher" -Every $DeepDiveEvery -PromptPath (Join-Path $promptRoot "opportunity-deep-dive.md") -Description "Deep dive the highest-value research opportunity."
Install-IntervalJob -Name "opportunity-promotion" -AgentId "aic-captain" -Every $PromotionEvery -PromptPath (Join-Path $promptRoot "opportunity-promotion.md") -Description "Promote mature opportunities into formal tasks."
Install-IntervalJob -Name "exploration-learning" -AgentId "aic-researcher" -Every $ExploreLearnEvery -PromptPath (Join-Path $promptRoot "exploration-learning.md") -Description "Learn better query expansions and blocked terms from exploration outcomes."
Install-IntervalJob -Name "planner-intake" -AgentId "aic-planner" -Every $PlannerIntakeEvery -PromptPath (Join-Path $promptRoot "planner-intake.md") -Description "Consume Intake tasks and turn them into concrete specs."
Install-IntervalJob -Name "reviewer-gate" -AgentId "aic-reviewer" -Every $ReviewerGateEvery -PromptPath (Join-Path $promptRoot "reviewer-gate.md") -Description "Review planned specs and turn them into Approved or Replan."
Install-IntervalJob -Name "dispatch-approved" -AgentId "aic-dispatcher" -Every $DispatchApprovedEvery -PromptPath (Join-Path $promptRoot "dispatch-approved.md") -Description "Move approved tasks into the builder queue."
Install-IntervalJob -Name "tester-gate" -AgentId "aic-tester" -Every $TesterGateEvery -PromptPath (Join-Path $promptRoot "tester-gate.md") -Description "Verify build outputs and route them to releaser or back to builder."
Install-IntervalJob -Name "releaser-gate" -AgentId "aic-releaser" -Every $ReleaserGateEvery -PromptPath (Join-Path $promptRoot "releaser-gate.md") -Description "Apply the release gate and hand released tasks to reflector."
Install-IntervalJob -Name "reflect-release" -AgentId "aic-reflector" -Every $ReflectReleaseEvery -PromptPath (Join-Path $promptRoot "reflect-release.md") -Description "Close released tasks with reflection and knowledge proposals."
Install-IntervalJob -Name "skill-scout" -AgentId "aic-researcher" -Every $SkillScoutEvery -PromptPath (Join-Path $promptRoot "skill-scout.md") -Description "Discover skill candidates from capability gaps."
Install-IntervalJob -Name "skill-maintenance" -AgentId "aic-researcher" -Every $SkillMaintenanceEvery -PromptPath (Join-Path $promptRoot "skill-maintenance.md") -Description "Auto-install trusted low-risk skills."
Install-IntervalJob -Name "research-sprint" -AgentId "aic-researcher" -Every $ResearchEvery -PromptPath (Join-Path $promptRoot "research-sprint.md") -Description "Run one research sprint and push the task toward scope."
Install-IntervalJob -Name "build-sprint" -AgentId "aic-builder" -Every $BuildEvery -PromptPath (Join-Path $promptRoot "build-sprint.md") -Description "Run one implementation sprint from the build queue."
Install-DailyJob -Name "daily-reflection" -AgentId "aic-reflector" -CronExpr "10 0 * * *" -PromptPath (Join-Path $promptRoot "daily-reflection.md") -Description "Run the daily reflection loop."
Install-DailyJob -Name "daily-curation" -AgentId "aic-curator" -CronExpr "20 0 * * *" -PromptPath (Join-Path $promptRoot "daily-curation.md") -Description "Run the daily curation loop."

foreach ($agentId in $TeamAgents) {
    Install-DailyJob -Name ("daily-backup-{0}" -f $agentId) -AgentId $agentId -CronExpr "0 0 * * *" -PromptPath (Join-Path $promptRoot "daily-backup.md") -Description ("Run the daily backup check for {0}." -f $agentId)
}

foreach ($agentId in $MemoryAgentList) {
    Install-IntervalJob -Name ("memory-hourly-{0}" -f $agentId) -AgentId $agentId -Every $MemoryHourlyEvery -PromptPath (Join-Path $promptRoot "memory-hourly.md") -Description ("Run memory-hourly sync for {0}." -f $agentId)
    Install-DailyJob -Name ("memory-weekly-{0}" -f $agentId) -AgentId $agentId -CronExpr "40 0 * * *" -PromptPath (Join-Path $promptRoot "memory-weekly.md") -Description ("Run gated weekly memory consolidation for {0}." -f $agentId)
}

if (-not $SkipIgnite) {
    $igniteText = "Initialize coding-team control loop. Refresh dashboards, scan external public signals, triage opportunities, and if the latest session contains a concrete but untracked request, create an Intake task and route it toward planning. If mature opportunities or delivery-stage tasks already exist, advance them to the next explicit owner. Stay quiet if nothing actionable exists."
    if ($DryRun) {
        Write-Host ("DRY-RUN system event: {0}" -f $igniteText)
    } else {
        openclaw system event --mode now --text $igniteText | Out-Null
    }
}

Write-Host ""
Write-Host "OpenClaw automation install result:" -ForegroundColor Green
Write-Host ("- openclaw_home: {0}" -f $OpenClawHome)
Write-Host ("- timezone: {0}" -f $Timezone)
Write-Host ("- dashboard-refresh: every {0}" -f $DashboardEvery)
Write-Host ("- ambient-discovery: every {0}" -f $AmbientEvery)
Write-Host ("- signal-triage: every {0}" -f $TriageEvery)
Write-Host ("- opportunity-deep-dive: every {0}" -f $DeepDiveEvery)
Write-Host ("- opportunity-promotion: every {0}" -f $PromotionEvery)
Write-Host ("- exploration-learning: every {0}" -f $ExploreLearnEvery)
Write-Host ("- planner-intake: every {0}" -f $PlannerIntakeEvery)
Write-Host ("- reviewer-gate: every {0}" -f $ReviewerGateEvery)
Write-Host ("- dispatch-approved: every {0}" -f $DispatchApprovedEvery)
Write-Host ("- tester-gate: every {0}" -f $TesterGateEvery)
Write-Host ("- releaser-gate: every {0}" -f $ReleaserGateEvery)
Write-Host ("- reflect-release: every {0}" -f $ReflectReleaseEvery)
Write-Host ("- skill-scout: every {0}" -f $SkillScoutEvery)
Write-Host ("- skill-maintenance: every {0}" -f $SkillMaintenanceEvery)
Write-Host ("- research-sprint: every {0}" -f $ResearchEvery)
Write-Host ("- build-sprint: every {0}" -f $BuildEvery)
Write-Host ("- memory-hourly agents: {0} every {1}" -f $MemoryAgents, $MemoryHourlyEvery)
Write-Host ("- daily-backup agents: {0}" -f $TeamAgents.Count)
Write-Host "- daily-reflection: 00:10"
Write-Host "- daily-curation: 00:20"
Write-Host ("- memory-weekly agents: {0} at 00:40" -f $MemoryAgents)
if ($SkipIgnite) {
    Write-Host "- ignition: skipped" -ForegroundColor Yellow
} else {
    Write-Host "- ignition: system event triggered"
}
if ($DryRun) {
    Write-Host "- dry-run mode: no cron jobs were written" -ForegroundColor Yellow
}
