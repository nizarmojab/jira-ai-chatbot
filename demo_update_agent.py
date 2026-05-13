#!/usr/bin/env python3
"""
demo_update_agent.py
====================
Interactive demo showing BEFORE/AFTER state for UpdateAgent operations.
"""
from src.test_agents.update_test_agent import FakeJiraClient
from src.agents.update_agent import UpdateAgent


def print_section(title: str):
    """Print section header."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def print_ticket_state(jira_client: FakeJiraClient, ticket_key: str, label: str):
    """Print current ticket state."""
    issue = jira_client.issues.get(ticket_key, {})
    if not issue:
        print(f"❌ Ticket {ticket_key} not found")
        return

    fields = issue.get("fields", {})
    priority = fields.get("priority", {}).get("name", "None") if fields.get("priority") else "None"
    status = fields.get("status", {}).get("name", "Unknown")
    assignee = fields.get("assignee", {}).get("displayName", "Unassigned") if fields.get("assignee") else "Unassigned"

    print(f"\n{label}:")
    print(f"  🎫 Ticket    : {ticket_key}")
    print(f"  📝 Summary   : {fields.get('summary', 'N/A')}")
    print(f"  ⚡ Priority  : {priority}")
    print(f"  🎯 Status    : {status}")
    print(f"  👤 Assignee  : {assignee}")


def print_comparison(before: dict, after: dict):
    """Print before/after comparison."""
    print("\n📊 COMPARISON:")

    # Priority
    if before.get("priority") != after.get("priority"):
        print(f"  ⚡ Priority  : {before['priority']} → {after['priority']}")

    # Status
    if before.get("status") != after.get("status"):
        print(f"  🎯 Status    : {before['status']} → {after['status']}")

    # Assignee
    if before.get("assignee") != after.get("assignee"):
        print(f"  👤 Assignee  : {before['assignee']} → {after['assignee']}")


def get_ticket_snapshot(jira_client: FakeJiraClient, ticket_key: str) -> dict:
    """Get snapshot of ticket state."""
    issue = jira_client.issues.get(ticket_key, {})
    fields = issue.get("fields", {})

    return {
        "priority": fields.get("priority", {}).get("name", "None") if fields.get("priority") else "None",
        "status": fields.get("status", {}).get("name", "Unknown"),
        "assignee": fields.get("assignee", {}).get("displayName", "Unassigned") if fields.get("assignee") else "Unassigned",
    }


def demo_update_priority():
    """Demo: Update ticket priority."""
    print_section("DEMO 1: Update Priority")

    # Setup
    jira_client = FakeJiraClient()
    jira_client.register_issue("SCRUM-100", "CAN bus initialization fails", priority="Medium")
    agent = UpdateAgent(jira_client=jira_client)

    # BEFORE
    before = get_ticket_snapshot(jira_client, "SCRUM-100")
    print_ticket_state(jira_client, "SCRUM-100", "🔵 BEFORE UPDATE")

    # Execute update
    print("\n⚙️  EXECUTING: 'change priority of SCRUM-100 to high'")
    result = agent.process("change priority of SCRUM-100 to high", [])

    # AFTER
    after = get_ticket_snapshot(jira_client, "SCRUM-100")
    print_ticket_state(jira_client, "SCRUM-100", "🟢 AFTER UPDATE")

    # Comparison
    print_comparison(before, after)

    # Result
    print(f"\n✅ Result: {result['success']}")
    print(f"📄 Message: {result['message'].split(chr(10))[0]}")  # First line only


def demo_update_status():
    """Demo: Update ticket status."""
    print_section("DEMO 2: Update Status (Transition)")

    # Setup
    jira_client = FakeJiraClient()
    jira_client.register_issue("SCRUM-200", "Implement vehicle speed sensor", status="To Do")
    agent = UpdateAgent(jira_client=jira_client)

    # BEFORE
    before = get_ticket_snapshot(jira_client, "SCRUM-200")
    print_ticket_state(jira_client, "SCRUM-200", "🔵 BEFORE UPDATE")

    # Execute update
    print("\n⚙️  EXECUTING: 'move SCRUM-200 to in progress'")
    result = agent.process("move SCRUM-200 to in progress", [])

    # AFTER
    after = get_ticket_snapshot(jira_client, "SCRUM-200")
    print_ticket_state(jira_client, "SCRUM-200", "🟢 AFTER UPDATE")

    # Comparison
    print_comparison(before, after)

    # Result
    print(f"\n✅ Result: {result['success']}")
    print(f"📄 Message: {result['message'].split(chr(10))[0]}")


def demo_update_assignee():
    """Demo: Update ticket assignee."""
    print_section("DEMO 3: Update Assignee")

    # Setup
    jira_client = FakeJiraClient()
    jira_client.register_issue("SCRUM-300", "Fix memory leak in logger", assignee="Other User")
    agent = UpdateAgent(jira_client=jira_client)
    agent.account_id = "test-me-123"  # Simulate current user

    # BEFORE
    before = get_ticket_snapshot(jira_client, "SCRUM-300")
    print_ticket_state(jira_client, "SCRUM-300", "🔵 BEFORE UPDATE")

    # Execute update
    print("\n⚙️  EXECUTING: 'assign SCRUM-300 to me'")
    result = agent.process("assign SCRUM-300 to me", [])

    # AFTER
    after = get_ticket_snapshot(jira_client, "SCRUM-300")
    print_ticket_state(jira_client, "SCRUM-300", "🟢 AFTER UPDATE")

    # Comparison
    print_comparison(before, after)

    # Result
    print(f"\n✅ Result: {result['success']}")
    print(f"📄 Message: {result['message'].split(chr(10))[0]}")


def demo_add_comment():
    """Demo: Add comment to ticket."""
    print_section("DEMO 4: Add Comment")

    # Setup
    jira_client = FakeJiraClient()
    jira_client.register_issue("SCRUM-400", "Update user documentation")
    agent = UpdateAgent(jira_client=jira_client)

    # BEFORE
    print_ticket_state(jira_client, "SCRUM-400", "🔵 BEFORE UPDATE")
    print(f"  💬 Comments  : {len(jira_client.comments.get('SCRUM-400', []))}")

    # Execute update
    print("\n⚙️  EXECUTING: 'add comment to SCRUM-400: Documentation updated in v2.1'")
    result = agent.process("add comment to SCRUM-400: Documentation updated in v2.1", [])

    # AFTER
    print_ticket_state(jira_client, "SCRUM-400", "🟢 AFTER UPDATE")
    print(f"  💬 Comments  : {len(jira_client.comments.get('SCRUM-400', []))}")

    # Show comment
    if jira_client.comments.get('SCRUM-400'):
        last_comment = jira_client.comments['SCRUM-400'][-1]
        print(f"\n📝 New comment:")
        print(f"  Author: {last_comment['author']['displayName']}")
        print(f"  Body  : {last_comment['body']}")

    # Result
    print(f"\n✅ Result: {result['success']}")
    print(f"📄 Message: {result['message'].split(chr(10))[0]}")


def demo_multiple_updates():
    """Demo: Multiple sequential updates on same ticket."""
    print_section("DEMO 5: Multiple Updates (Sequential)")

    # Setup
    jira_client = FakeJiraClient()
    jira_client.register_issue(
        "SCRUM-500",
        "Critical bug in payment module",
        status="To Do",
        priority="Medium",
        assignee=None
    )
    agent = UpdateAgent(jira_client=jira_client)
    agent.account_id = "test-me-123"

    # Initial state
    print_ticket_state(jira_client, "SCRUM-500", "🔵 INITIAL STATE")

    # Update 1: Priority
    print("\n⚙️  UPDATE 1: 'change priority of SCRUM-500 to highest'")
    agent.process("change priority of SCRUM-500 to highest", [])
    print_ticket_state(jira_client, "SCRUM-500", "  After Update 1")

    # Update 2: Assignee
    print("\n⚙️  UPDATE 2: 'assign SCRUM-500 to me'")
    agent.process("assign SCRUM-500 to me", [])
    print_ticket_state(jira_client, "SCRUM-500", "  After Update 2")

    # Update 3: Status
    print("\n⚙️  UPDATE 3: 'move SCRUM-500 to in progress'")
    agent.process("move SCRUM-500 to in progress", [])
    print_ticket_state(jira_client, "SCRUM-500", "🟢 FINAL STATE")

    # Show all updates
    print(f"\n📊 Total updates executed: {len(jira_client.updates)}")
    for i, update in enumerate(jira_client.updates, 1):
        if "fields" in update:
            field = list(update["fields"].keys())[0]
            value = update["fields"][field]
            if isinstance(value, dict) and "name" in value:
                print(f"  {i}. Updated {field} to {value['name']}")
            else:
                print(f"  {i}. Updated {field}")


def main():
    """Run all demos."""
    print("\n" + "█"*70)
    print("  UPDATE AGENT - INTERACTIVE DEMO")
    print("  Shows BEFORE/AFTER state for each update operation")
    print("█"*70)

    demo_update_priority()
    demo_update_status()
    demo_update_assignee()
    demo_add_comment()
    demo_multiple_updates()

    print("\n" + "="*70)
    print("  ✅ ALL DEMOS COMPLETED")
    print("="*70)
    print()


if __name__ == "__main__":
    main()
