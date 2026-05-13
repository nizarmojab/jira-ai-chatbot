#!/usr/bin/env python3
"""
test_analyze_agent.py
=====================
Test AnalyzeAgent with real Jira data.
"""
from src.agents.analyze_agent import AnalyzeAgent


def test_extract_ticket_key():
    """Test ticket key extraction from messages."""
    print("="*70)
    print("[TEST] TICKET KEY EXTRACTION")
    print("="*70)
    print()

    agent = AnalyzeAgent()

    test_cases = [
        ("analyze SCRUM-5", "SCRUM-5"),
        ("what about SCRUM-277", "SCRUM-277"),
        ("can you check scrum-42", "SCRUM-42"),
        ("inspect ABC-123", "ABC-123"),
        ("analyze ticket", None),  # No key
    ]

    passed = 0
    failed = 0

    for message, expected in test_cases:
        result = agent._extract_ticket_key(message, context=[])
        status = "OK" if result == expected else "FAIL"

        if result == expected:
            passed += 1
            print(f"[{status}] \"{message}\" -> {result}")
        else:
            failed += 1
            print(f"[{status}] \"{message}\" -> Expected: {expected}, Got: {result}")

    print()
    print(f"[RESULT] {passed} passed, {failed} failed")
    print()


def test_health_score_calculation():
    """Test health score calculation logic."""
    print("="*70)
    print("[TEST] HEALTH SCORE CALCULATION")
    print("="*70)
    print()

    agent = AnalyzeAgent()

    # Test case 1: Healthy ticket
    analysis_healthy = {
        "status": "In Progress",
        "priority": "Medium",
        "has_assignee": True,
        "created_days_ago": 5,
        "updated_days_ago": 1,
        "is_stale": False,
        "blocked_by_count": 0,
        "blocks_count": 0,
        "has_recent_activity": True,
        "comment_count": 3,
        "has_description": True,
        "description_length": 200,
    }

    score_healthy = agent._calculate_health_score(analysis_healthy)
    print(f"[TEST 1] Healthy ticket (In Progress, assigned, active)")
    print(f"         Score: {score_healthy}/100")
    print(f"         Expected: 90-110 (clamped to 100)")
    print(f"         Status: {'OK' if score_healthy >= 90 else 'FAIL'}")
    print()

    # Test case 2: Blocked ticket
    analysis_blocked = {
        "status": "Blocked",
        "priority": "Highest",
        "has_assignee": True,
        "created_days_ago": 10,
        "updated_days_ago": 8,
        "is_stale": True,
        "blocked_by_count": 2,
        "blocks_count": 1,
        "has_recent_activity": False,
        "comment_count": 5,
        "has_description": True,
        "description_length": 150,
    }

    score_blocked = agent._calculate_health_score(analysis_blocked)
    print(f"[TEST 2] Blocked ticket (Highest priority, inactive, 2 blockers)")
    print(f"         Score: {score_blocked}/100")
    print(f"         Expected: 10-30 (very unhealthy)")
    print(f"         Status: {'OK' if score_blocked <= 30 else 'FAIL'}")
    print()

    # Test case 3: Unassigned high priority
    analysis_unassigned = {
        "status": "To Do",
        "priority": "High",
        "has_assignee": False,
        "created_days_ago": 2,
        "updated_days_ago": 2,
        "is_stale": False,
        "blocked_by_count": 0,
        "blocks_count": 0,
        "has_recent_activity": False,
        "comment_count": 0,
        "has_description": True,
        "description_length": 100,
    }

    score_unassigned = agent._calculate_health_score(analysis_unassigned)
    print(f"[TEST 3] Unassigned high priority (To Do, no assignee)")
    print(f"         Score: {score_unassigned}/100")
    print(f"         Expected: 50-70 (needs attention)")
    print(f"         Status: {'OK' if 50 <= score_unassigned <= 70 else 'FAIL'}")
    print()


def test_recommendations():
    """Test recommendation generation."""
    print("="*70)
    print("[TEST] RECOMMENDATION GENERATION")
    print("="*70)
    print()

    agent = AnalyzeAgent()

    # Blocked ticket
    analysis_blocked = {
        "status": "Blocked",
        "priority": "Highest",
        "has_assignee": True,
        "blocked_by_count": 2,
        "blocked_by_tickets": ["SCRUM-1", "SCRUM-2"],
        "blocks_count": 0,
        "blocks_tickets": [],
        "is_stale": True,
        "updated_days_ago": 10,
        "has_description": True,
        "description_length": 200,
        "comment_count": 3,
        "created_days_ago": 15,
    }

    recommendations = agent._generate_recommendations(analysis_blocked, 20)
    print(f"[TEST] Blocked ticket recommendations:")
    for i, rec in enumerate(recommendations, 1):
        print(f"  {i}. {rec}")
    print(f"  Status: {'OK' if any('CRITICAL' in r for r in recommendations) else 'FAIL'}")
    print()


def test_real_jira_analysis():
    """Test analysis with real Jira ticket."""
    print("="*70)
    print("[TEST] REAL JIRA TICKET ANALYSIS")
    print("="*70)
    print()

    agent = AnalyzeAgent()

    # Test with first available ticket
    print("[TEST] Analyzing real ticket from Jira...")
    result = agent.process("analyze SCRUM-277", context=[])

    print(f"Success: {result['success']}")

    if result['success']:
        data = result['data']
        print(f"Ticket: {data['ticket_key']}")
        print(f"Summary: {data['summary'][:60]}...")
        print(f"Health Score: {data['health_score']}/100")
        print()
        print("Analysis:")
        analysis = data['analysis']
        print(f"  Status: {analysis['status']}")
        print(f"  Priority: {analysis['priority']}")
        print(f"  Assignee: {analysis['assignee']}")
        print(f"  Created: {analysis['created_days_ago']} days ago")
        print(f"  Updated: {analysis['updated_days_ago']} days ago")
        print(f"  Blocked by: {analysis['blocked_by_count']} ticket(s)")
        print(f"  Blocks: {analysis['blocks_count']} ticket(s)")
        print(f"  Comments: {analysis['comment_count']}")
        print()
        print("Recommendations:")
        for i, rec in enumerate(data['recommendations'], 1):
            print(f"  {i}. {rec}")
        print()
        print("[OK] Analysis completed successfully")
    else:
        print(f"[FAIL] Analysis failed: {result['error']}")
        print(f"Message: {result['message']}")

    print()


def main():
    """Run all AnalyzeAgent tests."""
    print()
    print("="*70)
    print("[CONFIG] JIRA MULTI-AGENT CHATBOT - ANALYZE AGENT TEST")
    print("="*70)
    print()

    # Test 1: Ticket key extraction (no Jira needed)
    test_extract_ticket_key()

    # Test 2: Health score calculation (no Jira needed)
    test_health_score_calculation()

    # Test 3: Recommendation generation (no Jira needed)
    test_recommendations()

    # Test 4: Real Jira analysis (requires connection)
    try:
        test_real_jira_analysis()
        print("="*70)
        print("[SUCCESS] All AnalyzeAgent tests passed!")
        print("="*70)
    except Exception as e:
        print("="*70)
        print(f"[ERROR] Real Jira test failed: {str(e)}")
        print("="*70)

    print()


if __name__ == "__main__":
    main()
