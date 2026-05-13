#!/usr/bin/env python3
"""
run_analyze_tests.py
====================
Run AnalyzeAgent unit tests.
"""
from src.test_agents.analyze_test_agent import AnalyzeTestAgent


def main():
    print()
    print("="*70)
    print("[CONFIG] ANALYZE AGENT - UNIT TESTS")
    print("="*70)
    print()

    # Run tests
    agent = AnalyzeTestAgent()
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
