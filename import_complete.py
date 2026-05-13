#!/usr/bin/env python3
"""
import_complete.py
==================
Complete import with ALL Excel fields mapped to Jira.

Usage:
    python import_complete.py "Capas test.xlsx"
    DRY_RUN=true python import_complete.py "Capas test.xlsx"
"""
import os
import sys
from typing import Any, Dict
import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))

from src.jira_client import JiraClient

load_dotenv()

DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "SCRUM")


def build_rich_description(row: pd.Series) -> Dict[str, Any]:
    """Build rich ADF description with all Excel fields."""
    content = []

    # Add heading
    content.append({
        "type": "heading",
        "attrs": {"level": 3},
        "content": [{"type": "text", "text": "Imported from Excel", "marks": [{"type": "strong"}]}]
    })

    # Add table with all fields
    table_rows = []

    for col in row.index:
        value = row[col]
        if pd.notna(value) and str(value).strip():
            # Skip fields that are already in Jira fields
            if col in ["Summary", "Priority", "Status", "Issue Type"]:
                continue

            table_rows.append({
                "type": "tableRow",
                "content": [
                    {
                        "type": "tableCell",
                        "content": [{
                            "type": "paragraph",
                            "content": [{"type": "text", "text": str(col), "marks": [{"type": "strong"}]}]
                        }]
                    },
                    {
                        "type": "tableCell",
                        "content": [{
                            "type": "paragraph",
                            "content": [{"type": "text", "text": str(value)}]
                        }]
                    }
                ]
            })

    if table_rows:
        content.append({
            "type": "table",
            "content": table_rows
        })

    return {
        "type": "doc",
        "version": 1,
        "content": content
    }


def parse_priority(priority: str) -> str:
    """Normalize priority."""
    if not priority or pd.isna(priority):
        return "Medium"

    priority = str(priority).strip().lower()
    mapping = {
        "low": "Low", "bas": "Low", "basse": "Low",
        "medium": "Medium", "med": "Medium", "moyenne": "Medium", "moyen": "Medium",
        "high": "High", "haute": "High", "haut": "High",
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
        "psa skin": "Task",  # Custom type from Excel
    }
    return mapping.get(issue_type, "Task")


def create_ticket_complete(jira: JiraClient, row: pd.Series, row_num: int) -> str:
    """Create ticket with ALL Excel data."""

    # Required fields
    summary = row.get("Summary")
    if not summary or pd.isna(summary):
        raise ValueError("Missing summary")

    issue_type = parse_issue_type(row.get("Issue Type"))
    priority = parse_priority(row.get("Priority"))

    # Build rich description with ALL Excel fields
    description = build_rich_description(row)

    # Build labels from various fields
    labels = []

    # Team as label
    team = row.get("Team")
    if pd.notna(team) and str(team).strip():
        team_label = str(team).strip().replace(" ", "_").replace("-", "_")
        labels.append(f"team:{team_label}")

    # Use cases as label
    use_cases = row.get("Use cases")
    if pd.notna(use_cases) and str(use_cases).strip():
        uc_label = str(use_cases).strip().replace(" ", "_").replace("-", "_")
        labels.append(f"usecase:{uc_label}")

    # Original key as label
    original_key = row.get("Key")
    if pd.notna(original_key) and str(original_key).strip():
        labels.append(f"original:{str(original_key).strip()}")

    # Assignee as label (since we can't map to real users)
    assignee = row.get("Assignee")
    if pd.notna(assignee) and str(assignee).strip():
        # Extract name part before " - " or " [X]"
        assignee_name = str(assignee).split(" - ")[0].strip()
        assignee_label = assignee_name.replace(" ", "_").replace("-", "_")
        labels.append(f"assignee:{assignee_label}")

    # Reporter as label
    reporter = row.get("Reporter")
    if pd.notna(reporter) and str(reporter).strip():
        reporter_name = str(reporter).split(" - ")[0].strip()
        reporter_label = reporter_name.replace(" ", "_").replace("-", "_")
        labels.append(f"reporter:{reporter_label}")

    # Status as label (for tracking original status)
    status = row.get("Status")
    if pd.notna(status) and str(status).strip():
        labels.append(f"excel_status:{str(status).strip().replace(' ', '_')}")

    # Prepare fields
    fields = {
        "project": {"key": PROJECT_KEY},
        "summary": str(summary),
        "issuetype": {"name": issue_type},
        "priority": {"name": priority},
        "description": description,
    }

    # Component
    component = row.get("Component/s")
    if pd.notna(component) and str(component).strip():
        fields["components"] = [{"name": str(component).strip()}]

    # Labels
    if labels:
        fields["labels"] = labels

    # Create issue
    result = jira._request("POST", "/rest/api/3/issue", json_data={"fields": fields})
    issue_key = result.get("key")

    return issue_key


