#!/usr/bin/env python3
"""
reimport_complete.py
====================
Delete existing tickets and reimport with complete fields.

Usage:
    python reimport_complete.py "Capas test.xlsx" SCRUM-312 SCRUM-443
    DRY_RUN=true python reimport_complete.py "Capas test.xlsx" SCRUM-312 SCRUM-443
"""
import os
import sys
import subprocess


def main():
    if len(sys.argv) < 4:
        print("Usage: python reimport_complete.py <excel> <start> <end>")
        print('Example: python reimport_complete.py "Capas test.xlsx" SCRUM-312 SCRUM-443')
        sys.exit(1)

    excel_file = sys.argv[1]
    start_ticket = sys.argv[2]
    end_ticket = sys.argv[3]

    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    print("\n" + "="*70)
    print("  COMPLETE REIMPORT WORKFLOW")
    print("="*70)
    print(f"  Excel: {excel_file}")
    print(f"  Range to delete: {start_ticket} to {end_ticket}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print("="*70)
    print()

    # Check for --yes flag
    auto_confirm = "--yes" in sys.argv or "-y" in sys.argv

    if not dry_run and not auto_confirm:
        print("This will:")
        print("  1. DELETE 132 tickets (SCRUM-312 to SCRUM-443)")
        print("  2. REIMPORT 132 tickets with COMPLETE fields")
        print()
        confirm = input("Are you sure? Type 'yes' to continue: ")
        if confirm.lower() != "yes":
            print("Cancelled.")
            return
    elif not dry_run:
        print("Auto-confirmed with --yes flag")
        print("  1. DELETE 132 tickets (SCRUM-312 to SCRUM-443)")
        print("  2. REIMPORT 132 tickets with COMPLETE fields")
        print()

    # Step 1: Delete
    print("\n" + "="*70)
    print("  STEP 1: DELETING EXISTING TICKETS")
    print("="*70)
    print()

    env = os.environ.copy()
    if dry_run:
        env["DRY_RUN"] = "true"

    delete_cmd = ["python", "delete_tickets.py", start_ticket, end_ticket]
    if auto_confirm:
        delete_cmd.append("--yes")

    result = subprocess.run(delete_cmd, env=env)

    if result.returncode != 0:
        print("\n[ERROR] Deletion failed!")
        return

    # Step 2: Import
    print("\n" + "="*70)
    print("  STEP 2: IMPORTING WITH COMPLETE FIELDS")
    print("="*70)
    print()

    result = subprocess.run(
        ["python", "import_complete.py", excel_file],
        env=env
    )

    if result.returncode != 0:
        print("\n[ERROR] Import failed!")
        return

    # Done
    print("\n" + "="*70)
    print("  REIMPORT COMPLETE!")
    print("="*70)
    print()
    print("All tickets have been reimported with complete field mapping:")
    print("  - Summary, Type, Priority, Component -> Jira fields")
    print("  - Team, Assignee, Reporter, Original Key -> Labels")
    print("  - All other fields -> Rich description table")
    print()


if __name__ == "__main__":
    main()
