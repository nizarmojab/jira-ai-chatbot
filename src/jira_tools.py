#!/usr/bin/env python3
"""
jira_tools.py
=============
12 Jira tools exposed to GPT-4o via OpenAI Tool Use.

Each tool = Python function + OpenAI Tool JSON schema.
GPT-4o selects which tools to call based on user intent.
"""
from __future__ import annotations

import logging
import webbrowser
from typing import Any, Dict, List, Optional

from .jira_client import JiraClient, JiraError

logger = logging.getLogger(__name__)

# Global client instance
_jira_client: Optional[JiraClient] = None


def get_jira_client() -> JiraClient:
    """Get or create singleton JiraClient."""
    global _jira_client
    if _jira_client is None:
        _jira_client = JiraClient()
    return _jira_client


# ─────────────────────────────────────────────────────
#  Tool 1: Search Issues
# ─────────────────────────────────────────────────────
def search_issues(jql: str, max_results: int = 25) -> Dict[str, Any]:
    """
    Search Jira issues using JQL query.

    Args:
        jql: JQL query string (e.g., "project = SCRUM AND status = Blocked")
        max_results: Maximum number of results to return (default: 25)

    Returns:
        {
            "success": true,
            "issues": [...],
            "total": 42,
            "jql": "project = SCRUM AND status = Blocked"
        }
    """
    try:
        client = get_jira_client()
        result = client.search_issues(jql, max_results=max_results)

        # Simplify issue format
        simplified_issues = []
        for issue in result["issues"]:
            fields = issue.get("fields", {})

            # Safely extract nested fields (may be None)
            status = fields.get("status")
            priority = fields.get("priority")
            assignee = fields.get("assignee")

            simplified_issues.append({
                "key": issue["key"],
                "summary": fields.get("summary", ""),
                "status": status.get("name", "") if status else "",
                "priority": priority.get("name", "") if priority else "",
                "assignee": assignee.get("displayName", "Unassigned") if assignee else "Unassigned",
                "created": fields.get("created", ""),
                "updated": fields.get("updated", ""),
            })

        return {
            "success": True,
            "issues": simplified_issues,
            "total": result["total"],
            "jql": jql,
        }

    except JiraError as e:
        logger.error(f"search_issues failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ─────────────────────────────────────────────────────
#  Tool 2: Get Issue Details
# ─────────────────────────────────────────────────────
def get_issue(issue_key: str) -> Dict[str, Any]:
    """
    Get full details for a single issue.

    Args:
        issue_key: Issue key (e.g., "SCRUM-5")

    Returns:
        {
            "success": true,
            "issue": {
                "key": "SCRUM-5",
                "summary": "...",
                "description": "...",
                "status": "Blocked",
                "priority": "Highest",
                "assignee": "John Doe",
                "reporter": "Jane Smith",
                "created": "2026-01-15T10:30:00",
                "updated": "2026-04-20T14:22:00",
                "labels": ["bug", "critical"],
                "components": ["CAN Driver"],
                "fix_versions": ["v2.1.0"],
            }
        }
    """
    try:
        client = get_jira_client()
        issue = client.get_issue(issue_key)
        fields = issue.get("fields", {})

        # Extract description text from ADF
        description = ""
        desc_adf = fields.get("description")
        if desc_adf and isinstance(desc_adf, dict):
            content = desc_adf.get("content", [])
            for block in content:
                if block.get("type") == "paragraph":
                    for item in block.get("content", []):
                        if item.get("type") == "text":
                            description += item.get("text", "")
                    description += "\n"

        # Safely extract nested fields (may be None)
        status = fields.get("status")
        priority = fields.get("priority")
        assignee = fields.get("assignee")
        reporter = fields.get("reporter")

        return {
            "success": True,
            "issue": {
                "key": issue["key"],
                "summary": fields.get("summary", ""),
                "description": description.strip(),
                "status": status.get("name", "") if status else "",
                "priority": priority.get("name", "") if priority else "",
                "assignee": assignee.get("displayName", "Unassigned") if assignee else "Unassigned",
                "reporter": reporter.get("displayName", "Unknown") if reporter else "Unknown",
                "created": fields.get("created", ""),
                "updated": fields.get("updated", ""),
                "labels": fields.get("labels", []),
                "components": [c.get("name") for c in fields.get("components", [])],
                "fix_versions": [v.get("name") for v in fields.get("fixVersions", [])],
            }
        }

    except JiraError as e:
        logger.error(f"get_issue failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ─────────────────────────────────────────────────────
#  Tool 3: Get Epic Tree
# ─────────────────────────────────────────────────────
def get_epic_tree(epic_key: str) -> Dict[str, Any]:
    """
    Get epic with all child stories and subtasks.

    Args:
        epic_key: Epic issue key (e.g., "SCRUM-42")

    Returns:
        {
            "success": true,
            "epic": {...},
            "stories": [...],
            "subtasks": [...]
        }
    """
    try:
        client = get_jira_client()
        epic = client.get_issue(epic_key)

        # Get all issues in epic
        jql = f'"Epic Link" = {epic_key}'
        stories_result = client.search_issues(jql, max_results=100)

        stories = []
        subtasks = []

        for issue in stories_result["issues"]:
            fields = issue.get("fields", {})

            # Safely extract nested fields (may be None)
            issuetype = fields.get("issuetype")
            status = fields.get("status")
            issue_type = issuetype.get("name", "") if issuetype else ""

            issue_data = {
                "key": issue["key"],
                "summary": fields.get("summary", ""),
                "status": status.get("name", "") if status else "",
                "type": issue_type,
            }

            if issue_type == "Sub-task":
                subtasks.append(issue_data)
            else:
                stories.append(issue_data)

        return {
            "success": True,
            "epic": {
                "key": epic["key"],
                "summary": epic["fields"].get("summary", ""),
                "status": epic["fields"].get("status", {}).get("name", ""),
            },
            "stories": stories,
            "subtasks": subtasks,
            "total_children": len(stories) + len(subtasks),
        }

    except JiraError as e:
        logger.error(f"get_epic_tree failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ─────────────────────────────────────────────────────
#  Tool 4: Get Dependencies
# ─────────────────────────────────────────────────────
def get_dependencies(issue_key: str) -> Dict[str, Any]:
    """
    Get issue links (blocks, is blocked by, relates to).

    Args:
        issue_key: Issue key

    Returns:
        {
            "success": true,
            "blocks": [...],
            "blocked_by": [...],
            "relates_to": [...]
        }
    """
    try:
        client = get_jira_client()
        links = client.get_issue_links(issue_key)

        blocks = []
        blocked_by = []
        relates_to = []

        for link in links:
            link_issue = link["issue"]
            fields = link_issue.get("fields", {})

            # Safely extract nested fields (may be None)
            status = fields.get("status")

            issue_data = {
                "key": link_issue["key"],
                "summary": fields.get("summary", ""),
                "status": status.get("name", "") if status else "",
            }

            link_type = link["type"].lower()
            if "blocks" in link_type and link["direction"] == "outward":
                blocks.append(issue_data)
            elif "blocks" in link_type and link["direction"] == "inward":
                blocked_by.append(issue_data)
            else:
                relates_to.append(issue_data)

        return {
            "success": True,
            "blocks": blocks,
            "blocked_by": blocked_by,
            "relates_to": relates_to,
        }

    except JiraError as e:
        logger.error(f"get_dependencies failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ─────────────────────────────────────────────────────
#  Tool 5: Get Sprint Info
# ─────────────────────────────────────────────────────
def get_sprint_info() -> Dict[str, Any]:
    """
    Get active sprint status and metrics.

    Returns:
        {
            "success": true,
            "sprint": {
                "id": 1,
                "name": "Sprint 4",
                "state": "active",
                "startDate": "...",
                "endDate": "...",
            },
            "metrics": {
                "todo": 8,
                "in_progress": 12,
                "done": 18,
                "blocked": 5,
                "total": 43
            }
        }
    """
    try:
        client = get_jira_client()
        sprint = client.get_active_sprint()

        if not sprint:
            return {
                "success": False,
                "error": "No active sprint found",
            }

        # Get sprint issues
        issues = client.get_sprint_issues(sprint["id"])

        # Count by status
        metrics = {
            "todo": 0,
            "in_progress": 0,
            "done": 0,
            "blocked": 0,
            "total": len(issues),
        }

        for issue in issues:
            status = issue["fields"].get("status", {}).get("name", "").lower()
            if "done" in status or "closed" in status:
                metrics["done"] += 1
            elif "progress" in status:
                metrics["in_progress"] += 1
            elif "blocked" in status:
                metrics["blocked"] += 1
            else:
                metrics["todo"] += 1

        return {
            "success": True,
            "sprint": {
                "id": sprint["id"],
                "name": sprint["name"],
                "state": sprint["state"],
                "startDate": sprint.get("startDate", ""),
                "endDate": sprint.get("endDate", ""),
            },
            "metrics": metrics,
        }

    except JiraError as e:
        logger.error(f"get_sprint_info failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ─────────────────────────────────────────────────────
#  Tool 6: Get Project Info
# ─────────────────────────────────────────────────────
def get_project_info() -> Dict[str, Any]:
    """
    Get project metadata (components, versions, etc.).

    Returns:
        {
            "success": true,
            "project": {
                "key": "SCRUM",
                "name": "Infotainment & Connectivity",
                "components": ["CAN Driver", "OTA", ...],
                "versions": ["v2.0.0", "v2.1.0", ...]
            }
        }
    """
    try:
        client = get_jira_client()
        project = client.get_project_info()
        components = client.get_components()
        versions = client.get_versions()

        return {
            "success": True,
            "project": {
                "key": project["key"],
                "name": project["name"],
                "components": [c["name"] for c in components],
                "versions": [v["name"] for v in versions],
            }
        }

    except JiraError as e:
        logger.error(f"get_project_info failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ─────────────────────────────────────────────────────
#  Tool 7: Get My Issues
# ─────────────────────────────────────────────────────
def get_my_issues() -> Dict[str, Any]:
    """
    Get issues assigned to the current user.

    Returns:
        {
            "success": true,
            "issues": [...],
            "total": 12
        }
    """
    try:
        client = get_jira_client()
        user = client.get_current_user()
        jql = f'assignee = "{user["emailAddress"]}" AND resolution = Unresolved'

        result = search_issues(jql, max_results=50)
        return result

    except JiraError as e:
        logger.error(f"get_my_issues failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ─────────────────────────────────────────────────────
#  Tool 8: Get Components
# ─────────────────────────────────────────────────────
def get_components() -> Dict[str, Any]:
    """
    Get list of project components.

    Returns:
        {
            "success": true,
            "components": [
                {"name": "CAN Driver", "description": "..."},
                ...
            ]
        }
    """
    try:
        client = get_jira_client()
        components = client.get_components()

        return {
            "success": True,
            "components": [
                {
                    "name": c["name"],
                    "description": c.get("description", ""),
                }
                for c in components
            ],
        }

    except JiraError as e:
        logger.error(f"get_components failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ─────────────────────────────────────────────────────
#  Tool 9: Get Versions
# ─────────────────────────────────────────────────────
def get_versions() -> Dict[str, Any]:
    """
    Get list of project versions/releases.

    Returns:
        {
            "success": true,
            "versions": [
                {"name": "v2.1.0", "released": true},
                ...
            ]
        }
    """
    try:
        client = get_jira_client()
        versions = client.get_versions()

        return {
            "success": True,
            "versions": [
                {
                    "name": v["name"],
                    "released": v.get("released", False),
                }
                for v in versions
            ],
        }

    except JiraError as e:
        logger.error(f"get_versions failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ─────────────────────────────────────────────────────
#  Tool 10: Get Comments
# ─────────────────────────────────────────────────────
def get_comments(issue_key: str) -> Dict[str, Any]:
    """
    Get all comments for an issue.

    Args:
        issue_key: Issue key

    Returns:
        {
            "success": true,
            "comments": [
                {
                    "author": "John Doe",
                    "body": "...",
                    "created": "2026-04-20T10:30:00"
                },
                ...
            ]
        }
    """
    try:
        client = get_jira_client()
        comments = client.get_comments(issue_key)

        simplified_comments = []
        for comment in comments:
            # Extract text from ADF
            body_text = ""
            body_adf = comment.get("body", {})
            if isinstance(body_adf, dict):
                content = body_adf.get("content", [])
                for block in content:
                    if block.get("type") == "paragraph":
                        for item in block.get("content", []):
                            if item.get("type") == "text":
                                body_text += item.get("text", "")
                        body_text += "\n"

            simplified_comments.append({
                "author": comment.get("author", {}).get("displayName", "Unknown"),
                "body": body_text.strip(),
                "created": comment.get("created", ""),
            })

        return {
            "success": True,
            "comments": simplified_comments,
            "total": len(simplified_comments),
        }

    except JiraError as e:
        logger.error(f"get_comments failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ─────────────────────────────────────────────────────
#  Tool 11: Open in Jira
# ─────────────────────────────────────────────────────
def open_in_jira(issue_key: str) -> Dict[str, Any]:
    """
    Open issue in browser.

    Args:
        issue_key: Issue key

    Returns:
        {
            "success": true,
            "url": "https://..."
        }
    """
    try:
        client = get_jira_client()
        url = f"{client.base_url}/browse/{issue_key}"
        webbrowser.open(url)

        return {
            "success": True,
            "url": url,
            "message": f"Opened {issue_key} in browser",
        }

    except Exception as e:
        logger.error(f"open_in_jira failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ─────────────────────────────────────────────────────
#  Tool 12: Get Worklogs
# ─────────────────────────────────────────────────────
def get_worklogs(issue_key: str) -> Dict[str, Any]:
    """
    Get time tracking/work logs for an issue.

    Args:
        issue_key: Issue key

    Returns:
        {
            "success": true,
            "worklogs": [
                {
                    "author": "John Doe",
                    "timeSpent": "2h",
                    "comment": "Fixed bug",
                    "started": "2026-04-20T09:00:00"
                },
                ...
            ]
        }
    """
    try:
        client = get_jira_client()
        worklogs = client.get_worklogs(issue_key)

        simplified_worklogs = []
        for worklog in worklogs:
            # Extract comment text from ADF
            comment_text = ""
            comment_adf = worklog.get("comment")
            if comment_adf and isinstance(comment_adf, dict):
                content = comment_adf.get("content", [])
                for block in content:
                    if block.get("type") == "paragraph":
                        for item in block.get("content", []):
                            if item.get("type") == "text":
                                comment_text += item.get("text", "")

            simplified_worklogs.append({
                "author": worklog.get("author", {}).get("displayName", "Unknown"),
                "timeSpent": worklog.get("timeSpent", ""),
                "comment": comment_text.strip(),
                "started": worklog.get("started", ""),
            })

        return {
            "success": True,
            "worklogs": simplified_worklogs,
            "total": len(simplified_worklogs),
        }

    except JiraError as e:
        logger.error(f"get_worklogs failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ─────────────────────────────────────────────────────
#  OpenAI Tool Schemas
# ─────────────────────────────────────────────────────
JIRA_TOOLS_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_issues",
            "description": "Search Jira issues using JQL. Use for queries like 'show me critical bugs', 'what tickets are blocked', 'bugs in CAN component'. Returns list of matching issues.",
            "parameters": {
                "type": "object",
                "properties": {
                    "jql": {
                        "type": "string",
                        "description": "JQL query string (e.g., 'project = SCRUM AND status = Blocked')",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 25)",
                        "default": 25,
                    },
                },
                "required": ["jql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_issue",
            "description": "Get full details for a single issue including description, comments, links. Use when user asks to 'analyze SCRUM-5' or 'show details of SCRUM-42'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "Issue key (e.g., 'SCRUM-5')",
                    },
                },
                "required": ["issue_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_epic_tree",
            "description": "Get epic with all child stories and subtasks. Use when user asks about an epic structure or 'show epic SCRUM-42'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "epic_key": {
                        "type": "string",
                        "description": "Epic issue key (e.g., 'SCRUM-42')",
                    },
                },
                "required": ["epic_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dependencies",
            "description": "Get issue links (blocks, is blocked by, relates to). Use when user asks 'what blocks SCRUM-5' or 'show dependencies'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "Issue key",
                    },
                },
                "required": ["issue_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sprint_info",
            "description": "Get active sprint status with metrics (todo, in progress, done, blocked). Use for 'sprint report' or 'sprint status'.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_project_info",
            "description": "Get project metadata including components and versions. Use for 'list components' or 'project info'.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_issues",
            "description": "Get issues assigned to current user. Use for 'my tickets' or 'what am I working on'.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_components",
            "description": "Get list of project components. Use when user asks about available components.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_versions",
            "description": "Get list of project versions/releases. Use when user asks about release versions.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_comments",
            "description": "Get all comments for an issue. Use when user asks for comments on a specific ticket.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "Issue key",
                    },
                },
                "required": ["issue_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_in_jira",
            "description": "Open issue in web browser. Use when user says 'open SCRUM-5'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "Issue key",
                    },
                },
                "required": ["issue_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_worklogs",
            "description": "Get time tracking/work logs for an issue. Use when user asks about time spent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "Issue key",
                    },
                },
                "required": ["issue_key"],
            },
        },
    },
]

# Map function names to Python functions
JIRA_TOOLS_MAP = {
    "search_issues": search_issues,
    "get_issue": get_issue,
    "get_epic_tree": get_epic_tree,
    "get_dependencies": get_dependencies,
    "get_sprint_info": get_sprint_info,
    "get_project_info": get_project_info,
    "get_my_issues": get_my_issues,
    "get_components": get_components,
    "get_versions": get_versions,
    "get_comments": get_comments,
    "open_in_jira": open_in_jira,
    "get_worklogs": get_worklogs,
}
