#Requires -Version 5.1
param(
    [Parameter(Position = 0)]
    [ValidateSet('install', 'uninstall', 'help')]
    [string]$Action = 'help',

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Agents = @(),

    [switch]$Yes,
    [switch]$GlobalInstructions,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Show-Usage {
    @'
Usage: .\install.cmd <install|uninstall> [claude|codex|opencode|dsh|all ...] [-Yes] [-GlobalInstructions]
       .\install.ps1 <install|uninstall> [claude|codex|opencode|dsh|all ...] [-Yes] [-GlobalInstructions]

Discover skill directories recursively and group by relative parent directory.
Choose AI tools first, then skills for each selected tool. Named agents are
preselected; install codex still opens the tool checklist. Enter a tool, skill
or category number to toggle it, a for all, n for none, Enter to apply, or q to
cancel. Install preselects installed repository skills; uninstall starts with
no skills selected and removes only checked repository links. -Yes skips both
checklists and processes all skills for named tools, or all tools if omitted.
Select global instructions to replace the existing file with a symlink to this
repository's AGENTS.md. -GlobalInstructions preselects this option; combine with
-Yes to install it directly. On install, -Yes alone leaves global instructions unchanged.
Deselecting or uninstalling removes only this repository's instruction links.

Default destinations (relative to your user profile):
  claude    .claude\skills
  codex     .codex\skills
  opencode  .config\opencode\skills
  dsh       .dsh\skills

Default global instruction files:
  claude    .claude\CLAUDE.md
  codex     .codex\AGENTS.md
  opencode  .config\opencode\AGENTS.md
  dsh       .dsh\AGENTS.md

Overrides: SKILLS_INSTALL_HOME, CLAUDE_CONFIG_DIR, CODEX_HOME, XDG_CONFIG_HOME, DSH_HOME.
Windows creates directory junctions; other platforms use symbolic links.
Global instructions use file symlinks, which require Developer Mode or an
elevated terminal on Windows.
Keep the checkout in a permanent location. Windows requires a local filesystem
that supports junctions. Selected skills replace same-named destination items.
Uninstall removes only this repository's links, including broken links.
'@
}

function Get-NormalPath([string]$Path) {
    $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
}

function Test-SamePath([string]$Left, [string]$Right) {
    [string]::Equals($Left, $Right, $pathComparison)
}

function Get-Skills([string]$Directory, [hashtable]$Seen) {
    foreach ($entry in Get-ChildItem -LiteralPath $Directory -Directory | Sort-Object Name) {
        if ($entry.Name.StartsWith('.') -or ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            continue
        }
        if (Test-Path -LiteralPath (Join-Path $entry.FullName 'SKILL.md') -PathType Leaf) {
            if ($Seen.ContainsKey($entry.Name)) {
                throw "Duplicate skill name: $($Seen[$entry.Name]) and $($entry.FullName)"
            }
            $Seen[$entry.Name] = $entry.FullName
            $entry
        } else {
            Get-Skills $entry.FullName $Seen
        }
    }
}

function Get-SkillsDirectory([string]$Agent) {
    switch ($Agent) {
        'claude' {
            $config = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $installHome '.claude' }
            Get-NormalPath (Join-Path $config 'skills')
        }
        'codex' {
            $config = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $installHome '.codex' }
            Get-NormalPath (Join-Path $config 'skills')
        }
        'dsh' {
            $config = if ($env:DSH_HOME) { $env:DSH_HOME } else { Join-Path $installHome '.dsh' }
            Get-NormalPath (Join-Path $config 'skills')
        }
        'opencode' {
            $config = if ($env:XDG_CONFIG_HOME) { $env:XDG_CONFIG_HOME } else { Join-Path $installHome '.config' }
            Get-NormalPath (Join-Path $config 'opencode/skills')
        }
    }
}

