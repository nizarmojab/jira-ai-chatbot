#!/usr/bin/env python3
"""
update_test_agent.py
====================
Dedicated test agent for UpdateAgent.
"""
from __future__ import annotations

from typing import Any, Dict, List
from datetime import datetime, timezone

from src.agents.update_agent import UpdateAgent
from src.jira_client import JiraError
from src.test_agents.base_test_agent import BaseTestAgent


class FakeJiraClient:
    """
    Minimal Jira-compatible fake for testing UpdateAgent.
    """

    def __init__(self, project_key: str = "SCRUM"):
        self.project_key = project_key
        self.base_url = "https://test.atlassian.net"
        self.issues: Dict[str, Dict[str, Any]] = {}
        self.comments: Dict[str, List[Dict[str, Any]]] = {}
        self.updates: List[Dict[str, Any]] = []  # Track all updates
        self.errors: Dict[str, Exception] = {}

    def register_issue(
        self,
        key: str,
        summary: str,
        status: str = "To Do",
        priority: str = "Medium",
        assignee: str | None = "Test User",
        description: str = "Test description"
    ):
        """Register a fake issue."""
        self.issues[key] = {
            "key": key,
            "fields": {
                "summary": summary,
                "status": {"name": status},
                "priority": {"name": priority} if priority else None,
                "assignee": {"displayName": assignee, "accountId": "test-123"} if assignee else None,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description}]
                        }
                    ]
                }
            }
        }
        self.comments[key] = []

    def register_error(self, key: str, error: Exception):
        """Register an error for an issue."""
        self.errors[key] = error

    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        if issue_key in self.errors:
            raise self.errors[issue_key]
        if issue_key not in self.issues:
            raise JiraError(f"Issue {issue_key} not found")
        return self.issues[issue_key]

    def update_issue(self, issue_key: str, fields: Dict[str, Any]):
        """Update issue fields."""
        if issue_key not in self.issues:
            raise JiraError(f"Issue {issue_key} not found")

        # Track update
        self.updates.append({
            "issue_key": issue_key,
            "fields": fields,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # Apply update
        for field, value in fields.items():
            if field == "priority":
                self.issues[issue_key]["fields"]["priority"] = value
            elif field == "assignee":
                self.issues[issue_key]["fields"]["assignee"] = value
            elif field == "description":
                self.issues[issue_key]["fields"]["description"] = value

    def add_comment(self, issue_key: str, comment_text: str) -> Dict[str, Any]:
        """Add comment to issue."""
        if issue_key not in self.issues:
            raise JiraError(f"Issue {issue_key} not found")

        comment = {
            "id": f"comment-{len(self.comments[issue_key])+1}",
            "author": {"displayName": "Test User"},
            "body": comment_text,
            "created": datetime.now(timezone.utc).isoformat()
        }
        self.comments[issue_key].append(comment)

        # Track as update
        self.updates.append({
            "issue_key": issue_key,
            "type": "comment",
            "comment": comment_text,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        return comment

    def _request(self, method: str, endpoint: str, params=None, json_data=None):
        """Mock request method for transitions."""
        # Handle transitions endpoint
        if "/transitions" in endpoint:
            issue_key = endpoint.split("/")[4]

            # GET transitions - return available transitions
            if method == "GET":
                current_status = self.issues[issue_key]["fields"]["status"]["name"]

                # Define workflow
                transitions = {
                    "To Do": [
                        {"id": "11", "to": {"name": "In Progress"}},
                        {"id": "21", "to": {"name": "Done"}},
                    ],
                    "In Progress": [
                        {"id": "31", "to": {"name": "To Do"}},
                        {"id": "41", "to": {"name": "Blocked"}},
                        {"id": "51", "to": {"name": "Done"}},
                    ],
                    "Blocked": [
                        {"id": "61", "to": {"name": "In Progress"}},
                        {"id": "71", "to": {"name": "To Do"}},
                    ],
                    "Done": [
                        {"id": "81", "to": {"name": "To Do"}},
                    ]
                }
                return {"transitions": transitions.get(current_status, [])}

            # POST transition - execute it
            elif method == "POST":
                transition_id = json_data["transition"]["id"]

                # Map transition ID to new status
                transition_map = {
                    "11": "In Progress", "21": "Done",
                    "31": "To Do", "41": "Blocked", "51": "Done",
                    "61": "In Progress", "71": "To Do",
                    "81": "To Do"
                }

                new_status = transition_map.get(transition_id)
                if new_status:
                    self.issues[issue_key]["fields"]["status"]["name"] = new_status

                    # Track update
                    self.updates.append({
                        "issue_key": issue_key,
                        "type": "transition",
                        "new_status": new_status,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    return {}
                else:
                    raise JiraError(f"Invalid transition ID: {transition_id}")

        raise NotImplementedError(f"Mock _request not implemented for {method} {endpoint}")


class UpdateTestAgent(BaseTestAgent):
    """
    Test agent for validating UpdateAgent behavior.
    """

    def __init__(self):
        super().__init__("UpdateTestAgent", "UpdateAgent")

    def run(self) -> Dict[str, Any]:
        """Run test suite for UpdateAgent."""
        results = [
            self._test_parse_priority_change(),
            self._test_parse_status_change(),
            self._test_parse_assignee_change(),
            self._test_parse_add_comment(),
            self._test_update_priority(),
            self._test_update_status(),
            self._test_update_assignee_to_me(),
            self._test_update_assignee_to_unassigned(),
            self._test_add_comment(),
            self._test_invalid_priority(),
            self._test_invalid_status_transition(),
            self._test_missing_ticket(),
            self._test_jira_error(),
        ]
        return self._build_summary(results)

    def _test_parse_priority_change(self) -> Dict[str, Any]:
        """Test parsing priority change request."""
        jira_client = FakeJiraClient()
        agent = UpdateAgent(jira_client=jira_client)

        result = agent._parse_update_action("change priority of SCRUM-5 to high", [])

        return {
            "name": "parse_priority_change",
            "success": result == ("SCRUM-5", "priority", "high"),
            "details": {"expected": ("SCRUM-5", "priority", "high"), "actual": result}
        }

    def _test_parse_status_change(self) -> Dict[str, Any]:
        """Test parsing status change request."""
        jira_client = FakeJiraClient()
        agent = UpdateAgent(jira_client=jira_client)

        result = agent._parse_update_action("move SCRUM-10 to in progress", [])

        return {
            "name": "parse_status_change",
            "success": result == ("SCRUM-10", "status", "in progress"),
            "details": {"expected": ("SCRUM-10", "status", "in progress"), "actual": result}
        }

    def _test_parse_assignee_change(self) -> Dict[str, Any]:
        """Test parsing assignee change request."""
        jira_client = FakeJiraClient()
        agent = UpdateAgent(jira_client=jira_client)

        result = agent._parse_update_action("assign SCRUM-42 to me", [])

        return {
            "name": "parse_assignee_change",
            "success": result == ("SCRUM-42", "assignee", "me"),
            "details": {"expected": ("SCRUM-42", "assignee", "me"), "actual": result}
        }

    def _test_parse_add_comment(self) -> Dict[str, Any]:
        """Test parsing add comment request."""
        jira_client = FakeJiraClient()
        agent = UpdateAgent(jira_client=jira_client)

        result = agent._parse_update_action("add comment to SCRUM-1: This is a test comment", [])

        return {
            "name": "parse_add_comment",
            "success": result == ("SCRUM-1", "comment", "This is a test comment"),
            "details": {"expected": ("SCRUM-1", "comment", "This is a test comment"), "actual": result}
        }

    def _test_update_priority(self) -> Dict[str, Any]:
        """Test updating ticket priority."""
        jira_client = FakeJiraClient()
        jira_client.register_issue("SCRUM-100", "Test ticket", priority="Medium")

        agent = UpdateAgent(jira_client=jira_client)
        result = agent.process("change priority of SCRUM-100 to high", [])

        # Check update was tracked
        priority_updated = any(
            u["issue_key"] == "SCRUM-100" and
            u["fields"].get("priority", {}).get("name") == "High"
            for u in jira_client.updates
        )

        return {
            "name": "update_priority",
            "success": result["success"] and priority_updated,
            "details": {
                "result_success": result["success"],
                "priority_updated": priority_updated,
                "message": result["message"][:100]
            }
        }

    def _test_update_status(self) -> Dict[str, Any]:
        """Test updating ticket status via transition."""
        jira_client = FakeJiraClient()
        jira_client.register_issue("SCRUM-200", "Test ticket", status="To Do")

        agent = UpdateAgent(jira_client=jira_client)
        result = agent.process("move SCRUM-200 to in progress", [])

        # Check status was updated
        new_status = jira_client.issues["SCRUM-200"]["fields"]["status"]["name"]

        return {
            "name": "update_status",
            "success": result["success"] and new_status == "In Progress",
            "details": {
                "result_success": result["success"],
                "new_status": new_status,
                "expected": "In Progress",
                "message": result["message"][:100]
            }
        }

    def _test_update_assignee_to_me(self) -> Dict[str, Any]:
        """Test assigning ticket to self."""
        jira_client = FakeJiraClient()
        jira_client.register_issue("SCRUM-300", "Test ticket", assignee="Other User")

        # Set account ID for agent
        agent = UpdateAgent(jira_client=jira_client)
        agent.account_id = "test-me-123"

        result = agent.process("assign SCRUM-300 to me", [])

        return {
            "name": "update_assignee_to_me",
            "success": result["success"],
            "details": {
                "result_success": result["success"],
                "message": result["message"][:100]
            }
        }

    def _test_update_assignee_to_unassigned(self) -> Dict[str, Any]:
        """Test unassigning ticket."""
        jira_client = FakeJiraClient()
        jira_client.register_issue("SCRUM-400", "Test ticket", assignee="Test User")

        agent = UpdateAgent(jira_client=jira_client)
        result = agent.process("assign SCRUM-400 to unassigned", [])

        # Check assignee was removed
        assignee_removed = any(
            u["issue_key"] == "SCRUM-400" and
            u["fields"].get("assignee") is None
            for u in jira_client.updates
        )

        return {
            "name": "update_assignee_to_unassigned",
            "success": result["success"] and assignee_removed,
            "details": {
                "result_success": result["success"],
                "assignee_removed": assignee_removed,
                "message": result["message"][:100]
            }
        }

    def _test_add_comment(self) -> Dict[str, Any]:
        """Test adding comment to ticket."""
        jira_client = FakeJiraClient()
        jira_client.register_issue("SCRUM-500", "Test ticket")

        agent = UpdateAgent(jira_client=jira_client)
        result = agent.process("add comment to SCRUM-500: This is a test comment", [])

        # Check comment was added
        comment_added = len(jira_client.comments.get("SCRUM-500", [])) > 0

        return {
            "name": "add_comment",
            "success": result["success"] and comment_added,
            "details": {
                "result_success": result["success"],
                "comment_added": comment_added,
                "comment_count": len(jira_client.comments.get("SCRUM-500", [])),
                "message": result["message"][:100]
            }
        }

    def _test_invalid_priority(self) -> Dict[str, Any]:
        """Test handling of invalid priority value."""
        jira_client = FakeJiraClient()
        jira_client.register_issue("SCRUM-600", "Test ticket")

        agent = UpdateAgent(jira_client=jira_client)
        result = agent.process("change priority of SCRUM-600 to ultra-mega-high", [])

        return {
            "name": "invalid_priority",
            "success": not result["success"] and "Invalid priority" in result["error"],
            "details": {
                "result_success": result["success"],
                "error": result["error"]
            }
        }

    def _test_invalid_status_transition(self) -> Dict[str, Any]:
        """Test handling of invalid status transition."""
        jira_client = FakeJiraClient()
        jira_client.register_issue("SCRUM-700", "Test ticket", status="Done")

        agent = UpdateAgent(jira_client=jira_client)
        result = agent.process("move SCRUM-700 to blocked", [])

        return {
            "name": "invalid_status_transition",
            "success": not result["success"] and "Cannot transition" in result["error"],
            "details": {
                "result_success": result["success"],
                "error": result["error"]
            }
        }

    def _test_missing_ticket(self) -> Dict[str, Any]:
        """Test handling of non-existent ticket."""
        jira_client = FakeJiraClient()

        agent = UpdateAgent(jira_client=jira_client)
        result = agent.process("change priority of SCRUM-9999 to high", [])

        return {
            "name": "missing_ticket",
            "success": not result["success"] and "not found" in result["error"].lower(),
            "details": {
                "result_success": result["success"],
                "error": result["error"]
            }
        }

    def _test_jira_error(self) -> Dict[str, Any]:
        """Test handling of Jira API errors."""
        jira_client = FakeJiraClient()
        jira_client.register_error("SCRUM-800", JiraError("API rate limit exceeded"))

        agent = UpdateAgent(jira_client=jira_client)
        result = agent.process("change priority of SCRUM-800 to high", [])

        return {
            "name": "jira_error",
            "success": not result["success"] and "rate limit" in result["error"].lower(),
            "details": {
                "result_success": result["success"],
                "error": result["error"]
            }
        }


if __name__ == "__main__":
    import sys
    import os

    # Add project root to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

    # Run tests
    agent = UpdateTestAgent()
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
