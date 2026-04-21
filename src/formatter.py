#!/usr/bin/env python3
"""
formatter.py
============
Rich terminal output formatter for Jira chatbot.
Displays issues, sprint reports, and analysis in beautiful tables/panels.
"""
from __future__ import annotations

from typing import Any, Dict, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text

console = Console()


def format_issues_table(issues: List[Dict[str, Any]], title: str = "Issues") -> Table:
    """
    Format list of issues as Rich table.

    Args:
        issues: List of issue dicts
        title: Table title

    Returns:
        Rich Table object
    """
    table = Table(title=title, show_header=True, header_style="bold cyan")

    table.add_column("Key", style="cyan", width=12)
    table.add_column("Summary", style="white", width=50)
    table.add_column("Status", width=15)
    table.add_column("Priority", width=10)
    table.add_column("Assignee", width=20)

    for issue in issues:
        # Color status
        status = issue.get("status", "")
        if "Done" in status or "Closed" in status:
            status_style = "green"
        elif "Progress" in status:
            status_style = "yellow"
        elif "Blocked" in status:
            status_style = "red"
        else:
            status_style = "white"

        # Color priority
        priority = issue.get("priority", "")
        if priority == "Highest":
            priority_style = "bold red"
        elif priority == "High":
            priority_style = "red"
        elif priority == "Medium":
            priority_style = "yellow"
        elif priority == "Low":
            priority_style = "green"
        else:
            priority_style = "white"

        table.add_row(
            issue.get("key", ""),
            issue.get("summary", "")[:50],
            f"[{status_style}]{status}[/{status_style}]",
            f"[{priority_style}]{priority}[/{priority_style}]",
            issue.get("assignee", "Unassigned"),
        )

    return table


def format_issue_details(issue: Dict[str, Any]) -> Panel:
    """
    Format single issue details as Rich panel.

    Args:
        issue: Issue dict

    Returns:
        Rich Panel object
    """
    key = issue.get("key", "")
    summary = issue.get("summary", "")
    description = issue.get("description", "No description")
    status = issue.get("status", "")
    priority = issue.get("priority", "")
    assignee = issue.get("assignee", "Unassigned")
    reporter = issue.get("reporter", "Unknown")
    created = issue.get("created", "")[:10]
    updated = issue.get("updated", "")[:10]
    labels = ", ".join(issue.get("labels", []))
    components = ", ".join(issue.get("components", []))
    fix_versions = ", ".join(issue.get("fix_versions", []))

    content = f"""
**Summary**: {summary}

**Description**:
{description}

**Status**: {status}
**Priority**: {priority}
**Assignee**: {assignee}
**Reporter**: {reporter}

**Created**: {created}
**Updated**: {updated}

**Labels**: {labels or "None"}
**Components**: {components or "None"}
**Fix Versions**: {fix_versions or "None"}
    """.strip()

    md = Markdown(content)
    return Panel(md, title=f"[bold cyan]{key}[/bold cyan]", border_style="cyan")


def format_sprint_report(sprint: Dict[str, Any], metrics: Dict[str, Any]) -> Panel:
    """
    Format sprint report as Rich panel.

    Args:
        sprint: Sprint dict
        metrics: Metrics dict (todo, in_progress, done, blocked, total)

    Returns:
        Rich Panel object
    """
    sprint_name = sprint.get("name", "Sprint")
    start_date = sprint.get("startDate", "")[:10]
    end_date = sprint.get("endDate", "")[:10]

    todo = metrics.get("todo", 0)
    in_progress = metrics.get("in_progress", 0)
    done = metrics.get("done", 0)
    blocked = metrics.get("blocked", 0)
    total = metrics.get("total", 0)

    # Calculate progress
    progress_pct = (done / total * 100) if total > 0 else 0

    # Health indicator
    if blocked > 5:
        health = "🔴 At Risk"
    elif blocked > 2:
        health = "🟡 Caution"
    else:
        health = "🟢 Healthy"

    content = f"""
**📅 Period**: {start_date} → {end_date}

**📊 Status Breakdown**:
- ✅ Done: {done} tickets ({progress_pct:.1f}%)
- 🔄 In Progress: {in_progress} tickets
- 🚫 Blocked: {blocked} tickets
- ⏸️  To Do: {todo} tickets

**📈 Total**: {total} tickets

**🏥 Health**: {health}
    """.strip()

    md = Markdown(content)
    return Panel(md, title=f"[bold cyan]{sprint_name} Report[/bold cyan]", border_style="cyan")