function Get-RepoLinkTarget($Item) {
    if ($null -eq $Item -or -not ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        return $null
    }
    if ($Item.LinkType -notin @('Junction', 'SymbolicLink')) { return $null }
    $target = @($Item.Target)[0]
    if (-not $target) { return $null }
    if (-not [IO.Path]::IsPathRooted($target)) {
        $target = Join-Path (Split-Path -Parent $Item.FullName) $target
    }
    $target = Get-NormalPath $target
    if ($target.StartsWith($repoPrefix, $pathComparison) -and
        (Test-SamePath ([IO.Path]::GetFileName($target)) $Item.Name)) {
        return $target
    }
    return $null
}

function Get-InstructionsFile([string]$Agent) {
    $config = Split-Path -Parent (Get-SkillsDirectory $Agent)
    $name = if ($Agent -eq 'claude') { 'CLAUDE.md' } else { 'AGENTS.md' }
    Get-NormalPath (Join-Path $config $name)
}

function Get-LegacySkillName([string]$Name) {
    switch ($Name) {
        'opencode-tools' { 'check-opencode-usage' }
        'token-usage' { 'token_usage' }
        'wechat-get-data' { 'wechat_get_data' }
    }
}

function Remove-LegacySkillLink([string]$Agent, [string]$TargetDirectory, [string]$Name) {
    $legacy = Get-LegacySkillName $Name
    if (-not $legacy) { return $false }
    $existing = Get-Item -LiteralPath (Join-Path $TargetDirectory $legacy) -Force -ErrorAction SilentlyContinue
    if (-not (Get-RepoLinkTarget $existing)) { return $false }
    Remove-Destination $existing
    Write-Host "[$Agent] Removed renamed skill: $legacy -> $Name"
    return $true
}

function Test-InstructionsLink($Item) {
    if ($null -eq $Item -or $Item.LinkType -ne 'SymbolicLink') { return $false }
    $target = @($Item.Target)[0]
    if (-not $target) { return $false }
    if (-not [IO.Path]::IsPathRooted($target)) {
        $target = Join-Path (Split-Path -Parent $Item.FullName) $target
    }
    Test-SamePath (Get-NormalPath $target) (Join-Path $repoRoot 'AGENTS.md')
}