def import_complete(excel_file: str):
    """Import with complete field mapping."""
    print("\n" + "="*70)
    print("  COMPLETE IMPORT - ALL EXCEL FIELDS")
    print("="*70)
    print(f"  File: {excel_file}")
    print(f"  Project: {PROJECT_KEY}")
    print(f"  Mode: {'DRY RUN' if DRY_RUN else 'LIVE'}")
    print("="*70)
    print()

    # Read Excel
    df = pd.read_excel(excel_file)
    print(f"[OK] Loaded {len(df)} rows")
    print(f"Columns: {', '.join(df.columns.tolist())}")
    print()

    # Connect to Jira
    if not DRY_RUN:
        jira = JiraClient()
        print(f"[OK] Connected to Jira: {jira.base_url}")
        print()
    else:
        jira = None
        print("[WARN] DRY RUN mode")
        print()

    # Process rows
    created = 0
    failed = 0
    skipped = 0

    for idx, row in df.iterrows():
        row_num = idx + 2

        # Check required fields
        summary = row.get("Summary")
        if not summary or pd.isna(summary):
            print(f"[SKIP] Row {row_num}: No summary")
            skipped += 1
            continue

        print(f"Row {row_num}: {str(summary)[:60]}")

        # Show what will be imported
        fields_info = []
        if pd.notna(row.get("Component/s")):
            fields_info.append(f"Component: {row['Component/s']}")
        if pd.notna(row.get("Team")):
            fields_info.append(f"Team: {row['Team']}")
        if pd.notna(row.get("Assignee")):
            assignee_short = str(row['Assignee']).split(" - ")[0]
            fields_info.append(f"Assignee: {assignee_short}")
        if pd.notna(row.get("Key")):
            fields_info.append(f"Original: {row['Key']}")

        if fields_info:
            print(f"  {' | '.join(fields_info)}")

        if DRY_RUN:
            print(f"  [OK] [DRY RUN] Would create with complete fields")
            created += 1
        else:
            try:
                issue_key = create_ticket_complete(jira, row, row_num)
                print(f"  [OK] Created: {issue_key}")
                print(f"  URL: {jira.base_url}/browse/{issue_key}")
                created += 1
            except Exception as e:
                print(f"  [ERROR] {str(e)[:80]}")
                failed += 1

        print()

    # Summary
    print("="*70)
    print("  IMPORT SUMMARY")
    print("="*70)
    print(f"  Total rows  : {len(df)}")
    print(f"  [OK] Created   : {created}")
    print(f"  [ERROR] Failed : {failed}")
    print(f"  [SKIP] Skipped : {skipped}")
    print("="*70)
    print()

    if created > 0:
        print("IMPORTED FIELDS:")
        print("  - Summary, Type, Priority -> Jira fields")
        print("  - Component/s -> Component")
        print("  - Team, Use cases, Assignee, Reporter -> Labels")
        print("  - Original Key -> Label")
        print("  - Excel Status -> Label")
        print("  - ALL other fields -> Rich description table")
        print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python import_complete.py <excel_file>")
        print('Example: python import_complete.py "Capas test.xlsx"')
        sys.exit(1)

    excel_file = sys.argv[1]
    if not os.path.exists(excel_file):
        print(f"[ERROR] File not found: {excel_file}")
        sys.exit(1)

    import_complete(excel_file)


if __name__ == "__main__":
    main()
