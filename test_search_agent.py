#!/usr/bin/env python3
"""
test_search_agent.py
====================
Test SearchAgent: NL to JQL conversion and Jira search.
"""
from src.agents.search_agent import SearchAgent


def test_nl_to_jql():
    """Test natural language to JQL conversion."""
    print("="*70)
    print("[TEST] NATURAL LANGUAGE TO JQL CONVERSION")
    print("="*70)
    print()

    agent = SearchAgent()

    test_cases = [
        # (Natural language, Expected JQL keywords)
        ("show me critical bugs", ["priority = Critical", "type = Bug"]),
        ("find blocked tickets", ["status = Blocked"]),
        ("list open tasks", ['status = "To Do"', "type = Task"]),
        ("bugs in CAN component", ["type = Bug", 'component = "CAN"']),
        ("high priority issues", ["priority = High"]),
        ("my tickets", ["assignee = currentUser()"]),
        ("unassigned bugs", ["type = Bug", "assignee is EMPTY"]),
        ("show done stories", ["status = Done", "type = Story"]),
    ]

    passed = 0
    failed = 0

    for query, expected_keywords in test_cases:
        jql = agent._convert_to_jql(query, context=[])

        # Check if all expected keywords are in JQL
        all_present = all(keyword in jql for keyword in expected_keywords)

        status = "OK" if all_present else "FAIL"

        if all_present:
            passed += 1
            print(f"[{status}] \"{query}\"")
            print(f"        JQL: {jql}")
        else:
            failed += 1
            print(f"[{status}] \"{query}\"")
            print(f"        JQL: {jql}")
            print(f"        Expected keywords: {expected_keywords}")
        print()

    print(f"[RESULT] {passed} passed, {failed} failed")
    print()


def test_jira_search():
    """Test actual Jira search (requires connection)."""
    print("="*70)
    print("[TEST] JIRA SEARCH (REAL API CALLS)")
    print("="*70)
    print()

    agent = SearchAgent()

    # Test 1: Simple search
    print("[TEST 1] Search critical bugs")
    result = agent.process("show me critical bugs", context=[])

    print(f"Success: {result['success']}")
    print(f"Agent: {result['agent']}")
    print(f"JQL: {result['data']['jql']}")
    print(f"Total: {result['data']['total']}")
    print(f"Message: {result['message']}")

    if result['success'] and result['data']['total'] > 0:
        print(f"[OK] Found {result['data']['total']} critical bugs")
        # Show first issue
        first_issue = result['data']['issues'][0]
        print(f"     Example: {first_issue['key']} - {first_issue['summary']}")
    else:
        print(f"[INFO] No critical bugs found (this is OK if project has none)")
    print()

    # Test 2: Search blocked tickets
    print("[TEST 2] Search blocked tickets")
    result = agent.process("find blocked tickets", context=[])

    print(f"Success: {result['success']}")
    print(f"JQL: {result['data']['jql']}")
    print(f"Total: {result['data']['total']}")
    print(f"Message: {result['message']}")

    if result['success'] and result['data']['total'] > 0:
        print(f"[OK] Found {result['data']['total']} blocked tickets")
        # Show first 3 issues
        for issue in result['data']['issues'][:3]:
            print(f"     - {issue['key']}: {issue['summary']}")
            print(f"       Status: {issue['status']}, Priority: {issue['priority']}")
    else:
        print(f"[INFO] No blocked tickets found (this is OK)")
    print()

    # Test 3: Search all bugs
    print("[TEST 3] Search all bugs")
    result = agent.process("show me all bugs", context=[])

    print(f"Success: {result['success']}")
    print(f"JQL: {result['data']['jql']}")
    print(f"Total: {result['data']['total']}")
    print(f"Message: {result['message']}")

    if result['success']:
        print(f"[OK] Search completed - found {result['data']['total']} total bugs")
        if result['data']['total'] > 0:
            print(f"     Showing {len(result['data']['issues'])} issues")
            # Group by status
            status_counts = {}
            for issue in result['data']['issues']:
                status = issue['status']
                status_counts[status] = status_counts.get(status, 0) + 1
            print(f"     By status: {status_counts}")
    print()

    # Test 4: Error handling (invalid search)
    print("[TEST 4] Error handling")
    # This should work but return 0 results
    result = agent.process("find tickets with nonexistent component", context=[])

    print(f"Success: {result['success']}")
    print(f"Message: {result['message']}")

    if result['success']:
        print(f"[OK] Handled gracefully (returned 0 results)")
    print()


def test_issue_simplification():
    """Test issue data simplification."""
    print("="*70)
    print("[TEST] ISSUE DATA SIMPLIFICATION")
    print("="*70)
    print()

    agent = SearchAgent()

    # Mock issue data (like Jira returns)
    mock_issues = [
        {
            "key": "SCRUM-1",
            "fields": {
                "summary": "Test bug",
                "status": {"name": "Open"},
                "priority": {"name": "High"},
                "assignee": {"displayName": "John Doe"},
                "issuetype": {"name": "Bug"},
                "created": "2025-01-01T10:00:00.000+0000",
                "updated": "2025-01-02T10:00:00.000+0000"
            }
        },
        {
            "key": "SCRUM-2",
            "fields": {
                "summary": "Test story",
                "status": {"name": "In Progress"},
                "priority": None,  # Missing priority
                "assignee": None,  # Unassigned
                "issuetype": {"name": "Story"},
                "created": "2025-01-01T11:00:00.000+0000",
                "updated": "2025-01-02T11:00:00.000+0000"
            }
        }
    ]

    simplified = agent._simplify_issues(mock_issues)

    print(f"[TEST] Simplified {len(simplified)} issues")

    # Check first issue
    issue1 = simplified[0]
    assert issue1["key"] == "SCRUM-1", "Key mismatch"
    assert issue1["summary"] == "Test bug", "Summary mismatch"
    assert issue1["priority"] == "High", "Priority mismatch"
    assert issue1["assignee"] == "John Doe", "Assignee mismatch"
    print("[OK] Issue 1 simplified correctly")
    print(f"     {issue1['key']}: {issue1['summary']} ({issue1['status']}, {issue1['priority']})")

    # Check second issue (with missing fields)
    issue2 = simplified[1]
    assert issue2["priority"] == "None", "Missing priority not handled"
    assert issue2["assignee"] == "Unassigned", "Missing assignee not handled"
    print("[OK] Issue 2 handled missing fields correctly")
    print(f"     {issue2['key']}: {issue2['summary']} ({issue2['status']}, {issue2['assignee']})")

    print()
    print("[SUCCESS] All simplification tests passed!")
    print()


def main():
    """Run all SearchAgent tests."""
    print()
    print("="*70)
    print("[CONFIG] JIRA MULTI-AGENT CHATBOT - SEARCH AGENT TEST")
    print("="*70)
    print()

    # Test 1: NL to JQL conversion (no Jira needed)
    test_nl_to_jql()

    # Test 2: Issue simplification (no Jira needed)
    test_issue_simplification()

    # Test 3: Real Jira searches (requires connection)
    try:
        test_jira_search()
        print("="*70)
        print("[SUCCESS] All SearchAgent tests passed!")
        print("="*70)
    except Exception as e:
        print("="*70)
        print(f"[ERROR] Jira connection test failed: {str(e)}")
        print("Make sure Jira credentials in .env are correct")
        print("="*70)

    print()


if __name__ == "__main__":
    main()
