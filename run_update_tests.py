#!/usr/bin/env python3
"""
run_update_tests.py
===================
Run UpdateAgent unit tests.
"""
from src.test_agents.update_test_agent import UpdateTestAgent


def main():
    print()
    print("="*70)
    print("[CONFIG] UPDATE AGENT - UNIT TESTS")
    print("="*70)
    print()

    # Run tests
    agent = UpdateTestAgent()
    result = agent.run()

    # Display results
    print(f"Test Agent: {result['test_agent']}")
    print(f"Target: {result['agent_tested']}")
    print(f"Success: {result['success']}")
    print(f"Results: {result['passed']}/{result['passed']+result['failed']} passed")
    print()

    print("Details:")
    for r in result['results']:
        status = 'OK' if r['success'] else 'FAIL'
        print(f"  [{status}] {r['name']}")

        # Show more details for specific tests
        if r['success'] and 'details' in r:
            details = r['details']

            # Show before/after for update tests
            if 'new_status' in details:
                print(f"       → Status changed to: {details['new_status']}")

            if 'assignee_removed' in details and details['assignee_removed']:
                print(f"       → Assignee removed (unassigned)")

            if 'comment_added' in details and details['comment_added']:
                print(f"       → Comment added (total: {details.get('comment_count', 0)})")

        # Show errors
        if not r['success']:
            print(f"       Details: {r['details']}")

    print()
    print("="*70)
    if result['success']:
        print("[SUCCESS] All tests passed!")
    else:
        print(f"[FAILED] {result['failed']} test(s) failed")
    print("="*70)
    print()


if __name__ == "__main__":
    main()
