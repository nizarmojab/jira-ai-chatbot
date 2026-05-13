#!/usr/bin/env python3
"""
analyze_test_agent.py
=====================
Dedicated test agent for AnalyzeAgent.
"""
from __future__ import annotations

from typing import Any, Dict, List
from datetime import datetime, timezone, timedelta

from src.agents.analyze_agent import AnalyzeAgent
from src.jira_client import JiraError
from src.test_agents.base_test_agent import BaseTestAgent


class FakeJiraClient:
    """
    Minimal Jira-compatible fake for testing AnalyzeAgent.
    """

    def __init__(self, project_key: str = "SCRUM"):
        self.project_key = project_key
        self.base_url = "https://test.atlassian.net"
        self.issues: Dict[str, Dict[str, Any]] = {}
        self.links: Dict[str, List[Dict[str, Any]]] = {}
        self.comments: Dict[str, List[Dict[str, Any]]] = {}
        self.worklogs: Dict[str, List[Dict[str, Any]]] = {}
        self.errors: Dict[str, Exception] = {}

    def register_issue(
        self,
        key: str,
        summary: str,
        status: str = "To Do",
        priority: str = "Medium",
        assignee: str | None = "Test User",
        created_days_ago: int = 5,
        updated_days_ago: int = 2,
        description: str = "Test description with enough content",
        issue_type: str = "Bug"
    ):
        """Register a fake issue."""
        now = datetime.now(timezone.utc)
        created = (now - timedelta(days=created_days_ago)).isoformat()
        updated = (now - timedelta(days=updated_days_ago)).isoformat()

        self.issues[key] = {
            "key": key,
            "fields": {
                "summary": summary,
                "status": {"name": status},
                "priority": {"name": priority} if priority else None,
                "assignee": {"displayName": assignee} if assignee else None,
                "issuetype": {"name": issue_type},
                "created": created,
                "updated": updated,
                "description": description,
            }
        }

    def register_links(self, key: str, links: List[Dict[str, Any]]):
        """Register issue links (blockers, etc.)."""
        self.links[key] = links

    def register_comments(self, key: str, comments: List[Dict[str, Any]]):
        """Register comments for an issue."""
        self.comments[key] = comments

    def register_worklogs(self, key: str, worklogs: List[Dict[str, Any]]):
        """Register work logs for an issue."""
        self.worklogs[key] = worklogs

    def register_error(self, key: str, error: Exception):
        """Register an error for an issue."""
        self.errors[key] = error

    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        if issue_key in self.errors:
            raise self.errors[issue_key]
        return self.issues.get(issue_key, {})

    def get_issue_links(self, issue_key: str) -> List[Dict[str, Any]]:
        return self.links.get(issue_key, [])

    def get_comments(self, issue_key: str) -> List[Dict[str, Any]]:
        return self.comments.get(issue_key, [])

    def get_worklogs(self, issue_key: str) -> List[Dict[str, Any]]:
        return self.worklogs.get(issue_key, [])


