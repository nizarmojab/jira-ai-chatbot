#!/usr/bin/env python3
"""
import_tickets_from_excel.py
============================
Import tickets from Excel file to Jira.

Usage:
    python import_tickets_from_excel.py "Capas test.xlsx"
    DRY_RUN=true python import_tickets_from_excel.py "Capas test.xlsx"  # test mode
"""
import os
import sys
from typing import Any, Dict, List
import pandas as pd
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from src.jira_client import JiraClient, JiraError

load_dotenv()

# Config
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "SCRUM")


def normalize_column_name(col: str) -> str:
    """Normalize column names (remove spaces, lowercase)."""
    return col.strip().lower().replace(" ", "_")


def parse_priority(priority: str) -> str:
    """Normalize priority value."""
    if not priority or pd.isna(priority):
        return "Medium"

    priority = str(priority).strip().lower()
    mapping = {
        "low": "Low",
        "medium": "Medium", "med": "Medium", "moyenne": "Medium",
        "high": "High", "haute": "High",
        "highest": "Highest", "critical": "Highest", "critique": "Highest",
    }
    return mapping.get(priority, "Medium")


def parse_issue_type(issue_type: str) -> str:
    """Normalize issue type."""
    if not issue_type or pd.isna(issue_type):
        return "Task"

    issue_type = str(issue_type).strip().lower()
    mapping = {
        "bug": "Bug",
        "story": "Story", "user story": "Story",
        "task": "Task", "tache": "Task", "tâche": "Task",
        "epic": "Epic",
        "sub-task": "Sub-task", "subtask": "Sub-task",
    }
    return mapping.get(issue_type, "Task")


def parse_status(status: str) -> str:
    """Normalize status."""
    if not status or pd.isna(status):
        return "To Do"

    status = str(status).strip().lower()
    mapping = {
        "to do": "To Do", "todo": "To Do", "à faire": "To Do",
        "in progress": "In Progress", "en cours": "In Progress", "doing": "In Progress",
        "done": "Done", "terminé": "Done", "fait": "Done",
        "blocked": "Blocked", "bloqué": "Blocked",
    }
    return mapping.get(status, "To Do")


def parse_excel_row(row: pd.Series, columns: List[str]) -> Dict[str, Any]:
    """Parse Excel row to Jira ticket fields."""
    # Normalize column access
    def get_col(name: str, default: Any = None) -> Any:
        for col in columns:
            if normalize_column_name(col) == name.lower():
                val = row[col]
                return val if not pd.isna(val) else default
        return default

    # Extract fields
    summary = get_col("summary") or get_col("titre") or get_col("title")
    description = get_col("description") or get_col("desc")
    priority = parse_priority(get_col("priority") or get_col("priorité") or get_col("priorite"))
    issue_type = parse_issue_type(get_col("type") or get_col("issue_type") or get_col("type_issue"))
    status = parse_status(get_col("status") or get_col("statut"))
    assignee = get_col("assignee") or get_col("assigné") or get_col("assigne")
    component = get_col("component") or get_col("composant")
    labels = get_col("labels") or get_col("étiquettes")

    if not summary:
        return None

    # Convert description to ADF format
    adf_description = None
    if description:
        adf_description = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": str(description)}]
                }
            ]
        }

    ticket = {
        "summary": str(summary),
        "description": adf_description,
        "priority": priority,
        "issue_type": issue_type,
        "status": status,
        "assignee": assignee,
        "component": component,
        "labels": labels,
    }

    return ticket


