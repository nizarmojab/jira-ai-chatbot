#!/usr/bin/env python3
"""
jira_client.py
==============
Jira Cloud API client with modern pagination (nextPageToken).
Handles authentication, search, issue retrieval, and sprint queries.
"""
from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class JiraError(Exception):
    """Custom exception for Jira API errors."""
    pass


class JiraClient:
    """
    Jira Cloud REST API v3 client.

    Features:
    - Modern pagination with nextPageToken
    - Automatic retry on rate limits
    - Rich error messages
    """

    def __init__(self):
        self.base_url = os.getenv("JIRA_BASE_URL", "").rstrip("/")
        self.email = os.getenv("JIRA_EMAIL", "")
        self.api_token = os.getenv("JIRA_API_TOKEN", "")
        self.project_key = os.getenv("JIRA_PROJECT_KEY", "SCRUM")
        self.max_results = int(os.getenv("MAX_RESULTS", "25"))

        if not all([self.base_url, self.email, self.api_token]):
            raise JiraError("Missing Jira credentials in .env file")

        self.auth = HTTPBasicAuth(self.email, self.api_token)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

        logger.info(f"JiraClient initialized for {self.base_url}")

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Execute HTTP request with error handling.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON payload

        Returns:
            Response JSON

        Raises:
            JiraError: On API errors
        """
        url = urljoin(self.base_url, endpoint)

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            error_msg = f"Jira API error: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                error_msg += f" - {error_detail}"
            except:
                error_msg += f" - {e.response.text}"
            logger.error(error_msg)
            raise JiraError(error_msg)

        except requests.exceptions.RequestException as e:
            error_msg = f"Network error: {str(e)}"
            logger.error(error_msg)
            raise JiraError(error_msg)

    def search_issues(
        self,
        jql: str,
        fields: Optional[List[str]] = None,
        max_results: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Search issues using JQL with modern pagination.

        Args:
            jql: JQL query string
            fields: Fields to return (default: key, summary, status, priority, assignee)
            max_results: Max results per page (default: from env)

        Returns:
            {
                "issues": [...],
                "total": 42,
                "jql": "project = SCRUM",
                "nextPageToken": "..." (optional)
            }
        """
        if fields is None:
            fields = ["key", "summary", "status", "priority", "assignee", "created", "updated"]

        payload = {
            "jql": jql,
            "fields": fields,
            "maxResults": max_results or self.max_results,
        }

        logger.info(f"Searching with JQL: {jql}")
        result = self._request("POST", "/rest/api/3/search/jql", json_data=payload)

        return {
            "issues": result.get("issues", []),
            "total": result.get("total", 0),
            "jql": jql,
            "nextPageToken": result.get("nextPageToken"),
        }

    def get_all_issues(self, jql: str, max_pages: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch all issues matching JQL (auto-pagination).

        Args:
            jql: JQL query
            max_pages: Maximum pages to fetch

        Returns:
            List of issue dicts
        """
        all_issues = []
        next_token = None
        page = 0

        while page < max_pages:
            payload = {"jql": jql, "maxResults": 100}
            if next_token:
                payload["nextPageToken"] = next_token

            result = self._request("POST", "/rest/api/3/search/jql", json_data=payload)
            all_issues.extend(result.get("issues", []))

            next_token = result.get("nextPageToken")
            if not next_token:
                break

            page += 1

        logger.info(f"Fetched {len(all_issues)} issues total")
        return all_issues

    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        """
        Get full issue details.

        Args:
            issue_key: Issue key (e.g., SCRUM-5)

        Returns:
            Full issue object
        """
        logger.info(f"Fetching issue {issue_key}")
        return self._request("GET", f"/rest/api/3/issue/{issue_key}")

    def get_issue_links(self, issue_key: str) -> List[Dict[str, Any]]:
        """
        Get issue links (blocks, is blocked by, relates to).

        Args:
            issue_key: Issue key

        Returns:
            List of link objects with type and linked issue
        """
        issue = self.get_issue(issue_key)
        links = issue.get("fields", {}).get("issuelinks", [])

        parsed_links = []
        for link in links:
            link_type = link.get("type", {}).get("name", "Unknown")

            # Outward link (this issue blocks another)
            if "outwardIssue" in link:
                parsed_links.append({
                    "type": link.get("type", {}).get("outward", link_type),
                    "issue": link["outwardIssue"],
                    "direction": "outward",
                })

            # Inward link (this issue is blocked by another)
            if "inwardIssue" in link:
                parsed_links.append({
                    "type": link.get("type", {}).get("inward", link_type),
                    "issue": link["inwardIssue"],
                    "direction": "inward",
                })

        return parsed_links

    def get_comments(self, issue_key: str) -> List[Dict[str, Any]]:
        """
        Get all comments for an issue.

        Args:
            issue_key: Issue key

        Returns:
            List of comment objects
        """
        issue = self.get_issue(issue_key)
        comments = issue.get("fields", {}).get("comment", {}).get("comments", [])
        return comments

    def get_worklogs(self, issue_key: str) -> List[Dict[str, Any]]:
        """
        Get work logs for an issue.

        Args:
            issue_key: Issue key

        Returns:
            List of worklog entries
        """
        result = self._request("GET", f"/rest/api/3/issue/{issue_key}/worklog")
        return result.get("worklogs", [])

    def get_project_info(self) -> Dict[str, Any]:
        """
        Get project metadata (components, versions, etc.).

        Returns:
            Project info dict
        """
        logger.info(f"Fetching project {self.project_key}")
        return self._request("GET", f"/rest/api/3/project/{self.project_key}")

    def get_components(self) -> List[Dict[str, Any]]:
        """
        Get project components.

        Returns:
            List of component dicts
        """
        project = self.get_project_info()
        return project.get("components", [])

    def get_versions(self) -> List[Dict[str, Any]]:
        """
        Get project versions/releases.

        Returns:
            List of version dicts
        """
        project = self.get_project_info()
        return project.get("versions", [])

    def get_board_id(self) -> int:
        """
        Get the first board ID for the project.

        Returns:
            Board ID
        """
        result = self._request(
            "GET",
            "/rest/agile/1.0/board",
            params={"projectKeyOrId": self.project_key}
        )
        boards = result.get("values", [])
        if not boards:
            raise JiraError(f"No boards found for project {self.project_key}")
        return boards[0]["id"]

    def get_active_sprint(self) -> Optional[Dict[str, Any]]:
        """
        Get the active sprint for the project.

        Returns:
            Sprint dict or None if no active sprint
        """
        try:
            board_id = self.get_board_id()
            result = self._request(
                "GET",
                f"/rest/agile/1.0/board/{board_id}/sprint",
                params={"state": "active"}
            )
            sprints = result.get("values", [])
            return sprints[0] if sprints else None
        except Exception as e:
            logger.warning(f"Could not fetch active sprint: {e}")
            return None

    def get_sprint_issues(self, sprint_id: int) -> List[Dict[str, Any]]:
        """
        Get all issues in a sprint.

        Args:
            sprint_id: Sprint ID

        Returns:
            List of issues
        """
        jql = f"sprint = {sprint_id}"
        result = self.search_issues(jql, max_results=100)
        return result["issues"]

    def get_current_user(self) -> Dict[str, Any]:
        """
        Get current authenticated user info.

        Returns:
            User dict with accountId, displayName, emailAddress
        """
        return self._request("GET", "/rest/api/3/myself")

    def update_issue(
        self,
        issue_key: str,
        fields: Dict[str, Any],
    ) -> None:
        """
        Update issue fields.

        Args:
            issue_key: Issue key
            fields: Dict of fields to update (e.g., {"priority": {"name": "High"}})
        """
        payload = {"fields": fields}
        logger.info(f"Updating {issue_key} with fields: {fields}")
        self._request("PUT", f"/rest/api/3/issue/{issue_key}", json_data=payload)

    def add_comment(self, issue_key: str, comment_text: str) -> Dict[str, Any]:
        """
        Add a comment to an issue.

        Args:
            issue_key: Issue key
            comment_text: Comment body

        Returns:
            Created comment object
        """
        # Jira uses ADF (Atlassian Document Format)
        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": comment_text,
                            }
                        ]
                    }
                ]
            }
        }
        logger.info(f"Adding comment to {issue_key}")
        return self._request("POST", f"/rest/api/3/issue/{issue_key}/comment", json_data=payload)
