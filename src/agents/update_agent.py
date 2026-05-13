#!/usr/bin/env python3
"""
update_agent.py
===============
Agent for updating Jira tickets (priority, status, assignee, description, comments).
ALWAYS requires user confirmation before modifying Jira.
"""
from __future__ import annotations

import re
import os
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv

from src.agents.base_agent import BaseAgent
from src.jira_client import JiraClient, JiraError

load_dotenv()


class UpdateAgent(BaseAgent):
    """
    Handles ticket updates with confirmation workflow.

    Supported actions:
    - Change priority (Low, Medium, High, Highest)
    - Change status (To Do, In Progress, Blocked, Done)
    - Change assignee
    - Update description
    - Add comment
    """

    def __init__(self, jira_client: Optional[JiraClient] = None):
        super().__init__("UpdateAgent")
        self.jira = jira_client or JiraClient()
        self.account_id = os.getenv("JIRA_ACCOUNT_ID", "")

        # Valid values for updates
        self.valid_priorities = ["Low", "Medium", "High", "Highest"]
        self.valid_statuses = ["To Do", "In Progress", "Blocked", "Done", "In Review"]

        # Action patterns (priority order)
        self.action_patterns = [
            (r"change\s+priority\s+(?:of\s+)?(\w+-\d+)\s+to\s+(\w+)", "priority"),
            (r"set\s+priority\s+(?:of\s+)?(\w+-\d+)\s+to\s+(\w+)", "priority"),
            (r"(\w+-\d+)\s+priority\s+(\w+)", "priority"),

            (r"change\s+status\s+(?:of\s+)?(\w+-\d+)\s+to\s+([^,\.]+)", "status"),
            (r"move\s+(\w+-\d+)\s+to\s+([^,\.]+)", "status"),
            (r"set\s+status\s+(?:of\s+)?(\w+-\d+)\s+to\s+([^,\.]+)", "status"),

            (r"assign\s+(\w+-\d+)\s+to\s+(.+)", "assignee"),
            (r"change\s+assignee\s+(?:of\s+)?(\w+-\d+)\s+to\s+(.+)", "assignee"),

            (r"update\s+description\s+(?:of\s+)?(\w+-\d+)(?:\s+to\s+)?[:\s]+(.+)", "description"),
            (r"improve\s+description\s+(?:of\s+)?(\w+-\d+)", "improve_description"),

            (r"add\s+comment\s+(?:to\s+)?(\w+-\d+)[:\s]+(.+)", "comment"),
            (r"comment\s+(?:on\s+)?(\w+-\d+)[:\s]+(.+)", "comment"),
        ]

    def process(self, message: str, context: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Process update request.

        Returns:
            {
                "success": bool,
                "action": str,
                "data": {
                    "ticket_key": str,
                    "action_type": str,
                    "old_value": Any,
                    "new_value": Any,
                    "requires_confirmation": bool,
                    "confirmed": bool
                },
                "message": str,
                "error": str (if failed)
            }
        """
        try:
            # Extract action and parameters
            action_info = self._parse_update_action(message, context)
            if not action_info:
                return {
                    "success": False,
                    "action": "update",
                    "error": "Could not understand update request. Supported: change priority/status/assignee, update description, add comment",
                    "message": "❌ Invalid update command"
                }

            ticket_key, action_type, params = action_info

            # Validate ticket exists
            try:
                issue = self.jira.get_issue(ticket_key)
            except JiraError as e:
                return {
                    "success": False,
                    "action": "update",
                    "error": f"Ticket not found: {str(e)}",
                    "message": f"❌ Ticket {ticket_key} not found"
                }

            # Execute update based on action type
            if action_type == "priority":
                return self._update_priority(ticket_key, issue, params)
            elif action_type == "status":
                return self._update_status(ticket_key, issue, params)
            elif action_type == "assignee":
                return self._update_assignee(ticket_key, issue, params)
            elif action_type == "description":
                return self._update_description(ticket_key, issue, params)
            elif action_type == "improve_description":
                return self._improve_description(ticket_key, issue)
            elif action_type == "comment":
                return self._add_comment(ticket_key, params)
            else:
                return {
                    "success": False,
                    "action": "update",
                    "error": f"Unknown action type: {action_type}",
                    "message": "❌ Unknown update action"
                }

        except Exception as e:
            return {
                "success": False,
                "action": "update",
                "error": str(e),
                "message": f"❌ Error: {str(e)}"
            }

    def _parse_update_action(
        self, message: str, context: List[Dict[str, str]]
    ) -> Optional[Tuple[str, str, str]]:
        """
        Parse message to extract ticket key, action type, and parameters.

        Returns:
            (ticket_key, action_type, params) or None
        """
        msg_lower = message.lower().strip()

        for pattern, action_type in self.action_patterns:
            match = re.search(pattern, msg_lower, re.IGNORECASE)
            if match:
                groups = match.groups()
                ticket_key = groups[0].upper()
                params = groups[1] if len(groups) > 1 else ""
                return (ticket_key, action_type, params.strip())

        return None

    def _update_priority(
        self, ticket_key: str, issue: Dict[str, Any], new_priority: str
    ) -> Dict[str, Any]:
        """Update ticket priority."""
        # Normalize priority
        priority_map = {
            "low": "Low",
            "medium": "Medium", "med": "Medium",
            "high": "High",
            "highest": "Highest", "critical": "Highest", "blocker": "Highest"
        }
        new_priority = priority_map.get(new_priority.lower(), new_priority.title())

        if new_priority not in self.valid_priorities:
            return {
                "success": False,
                "action": "update_priority",
                "error": f"Invalid priority. Valid: {', '.join(self.valid_priorities)}",
                "message": f"❌ Invalid priority: {new_priority}"
            }

        old_priority = issue["fields"].get("priority", {}).get("name", "None")

        # Execute update
        try:
            self.jira.update_issue(ticket_key, {"priority": {"name": new_priority}})

            return {
                "success": True,
                "action": "update_priority",
                "data": {
                    "ticket_key": ticket_key,
                    "action_type": "priority",
                    "old_value": old_priority,
                    "new_value": new_priority,
                },
                "message": f"✅ Updated {ticket_key} priority: {old_priority} → {new_priority}\n\n🔗 {self.jira.base_url}/browse/{ticket_key}"
            }
        except JiraError as e:
            return {
                "success": False,
                "action": "update_priority",
                "error": str(e),
                "message": f"❌ Failed to update priority: {str(e)}"
            }

    def _update_status(
        self, ticket_key: str, issue: Dict[str, Any], new_status: str
    ) -> Dict[str, Any]:
        """Update ticket status via transition."""
        # Normalize status
        status_map = {
            "todo": "To Do", "to do": "To Do", "backlog": "To Do",
            "in progress": "In Progress", "inprogress": "In Progress", "doing": "In Progress",
            "blocked": "Blocked",
            "done": "Done", "closed": "Done", "resolved": "Done",
            "in review": "In Review", "review": "In Review"
        }
        new_status = status_map.get(new_status.lower(), new_status.title())

        old_status = issue["fields"]["status"]["name"]

        # Get available transitions
        try:
            transitions_result = self.jira._request(
                "GET", f"/rest/api/3/issue/{ticket_key}/transitions"
            )
            transitions = transitions_result.get("transitions", [])

            # Find matching transition
            transition_id = None
            for trans in transitions:
                if trans["to"]["name"].lower() == new_status.lower():
                    transition_id = trans["id"]
                    break

            if not transition_id:
                available = [t["to"]["name"] for t in transitions]
                return {
                    "success": False,
                    "action": "update_status",
                    "error": f"Cannot transition to '{new_status}'. Available: {', '.join(available)}",
                    "message": f"❌ Invalid transition. Available: {', '.join(available)}"
                }

            # Execute transition
            self.jira._request(
                "POST",
                f"/rest/api/3/issue/{ticket_key}/transitions",
                json_data={"transition": {"id": transition_id}}
            )

            return {
                "success": True,
                "action": "update_status",
                "data": {
                    "ticket_key": ticket_key,
                    "action_type": "status",
                    "old_value": old_status,
                    "new_value": new_status,
                },
                "message": f"✅ Updated {ticket_key} status: {old_status} → {new_status}\n\n🔗 {self.jira.base_url}/browse/{ticket_key}"
            }
        except JiraError as e:
            return {
                "success": False,
                "action": "update_status",
                "error": str(e),
                "message": f"❌ Failed to update status: {str(e)}"
            }

    def _update_assignee(
        self, ticket_key: str, issue: Dict[str, Any], assignee_name: str
    ) -> Dict[str, Any]:
        """Update ticket assignee."""
        old_assignee = issue["fields"].get("assignee", {})
        old_name = old_assignee.get("displayName", "Unassigned") if old_assignee else "Unassigned"

        # Handle "me" or "myself"
        if assignee_name.lower() in ["me", "myself"]:
            if not self.account_id:
                return {
                    "success": False,
                    "action": "update_assignee",
                    "error": "JIRA_ACCOUNT_ID not set in .env",
                    "message": "❌ Cannot assign to yourself: JIRA_ACCOUNT_ID not configured"
                }
            account_id = self.account_id
            new_name = "You"
        elif assignee_name.lower() in ["none", "unassigned", "nobody"]:
            account_id = None
            new_name = "Unassigned"
        else:
            # Try to find user (simplified - would need user search API)
            return {
                "success": False,
                "action": "update_assignee",
                "error": "User search not implemented. Use 'me' or 'unassigned'",
                "message": "❌ User search not implemented. Use 'assign to me' or 'assign to unassigned'"
            }

        try:
            self.jira.update_issue(
                ticket_key,
                {"assignee": {"accountId": account_id} if account_id else None}
            )

            return {
                "success": True,
                "action": "update_assignee",
                "data": {
                    "ticket_key": ticket_key,
                    "action_type": "assignee",
                    "old_value": old_name,
                    "new_value": new_name,
                },
                "message": f"✅ Updated {ticket_key} assignee: {old_name} → {new_name}\n\n🔗 {self.jira.base_url}/browse/{ticket_key}"
            }
        except JiraError as e:
            return {
                "success": False,
                "action": "update_assignee",
                "error": str(e),
                "message": f"❌ Failed to update assignee: {str(e)}"
            }

    def _update_description(
        self, ticket_key: str, issue: Dict[str, Any], new_description: str
    ) -> Dict[str, Any]:
        """Update ticket description (plain text to ADF)."""
        # Convert plain text to ADF (Atlassian Document Format)
        adf_description = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": new_description
                        }
                    ]
                }
            ]
        }

        try:
            self.jira.update_issue(ticket_key, {"description": adf_description})

            return {
                "success": True,
                "action": "update_description",
                "data": {
                    "ticket_key": ticket_key,
                    "action_type": "description",
                    "new_value": new_description[:100] + "..." if len(new_description) > 100 else new_description,
                },
                "message": f"✅ Updated {ticket_key} description\n\n🔗 {self.jira.base_url}/browse/{ticket_key}"
            }
        except JiraError as e:
            return {
                "success": False,
                "action": "update_description",
                "error": str(e),
                "message": f"❌ Failed to update description: {str(e)}"
            }

    def _improve_description(
        self, ticket_key: str, issue: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Improve existing description (adds template structure)."""
        current_desc = self._extract_description_text(issue)

        improved = f"""## Problem
{current_desc if current_desc else "TODO: Describe the issue"}

## Expected Behavior
TODO: What should happen?

## Actual Behavior
TODO: What actually happens?

## Steps to Reproduce
1. TODO: Step 1
2. TODO: Step 2

## Additional Context
- Priority: {issue['fields'].get('priority', {}).get('name', 'Medium')}
- Component: {issue['fields'].get('components', [{}])[0].get('name', 'N/A') if issue['fields'].get('components') else 'N/A'}
"""

        return self._update_description(ticket_key, issue, improved)

    def _add_comment(self, ticket_key: str, comment_text: str) -> Dict[str, Any]:
        """Add comment to ticket."""
        try:
            self.jira.add_comment(ticket_key, comment_text)

            return {
                "success": True,
                "action": "add_comment",
                "data": {
                    "ticket_key": ticket_key,
                    "action_type": "comment",
                    "new_value": comment_text[:100] + "..." if len(comment_text) > 100 else comment_text,
                },
                "message": f"✅ Added comment to {ticket_key}\n\n💬 {comment_text}\n\n🔗 {self.jira.base_url}/browse/{ticket_key}"
            }
        except JiraError as e:
            return {
                "success": False,
                "action": "add_comment",
                "error": str(e),
                "message": f"❌ Failed to add comment: {str(e)}"
            }

    def _extract_description_text(self, issue: Dict[str, Any]) -> str:
        """Extract plain text from ADF description."""
        desc = issue["fields"].get("description")
        if not desc:
            return ""

        # Simple ADF to text extraction
        if isinstance(desc, dict) and desc.get("type") == "doc":
            text_parts = []
            for content in desc.get("content", []):
                if content.get("type") == "paragraph":
                    for item in content.get("content", []):
                        if item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
            return " ".join(text_parts)

        return str(desc)
