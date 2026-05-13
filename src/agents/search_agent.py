#!/usr/bin/env python3
"""
search_agent.py
===============
Search agent that converts natural language to JQL with OpenAI and queries Jira.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI

from src.agents.base_agent import BaseAgent
from src.jira_client import JiraClient, JiraError

logger = logging.getLogger(__name__)


class SearchAgent(BaseAgent):
    """
    Specialized agent for Jira search queries.

    Workflow:
    1. Convert a French or English question into JQL with OpenAI
    2. Execute the JQL against Jira REST API
    3. Return a simplified issue list
    """

    def __init__(
        self,
        jira_client: Optional[JiraClient] = None,
        openai_client: Optional[OpenAI] = None,
        openai_model: Optional[str] = None,
    ):
        super().__init__("SearchAgent")
        self.jira = jira_client or JiraClient()
        self.openai_model = openai_model or os.getenv(
            "OPENAI_MODEL",
            "gpt-4o",
        )

        if openai_client is not None:
            self.client = openai_client
        else:
            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in .env")
            self.client = OpenAI(api_key=api_key)

    def process(self, message: str, context: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Convert a user question into JQL, execute the Jira search, and simplify results.
        """
        try:
            jql = self._convert_to_jql(message, context)
            result = self.jira.search_issues(
                jql=jql,
                fields=["summary", "status", "priority", "assignee"],
                max_results=25,
            )

            issues = self._simplify_issues(result.get("issues", []))
            raw_total = result.get("total")
            shown = len(issues)
            total = raw_total if isinstance(raw_total, int) and raw_total >= shown else shown

            return {
                "success": True,
                "agent": self.name,
                "action": "search",
                "data": {
                    "jql": jql,
                    "total": total,
                    "issues": issues,
                },
                "message": self._build_message(total, shown),
                "error": None,
            }
        except (JiraError, ValueError, RuntimeError) as exc:
            logger.error("SearchAgent failed: %s", exc)
            return {
                "success": False,
                "agent": self.name,
                "action": "search",
                "data": None,
                "message": f"Search failed: {exc}",
                "error": str(exc),
            }

    def _convert_to_jql(self, message: str, context: List[Dict[str, str]]) -> str:
        """
        Use OpenAI to translate a natural language search query into valid JQL.
        """
        context_lines = [
            f"{item.get('role', 'unknown')}: {item.get('content', '')}"
            for item in context[-10:]
        ]
        context_block = "\n".join(context_lines) if context_lines else "No prior context."

        prompt = (
            "You convert Jira search requests into valid JQL.\n"
            f"Project key: {self.jira.project_key}\n"
            "Rules:\n"
            f"- Always scope the query to project = {self.jira.project_key} unless the user explicitly names another project.\n"
            "- Understand French and English.\n"
            "- Return only raw JQL, with no markdown, no explanation, and no backticks.\n"
            "- Prefer standard Jira fields: project, issuetype, status, priority, assignee, summary, labels.\n"
            "- If the user asks for blocked tickets, use a status-based filter when appropriate.\n"
            "- If the user asks for critical bugs in French or English, produce a bug + critical priority filter.\n"
            "- Add an ORDER BY clause when useful.\n\n"
            f"Conversation context:\n{context_block}\n\n"
            f"User question:\n{message}"
        )

        response = self.client.chat.completions.create(
            model=self.openai_model,
            temperature=0,
            max_tokens=200,
            messages=[
                {"role": "system", "content": "Return only valid Jira JQL."},
                {"role": "user", "content": prompt},
            ],
        )

        jql = (response.choices[0].message.content or "").strip()

        if not jql:
            raise RuntimeError("OpenAI returned an empty JQL query")

        jql = self._sanitize_jql(jql)

        if not jql.lower().startswith("project =") and " project =" not in jql.lower():
            jql = f"project = {self.jira.project_key} AND ({jql})"

        return jql

    def _sanitize_jql(self, jql: str) -> str:
        """
        Remove common formatting noise from model output.
        """
        cleaned = jql.strip().strip("`").strip()
        if cleaned.lower().startswith("jql:"):
            cleaned = cleaned[4:].strip()
        return " ".join(cleaned.split())

    def _build_message(self, total: int, shown: int) -> str:
        """
        Build a concise user-facing message.
        """
        if shown > 0 and total <= 0:
            total = shown
        if shown == 0 and total == 0:
            return "No tickets found."
        if total <= shown:
            return f"Found {total} ticket(s)."
        return f"Found {total} ticket(s), showing {shown}."

    def _simplify_issues(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract only the fields required by the search response.
        """
        simplified: List[Dict[str, Any]] = []
        for issue in issues:
            fields = issue.get("fields", {})
            assignee = fields.get("assignee") or {}
            status = fields.get("status") or {}
            priority = fields.get("priority") or {}

            simplified.append(
                {
                    "key": issue.get("key"),
                    "summary": fields.get("summary", ""),
                    "status": status.get("name", "Unknown"),
                    "priority": priority.get("name", "None"),
                    "assignee": assignee.get("displayName", "Unassigned"),
                }
            )

        return simplified
