#!/usr/bin/env python3
"""
test_orchestrator.py
====================
Simple orchestrator for agent-specific test runners.
"""
from __future__ import annotations

from typing import Any, Dict, List

from src.test_agents.search_test_agent import SearchTestAgent


class TestOrchestrator:
    """
    Runs all registered test agents and aggregates their reports.
    """

    def __init__(self):
        self.test_agents = [
            SearchTestAgent(),
        ]

    def run_all(self) -> Dict[str, Any]:
        reports: List[Dict[str, Any]] = [agent.run() for agent in self.test_agents]
        passed = sum(report["passed"] for report in reports)
        failed = sum(report["failed"] for report in reports)

        return {
            "success": failed == 0,
            "total_test_agents": len(reports),
            "passed": passed,
            "failed": failed,
            "reports": reports,
        }