function Set-InstructionsLink([string]$Agent, [string]$Destination, [bool]$Selected) {
    $existing = Get-Item -LiteralPath $Destination -Force -ErrorAction SilentlyContinue
    if (-not $Selected) {
        if (Test-InstructionsLink $existing) {
            Remove-Destination $existing
            Write-Host "[$Agent] Removed: $Destination"
        }
        return
    }
    if (Test-InstructionsLink $existing) {
        Write-Host "[$Agent] Already linked: $Destination"
        return
    }
    $source = Join-Path $repoRoot 'AGENTS.md'
    if (Test-SamePath $Destination $source) {
        throw "Refusing to replace the source instructions: $Destination"
    }
    if ($null -ne $existing -and $existing.PSIsContainer -and
        -not ($existing.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "Refusing to replace an instructions directory: $Destination"
    }
    $directory = Split-Path -Parent $Destination
    [IO.Directory]::CreateDirectory($directory) | Out-Null
    $temporary = Join-Path $directory ('.instructions-' + [guid]::NewGuid().ToString('N'))
    try {
        # Check file-symlink privileges before removing an existing file.
        New-Item -Path $temporary -ItemType SymbolicLink -Value $source | Out-Null
        if ($null -ne $existing) { Remove-Destination $existing }
        Move-Item -LiteralPath $temporary -Destination $Destination
    } finally {
        $pending = Get-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
        if ($null -ne $pending) { Remove-Destination $pending }
    }
    Write-Host "[$Agent] Linked: $Destination -> $source"
}

function New-SelectionItem([string]$Source, [bool]$Selected, [string]$Status) {
    $relative = $Source.Substring($repoPrefix.Length)
    $category = Split-Path -Parent $relative
    if (-not $category) { $category = 'Uncategorized' }
    [pscustomobject]@{
        Name = [IO.Path]::GetFileName($Source)
        Source = $Source
        Category = $category
        Selected = $Selected
        Status = $Status
    }
}

function Get-Selection([string]$TargetDirectory, [string]$Instructions) {
    $existing = Get-Item -LiteralPath $Instructions -Force -ErrorAction SilentlyContinue
    $linked = Test-InstructionsLink $existing
    $status = if ($linked) { 'Installed' } elseif ($null -ne $existing) { '' } else { 'Not installed' }
    $item = New-SelectionItem (Join-Path $repoRoot 'AGENTS.md') ($linked -or $GlobalInstructions) $status
    $item.Category = ''
    $item.Name = "AGENTS.md -> $Instructions (replaces file)"
    $item

    foreach ($skill in $skills) {
        $destination = Join-Path $TargetDirectory $skill.Name
        $existing = Get-Item -LiteralPath $destination -Force -ErrorAction SilentlyContinue
        if (Test-SamePath $destination $skill.FullName) {
            New-SelectionItem $skill.FullName $true 'Source directory; cannot uninstall'
        } elseif (Get-RepoLinkTarget $existing) {
            New-SelectionItem $skill.FullName $true 'Installed'
        } elseif ($null -ne $existing) {
            New-SelectionItem $skill.FullName $false ''
        } else {
            $legacy = Get-LegacySkillName $skill.Name
            $legacyItem = if ($legacy) {
                Get-Item -LiteralPath (Join-Path $TargetDirectory $legacy) -Force -ErrorAction SilentlyContinue
            } else { $null }
            if (Get-RepoLinkTarget $legacyItem) {
                New-SelectionItem $skill.FullName $true 'Installed; renamed skill'
            } else {
                New-SelectionItem $skill.FullName $false 'Not installed'
            }
        }
    }
    if (Test-Path -LiteralPath $TargetDirectory -PathType Container) {
        foreach ($existing in Get-ChildItem -LiteralPath $TargetDirectory -Force) {
            $source = Get-RepoLinkTarget $existing
            if ($source -and -not $skillNames.ContainsKey($existing.Name)) {
                $replacement = @($skills | Where-Object { (Get-LegacySkillName $_.Name) -eq $existing.Name })
                if ($replacement.Count -eq 0) {
                    New-SelectionItem $source $true 'Installed; source skill removed'
                }
            }
        }
    }
}

function Get-RemovalSelection([string]$TargetDirectory, [string]$Instructions) {
    $existing = Get-Item -LiteralPath $Instructions -Force -ErrorAction SilentlyContinue
    if (Test-InstructionsLink $existing) {
        $item = New-SelectionItem (Join-Path $repoRoot 'AGENTS.md') $false 'Installed'
        $item.Category = ''
        $item.Name = "AGENTS.md -> $Instructions (remove link)"
        $item
    }
    if (Test-Path -LiteralPath $TargetDirectory -PathType Container) {
        foreach ($existing in Get-ChildItem -LiteralPath $TargetDirectory -Force) {
            $source = Get-RepoLinkTarget $existing
            if ($source) { New-SelectionItem $source $false 'Installed' }
        }
    }
}

function Select-Skills([object[]]$Items, [string]$Agent, [string]$TargetDirectory, [switch]$Tools) {
    while ($true) {
        if ($Tools) {
            Write-Host "`nAI tool selection"
        } elseif ($Action -eq 'uninstall') {
            Write-Host "`nSkills to uninstall - $Agent`nDirectory: $TargetDirectory"
            Write-Host 'Only checked repository links will be removed.'
        } else {
            Write-Host "`nSkill selection - $Agent`nDirectory: $TargetDirectory"
        }
        $rows = @{}
        $number = 0
        foreach ($item in $Items | Where-Object { -not $_.Category }) {
            $number++
            $rows[$number] = @($item)
            $marker = if ($item.Selected) { 'x' } else { ' ' }
            $status = if ($item.Status) { " ($($item.Status))" } else { '' }
            Write-Host ("{0,3}. [{1}] {2}{3}" -f $number, $marker, $item.Name, $status)
        }
        foreach ($group in $Items | Where-Object Category | Group-Object Category | Sort-Object Name) {
            $children = @($group.Group)
            $checked = @($children | Where-Object Selected).Count
            $marker = if ($checked -eq $children.Count) { 'x' } elseif ($checked) { '-' } else { ' ' }
            $number++
            $rows[$number] = $children
            Write-Host ("{0,3}. [{1}] {2} ({3}/{4})" -f $number, $marker, $group.Name, $checked, $children.Count)
            foreach ($item in $children) {
                $number++
                $rows[$number] = @($item)
                $marker = if ($item.Selected) { 'x' } else { ' ' }
                $status = if ($item.Status) { " ($($item.Status))" } else { '' }
                Write-Host ("{0,3}.   [{1}] {2}{3}" -f $number, $marker, $item.Name, $status)
            }
        }
        $choice = (Read-Host 'Number: toggle | a: all | n: none | Enter: apply | q: cancel').Trim()
        if ($choice -eq '') {
            if ($Tools -and @($Items | Where-Object Selected).Count -eq 0) {
                Write-Host 'Select at least one AI tool.'
                continue
            }
            return $true
        }
        if ($choice -eq 'q') { return $false }
        if ($choice -in @('a', 'n')) {
            $changed = $Items
            $selected = $choice -eq 'a'
        } else {
            $index = 0
            if (-not [int]::TryParse($choice, [ref]$index) -or -not $rows.ContainsKey($index)) {
                Write-Host 'Enter a displayed number, a, n, or q.'
                continue
            }
            $changed = $rows[$index]
            $selected = @($changed | Where-Object { -not $_.Selected }).Count -gt 0
        }
        foreach ($item in $changed) {
            if ($item.Status -ne 'Source directory; cannot uninstall') { $item.Selected = $selected }
        }
    }
}

function Remove-Destination($Item) {
    if ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        # Delete only the link, never recurse into a junction's target.
        $Item.Delete()
    } elseif ($Item.PSIsContainer) {
        foreach ($child in Get-ChildItem -LiteralPath $Item.FullName -Force) {
            Remove-Destination $child
        }
        $Item.Delete()
    } else {
        Remove-Item -LiteralPath $Item.FullName -Force
    }
}