class AnalyzeTestAgent(BaseTestAgent):
    """
    Test agent for validating AnalyzeAgent behavior.
    """

    def __init__(self):
        super().__init__("AnalyzeTestAgent", "AnalyzeAgent")

    def run(self) -> Dict[str, Any]:
        """Run test suite for AnalyzeAgent."""
        results = [
            self._test_extract_single_ticket_key(),
            self._test_extract_multiple_ticket_keys(),
            self._test_health_score_healthy_ticket(),
            self._test_health_score_blocked_ticket(),
            self._test_health_score_stale_high_priority(),
            self._test_single_ticket_analysis(),
            self._test_multiple_ticket_analysis(),
            self._test_missing_ticket_key(),
            self._test_jira_error_handling(),
        ]
        return self._build_summary(results)

    def _test_extract_single_ticket_key(self) -> Dict[str, Any]:
        """Test extraction of single ticket key."""
        jira_client = FakeJiraClient()
        agent = AnalyzeAgent(jira_client=jira_client)

        key = agent._extract_ticket_key("analyze SCRUM-42", context=[])

        return {
            "name": "extract_single_ticket_key",
            "success": key == "SCRUM-42",
            "details": {"expected": "SCRUM-42", "actual": key}
        }

    def _test_extract_multiple_ticket_keys(self) -> Dict[str, Any]:
        """Test extraction of multiple ticket keys."""
        jira_client = FakeJiraClient()
        agent = AnalyzeAgent(jira_client=jira_client)

        keys = agent._extract_ticket_keys("analyze SCRUM-42, SCRUM-100, ABC-5", context=[])

        expected = ["SCRUM-42", "SCRUM-100", "ABC-5"]
        return {
            "name": "extract_multiple_ticket_keys",
            "success": keys == expected,
            "details": {"expected": expected, "actual": keys}
        }

    def _test_health_score_healthy_ticket(self) -> Dict[str, Any]:
        """Test health score for a healthy ticket."""
        jira_client = FakeJiraClient()
        agent = AnalyzeAgent(jira_client=jira_client)

        # Healthy ticket: In Progress, assigned, recent activity
        analysis = {
            "status": "In Progress",
            "priority": "Medium",
            "has_assignee": True,
            "created_days_ago": 3,
            "updated_days_ago": 1,
            "is_stale": False,
            "blocked_by_count": 0,
            "blocks_count": 0,
            "has_recent_activity": True,
            "comment_count": 5,
            "has_description": True,
            "description_length": 200,
        }

        score = agent._calculate_health_score(analysis)
        expected_range = (90, 110)  # Will be clamped to 100

        return {
            "name": "health_score_healthy_ticket",
            "success": expected_range[0] <= score <= 100,
            "details": {
                "score": score,
                "expected_range": expected_range,
                "analysis": "Healthy ticket should score 90+"
            }
        }

    def _test_health_score_blocked_ticket(self) -> Dict[str, Any]:
        """Test health score for a blocked ticket."""
        jira_client = FakeJiraClient()
        agent = AnalyzeAgent(jira_client=jira_client)

        # Blocked ticket: Blocked status, high priority, multiple blockers
        analysis = {
            "status": "Blocked",
            "priority": "Highest",
            "has_assignee": True,
            "created_days_ago": 10,
            "updated_days_ago": 8,
            "is_stale": True,
            "blocked_by_count": 2,
            "blocks_count": 0,
            "has_recent_activity": False,
            "comment_count": 3,
            "has_description": True,
            "description_length": 100,
        }

        score = agent._calculate_health_score(analysis)
        expected_max = 30  # Should be very low

        return {
            "name": "health_score_blocked_ticket",
            "success": score <= expected_max,
            "details": {
                "score": score,
                "expected_max": expected_max,
                "analysis": "Blocked + Highest priority + stale should score very low"
            }
        }

    def _test_health_score_stale_high_priority(self) -> Dict[str, Any]:
        """Test health score for stale high-priority ticket."""
        jira_client = FakeJiraClient()
        agent = AnalyzeAgent(jira_client=jira_client)

        # Stale high priority: High priority but inactive
        analysis = {
            "status": "To Do",
            "priority": "High",
            "has_assignee": False,
            "created_days_ago": 15,
            "updated_days_ago": 10,
            "is_stale": True,
            "blocked_by_count": 0,
            "blocks_count": 0,
            "has_recent_activity": False,
            "comment_count": 0,
            "has_description": True,
            "description_length": 50,
        }

        score = agent._calculate_health_score(analysis)
        expected_range = (25, 40)  # Should be low (many penalties)

        return {
            "name": "health_score_stale_high_priority",
            "success": expected_range[0] <= score <= expected_range[1],
            "details": {
                "score": score,
                "expected_range": expected_range,
                "analysis": "High priority + stale + unassigned = medium-low score"
            }
        }

    def _test_single_ticket_analysis(self) -> Dict[str, Any]:
        """Test full analysis of a single ticket."""
        jira_client = FakeJiraClient()
        jira_client.register_issue(
            "SCRUM-100",
            "Test bug with moderate issues",
            status="In Progress",
            priority="High",
            assignee="Test User",
            created_days_ago=10,
            updated_days_ago=8
        )
        jira_client.register_comments("SCRUM-100", [
            {"author": {"displayName": "Test User"}, "created": datetime.now(timezone.utc).isoformat()}
        ])
        jira_client.register_worklogs("SCRUM-100", [])

        agent = AnalyzeAgent(jira_client=jira_client)
        result = agent.process("analyze SCRUM-100", context=[])

        return {
            "name": "single_ticket_analysis",
            "success": (
                result["success"] and
                result["data"]["ticket_key"] == "SCRUM-100" and
                0 <= result["data"]["health_score"] <= 100
            ),
            "details": {
                "success": result["success"],
                "health_score": result["data"]["health_score"] if result["success"] else None,
                "message": result["message"][:100]
            }
        }

    def _test_multiple_ticket_analysis(self) -> Dict[str, Any]:
        """Test analysis of multiple tickets."""
        jira_client = FakeJiraClient()
        for i in [1, 2, 3]:
            jira_client.register_issue(
                f"SCRUM-{i}",
                f"Test ticket {i}",
                status="To Do",
                priority="Medium",
                created_days_ago=5,
                updated_days_ago=2
            )
            jira_client.register_comments(f"SCRUM-{i}", [])
            jira_client.register_worklogs(f"SCRUM-{i}", [])

        agent = AnalyzeAgent(jira_client=jira_client)
        result = agent.process("analyze SCRUM-1, SCRUM-2, SCRUM-3", context=[])

        return {
            "name": "multiple_ticket_analysis",
            "success": (
                result["success"] and
                result["action"] == "analyze_multiple" and
                result["data"]["successful"] == 3
            ),
            "details": {
                "success": result["success"],
                "total_analyzed": result["data"]["successful"] if result["success"] else None,
                "message_preview": result["message"][:150]
            }
        }

    def _test_missing_ticket_key(self) -> Dict[str, Any]:
        """Test handling of missing ticket key."""
        jira_client = FakeJiraClient()
        agent = AnalyzeAgent(jira_client=jira_client)

        result = agent.process("analyze this ticket please", context=[])

        return {
            "name": "missing_ticket_key",
            "success": not result["success"] and "Missing ticket key" in result["error"],
            "details": {
                "success": result["success"],
                "error": result["error"]
            }
        }

    def _test_jira_error_handling(self) -> Dict[str, Any]:
        """Test handling of Jira API errors."""
        jira_client = FakeJiraClient()
        jira_client.register_error("SCRUM-999", JiraError("Ticket not found"))

        agent = AnalyzeAgent(jira_client=jira_client)
        result = agent.process("analyze SCRUM-999", context=[])

        return {
            "name": "jira_error_handling",
            "success": not result["success"] and "Ticket not found" in result["error"],
            "details": {
                "success": result["success"],
                "error": result["error"]
            }
        }


if __name__ == "__main__":
    import sys
    import os

    # Add project root to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

    # Run tests
    agent = AnalyzeTestAgent()
    result = agent.run()

    print()
    print("="*70)
    print(f"Test Agent: {result['test_agent']}")
    print(f"Target: {result['agent_tested']}")
    print(f"Success: {result['success']}")
    print(f"Results: {result['passed']}/{result['passed']+result['failed']} passed")
    print("="*70)

    for r in result['results']:
        status = 'OK' if r['success'] else 'FAIL'
        print(f"  [{status}] {r['name']}")

    print("="*70)
    print()
