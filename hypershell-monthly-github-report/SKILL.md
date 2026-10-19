---
name: hypershell-monthly-github-report
description: Generate a monthly development report for openshift-online/hypershell, including issue and PR throughput, closure attribution, cycle time, backlog age, contributor activity, and charts. Use when the user asks for the monthly HyperShell GitHub report or when a scheduled monthly run should produce it.
---

# HyperShell Monthly GitHub Report

## Workflow

1. Run `scripts/generate_monthly_report.py`.
2. Read the generated report under `~/hypershell-repo-analysis/monthly/<YYYY-MM>/REPORT.md`.
3. Summarize the most important changes, risks, and next actions in 5-8 bullets.
4. Do not publish, merge, or send anything unless explicitly requested.
5. To publish a secret GitHub Gist, run the script with `--publish-gist`.

## Automation

- A local `launchd` job can run this skill on the first day of each month at 09:00 America/New_York.
- Outputs are written to `~/hypershell-repo-analysis/monthly/<YYYY-MM>/`.
- The report month defaults to the previous calendar month. Pass `YYYY-MM` as the first argument to override it.
- Gist publishing is opt-in with `--publish-gist`; it creates a secret Gist and returns the URL.
