#!/usr/bin/env python3
import csv
import json
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO = "openshift-online/hypershell"
ROOT = Path.home() / "hypershell-repo-analysis"
MONTHLY_ROOT = ROOT / "monthly"


def parse_json_stream(text):
    decoder = json.JSONDecoder()
    items = []
    index = 0
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        value, index = decoder.raw_decode(text, index)
        if isinstance(value, list):
            items.extend(value)
        else:
            items.append(value)
    return items


def gh_paginate(endpoint):
    result = subprocess.run(
        ["gh", "api", "--paginate", endpoint],
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_json_stream(result.stdout)


def parse_time(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def month_bounds(year, month):
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end


def previous_month(now):
    first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_previous = first - timedelta(days=1)
    return last_previous.year, last_previous.month


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def actor(item, field):
    value = item.get(field) or {}
    return value.get("login", ""), value.get("type", "")


def item_kind(item):
    return "pull_request" if "pull_request" in item else "issue"


def pr_status(item):
    if item_kind(item) != "pull_request":
        return item["state"]
    if item.get("merged_at"):
        return "merged"
    if item["state"] == "closed":
        return "closed_unmerged"
    return "open"


def in_month(value, start, end):
    timestamp = parse_time(value)
    return timestamp is not None and start <= timestamp < end


def age_hours(start, end):
    return (end - start).total_seconds() / 3600


def write_csv(path, rows, fields):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def svg_text(x, y, text, size=14, weight="normal", anchor="start", fill="#263238"):
    escaped = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<text x="{x}" y="{y}" font-family="Inter, Segoe UI, sans-serif" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" fill="{fill}">{escaped}</text>'


def start_svg(width, height, title, description):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{title}">'
        f'<title>{title}</title><desc>{description}</desc><rect width="100%" height="100%" fill="#ffffff"/>'
    )


def save_svg(path, parts):
    path.write_text("\n".join(parts) + "\n</svg>\n")


def notify(title, message):
    escaped_title = title.replace('"', '\\"')
    escaped_message = message.replace('"', '\\"')
    subprocess.run(
        [
            "osascript",
            "-e",
            f'display notification "{escaped_message}" with title "{escaped_title}"',
        ],
        check=False,
    )


def grouped_bar_chart(path, title, subtitle, categories, series, value_label):
    width, height = 1150, 620
    left, right, top, bottom = 90, 50, 120, 130
    chart_width = width - left - right
    chart_height = height - top - bottom
    max_value = max(value for values in series.values() for key, value in values.items() if key != "color")
    group_width = chart_width / len(categories)
    bar_width = min(40, (group_width - 30) / len(series))
    parts = [start_svg(width, height, title, subtitle), svg_text(40, 48, title, 26, "700"), svg_text(40, 78, subtitle, 15, "400", fill="#607d8b")]
    parts.append(f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#cfd8dc"/>')
    for category_index, category in enumerate(categories):
        group_x = left + category_index * group_width + 20
        for series_index, (name, values) in enumerate(series.items()):
            value = values[category]
            bar_height = int(value / max_value * chart_height) if max_value else 0
            x = group_x + series_index * (bar_width + 6)
            y = height - bottom - bar_height
            parts.append(f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" rx="4" fill="{values["color"]}"/>')
            parts.append(svg_text(x + bar_width / 2, y - 10, f"{value:,}", 12, "600", "middle"))
        parts.append(svg_text(group_x + (len(series) * (bar_width + 6) - 6) / 2, height - bottom + 30, category, 15, "600", "middle"))
    legend_y, legend_x = height - 72, left
    for name, values in series.items():
        parts.append(f'<rect x="{legend_x}" y="{legend_y-12}" width="14" height="14" rx="3" fill="{values["color"]}"/>')
        parts.append(svg_text(legend_x + 22, legend_y, name, 14, "500"))
        legend_x += 190
    parts.append(svg_text(left, height - 28, value_label, 14, "600", fill="#546e7a"))
    save_svg(path, parts)


def horizontal_bar_chart(path, title, subtitle, rows, value_label):
    width, row_height, left, right, top, bottom = 1100, 48, 240, 160, 120, 90
    height = top + row_height * len(rows) + bottom
    max_value = max(value for _, value in rows) if rows else 1
    chart_width = width - left - right
    parts = [start_svg(width, height, title, subtitle), svg_text(40, 48, title, 26, "700"), svg_text(40, 78, subtitle, 15, "400", fill="#607d8b")]
    parts.append(f'<line x1="{left}" y1="{top-20}" x2="{left}" y2="{height-bottom+20}" stroke="#cfd8dc"/>')
    total = sum(value for _, value in rows)
    for index, (label, value) in enumerate(rows):
        y = top + index * row_height
        bar_width = int(value / max_value * chart_width)
        color = "#f57c00" if label.endswith("[bot]") else "#1976d2"
        parts.append(svg_text(left - 20, y + 30, label, 15, "600", "end"))
        parts.append(f'<rect x="{left}" y="{y+12}" width="{bar_width}" height="24" rx="4" fill="{color}"/>')
        parts.append(svg_text(left + bar_width + 12, y + 30, f"{value:,} ({value/total:.1%})" if total else "0", 14, "600"))
    parts.append(svg_text(left, height - 38, value_label, 14, "600", fill="#546e7a"))
    save_svg(path, parts)


def stacked_bar_chart(path, title, subtitle, rows, segments, value_label):
    width, row_height, left, right, top, bottom = 1150, 52, 230, 140, 120, 100
    height = top + row_height * len(rows) + bottom
    max_total = max(sum(values.values()) for _, values in rows) if rows else 1
    chart_width = width - left - right
    parts = [start_svg(width, height, title, subtitle), svg_text(40, 48, title, 26, "700"), svg_text(40, 78, subtitle, 15, "400", fill="#607d8b")]
    parts.append(f'<line x1="{left}" y1="{top-20}" x2="{left}" y2="{height-bottom+20}" stroke="#cfd8dc"/>')
    for index, (label, values) in enumerate(rows):
        y = top + index * row_height
        x = left
        total = sum(values.values())
        parts.append(svg_text(left - 20, y + 32, label, 15, "600", "end"))
        for segment, color in segments:
            value = values.get(segment, 0)
            segment_width = int(value / max_total * chart_width)
            if segment_width:
                parts.append(f'<rect x="{x}" y="{y+14}" width="{segment_width}" height="26" fill="{color}"/>')
                if segment_width > 34:
                    parts.append(svg_text(x + segment_width / 2, y + 32, f"{value:,}", 12, "600", "middle", "#ffffff"))
            x += segment_width
        parts.append(svg_text(x + 12, y + 32, f"{total:,}", 14, "600"))
    legend_y, legend_x = height - 56, left
    for segment, color in segments:
        parts.append(f'<rect x="{legend_x}" y="{legend_y-12}" width="14" height="14" rx="3" fill="{color}"/>')
        parts.append(svg_text(legend_x + 22, legend_y, segment, 14, "500"))
        legend_x += 180
    parts.append(svg_text(left, height - 26, value_label, 14, "600", fill="#546e7a"))
    save_svg(path, parts)


def main():
    now = datetime.now(timezone.utc)
    if len(sys.argv) > 1:
        year, month = map(int, sys.argv[1].split("-"))
    else:
        year, month = previous_month(now)
    start, end = month_bounds(year, month)
    month_label = f"{year:04d}-{month:02d}"
    output_dir = MONTHLY_ROOT / month_label
    output_dir.mkdir(parents=True, exist_ok=True)

    issues = gh_paginate(f"repos/{REPO}/issues?state=all&per_page=100")
    pulls = gh_paginate(f"repos/{REPO}/pulls?state=all&per_page=100")
    pull_by_number = {pull["number"]: pull for pull in pulls}
    for item in issues:
        pull = pull_by_number.get(item["number"])
        if pull:
            item["merged_at"] = pull.get("merged_at")
            item["draft"] = pull.get("draft", False)

    created = [item for item in issues if in_month(item["created_at"], start, end)]
    closed = [item for item in issues if in_month(item.get("closed_at"), start, end)]
    merged = [item for item in issues if item_kind(item) == "pull_request" and in_month(item.get("merged_at"), start, end)]
    open_at_end = [
        item for item in issues
        if parse_time(item["created_at"]) and parse_time(item["created_at"]) < end
        and (not item.get("closed_at") or parse_time(item["closed_at"]) >= end)
    ]

    issue_created = [item for item in created if item_kind(item) == "issue"]
    issue_closed = [item for item in closed if item_kind(item) == "issue"]
    pr_created = [item for item in created if item_kind(item) == "pull_request"]
    pr_closed = [item for item in closed if item_kind(item) == "pull_request"]
    open_issues = [item for item in open_at_end if item_kind(item) == "issue"]
    open_prs = [item for item in open_at_end if item_kind(item) == "pull_request"]

    closure_counts = Counter()
    closure_type_counts = Counter()
    self_closed = 0
    for item in closed:
        closer, closer_type = actor(item, "closed_by")
        author, _ = actor(item, "user")
        closure_counts[closer] += 1
        closure_type_counts[closer_type] += 1
        if closer == author:
            self_closed += 1

    top_closers = closure_counts.most_common(12)
    author_counts = Counter(item["user"]["login"] for item in created)
    top_authors = author_counts.most_common(12)
    pr_author_outcomes = defaultdict(Counter)
    for item in pr_created:
        status = pr_status(item)
        status = {
            "merged": "Merged",
            "closed_unmerged": "Closed unmerged",
            "open": "Open",
        }[status]
        pr_author_outcomes[item["user"]["login"]][status] += 1
    top_pr_authors = sorted(pr_author_outcomes.items(), key=lambda pair: sum(pair[1].values()), reverse=True)[:10]

    closed_cycles = defaultdict(list)
    open_ages = defaultdict(list)
    for item in closed:
        created_at, closed_at = parse_time(item["created_at"]), parse_time(item["closed_at"])
        if created_at and closed_at:
            closed_cycles[item_kind(item)].append(age_hours(created_at, closed_at))
    for item in open_at_end:
        created_at = parse_time(item["created_at"])
        if created_at:
            open_ages[item_kind(item)].append(age_hours(created_at, end))

    trend_months = []
    trend_start = start
    for _ in range(6):
        trend_months.append(trend_start.strftime("%Y-%m"))
        trend_start = (trend_start.replace(day=1) - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    trend_months.reverse()
    trend = defaultdict(Counter)
    for item in issues:
        created_at, closed_at = parse_time(item["created_at"]), parse_time(item.get("closed_at"))
        if created_at:
            trend[created_at.strftime("%Y-%m")][f"{item_kind(item)}_created"] += 1
        if closed_at:
            trend[closed_at.strftime("%Y-%m")][f"{item_kind(item)}_closed"] += 1
        if item_kind(item) == "pull_request" and item.get("merged_at"):
            merged_at = parse_time(item["merged_at"])
            if merged_at:
                trend[merged_at.strftime("%Y-%m")]["pull_requests_merged"] += 1

    summary = {
        "repository": REPO,
        "report_month": month_label,
        "generated_at": now.isoformat(),
        "issues_created": len(issue_created),
        "issues_closed": len(issue_closed),
        "pull_requests_created": len(pr_created),
        "pull_requests_closed": len(pr_closed),
        "pull_requests_merged": len(merged),
        "open_issues_at_month_end": len(open_issues),
        "open_pull_requests_at_month_end": len(open_prs),
        "human_closures": closure_type_counts.get("User", 0),
        "bot_closures": closure_type_counts.get("Bot", 0),
        "self_closed": self_closed,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    monthly_rows = []
    for month in trend_months:
        counts = trend[month]
        monthly_rows.append({
            "month": month,
            "issue_created": counts["issue_created"],
            "issue_closed": counts["issue_closed"],
            "pull_request_created": counts["pull_request_created"],
            "pull_request_closed": counts["pull_request_closed"],
            "pull_requests_merged": counts["pull_requests_merged"],
        })
    write_csv(output_dir / "monthly.csv", monthly_rows, ["month", "issue_created", "issue_closed", "pull_request_created", "pull_request_closed", "pull_requests_merged"])

    all_rows = []
    for item in issues:
        author, author_type = actor(item, "user")
        closer, closer_type = actor(item, "closed_by")
        all_rows.append({
            "number": item["number"], "kind": item_kind(item), "status": pr_status(item), "state": item["state"],
            "title": item["title"], "author": author, "author_type": author_type,
            "closer": closer, "closer_type": closer_type, "created_at": item["created_at"],
            "closed_at": item.get("closed_at", ""), "merged_at": item.get("merged_at", ""),
            "labels": "|".join(label["name"] for label in item.get("labels", [])), "url": item["html_url"],
        })
    fields = ["number", "kind", "status", "state", "title", "author", "author_type", "closer", "closer_type", "created_at", "closed_at", "merged_at", "labels", "url"]
    write_csv(output_dir / "all-items.csv", all_rows, fields)
    write_csv(output_dir / "issues.csv", [row for row in all_rows if row["kind"] == "issue"], fields)
    write_csv(output_dir / "pull_requests.csv", [row for row in all_rows if row["kind"] == "pull_request"], fields)
    closure_rows = [{"closer": closer, "closures": count, "share": f"{count / len(closed):.1%}"} for closer, count in top_closers]
    write_csv(output_dir / "closures.csv", closure_rows, ["closer", "closures", "share"])
    contributor_rows = [{"author": author, "items_created": count} for author, count in top_authors]
    write_csv(output_dir / "contributors.csv", contributor_rows, ["author", "items_created"])

    charts_dir = output_dir / "charts"
    charts_dir.mkdir(exist_ok=True)
    grouped_bar_chart(
        charts_dir / "monthly-activity.svg", "Monthly GitHub activity", "Creation, closure, and merge volume",
        trend_months,
        {
            "Issues created": {"color": "#42a5f5", **{row["month"]: row["issue_created"] for row in monthly_rows}},
            "Issues closed": {"color": "#0d47a1", **{row["month"]: row["issue_closed"] for row in monthly_rows}},
            "PRs created": {"color": "#66bb6a", **{row["month"]: row["pull_request_created"] for row in monthly_rows}},
            "PRs closed": {"color": "#2e7d32", **{row["month"]: row["pull_request_closed"] for row in monthly_rows}},
            "PRs merged": {"color": "#ffca28", **{row["month"]: row["pull_requests_merged"] for row in monthly_rows}},
        },
        "Count",
    )
    horizontal_bar_chart(charts_dir / "closure-attribution.svg", "Closure attribution", "Who closed or merged items", top_closers, "Items closed")
    stacked_bar_chart(
        charts_dir / "pr-author-outcomes.svg", "Top PR authors and outcomes", "Merged, closed without merge, and open pull requests",
        [(author, dict(outcomes)) for author, outcomes in top_pr_authors],
        [("Merged", "#2e7d32"), ("Closed unmerged", "#ef6c00"), ("Open", "#90a4ae")],
        "Pull requests",
    )

    issue_cycle = closed_cycles["issue"]
    pr_cycle = closed_cycles["pull_request"]
    issue_open_age = open_ages["issue"]
    pr_open_age = open_ages["pull_request"]
    cycle_rows = [
        {"measure": "Issue median cycle time (hours)", "value": round(statistics.median(issue_cycle), 2) if issue_cycle else ""},
        {"measure": "Issue p90 cycle time (hours)", "value": round(percentile(issue_cycle, 0.9), 2) if issue_cycle else ""},
        {"measure": "PR median cycle time (hours)", "value": round(statistics.median(pr_cycle), 2) if pr_cycle else ""},
        {"measure": "PR p90 cycle time (hours)", "value": round(percentile(pr_cycle, 0.9), 2) if pr_cycle else ""},
        {"measure": "Open issue median age at month end (days)", "value": round(statistics.median(issue_open_age) / 24, 2) if issue_open_age else ""},
        {"measure": "Open PR median age at month end (days)", "value": round(statistics.median(pr_open_age) / 24, 2) if pr_open_age else ""},
    ]
    write_csv(output_dir / "cycle-time.csv", cycle_rows, ["measure", "value"])

    report = []
    report.append(f"# HyperShell GitHub Monthly Report — {month_label}")
    report.append("")
    report.append(f"Generated: {now.isoformat()}")
    report.append("")
    report.append("## Executive summary")
    report.append("")
    report.append(f"- Issues created: **{len(issue_created)}**; issues closed: **{len(issue_closed)}**.")
    report.append(f"- PRs created: **{len(pr_created)}**; PRs closed: **{len(pr_closed)}**; PRs merged: **{len(merged)}**.")
    report.append(f"- Open at month end: **{len(open_issues)} issues**, **{len(open_prs)} PRs**.")
    report.append(f"- Closures by humans: **{closure_type_counts.get('User', 0)}**; by bots: **{closure_type_counts.get('Bot', 0)}**.")
    report.append(f"- Self-closed items: **{self_closed} of {len(closed)} ({self_closed / len(closed):.1%})**." if closed else "- No items closed in this month.")
    if top_closers:
        report.append(f"- Top closer: **{top_closers[0][0]}** with **{top_closers[0][1]}** closures.")
    report.append("")
    report.append("## Charts")
    report.append("")
    report.append("![Monthly GitHub activity](charts/monthly-activity.svg)")
    report.append("")
    report.append("![Closure attribution](charts/closure-attribution.svg)")
    report.append("")
    report.append("![Top PR authors and outcomes](charts/pr-author-outcomes.svg)")
    report.append("")
    report.append("## Cycle time and backlog")
    report.append("")
    report.append("| Measure | Value |")
    report.append("|---|---:|")
    for row in cycle_rows:
        report.append(f"| {row['measure']} | {row['value']} |")
    report.append("")
    report.append("## Top contributors")
    report.append("")
    report.append("| Author | Items created |")
    report.append("|---|---:|")
    for author, count in top_authors:
        report.append(f"| `{author}` | {count} |")
    report.append("")
    report.append("## Output files")
    report.append("")
    report.append("- `summary.json`")
    report.append("- `monthly.csv`")
    report.append("- `all-items.csv`")
    report.append("- `issues.csv`")
    report.append("- `pull_requests.csv`")
    report.append("- `closures.csv`")
    report.append("- `contributors.csv`")
    report.append("- `cycle-time.csv`")
    report.append("- `charts/*.svg`")
    report.append("")
    report.append("## Method")
    report.append("")
    report.append("This report uses GitHub's public REST API via the authenticated `gh` CLI. It includes every issue and pull request returned by `state=all`, separates PRs using GitHub's `pull_request` field, and enriches PRs with merge state from the pull-request endpoint. Closure attribution uses GitHub's `closed_by` field.")
    report.append("")
    report.append("## Limitations")
    report.append("")
    report.append("- The pull-request list endpoint does not provide review timestamps or reviewer identities.")
    report.append("- Review latency and review depth are not calculated.")
    report.append("- `closed_by` identifies the merge/close actor, not necessarily a reviewer.")
    report.append("- This report does not publish or send anything externally.")
    (output_dir / "REPORT.md").write_text("\n".join(report) + "\n")
    notify("HyperShell monthly report", f"Created {output_dir / 'REPORT.md'}")
    print(json.dumps({"output_dir": str(output_dir), **summary}, indent=2))


if __name__ == "__main__":
    main()