def format_dependencies(
    blocks: List[Dict[str, Any]],
    blocked_by: List[Dict[str, Any]],
    relates_to: List[Dict[str, Any]],
) -> Panel:
    """
    Format issue dependencies as Rich panel.

    Args:
        blocks: Issues that this issue blocks
        blocked_by: Issues that block this issue
        relates_to: Related issues

    Returns:
        Rich Panel object
    """
    content = ""

    if blocked_by:
        content += "**🚫 Blocked By**:\n"
        for issue in blocked_by:
            content += f"- {issue['key']}: {issue['summary']} ({issue['status']})\n"
        content += "\n"

    if blocks:
        content += "**⛔ Blocks**:\n"
        for issue in blocks:
            content += f"- {issue['key']}: {issue['summary']} ({issue['status']})\n"
        content += "\n"

    if relates_to:
        content += "**🔗 Related To**:\n"
        for issue in relates_to:
            content += f"- {issue['key']}: {issue['summary']} ({issue['status']})\n"

    if not content:
        content = "No dependencies found."

    md = Markdown(content.strip())
    return Panel(md, title="[bold cyan]Dependencies[/bold cyan]", border_style="cyan")


def format_epic_tree(
    epic: Dict[str, Any],
    stories: List[Dict[str, Any]],
    subtasks: List[Dict[str, Any]],
) -> Panel:
    """
    Format epic tree as Rich panel.

    Args:
        epic: Epic dict
        stories: List of story dicts
        subtasks: List of subtask dicts

    Returns:
        Rich Panel object
    """
    epic_key = epic.get("key", "")
    epic_summary = epic.get("summary", "")
    epic_status = epic.get("status", "")

    content = f"**Epic**: {epic_key} - {epic_summary} ({epic_status})\n\n"

    if stories:
        content += "**📋 Stories**:\n"
        for story in stories:
            content += f"- {story['key']}: {story['summary']} ({story['status']})\n"
        content += "\n"

    if subtasks:
        content += "**📝 Subtasks**:\n"
        for subtask in subtasks:
            content += f"- {subtask['key']}: {subtask['summary']} ({subtask['status']})\n"

    md = Markdown(content.strip())
    return Panel(md, title=f"[bold cyan]Epic Tree[/bold cyan]", border_style="cyan")


def format_comments(comments: List[Dict[str, Any]]) -> Panel:
    """
    Format comments as Rich panel.

    Args:
        comments: List of comment dicts

    Returns:
        Rich Panel object
    """
    if not comments:
        content = "No comments found."
    else:
        content = ""
        for i, comment in enumerate(comments, 1):
            author = comment.get("author", "Unknown")
            created = comment.get("created", "")[:10]
            body = comment.get("body", "")
            content += f"**Comment {i}** ({author}, {created}):\n{body}\n\n"

    md = Markdown(content.strip())
    return Panel(md, title="[bold cyan]Comments[/bold cyan]", border_style="cyan")


def print_success(message: str) -> None:
    """Print success message."""
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str) -> None:
    """Print error message."""
    console.print(f"[red]✗[/red] {message}")


def print_warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def print_info(message: str) -> None:
    """Print info message."""
    console.print(f"[cyan]ℹ[/cyan] {message}")


def print_assistant_message(message: str) -> None:
    """Print assistant response with markdown support."""
    md = Markdown(message)
    panel = Panel(md, title="[bold cyan]🤖 Assistant[/bold cyan]", border_style="cyan")
    console.print(panel)
