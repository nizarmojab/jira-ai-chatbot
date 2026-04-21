#!/usr/bin/env python3
"""
chatbot.py
==========
Main CLI for Jira AI Chatbot.

Interactive terminal interface with:
- Natural language queries (FR/EN)
- Rich table/panel output
- Command history
- /commands for direct JQL
"""
from __future__ import annotations

import os
import sys
import logging
from typing import Optional

from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.markdown import Markdown
from dotenv import load_dotenv

from .llm_agent import JiraAgent
from .jira_client import JiraClient, JiraError
from .formatter import (
    format_issues_table,
    format_issue_details,
    format_sprint_report,
    format_dependencies,
    format_epic_tree,
    format_comments,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_assistant_message,
)

load_dotenv()

# Setup logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

console = Console()


class JiraChatbot:
    """
    Interactive Jira chatbot CLI.

    Commands:
    - Natural language: "show me critical bugs"
    - Direct JQL: /jql project = SCRUM AND status = Blocked
    - Issue details: /issue SCRUM-5
    - Sprint report: /sprint
    - Help: /help
    - Exit: /exit or /quit
    """

    def __init__(self):
        self.agent = JiraAgent()
        self.jira_client = JiraClient()
        self.running = True

        logger.info("JiraChatbot initialized")

    def run(self) -> None:
        """Main chatbot loop."""
        self._print_welcome()

        while self.running:
            try:
                # Get user input
                user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]").strip()

                if not user_input:
                    continue

                # Check for commands
                if user_input.startswith("/"):
                    self._handle_command(user_input)
                else:
                    # Natural language query
                    self._handle_natural_query(user_input)

            except KeyboardInterrupt:
                print_warning("\nInterrupted. Type /exit to quit.")
                continue

            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                print_error(f"An error occurred: {e}")

        self._print_goodbye()

    def _print_welcome(self) -> None:
        """Print welcome message."""
        welcome_text = """
# 🤖 Jira AI Chatbot

**Project**: SCRUM (Infotainment & Connectivity)
**Client**: Stellantis × Capgemini Engineering

**Usage**:
- Ask questions in natural language (FR/EN)
- Type `/help` for commands
- Type `/exit` to quit

**Examples**:
- "show me critical bugs"
- "what tickets are blocked?"
- "sprint report"
- "analyze SCRUM-5"
        """
        md = Markdown(welcome_text.strip())
        panel = Panel(md, border_style="cyan", title="[bold]Welcome[/bold]")
        console.print(panel)

    def _print_goodbye(self) -> None:
        """Print goodbye message."""
        print_success("Goodbye! 👋")

    def _handle_command(self, command: str) -> None:
        """
        Handle slash commands.

        Args:
            command: Command string (e.g., "/help", "/jql ...", "/exit")
        """
        cmd_parts = command.split(maxsplit=1)
        cmd_name = cmd_parts[0].lower()
        cmd_args = cmd_parts[1] if len(cmd_parts) > 1 else ""

        if cmd_name in ["/exit", "/quit"]:
            self.running = False

        elif cmd_name == "/help":
            self._show_help()

        elif cmd_name == "/clear":
            self.agent.clear_history()
            print_success("Conversation history cleared")

        elif cmd_name == "/jql":
            if not cmd_args:
                print_error("Usage: /jql <query>")
                return
            self._execute_jql(cmd_args)

        elif cmd_name == "/issue":
            if not cmd_args:
                print_error("Usage: /issue <KEY>")
                return
            self._show_issue_details(cmd_args)

        elif cmd_name == "/sprint":
            self._show_sprint_report()

        elif cmd_name == "/my":
            self._show_my_issues()

        else:
            print_error(f"Unknown command: {cmd_name}")
            print_info("Type /help for available commands")

    def _handle_natural_query(self, query: str) -> None:
        """
        Handle natural language query.

        Args:
            query: User's natural language query
        """
        try:
            # Process with LLM agent
            result = self.agent.process_query(query)

            # Display assistant response
            print_assistant_message(result["response"])

            # Display tickets if any
            if result.get("tickets"):
                table = format_issues_table(
                    result["tickets"],
                    title=f"Results ({len(result['tickets'])} tickets)"
                )
                console.print(table)

            # Show JQL if available
            if result.get("jql"):
                print_info(f"JQL: {result['jql']}")

        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            print_error(f"Error: {e}")

    def _execute_jql(self, jql: str) -> None:
        """
        Execute direct JQL query.

        Args:
            jql: JQL query string
        """
        try:
            result = self.jira_client.search_issues(jql, max_results=50)
            issues = result["issues"]

            if not issues:
                print_warning("No issues found")
                return

            # Simplify issue format
            simplified_issues = []
            for issue in issues:
                fields = issue.get("fields", {})
                simplified_issues.append({
                    "key": issue["key"],
                    "summary": fields.get("summary", ""),
                    "status": fields.get("status", {}).get("name", ""),
                    "priority": fields.get("priority", {}).get("name", ""),
                    "assignee": fields.get("assignee", {}).get("displayName", "Unassigned"),
                })

            table = format_issues_table(
                simplified_issues,
                title=f"JQL Results ({result['total']} total, showing {len(issues)})"
            )
            console.print(table)

        except JiraError as e:
            print_error(f"JQL error: {e}")

    def _show_issue_details(self, issue_key: str) -> None:
        """
        Show detailed issue information.

        Args:
            issue_key: Issue key (e.g., SCRUM-5)
        """
        try:
            issue = self.jira_client.get_issue(issue_key)
            fields = issue.get("fields", {})

            # Extract description
            description = ""
            desc_adf = fields.get("description")
            if desc_adf and isinstance(desc_adf, dict):
                content = desc_adf.get("content", [])
                for block in content:
                    if block.get("type") == "paragraph":
                        for item in block.get("content", []):
                            if item.get("type") == "text":
                                description += item.get("text", "")
                        description += "\n"

            issue_data = {
                "key": issue["key"],
                "summary": fields.get("summary", ""),
                "description": description.strip(),
                "status": fields.get("status", {}).get("name", ""),
                "priority": fields.get("priority", {}).get("name", ""),
                "assignee": fields.get("assignee", {}).get("displayName", "Unassigned"),
                "reporter": fields.get("reporter", {}).get("displayName", "Unknown"),
                "created": fields.get("created", ""),
                "updated": fields.get("updated", ""),
                "labels": fields.get("labels", []),
                "components": [c.get("name") for c in fields.get("components", [])],
                "fix_versions": [v.get("name") for v in fields.get("fixVersions", [])],
            }

            panel = format_issue_details(issue_data)
            console.print(panel)

            # Show dependencies
            links = self.jira_client.get_issue_links(issue_key)
            if links:
                blocks = []
                blocked_by = []
                relates_to = []

                for link in links:
                    link_issue = link["issue"]
                    issue_data = {
                        "key": link_issue["key"],
                        "summary": link_issue["fields"].get("summary", ""),
                        "status": link_issue["fields"].get("status", {}).get("name", ""),
                    }

                    link_type = link["type"].lower()
                    if "blocks" in link_type and link["direction"] == "outward":
                        blocks.append(issue_data)
                    elif "blocks" in link_type and link["direction"] == "inward":
                        blocked_by.append(issue_data)
                    else:
                        relates_to.append(issue_data)

                if blocks or blocked_by or relates_to:
                    dep_panel = format_dependencies(blocks, blocked_by, relates_to)
                    console.print(dep_panel)

        except JiraError as e:
            print_error(f"Error fetching issue: {e}")

    def _show_sprint_report(self) -> None:
        """Show active sprint report."""
        try:
            sprint = self.jira_client.get_active_sprint()

            if not sprint:
                print_warning("No active sprint found")
                return

            # Get sprint issues
            issues = self.jira_client.get_sprint_issues(sprint["id"])

            # Count by status
            metrics = {
                "todo": 0,
                "in_progress": 0,
                "done": 0,
                "blocked": 0,
                "total": len(issues),
            }

            for issue in issues:
                status = issue["fields"].get("status", {}).get("name", "").lower()
                if "done" in status or "closed" in status:
                    metrics["done"] += 1
                elif "progress" in status:
                    metrics["in_progress"] += 1
                elif "blocked" in status:
                    metrics["blocked"] += 1
                else:
                    metrics["todo"] += 1

            panel = format_sprint_report(sprint, metrics)
            console.print(panel)

        except JiraError as e:
            print_error(f"Error fetching sprint: {e}")

    def _show_my_issues(self) -> None:
        """Show current user's issues."""
        try:
            user = self.jira_client.get_current_user()
            jql = f'assignee = "{user["emailAddress"]}" AND resolution = Unresolved'

            result = self.jira_client.search_issues(jql, max_results=50)
            issues = result["issues"]

            if not issues:
                print_warning("No issues assigned to you")
                return

            # Simplify issue format
            simplified_issues = []
            for issue in issues:
                fields = issue.get("fields", {})
                simplified_issues.append({
                    "key": issue["key"],
                    "summary": fields.get("summary", ""),
                    "status": fields.get("status", {}).get("name", ""),
                    "priority": fields.get("priority", {}).get("name", ""),
                    "assignee": fields.get("assignee", {}).get("displayName", "Unassigned"),
                })

            table = format_issues_table(
                simplified_issues,
                title=f"My Issues ({result['total']} total)"
            )
            console.print(table)

        except JiraError as e:
            print_error(f"Error fetching issues: {e}")

    def _show_help(self) -> None:
        """Show help message."""
        help_text = """
# 📚 Commands

**Natural Language**:
- "show me critical bugs"
- "what tickets are blocked?"
- "sprint report"
- "analyze SCRUM-5"

**Direct Commands**:
- `/jql <query>` — Execute JQL directly
- `/issue <KEY>` — Show issue details
- `/sprint` — Show active sprint report
- `/my` — Show your assigned issues
- `/clear` — Clear conversation history
- `/help` — Show this help
- `/exit` — Quit chatbot

**Examples**:
```
/jql project = SCRUM AND status = Blocked
/issue SCRUM-5
/sprint
```
        """
        md = Markdown(help_text.strip())
        panel = Panel(md, border_style="cyan", title="[bold]Help[/bold]")
        console.print(panel)


def main():
    """Main entry point."""
    try:
        chatbot = JiraChatbot()
        chatbot.run()
    except KeyboardInterrupt:
        print_warning("\nInterrupted. Exiting...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print_error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