def create_ticket_in_jira(jira: JiraClient, ticket: Dict[str, Any]) -> str:
    """Create ticket in Jira."""
    fields = {
        "project": {"key": PROJECT_KEY},
        "summary": ticket["summary"],
        "issuetype": {"name": ticket["issue_type"]},
    }

    # Add optional fields
    if ticket.get("description"):
        fields["description"] = ticket["description"]

    if ticket.get("priority"):
        fields["priority"] = {"name": ticket["priority"]}

    if ticket.get("component"):
        fields["components"] = [{"name": ticket["component"]}]

    if ticket.get("labels"):
        labels = str(ticket["labels"]).split(",")
        fields["labels"] = [l.strip() for l in labels if l.strip()]

    # Create issue
    result = jira._request("POST", "/rest/api/3/issue", json_data={"fields": fields})
    issue_key = result.get("key")

    return issue_key


def import_tickets_from_excel(excel_file: str):
    """Import tickets from Excel file to Jira."""
    print("\n" + "="*70)
    print(f"  IMPORT TICKETS FROM EXCEL -> JIRA")
    print("="*70)
    print(f"  File: {excel_file}")
    print(f"  Project: {PROJECT_KEY}")
    print(f"  Mode: {'DRY RUN (test mode)' if DRY_RUN else 'LIVE (will create tickets)'}")
    print("="*70)
    print()

    # Read Excel file
    try:
        df = pd.read_excel(excel_file)
        print(f"[OK] Loaded {len(df)} rows from Excel")
        print(f"Columns: Columns: {', '.join(df.columns.tolist())}")
        print()
    except Exception as e:
        print(f"[ERROR] Failed to read Excel file: {e}")
        return

    # Initialize Jira client
    if not DRY_RUN:
        try:
            jira = JiraClient()
            print(f"[OK] Connected to Jira: {jira.base_url}")
            print()
        except Exception as e:
            print(f"[ERROR] Failed to connect to Jira: {e}")
            return
    else:
        jira = None
        print("[WARN]  DRY RUN mode - no tickets will be created")
        print()

    # Process each row
    created_count = 0
    failed_count = 0
    skipped_count = 0

    for idx, row in df.iterrows():
        row_num = idx + 2  # Excel row number (1-indexed + header)

        # Parse ticket
        ticket = parse_excel_row(row, df.columns.tolist())

        if not ticket:
            print(f"[SKIP]  Row {row_num}: Skipped (no summary)")
            skipped_count += 1
            continue

        # Display ticket info
        print(f"Row Row {row_num}: {ticket['summary'][:60]}")
        print(f"   Type: {ticket['issue_type']} | Priority: {ticket['priority']} | Status: {ticket['status']}")

        if DRY_RUN:
            print(f"   [OK] [DRY RUN] Would create ticket")
            created_count += 1
        else:
            # Create in Jira
            try:
                issue_key = create_ticket_in_jira(jira, ticket)
                print(f"   [OK] Created: {issue_key}")
                print(f"   URL: {jira.base_url}/browse/{issue_key}")
                created_count += 1
            except Exception as e:
                print(f"   [ERROR] Failed: {str(e)[:100]}")
                failed_count += 1

        print()

    # Summary
    print("="*70)
    print("  IMPORT SUMMARY")
    print("="*70)
    print(f"  Total rows     : {len(df)}")
    print(f"  [OK] Created     : {created_count}")
    print(f"  [ERROR] Failed      : {failed_count}")
    print(f"  [SKIP]  Skipped    : {skipped_count}")
    print("="*70)
    print()

    if DRY_RUN:
        print("[TIP] To actually create tickets, run without DRY_RUN:")
        print(f"   python import_tickets_from_excel.py \"{excel_file}\"")
        print()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python import_tickets_from_excel.py <excel_file>")
        print("Example: python import_tickets_from_excel.py \"Capas test.xlsx\"")
        print()
        print("Options:")
        print("  DRY_RUN=true  - Test mode (don't create tickets)")
        sys.exit(1)

    excel_file = sys.argv[1]

    if not os.path.exists(excel_file):
        print(f"[ERROR] File not found: {excel_file}")
        sys.exit(1)

    import_tickets_from_excel(excel_file)


if __name__ == "__main__":
    main()
