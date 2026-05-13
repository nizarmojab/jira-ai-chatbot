#!/usr/bin/env python3
"""
test_test_orchestrator.py
=========================
Manual runner for the test-agent orchestration layer.
"""
from src.test_agents import SearchTestAgent, TestOrchestrator


def print_report(report):
    print(f"[AGENT] {report['agent_tested']} via {report['test_agent']}")
    print(f"  Success: {report['success']}")
    print(f"  Passed: {report['passed']}")
    print(f"  Failed: {report['failed']}")
    for result in report["results"]:
        status = "OK" if result["success"] else "FAIL"
        print(f"  [{status}] {result['name']}")
        print(f"       Details: {result['details']}")
    print()


def main():
    print("=" * 70)
    print("[TEST AGENTS] SEARCH TEST AGENT")
    print("=" * 70)
    print()

    search_report = SearchTestAgent().run()
    print_report(search_report)

    print("=" * 70)
    print("[TEST AGENTS] ORCHESTRATED RUN")
    print("=" * 70)
    print()

    full_report = TestOrchestrator().run_all()
    print(f"Success: {full_report['success']}")
    print(f"Total test agents: {full_report['total_test_agents']}")
    print(f"Passed: {full_report['passed']}")
    print(f"Failed: {full_report['failed']}")
    print()

    for report in full_report["reports"]:
        print_report(report)


if __name__ == "__main__":
    main()
