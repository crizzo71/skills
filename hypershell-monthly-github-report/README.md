# HyperShell Monthly GitHub Report Skill

Generate a monthly development report for `openshift-online/hypershell`, including issue and PR throughput, closure attribution, cycle time, backlog age, contributor activity, and charts.

## Install

```bash
git clone https://github.com/crizzo71/skills.git
cp -R skills/hypershell-monthly-github-report ~/.codex/skills/
```

## Run

```bash
~/.codex/skills/hypershell-monthly-github-report/scripts/run_monthly.sh
```

The report is written to:

```text
~/hypershell-repo-analysis/monthly/<YYYY-MM>/REPORT.md
```

The report month defaults to the previous calendar month. To generate a specific month, pass `YYYY-MM` as the first argument:

```bash
~/.codex/skills/hypershell-monthly-github-report/scripts/run_monthly.sh 2026-09
```

To publish the report and charts as a secret GitHub Gist:

```bash
~/.codex/skills/hypershell-monthly-github-report/scripts/run_monthly.sh 2026-09 --publish-gist
```

## Requirements

- Python 3
- `gh` CLI, authenticated to GitHub

## Notes

- The script uses the GitHub REST API via `gh`.
- Gist publishing is opt-in; without `--publish-gist`, the report does not publish or send anything externally.
- The local `launchd` schedule is not included in this package.