try {
    if ($Help -or $Action -eq 'help') { Show-Usage; return }
    if ($Action -eq 'uninstall' -and $GlobalInstructions) {
        throw '-GlobalInstructions is an install option; uninstall already removes owned instruction links.'
    }
    $windowsPlatform = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
    $pathComparison = if ($windowsPlatform) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
    $repoRoot = Get-NormalPath $PSScriptRoot
    $repoPrefix = $repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    $installHome = if ($env:SKILLS_INSTALL_HOME) { $env:SKILLS_INSTALL_HOME } elseif ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
    if (-not $installHome) { throw 'Set SKILLS_INSTALL_HOME or USERPROFILE.' }

    $selectedAgents = @()
    foreach ($agent in $Agents) {
        switch ($agent) {
            'all' { $selectedAgents += 'claude', 'codex', 'opencode', 'dsh' }
            { $_ -in @('claude', 'codex', 'opencode', 'dsh') } { $selectedAgents += $agent }
            default { throw "Unknown agent: $agent (supported: claude, codex, opencode, dsh, all)" }
        }
    }
    $selectedAgents = @($selectedAgents | Select-Object -Unique)
    if (-not $Yes -and [Console]::IsInputRedirected) {
        throw 'Interactive selection requires a terminal. Use -Yes to skip both checklists.'
    }
    if ($Yes -and $selectedAgents.Count -eq 0) {
        $selectedAgents = @('claude', 'codex', 'opencode', 'dsh')
    } elseif (-not $Yes) {
        $toolItems = @('claude', 'codex', 'opencode', 'dsh' | ForEach-Object {
            $item = New-SelectionItem (Join-Path $repoRoot $_) ($_ -in $selectedAgents) ''
            $item.Category = ''
            $item
        })
        if (-not (Select-Skills $toolItems '' '' -Tools)) {
            Write-Host 'Cancelled; no changes applied.'
            return
        }
        $selectedAgents = @($toolItems | Where-Object Selected | ForEach-Object Name)
    }
    $skillNames = @{}
    $skills = @()
    if ($Action -eq 'install') {
        if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
            throw "Missing source: $repoRoot/AGENTS.md"
        }
        $skills = @(Get-Skills $repoRoot $skillNames)
    }

    foreach ($agent in $selectedAgents) {
        $targetDirectory = Get-SkillsDirectory $agent
        $instructions = Get-InstructionsFile $agent
        $installed = 0
        $removed = 0
        if ($Action -eq 'uninstall') {
            $items = @(Get-RemovalSelection $targetDirectory $instructions)
            if ($items.Count -eq 0) {
                Write-Host "[$agent] Nothing to uninstall: $targetDirectory"
                continue
            }
            if ($Yes) {
                foreach ($item in $items) { $item.Selected = $true }
            } elseif (-not (Select-Skills $items $agent $targetDirectory)) {
                Write-Host "[$agent] Cancelled; no changes applied to this agent."
                return
            }
            foreach ($item in $items | Where-Object Selected) {
                if (Test-SamePath $item.Source (Join-Path $repoRoot 'AGENTS.md')) {
                    Set-InstructionsLink $agent $instructions $false
                    continue
                }
                $existing = Get-Item -LiteralPath (Join-Path $targetDirectory $item.Name) -Force -ErrorAction SilentlyContinue
                if (Get-RepoLinkTarget $existing) {
                    Remove-Destination $existing
                    $removed++
                    Write-Host "[$agent] Removed: $($existing.FullName)"
                }
            }
            Write-Host "[$agent] Uninstalled $removed skill(s) from $targetDirectory"
            continue
        }

        $items = @(Get-Selection $targetDirectory $instructions)
        if ($items.Count -eq 0) { throw "No repository skills found in $repoRoot or $targetDirectory" }
        if ($Yes) {
            foreach ($item in $items) {
                $item.Selected = if (Test-SamePath $item.Source (Join-Path $repoRoot 'AGENTS.md')) { [bool]$GlobalInstructions } else { $true }
            }
        } elseif (-not (Select-Skills $items $agent $targetDirectory)) {
            Write-Host "[$agent] Cancelled; no changes applied to this agent."
            return
        }

        foreach ($item in $items) {
            if (Test-SamePath $item.Source (Join-Path $repoRoot 'AGENTS.md')) {
                if (-not $Yes -or $GlobalInstructions) {
                    Set-InstructionsLink $agent $instructions $item.Selected
                }
                continue
            }
            $destination = Join-Path $targetDirectory $item.Name
            $existing = Get-Item -LiteralPath $destination -Force -ErrorAction SilentlyContinue
            $linkedSource = Get-RepoLinkTarget $existing
            if (-not $item.Selected) {
                if ($linkedSource) {
                    Remove-Destination $existing
                    $removed++
                    Write-Host "[$agent] Removed: $destination"
                }
                continue
            }
            if (-not (Test-Path -LiteralPath (Join-Path $item.Source 'SKILL.md') -PathType Leaf)) { continue }
            if ((Test-SamePath $destination $item.Source) -or ($linkedSource -and (Test-SamePath $linkedSource $item.Source))) {
                Write-Host "[$agent] Already present: $($item.Name)"
                if (Remove-LegacySkillLink $agent $targetDirectory $item.Name) { $removed++ }
                continue
            }
            $destinationPrefix = $destination.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
            foreach ($source in @($repoRoot) + @($skills.FullName)) {
                if ((Test-SamePath $source $destination) -or $source.StartsWith($destinationPrefix, $pathComparison)) {
                    throw "Refusing to replace a repository source directory or its parent: $destination"
                }
            }
            [IO.Directory]::CreateDirectory($targetDirectory) | Out-Null
            if ($null -ne $existing) { Remove-Destination $existing }
            $linkType = if ($windowsPlatform) { 'Junction' } else { 'SymbolicLink' }
            New-Item -Path $targetDirectory -Name $item.Name -ItemType $linkType -Value $item.Source | Out-Null
            $installed++
            Write-Host "[$agent] Linked: $destination -> $($item.Source)"
            if (Remove-LegacySkillLink $agent $targetDirectory $item.Name) { $removed++ }
        }
        Write-Host "[$agent] Installed $installed skill(s), removed $removed skill(s) in $targetDirectory"
    }
} catch {
    [Console]::Error.WriteLine("Error: $($_.Exception.Message)")
    exit 1
}
