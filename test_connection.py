#!/usr/bin/env python3
"""
test_connection.py
==================
Quick test script to verify Jira connection and chatbot setup.
"""
import sys
from rich.console import Console
from rich.panel import Panel

console = Console()

def test_imports():
    """Test if all modules can be imported."""
    console.print("\n[cyan]1. Testing imports...[/cyan]")

    try:
        from src.jira_client import JiraClient
        console.print("   [green]+[/green] jira_client imported")

        from src.jira_tools import JIRA_TOOLS_SCHEMAS
        console.print("   [green]+[/green] jira_tools imported")

        from src.llm_agent import JiraAgent
        console.print("   [green]+[/green] llm_agent imported")

        from src.formatter import format_issues_table
        console.print("   [green]+[/green] formatter imported")

        console.print("[green]+ All imports successful![/green]")
        return True

    except Exception as e:
        console.print(f"[red]- Import error: {e}[/red]")
        return False


def test_jira_connection():
    """Test Jira API connection."""
    console.print("\n[cyan]2. Testing Jira connection...[/cyan]")

    try:
        from src.jira_client import JiraClient

        client = JiraClient()
        console.print(f"   -> Base URL: {client.base_url}")
        console.print(f"   -> Project: {client.project_key}")

        # Test connection by getting current user
        user = client.get_current_user()
        console.print(f"   -> Authenticated as: {user['displayName']} ({user['emailAddress']})")
        console.print(f"   -> Account ID: {user['accountId']}")

        # Test project access
        project = client.get_project_info()
        console.print(f"   -> Project Name: {project['name']}")

        console.print("[green]OK Jira connection successful![/green]")
        return True

    except Exception as e:
        console.print(f"[red]FAIL Jira connection error: {e}[/red]")
        return False


def test_openai_connection():
    """Test OpenAI API connection."""
    console.print("\n[cyan]3. Testing OpenAI connection...[/cyan]")

    try:
        from src.llm_agent import JiraAgent

        agent = JiraAgent()
        console.print(f"   -> Model: {agent.model}")
        console.print(f"   -> Tools available: {len(agent.system_prompt)} chars system prompt")

        console.print("[green]OK OpenAI agent initialized![/green]")
        return True

    except Exception as e:
        console.print(f"[red]FAIL OpenAI error: {e}[/red]")
        return False


def test_simple_query():
    """Test a simple query."""
    console.print("\n[cyan]4. Testing simple query...[/cyan]")

    try:
        from src.jira_tools import search_issues

        # Test direct tool call
        result = search_issues("project = SCRUM", max_results=3)

        if result.get("success"):
            console.print(f"   -> Found {result['total']} total issues")
            console.print(f"   -> Returned {len(result['issues'])} issues")

            if result['issues']:
                first = result['issues'][0]
                console.print(f"   -> Example: {first['key']} - {first['summary'][:50]}...")

            console.print("[green]OK Query successful![/green]")
            return True
        else:
            console.print(f"[red]FAIL Query failed: {result.get('error')}[/red]")
            return False

    except Exception as e:
        console.print(f"[red]FAIL Query error: {e}[/red]")
        return False


def main():
    """Run all tests."""
    panel = Panel(
        "[bold cyan]Jira Chatbot Connection Test[/bold cyan]\n"
        "Testing all components...",
        border_style="cyan"
    )
    console.print(panel)

    results = []

    results.append(("Imports", test_imports()))
    results.append(("Jira Connection", test_jira_connection()))
    results.append(("OpenAI Setup", test_openai_connection()))
    results.append(("Simple Query", test_simple_query()))

    # Summary
    console.print("\n" + "="*50)
    console.print("[bold cyan]Test Summary:[/bold cyan]\n")

    for name, passed in results:
        status = "[green]OK PASS[/green]" if passed else "[red]FAIL FAIL[/red]"
        console.print(f"  {status} - {name}")

    all_passed = all(r[1] for r in results)

    if all_passed:
        console.print("\n[bold green]SUCCESS All tests passed! Your chatbot is ready to use.[/bold green]")
        console.print("\n[cyan]Next steps:[/cyan]")
        console.print("  • Run CLI: [bold]python src/chatbot.py[/bold]")
        console.print("  • Run web UI: [bold]python dashboard/chatbot_ui.py[/bold]")
        return 0
    else:
        console.print("\n[bold red]WARNING Some tests failed. Check the errors above.[/bold red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
