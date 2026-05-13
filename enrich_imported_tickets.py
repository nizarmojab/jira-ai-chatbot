#!/usr/bin/env python3
"""
enrich_imported_tickets.py
==========================
Enrich already-imported tickets with missing information from Excel.

Usage:
    python enrich_imported_tickets.py "Capas test.xlsx" SCRUM-312 SCRUM-443
    DRY_RUN=true python enrich_imported_tickets.py "Capas test.xlsx" SCRUM-312 SCRUM-443
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


def parse_ticket_number(ticket_key: str) -> int:
    """Extract ticket number from key (SCRUM-312 -> 312)."""
    return int(ticket_key.split("-")[1])


def enrich_tickets(excel_file: str, start_ticket: str, end_ticket: str):
    """Enrich tickets with Excel data."""
    print("\n" + "="*70)
    print("  ENRICH IMPORTED TICKETS")
    print("="*70)
    print(f"  Excel: {excel_file}")
    print(f"  Range: {start_ticket} to {end_ticket}")
    print(f"  Mode: {'DRY RUN' if DRY_RUN else 'LIVE'}")
    print("="*70)
    print()

    # Read Excel
    df = pd.read_excel(excel_file)
    print(f"[OK] Loaded {len(df)} rows from Excel")
    print()

    # Connect to Jira
    if not DRY_RUN:
        jira = JiraClient()
        print(f"[OK] Connected to Jira: {jira.base_url}")
        print()
    else:
        jira = None

    # Parse range
    start_num = parse_ticket_number(start_ticket)
    end_num = parse_ticket_number(end_ticket)
    total = end_num - start_num + 1

    print(f"Will enrich {total} tickets...")
    print()

    # Process each ticket
    updated_count = 0
    failed_count = 0

    for idx in range(total):
        ticket_num = start_num + idx
        ticket_key = f"{PROJECT_KEY}-{ticket_num}"
        excel_row_idx = idx

        if excel_row_idx >= len(df):
            print(f"[SKIP] {ticket_key}: No Excel data")
            continue

        row = df.iloc[excel_row_idx]

        # Extract enrichment data
        enrichments = {}

        # Component
        component = row.get("Component/s")
        if pd.notna(component) and str(component).strip():
            enrichments["component"] = str(component).strip()

        # Labels from Team and Use cases
        labels = []
        team = row.get("Team")
        if pd.notna(team) and str(team).strip():
            labels.append(f"team:{str(team).strip().replace(' ', '_')}")

        use_cases = row.get("Use cases")
        if pd.notna(use_cases) and str(use_cases).strip():
            labels.append(f"usecase:{str(use_cases).strip().replace(' ', '_')}")

        if labels:
            enrichments["labels"] = labels

        # Skip if nothing to enrich
        if not enrichments:
            print(f"[SKIP] {ticket_key}: No enrichment data")
            continue

        # Show what will be updated
        print(f"{ticket_key}: {row['Summary'][:50]}")
        if "component" in enrichments:
            print(f"  + Component: {enrichments['component']}")
        if "labels" in enrichments:
            print(f"  + Labels: {', '.join(enrichments['labels'])}")

        if DRY_RUN:
            print(f"  [OK] [DRY RUN] Would enrich")
            updated_count += 1
        else:
            # Update ticket
            try:
                fields = {}

                if "component" in enrichments:
                    fields["components"] = [{"name": enrichments["component"]}]

                if "labels" in enrichments:
                    fields["labels"] = enrichments["labels"]

                if fields:
                    jira.update_issue(ticket_key, fields)
                    print(f"  [OK] Enriched")
                    updated_count += 1
            except Exception as e:
                print(f"  [ERROR] Failed: {str(e)[:80]}")
                failed_count += 1

        print()

    # Summary
    print("="*70)
    print("  ENRICHMENT SUMMARY")
    print("="*70)
    print(f"  Total tickets : {total}")
    print(f"  [OK] Updated  : {updated_count}")
    print(f"  [ERROR] Failed: {failed_count}")
    print(f"  [SKIP] Skipped: {total - updated_count - failed_count}")
    print("="*70)
    print()


def main():
    if len(sys.argv) < 4:
        print("Usage: python enrich_imported_tickets.py <excel> <start> <end>")
        print('Example: python enrich_imported_tickets.py "Capas test.xlsx" SCRUM-312 SCRUM-443')
        sys.exit(1)

    excel_file = sys.argv[1]
    start_ticket = sys.argv[2]
    end_ticket = sys.argv[3]

    if not os.path.exists(excel_file):
        print(f"[ERROR] File not found: {excel_file}")
        sys.exit(1)

    enrich_tickets(excel_file, start_ticket, end_ticket)


if __name__ == "__main__":
    main()
