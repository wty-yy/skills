#!/usr/bin/env bash
# Inspect prerequisites without installing packages or starting an interactive app.
set -uo pipefail

missing=0
for binary in node npm pnpm dsh dsh-tui; do
    if location="$(command -v "$binary")"; then
        printf 'OK       %-8s %s\n' "$binary" "$location"
    else
        printf 'MISSING  %s\n' "$binary"
        missing=1
    fi
done

for binary in node npm pnpm dsh; do
    if command -v "$binary" > /dev/null 2>&1; then
        if version="$("$binary" --version 2>/dev/null)"; then
            printf 'VERSION  %-8s %s\n' "$binary" "$version"
        else
            printf 'FAILED   %s --version\n' "$binary"
            missing=1
        fi
    fi
done

# npm's package metadata checks dsh-tui without launching the TUI.
if command -v node > /dev/null 2>&1 && command -v npm > /dev/null 2>&1; then
    if ! packages="$(npm list --global --depth=0 --json @deepseek-ai/dsh @deepseek-harness-tui/dsh-tui pnpm 2>/dev/null)"; then
        # npm also returns nonzero when a requested package is missing.
        :
    fi
    if ! printf '%s' "$packages" | node -e '
        let input = "";
        process.stdin.on("data", chunk => { input += chunk; });
        process.stdin.on("end", () => {
            let data;
            try { data = JSON.parse(input); }
            catch { console.log("FAILED   npm global package inventory"); process.exitCode = 1; return; }
            for (const name of ["@deepseek-ai/dsh", "@deepseek-harness-tui/dsh-tui", "pnpm"]) {
                const version = data.dependencies?.[name]?.version;
                console.log(`${version ? "NPM      " : "MISSING  "}${name}${version ? ` ${version}` : " (global package)"}`);
                if (!version) process.exitCode = 1;
            }
        });
    '; then
        missing=1
    fi
fi

exit "$missing"
