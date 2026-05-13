#!/usr/bin/env python3
"""
base_test_agent.py
==================
Abstract base class for agent-specific test runners.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseTestAgent(ABC):
    """
    Base class for test agents.

    Each concrete test agent runs a set of scenarios against one target agent
    and returns a structured report.
    """

    def __init__(self, name: str, target_agent_name: str):
        self.name = name
        self.target_agent_name = target_agent_name

    @abstractmethod
    def run(self) -> Dict[str, Any]:
        """
        Run the full test suite for a target agent.
        """
        raise NotImplementedError

    def _build_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build a consistent report payload from test case results.
        """
        passed = sum(1 for result in results if result["success"])
        failed = len(results) - passed

        return {
            "test_agent": self.name,
            "agent_tested": self.target_agent_name,
            "success": failed == 0,
            "passed": passed,
            "failed": failed,
            "results": results,
        }
