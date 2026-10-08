#Requires -Version 5.1
param(
    [Parameter(Position = 0)]
    [ValidateSet('install', 'uninstall', 'help')]
    [string]$Action = 'help',

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Agents = @('all'),

    [switch]$Yes,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Show-Usage {
    @'
Usage: .\install.cmd <install|uninstall> [claude|codex|opencode|all ...] [-Yes]
       .\install.ps1 <install|uninstall> [claude|codex|opencode|all ...] [-Yes]

Discover skill directories recursively and group by relative parent directory.
No agent argument selects all three agents. Install opens a numbered checklist;
enter a skill or category number to toggle it, a for all, n for none, Enter to
apply, or q to cancel. Installed repository skills are selected by default.
Use -Yes to skip selection and install every skill.

Default destinations (relative to your user profile):
  claude    .claude\skills
  codex     .codex\skills
  opencode  .config\opencode\skills

Overrides: SKILLS_INSTALL_HOME, CLAUDE_CONFIG_DIR, CODEX_HOME, XDG_CONFIG_HOME.
Windows creates directory junctions; other platforms use symbolic links.
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

function Get-Selection([string]$TargetDirectory) {
    foreach ($skill in $skills) {
        $destination = Join-Path $TargetDirectory $skill.Name
        $existing = Get-Item -LiteralPath $destination -Force -ErrorAction SilentlyContinue
        if (Test-SamePath $destination $skill.FullName) {
            New-SelectionItem $skill.FullName $true 'Source directory; cannot uninstall'
        } elseif (Get-RepoLinkTarget $existing) {
            New-SelectionItem $skill.FullName $true 'Installed'
        } elseif ($null -ne $existing) {
            New-SelectionItem $skill.FullName $false 'Name conflict; select to replace'
        } else {
            New-SelectionItem $skill.FullName $false 'Not installed'
        }
    }
    if (Test-Path -LiteralPath $TargetDirectory -PathType Container) {
        foreach ($existing in Get-ChildItem -LiteralPath $TargetDirectory -Force) {
            $source = Get-RepoLinkTarget $existing
            if ($source -and -not $skillNames.ContainsKey($existing.Name)) {
                New-SelectionItem $source $true 'Installed; source skill removed'
            }
        }
    }
}

function Select-Skills([object[]]$Items, [string]$Agent, [string]$TargetDirectory) {
    while ($true) {
        Write-Host "`nSkill selection - $Agent`nDirectory: $TargetDirectory"
        $rows = @{}
        $number = 0
        foreach ($group in $Items | Group-Object Category | Sort-Object Name) {
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
                Write-Host ("{0,3}.   [{1}] {2} ({3})" -f $number, $marker, $item.Name, $item.Status)
            }
        }
        $choice = (Read-Host 'Number: toggle | a: all | n: none | Enter: apply | q: cancel').Trim()
        if ($choice -eq '') { return $true }
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
    $windowsPlatform = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
    $pathComparison = if ($windowsPlatform) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
    $repoRoot = Get-NormalPath $PSScriptRoot
    $repoPrefix = $repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    $installHome = if ($env:SKILLS_INSTALL_HOME) { $env:SKILLS_INSTALL_HOME } elseif ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
    if (-not $installHome) { throw 'Set SKILLS_INSTALL_HOME or USERPROFILE.' }

    $selectedAgents = @()
    foreach ($agent in $Agents) {
        switch ($agent) {
            'all' { $selectedAgents += 'claude', 'codex', 'opencode' }
            { $_ -in @('claude', 'codex', 'opencode') } { $selectedAgents += $agent }
            default { throw "Unknown agent: $agent (supported: claude, codex, opencode, all)" }
        }
    }
    $selectedAgents = @($selectedAgents | Select-Object -Unique)
    if ($Action -eq 'install' -and -not $Yes -and [Console]::IsInputRedirected) {
        throw 'Interactive install requires a terminal. Use -Yes to install every skill.'
    }
    $skillNames = @{}
    $skills = @()
    if ($Action -eq 'install') { $skills = @(Get-Skills $repoRoot $skillNames) }

    foreach ($agent in $selectedAgents) {
        $targetDirectory = Get-SkillsDirectory $agent
        $installed = 0
        $removed = 0
        if ($Action -eq 'uninstall') {
            if (Test-Path -LiteralPath $targetDirectory -PathType Container) {
                foreach ($existing in Get-ChildItem -LiteralPath $targetDirectory -Force) {
                    if (Get-RepoLinkTarget $existing) {
                        Remove-Destination $existing
                        $removed++
                        Write-Host "[$agent] Removed: $($existing.FullName)"
                    }
                }
            }
            Write-Host "[$agent] Uninstalled $removed skill(s) from $targetDirectory"
            continue
        }

        $items = @(Get-Selection $targetDirectory)
        if ($items.Count -eq 0) { throw "No repository skills found in $repoRoot or $targetDirectory" }
        if ($Yes) {
            foreach ($item in $items) { $item.Selected = $true }
        } elseif (-not (Select-Skills $items $agent $targetDirectory)) {
            Write-Host "[$agent] Cancelled; no changes applied to this agent."
            return
        }

        foreach ($item in $items) {
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
        }
        Write-Host "[$agent] Installed $installed skill(s), removed $removed skill(s) in $targetDirectory"
    }
} catch {
    [Console]::Error.WriteLine("Error: $($_.Exception.Message)")
    exit 1
}
