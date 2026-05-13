#!/usr/bin/env python3
"""
delete_tickets.py
=================
Delete a range of Jira tickets.

Usage:
    python delete_tickets.py SCRUM-312 SCRUM-443
    DRY_RUN=true python delete_tickets.py SCRUM-312 SCRUM-443
"""
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))

from src.jira_client import JiraClient

load_dotenv()

DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"


def parse_ticket_number(ticket_key: str) -> int:
    """Extract ticket number from key."""
    return int(ticket_key.split("-")[1])


def delete_tickets(start_ticket: str, end_ticket: str):
    """Delete tickets in range."""
    print("\n" + "="*70)
    print("  DELETE TICKETS")
    print("="*70)
    print(f"  Range: {start_ticket} to {end_ticket}")
    print(f"  Mode: {'DRY RUN' if DRY_RUN else 'LIVE'}")
    print("="*70)
    print()

    # Parse range
    project_key = start_ticket.split("-")[0]
    start_num = parse_ticket_number(start_ticket)
    end_num = parse_ticket_number(end_ticket)
    total = end_num - start_num + 1

    print(f"Will delete {total} tickets...")
    print()

    # Check for --yes flag
    auto_confirm = "--yes" in sys.argv or "-y" in sys.argv

    if not DRY_RUN and not auto_confirm:
        confirm = input(f"Are you sure you want to DELETE {total} tickets? (yes/no): ")
        if confirm.lower() != "yes":
            print("Cancelled.")
            return
    elif not DRY_RUN:
        print(f"Auto-confirmed with --yes flag - deleting {total} tickets...")
        print()

    # Connect to Jira
    if not DRY_RUN:
        jira = JiraClient()
        print(f"[OK] Connected to Jira")
        print()

    # Delete tickets
    deleted = 0
    failed = 0

    for num in range(start_num, end_num + 1):
        ticket_key = f"{project_key}-{num}"

        if DRY_RUN:
            print(f"[OK] [DRY RUN] Would delete {ticket_key}")
            deleted += 1
        else:
            try:
                jira._request("DELETE", f"/rest/api/3/issue/{ticket_key}")
                print(f"[OK] Deleted {ticket_key}")
                deleted += 1
            except Exception as e:
                print(f"[ERROR] Failed to delete {ticket_key}: {str(e)[:60]}")
                failed += 1

    print()
    print("="*70)
    print("  DELETION SUMMARY")
    print("="*70)
    print(f"  Total tickets : {total}")
    print(f"  [OK] Deleted     : {deleted}")
    print(f"  [ERROR] Failed   : {failed}")
    print("="*70)
    print()


def main():
    if len(sys.argv) < 3:
        print("Usage: python delete_tickets.py <start> <end>")
        print("Example: python delete_tickets.py SCRUM-312 SCRUM-443")
        sys.exit(1)

    start_ticket = sys.argv[1]
    end_ticket = sys.argv[2]

    delete_tickets(start_ticket, end_ticket)


if __name__ == "__main__":
    main()
